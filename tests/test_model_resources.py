from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

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


def test_download_model_snapshot_restores_offline_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_id = "Qwen/Qwen3-ASR-0.6B"
    target_directory = tmp_path / "downloaded-model"
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "1")

    def _fake_snapshot_download(
        *,
        repo_id: str,
        local_dir: str,
        allow_patterns: list[str],
        local_dir_use_symlinks: bool,
    ) -> None:
        assert "HF_HUB_OFFLINE" not in os.environ
        assert "TRANSFORMERS_OFFLINE" not in os.environ
        assert allow_patterns == list(model_resources.get_model_spec(repo_id).managed_files)
        assert local_dir_use_symlinks is False
        _create_model_directory(repo_id, Path(local_dir))

    with (
        patch("src.asr.model_resources._reload_huggingface_hub_modules"),
        patch(
            "huggingface_hub.snapshot_download", side_effect=_fake_snapshot_download
        ) as mock_download,
    ):
        result = model_resources.download_model_snapshot(repo_id, target_directory)

    mock_download.assert_called_once()
    assert result == target_directory
    assert os.environ["HF_HUB_OFFLINE"] == "1"
    assert os.environ["TRANSFORMERS_OFFLINE"] == "1"


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
