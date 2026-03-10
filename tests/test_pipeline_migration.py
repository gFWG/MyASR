def test_pipeline_legacy_import_works() -> None:
    from src.pipeline_legacy import PipelineWorker

    assert PipelineWorker is not None
    assert hasattr(PipelineWorker, "sentence_ready")
    assert hasattr(PipelineWorker, "error_occurred")


def test_pipeline_package_is_the_new_orchestrator() -> None:
    # src.pipeline is now the new multi-stage pipeline package (not the old monolith).
    # The old monolith lives at src.pipeline_legacy (tested above).
    from src.pipeline.orchestrator import PipelineOrchestrator
    from src.pipeline.types import ASRResult, SpeechSegment, LLMResult

    assert PipelineOrchestrator is not None
    assert SpeechSegment is not None
    assert ASRResult is not None
    assert LLMResult is not None
