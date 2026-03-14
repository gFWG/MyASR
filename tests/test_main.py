from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from src.config import AppConfig
from src.main import _build_pipeline_config


def test_build_pipeline_config_includes_resolved_model_path(tmp_path: Path) -> None:
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    config = AppConfig(asr_model="Qwen/Qwen3-ASR-1.7B", asr_model_local_path=str(model_dir))

    with patch("src.main.resolve_model_load_path", return_value=str(model_dir)) as mock_resolve:
        pipeline_config, active_model_directory = _build_pipeline_config(config)

    mock_resolve.assert_called_once_with("Qwen/Qwen3-ASR-1.7B", str(model_dir))
    assert pipeline_config["model_path"] == str(model_dir)
    assert active_model_directory == str(model_dir.resolve(strict=False))


def test_build_pipeline_config_leaves_active_directory_blank_for_repo_id() -> None:
    config = AppConfig()

    with patch(
        "src.main.resolve_model_load_path",
        return_value="Qwen/Qwen3-ASR-0.6B",
    ):
        pipeline_config, active_model_directory = _build_pipeline_config(config)

    assert pipeline_config["model_path"] == "Qwen/Qwen3-ASR-0.6B"
    assert active_model_directory == ""
