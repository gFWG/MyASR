import pytest


def test_pipeline_legacy_import_works() -> None:
    from src.pipeline_legacy import PipelineWorker

    assert PipelineWorker is not None
    assert hasattr(PipelineWorker, "sentence_ready")
    assert hasattr(PipelineWorker, "error_occurred")


def test_pipeline_module_no_longer_exists() -> None:
    with pytest.raises(ImportError, match="pipeline"):
        from src import pipeline  # type: ignore[attr-defined]  # noqa: F401
