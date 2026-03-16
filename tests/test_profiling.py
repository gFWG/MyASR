"""Unit tests for the profiling module."""

import logging
import time

import pytest

from src.profiling import PipelineProfiler, ProfilingConfig, StageMetrics, StageTimer


class TestProfilingConfig:
    """Tests for ProfilingConfig dataclass."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = ProfilingConfig()
        assert config.enabled is True
        assert config.log_individual_stages is True
        assert config.log_summary is True
        assert config.summary_interval == 10
        assert config.slow_threshold_ms == 1000.0

    def test_custom_values(self) -> None:
        """Test custom configuration values."""
        config = ProfilingConfig(
            enabled=False,
            log_individual_stages=False,
            summary_interval=5,
            slow_threshold_ms=500.0,
        )
        assert config.enabled is False
        assert config.log_individual_stages is False
        assert config.summary_interval == 5
        assert config.slow_threshold_ms == 500.0


class TestStageMetrics:
    """Tests for StageMetrics dataclass."""

    def test_initial_state(self) -> None:
        """Test initial metrics state."""
        metrics = StageMetrics()
        assert metrics.count == 0
        assert metrics.total_ms == 0.0
        assert metrics.min_ms == float("inf")
        assert metrics.max_ms == 0.0

    def test_avg_ms_empty(self) -> None:
        """Test average with no recordings."""
        metrics = StageMetrics()
        assert metrics.avg_ms == 0.0

    def test_record_single(self) -> None:
        """Test recording a single timing."""
        metrics = StageMetrics()
        metrics.record(100.0)
        assert metrics.count == 1
        assert metrics.total_ms == 100.0
        assert metrics.min_ms == 100.0
        assert metrics.max_ms == 100.0
        assert metrics.avg_ms == 100.0

    def test_record_multiple(self) -> None:
        """Test recording multiple timings."""
        metrics = StageMetrics()
        metrics.record(100.0)
        metrics.record(200.0)
        metrics.record(50.0)
        assert metrics.count == 3
        assert metrics.total_ms == 350.0
        assert metrics.min_ms == 50.0
        assert metrics.max_ms == 200.0
        assert metrics.avg_ms == pytest.approx(116.666, rel=0.01)


class TestStageTimer:
    """Tests for StageTimer context manager."""

    def test_basic_timing(self) -> None:
        """Test basic timing functionality."""
        timer = StageTimer("test_stage")
        with timer:
            time.sleep(0.01)  # 10ms
        assert timer.elapsed_ms >= 10.0
        assert timer.elapsed_ms < 100.0  # Should not take 100ms

    def test_timer_records_to_profiler(self) -> None:
        """Test that timer records to profiler."""
        config = ProfilingConfig(enabled=True)
        profiler = PipelineProfiler(config)
        with StageTimer("test_stage", profiler):
            time.sleep(0.01)
        stats = profiler.get_stats()
        assert "test_stage" in stats.stages
        assert stats.stages["test_stage"].count == 1

    def test_disabled_profiler_no_record(self) -> None:
        """Test that disabled profiler doesn't record."""
        config = ProfilingConfig(enabled=False)
        profiler = PipelineProfiler(config)
        with StageTimer("test_stage", profiler):
            time.sleep(0.01)
        stats = profiler.get_stats()
        assert "test_stage" not in stats.stages

    def test_exception_still_records(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test that timing is recorded even on exception."""
        profiler = PipelineProfiler(ProfilingConfig())
        with pytest.raises(ValueError):
            with StageTimer("error_stage", profiler):
                time.sleep(0.005)
                raise ValueError("test error")
        # Timing should still be recorded
        stats = profiler.get_stats()
        assert "error_stage" in stats.stages


class TestPipelineProfiler:
    """Tests for PipelineProfiler class."""

    def test_record_stage(self) -> None:
        """Test recording a stage timing."""
        profiler = PipelineProfiler(ProfilingConfig())
        profiler.record("asr", 234.5)
        stats = profiler.get_stats()
        assert "asr" in stats.stages
        assert stats.stages["asr"].count == 1
        assert stats.stages["asr"].total_ms == 234.5

    def test_record_multiple_stages(self) -> None:
        """Test recording multiple different stages."""
        profiler = PipelineProfiler(ProfilingConfig())
        profiler.record("vad", 15.0)
        profiler.record("asr", 234.5)
        profiler.record("llm", 856.7)
        stats = profiler.get_stats()
        assert len(stats.stages) == 3
        assert stats.total_pipeline_ms == pytest.approx(1106.2)

    def test_disabled_profiler(self) -> None:
        """Test that disabled profiler doesn't record."""
        profiler = PipelineProfiler(ProfilingConfig(enabled=False))
        profiler.record("asr", 234.5)
        stats = profiler.get_stats()
        assert len(stats.stages) == 0
        assert stats.sentences_processed == 0

    def test_sentence_lifecycle(self) -> None:
        """Test start/end sentence cycle."""
        profiler = PipelineProfiler(ProfilingConfig())
        profiler.start_sentence()
        profiler.record("vad", 15.0)
        profiler.record("asr", 234.5)
        summary = profiler.end_sentence()
        assert "vad" in summary
        assert "asr" in summary
        assert "_total" in summary
        assert summary["vad"] == 15.0
        assert summary["asr"] == 234.5

    def test_sentence_count(self) -> None:
        """Test sentence counting."""
        profiler = PipelineProfiler(ProfilingConfig())
        for _ in range(3):
            profiler.start_sentence()
            profiler.record("asr", 100.0)
            profiler.end_sentence()
        stats = profiler.get_stats()
        assert stats.sentences_processed == 3
        assert stats.stages["asr"].count == 3

    def test_reset(self) -> None:
        """Test resetting profiler."""
        profiler = PipelineProfiler(ProfilingConfig())
        profiler.record("asr", 234.5)
        profiler.start_sentence()
        profiler.end_sentence()
        profiler.reset()
        stats = profiler.get_stats()
        assert len(stats.stages) == 0
        assert stats.sentences_processed == 0
        assert stats.total_pipeline_ms == 0.0

    def test_get_stats_snapshot(self) -> None:
        """Test that get_stats returns a snapshot."""
        profiler = PipelineProfiler(ProfilingConfig())
        profiler.record("asr", 100.0)
        stats1 = profiler.get_stats()
        profiler.record("asr", 200.0)
        stats2 = profiler.get_stats()
        # stats1 should be unchanged
        assert stats1.stages["asr"].count == 1
        assert stats1.stages["asr"].total_ms == 100.0
        # stats2 should have new data
        assert stats2.stages["asr"].count == 2
        assert stats2.stages["asr"].total_ms == 300.0

    def test_summary_log_interval(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test that summary is logged at configured interval."""
        caplog.set_level(logging.INFO)
        profiler = PipelineProfiler(ProfilingConfig(log_summary=True, summary_interval=3))
        for i in range(10):
            profiler.start_sentence()
            profiler.record("asr", 100.0)
            profiler.end_sentence()
        # Summary should be logged at 3, 6, 9
        summary_logs = [r for r in caplog.records if "Performance Summary" in r.message]
        assert len(summary_logs) == 3

    def test_no_summary_log_when_disabled(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test that summary logging can be disabled."""
        caplog.set_level(logging.INFO)
        profiler = PipelineProfiler(ProfilingConfig(log_summary=False))
        for _ in range(15):
            profiler.start_sentence()
            profiler.record("asr", 100.0)
            profiler.end_sentence()
        summary_logs = [r for r in caplog.records if "Performance Summary" in r.message]
        assert len(summary_logs) == 0


class TestIntegration:
    """Integration tests for profiling with StageTimer and PipelineProfiler."""

    def test_full_pipeline_simulation(self, caplog: pytest.LogCaptureFixture) -> None:
        """Simulate a full pipeline processing cycle."""
        caplog.set_level(logging.DEBUG)
        config = ProfilingConfig(
            enabled=True,
            log_individual_stages=True,
            log_summary=True,
            summary_interval=2,
        )
        profiler = PipelineProfiler(config)

        # Simulate processing 2 sentences
        for _ in range(2):
            profiler.start_sentence()

            with StageTimer("vad", profiler):
                time.sleep(0.005)

            with StageTimer("asr", profiler):
                time.sleep(0.010)

            with StageTimer("analysis", profiler):
                time.sleep(0.002)

            with StageTimer("llm", profiler):
                time.sleep(0.015)

            profiler.end_sentence()

        stats = profiler.get_stats()
        assert stats.sentences_processed == 2
        assert all(stage in stats.stages for stage in ["vad", "asr", "analysis", "llm"])

        # Check that timing was recorded
        assert stats.stages["vad"].count == 2
        assert stats.stages["asr"].count == 2
        assert stats.stages["analysis"].count == 2
        assert stats.stages["llm"].count == 2

        # Check that logs were generated
        sentence_logs = [r for r in caplog.records if "Sentence #" in r.message]
        assert len(sentence_logs) == 2

        summary_logs = [r for r in caplog.records if "Performance Summary" in r.message]
        assert len(summary_logs) == 1  # Logged at interval of 2
