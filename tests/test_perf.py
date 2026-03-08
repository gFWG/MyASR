"""Tests for pipeline performance instrumentation."""

import logging
import time

from src.pipeline.perf import PipelineMetrics, StageTimer, timed_stage
from src.pipeline.types import PipelineStageMetrics


def test_stage_timer_accuracy():
    """StageTimer should accurately measure elapsed time using perf_counter_ns."""
    sleep_seconds = 0.1  # 100ms

    with StageTimer("test_stage") as timer:
        time.sleep(sleep_seconds)

    result = timer.result
    assert result.stage == "test_stage"
    assert result.elapsed_ms > 0
    # Allow some variance (90ms to 150ms for 100ms sleep)
    assert 90 <= result.elapsed_ms <= 150


def test_pipeline_metrics_aggregation():
    """PipelineMetrics should aggregate multiple stage results."""
    metrics = PipelineMetrics()

    result1 = PipelineStageMetrics("vad", 0.0, 0.0, 50.0)
    result2 = PipelineStageMetrics("asr", 0.0, 0.0, 120.0)

    metrics.add(result1)
    metrics.add(result2)

    result_dict = metrics.to_dict()

    assert "vad" in result_dict
    assert "asr" in result_dict
    assert result_dict["vad"] == 50.0
    assert result_dict["asr"] == 120.0


def test_log_summary_uses_lazy_formatting():
    """log_summary should use lazy formatting without errors."""
    logger = logging.getLogger("test_logger")
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)
    logger.addHandler(handler)

    metrics = PipelineMetrics()
    result1 = PipelineStageMetrics("vad", 0.0, 0.0, 50.0)
    result2 = PipelineStageMetrics("asr", 0.0, 0.0, 120.0)
    metrics.add(result1)
    metrics.add(result2)

    # Should not raise any errors
    metrics.log_summary(logger)


def test_timed_stage_decorator():
    """@timed_stage decorator should measure function execution time."""
    logger = logging.getLogger("test_timed_stage")
    logger.setLevel(logging.INFO)

    @timed_stage("test_function")
    def slow_function():
        time.sleep(0.05)  # 50ms
        return "done"

    result = slow_function()

    assert result == "done"


def test_stage_timer_context_manager():
    """StageTimer should work as a context manager."""
    timer = StageTimer("my_stage")

    # Test __enter__ returns self
    with timer as t:
        assert t is timer
        time.sleep(0.01)

    # Test result is populated after exit
    assert t.result is not None
    assert t.result.stage == "my_stage"
    assert t.result.elapsed_ms > 0


def test_pipeline_metrics_empty():
    """PipelineMetrics with no stages returns empty dict."""
    metrics = PipelineMetrics()
    assert metrics.to_dict() == {}


def test_pipeline_metrics_log_empty():
    """log_summary with no stages should not error."""
    logger = logging.getLogger("test_empty")
    logger.setLevel(logging.INFO)

    metrics = PipelineMetrics()
    metrics.log_summary(logger)  # Should not raise
