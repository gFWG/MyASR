from __future__ import annotations

import logging
import os
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from src.exceptions import ModelResourceError

logger = logging.getLogger(__name__)

_DEFAULT_MODEL_ROOT = Path("data/models")
_COMMON_REQUIRED_FILES = (
    "chat_template.json",
    "config.json",
    "generation_config.json",
    "merges.txt",
    "preprocessor_config.json",
    "tokenizer_config.json",
    "vocab.json",
)
_COMMON_MANAGED_FILES = (".gitattributes", "README.md", *_COMMON_REQUIRED_FILES)


@dataclass(frozen=True, slots=True)
class ModelSpec:
    repo_id: str
    display_name: str
    required_files: tuple[str, ...]
    managed_files: tuple[str, ...]
    download_size_mb: int


@dataclass(frozen=True, slots=True)
class DeleteReport:
    target_directory: Path
    removed_entries: tuple[str, ...]
    remaining_entries: tuple[str, ...]
    removed_directory: bool


MODEL_SPECS: dict[str, ModelSpec] = {
    "Qwen/Qwen3-ASR-0.6B": ModelSpec(
        repo_id="Qwen/Qwen3-ASR-0.6B",
        display_name="Qwen-ASR-0.6B",
        required_files=(*_COMMON_REQUIRED_FILES, "model.safetensors"),
        managed_files=(*_COMMON_MANAGED_FILES, "model.safetensors"),
        download_size_mb=1200,
    ),
    "Qwen/Qwen3-ASR-1.7B": ModelSpec(
        repo_id="Qwen/Qwen3-ASR-1.7B",
        display_name="Qwen-ASR-1.7B",
        required_files=(
            *_COMMON_REQUIRED_FILES,
            "model-00001-of-00002.safetensors",
            "model-00002-of-00002.safetensors",
            "model.safetensors.index.json",
        ),
        managed_files=(
            *_COMMON_MANAGED_FILES,
            "model-00001-of-00002.safetensors",
            "model-00002-of-00002.safetensors",
            "model.safetensors.index.json",
        ),
        download_size_mb=3400,
    ),
}

_ALL_MANAGED_ENTRIES = frozenset(
    {".cache", *(entry for spec in MODEL_SPECS.values() for entry in spec.managed_files)}
)


def get_model_spec(repo_id: str) -> ModelSpec:
    try:
        return MODEL_SPECS[repo_id]
    except KeyError as exc:
        raise ModelResourceError(f"Unsupported ASR model: {repo_id}") from exc


def default_model_directory(repo_id: str) -> Path:
    get_model_spec(repo_id)
    return _DEFAULT_MODEL_ROOT / repo_id.replace("/", "--")


def resolve_model_directory(repo_id: str, custom_path: str = "") -> Path:
    custom_directory = _normalize_directory(custom_path)
    if custom_directory is not None:
        return custom_directory
    return default_model_directory(repo_id)


def validate_model_directory(repo_id: str, directory: str | Path) -> None:
    spec = get_model_spec(repo_id)
    directory_path = Path(directory).expanduser()

    if not directory_path.exists():
        raise ModelResourceError(f"Model directory does not exist: {directory_path}")
    if not directory_path.is_dir():
        raise ModelResourceError(f"Model path must be a directory, not a file: {directory_path}")

    missing_files: list[str] = []
    empty_files: list[str] = []
    for file_name in spec.required_files:
        file_path = directory_path / file_name
        if not file_path.exists():
            missing_files.append(file_name)
            continue
        try:
            if file_path.stat().st_size <= 0:
                empty_files.append(file_name)
        except OSError as exc:
            raise ModelResourceError(
                f"Failed to inspect {file_name} in {directory_path}: {exc}"
            ) from exc

    if missing_files or empty_files:
        details: list[str] = []
        if missing_files:
            details.append(f"Missing files: {', '.join(missing_files)}")
        if empty_files:
            details.append(f"Empty files: {', '.join(empty_files)}")
        raise ModelResourceError(
            f"{spec.display_name} is incomplete at {directory_path}. {' '.join(details)}"
        )


def resolve_model_load_path(repo_id: str, custom_path: str = "") -> str:
    custom_directory = _normalize_directory(custom_path)
    if custom_directory is not None:
        validate_model_directory(repo_id, custom_directory)
        return str(custom_directory)

    default_directory = default_model_directory(repo_id)
    if default_directory.exists():
        validate_model_directory(repo_id, default_directory)
        return str(default_directory)

    return repo_id


def find_hf_cache_snapshot(repo_id: str) -> Path | None:
    """Find the newest HF cache snapshot directory for a given repo.

    This probes the internal HF Hub cache layout directly
    (``models--{org}--{repo}/snapshots/<hash>/``) rather than using
    ``huggingface_hub.scan_cache_dir()`` for speed.  The layout has been
    stable since huggingface_hub 0.14, but a future reorganisation would
    require updating the path construction below.
    """
    hf_home = Path(os.environ.get("HF_HOME", "~/.cache/huggingface")).expanduser()
    hub_cache = Path(os.environ.get("HUGGINGFACE_HUB_CACHE", str(hf_home / "hub"))).expanduser()
    snapshots_root = hub_cache / f"models--{repo_id.replace('/', '--')}" / "snapshots"
    if not snapshots_root.is_dir():
        return None

    try:
        snapshots = [path for path in snapshots_root.iterdir() if path.is_dir()]
    except OSError:
        logger.exception("Failed to inspect Hugging Face cache for %s", repo_id)
        return None

    if not snapshots:
        return None

    try:
        return max(snapshots, key=lambda path: path.stat().st_mtime)
    except OSError:
        logger.exception("Failed to inspect snapshot metadata for %s", repo_id)
        return None


_HF_RESOLVE_URL = "https://huggingface.co/{repo_id}/resolve/main/{filename}"
_DOWNLOAD_CHUNK_SIZE = 8 * 1024 * 1024  # 8 MiB


def download_model_snapshot(
    repo_id: str,
    target_directory: str | Path,
    progress_callback: Callable[[str], None] | None = None,
    check_cancelled: Callable[[], bool] | None = None,
) -> Path:
    import requests  # noqa: PLC0415

    spec = get_model_spec(repo_id)
    directory_path = Path(target_directory).expanduser()
    directory_path.mkdir(parents=True, exist_ok=True)

    files_to_download = list(spec.managed_files)
    total_files = len(files_to_download)

    for file_index, filename in enumerate(files_to_download, start=1):
        if check_cancelled is not None and check_cancelled():
            raise ModelResourceError("Download cancelled.")

        file_path = directory_path / filename
        url = _HF_RESOLVE_URL.format(repo_id=repo_id, filename=filename)

        if progress_callback is not None:
            progress_callback(f"[{file_index}/{total_files}] Downloading {filename}...")

        try:
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise ModelResourceError(f"Failed to download {filename} from {url}: {exc}") from exc

        content_length = response.headers.get("Content-Length")
        total_bytes = int(content_length) if content_length else None
        downloaded_bytes = 0

        try:
            with file_path.open("wb") as f:
                for chunk in response.iter_content(chunk_size=_DOWNLOAD_CHUNK_SIZE):
                    if check_cancelled is not None and check_cancelled():
                        response.close()
                        raise ModelResourceError("Download cancelled.")

                    f.write(chunk)
                    downloaded_bytes += len(chunk)

                    if progress_callback is not None and total_bytes:
                        pct = downloaded_bytes * 100 // total_bytes
                        mb_done = downloaded_bytes / (1024 * 1024)
                        mb_total = total_bytes / (1024 * 1024)
                        progress_callback(
                            f"[{file_index}/{total_files}] {filename}: "
                            f"{mb_done:.1f} / {mb_total:.1f} MB ({pct}%)"
                        )
        except ModelResourceError:
            raise
        except OSError as exc:
            raise ModelResourceError(
                f"Failed to write {filename} to {directory_path}: {exc}"
            ) from exc

    validate_model_directory(repo_id, directory_path)
    if progress_callback is not None:
        progress_callback(f"Download complete: {directory_path}")
    return directory_path


def delete_model_artifacts(directory: str | Path) -> DeleteReport:
    directory_path = Path(directory).expanduser()
    if not directory_path.exists():
        return DeleteReport(
            target_directory=directory_path,
            removed_entries=(),
            remaining_entries=(),
            removed_directory=False,
        )
    if not directory_path.is_dir():
        raise ModelResourceError(
            f"Model path must be a directory before deletion: {directory_path}"
        )

    removed_entries: list[str] = []
    for entry_name in sorted(_ALL_MANAGED_ENTRIES):
        entry_path = directory_path / entry_name
        if not entry_path.exists():
            continue

        try:
            if entry_path.is_dir():
                shutil.rmtree(entry_path)
            else:
                entry_path.unlink()
        except PermissionError as exc:
            raise ModelResourceError(
                f"Failed to delete {entry_path}. The model may still be in use. Restart MyASR "
                "and try again."
            ) from exc
        except OSError as exc:
            raise ModelResourceError(f"Failed to delete {entry_path}: {exc}") from exc

        removed_entries.append(entry_name)

    remaining_entries = _list_directory_entries(directory_path)
    removed_directory = False
    if directory_path.exists() and not remaining_entries:
        try:
            directory_path.rmdir()
        except OSError as exc:
            raise ModelResourceError(f"Failed to remove {directory_path}: {exc}") from exc
        removed_directory = True

    return DeleteReport(
        target_directory=directory_path,
        removed_entries=tuple(removed_entries),
        remaining_entries=remaining_entries,
        removed_directory=removed_directory,
    )


def _normalize_directory(path_value: str | Path | None) -> Path | None:
    if path_value is None:
        return None
    if isinstance(path_value, Path):
        return path_value.expanduser()

    stripped_value = path_value.strip()
    if not stripped_value:
        return None
    return Path(stripped_value).expanduser()


def _list_directory_entries(directory: Path) -> tuple[str, ...]:
    if not directory.exists():
        return ()
    return tuple(sorted(entry.name for entry in directory.iterdir()))
