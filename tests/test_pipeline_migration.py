def test_pipeline_package_is_the_new_orchestrator() -> None:
    """Verify the multi-stage pipeline package is available."""
    from src.pipeline.orchestrator import PipelineOrchestrator
    from src.pipeline.types import ASRResult, SpeechSegment

    assert PipelineOrchestrator is not None
    assert SpeechSegment is not None
    assert ASRResult is not None
