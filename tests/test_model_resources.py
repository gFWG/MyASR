from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.asr import model_resources
from src.exceptions import ModelResourceError


def _create_model_directory(repo_id: str, directory: Path) -> Path:
    spec = model_resources.get_model_spec(repo_id)
    directory.mkdir(parents=True, exist_ok=True)
    for file_name in spec.required_files:
        (directory / file_name).write_bytes(b"ready")
    return directory


def test_validate_model_directory_accepts_complete_model(tmp_path: Path) -> None:
    model_dir = _create_model_directory("Qwen/Qwen3-ASR-0.6B", tmp_path / "model")

    model_resources.validate_model_directory("Qwen/Qwen3-ASR-0.6B", model_dir)


def test_resolve_model_load_path_raises_for_invalid_custom_directory(tmp_path: Path) -> None:
    model_dir = tmp_path / "incomplete-model"
    model_dir.mkdir()

    with pytest.raises(ModelResourceError, match="Missing files"):
        model_resources.resolve_model_load_path("Qwen/Qwen3-ASR-0.6B", str(model_dir))


def test_resolve_model_load_path_returns_repo_id_without_local_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(model_resources, "_DEFAULT_MODEL_ROOT", tmp_path / "models")

    result = model_resources.resolve_model_load_path("Qwen/Qwen3-ASR-0.6B")

    assert result == "Qwen/Qwen3-ASR-0.6B"


def test_download_model_snapshot_downloads_all_managed_files(
    tmp_path: Path,
) -> None:
    repo_id = "Qwen/Qwen3-ASR-0.6B"
    target_directory = tmp_path / "downloaded-model"
    spec = model_resources.get_model_spec(repo_id)

    def _fake_get(url: str, *, stream: bool, timeout: int) -> MagicMock:
        response = MagicMock()
        response.headers = {"Content-Length": "5"}
        response.iter_content.return_value = [b"ready"]
        response.raise_for_status = MagicMock()
        return response

    progress_messages: list[str] = []

    with patch("requests.get", side_effect=_fake_get) as mock_get:
        result = model_resources.download_model_snapshot(
            repo_id, target_directory, progress_callback=progress_messages.append
        )

    assert result == target_directory
    assert mock_get.call_count == len(spec.managed_files)
    for filename in spec.required_files:
        assert (target_directory / filename).exists()
    assert any("Download complete" in msg for msg in progress_messages)


def test_delete_model_artifacts_preserves_unmanaged_files(tmp_path: Path) -> None:
    model_dir = _create_model_directory("Qwen/Qwen3-ASR-0.6B", tmp_path / "model")
    (model_dir / ".cache").mkdir()
    unmanaged_file = model_dir / "notes.txt"
    unmanaged_file.write_text("keep me", encoding="utf-8")

    report = model_resources.delete_model_artifacts(model_dir)

    assert report.removed_entries
    assert report.remaining_entries == ("notes.txt",)
    assert report.removed_directory is False
    assert unmanaged_file.exists()
    assert not (model_dir / "model.safetensors").exists()
