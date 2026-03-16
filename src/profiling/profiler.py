"""Pipeline profiler for aggregating and reporting performance metrics."""

import logging
import threading
from dataclasses import dataclass, field

from src.profiling.config import ProfilingConfig

logger = logging.getLogger(__name__)


@dataclass
class StageMetrics:
    """Aggregated metrics for a single pipeline stage.

    Attributes:
        count: Number of times this stage was executed.
        total_ms: Total execution time in milliseconds.
        min_ms: Minimum execution time in milliseconds.
        max_ms: Maximum execution time in milliseconds.
    """

    count: int = 0
    total_ms: float = 0.0
    min_ms: float = float("inf")
    max_ms: float = 0.0

    @property
    def avg_ms(self) -> float:
        """Average execution time in milliseconds."""
        return self.total_ms / self.count if self.count > 0 else 0.0

    def record(self, elapsed_ms: float) -> None:
        """Record a single execution timing.

        Args:
            elapsed_ms: Execution time in milliseconds.
        """
        self.count += 1
        self.total_ms += elapsed_ms
        self.min_ms = min(self.min_ms, elapsed_ms)
        self.max_ms = max(self.max_ms, elapsed_ms)


@dataclass
class ProfilingStats:
    """Aggregated profiling statistics for all pipeline stages.

    Attributes:
        stages: Dictionary mapping stage names to their metrics.
        sentences_processed: Number of complete sentences processed.
        total_pipeline_ms: Total time spent in all stages combined.
    """

    stages: dict[str, StageMetrics] = field(default_factory=dict)
    sentences_processed: int = 0
    total_pipeline_ms: float = 0.0


class PipelineProfiler:
    """Aggregates and reports pipeline performance metrics.

    Tracks timing for each pipeline stage, aggregates statistics, and
    logs periodic summaries. Thread-safe for use in multi-threaded
    pipelines.

    Args:
        config: ProfilingConfig controlling behavior.

    Example:
        profiler = PipelineProfiler(ProfilingConfig())
        profiler.start_sentence()
        profiler.record("asr", 234.5)
        profiler.record("llm", 856.7)
        summary = profiler.end_sentence()
        # summary == {"asr": 234.5, "llm": 856.7, "_total": 1091.2}
    """

    def __init__(self, config: ProfilingConfig) -> None:
        self._config = config
        self._lock = threading.Lock()
        self._stats = ProfilingStats()
        self._current_sentence: dict[str, float] = {}
        self._sentence_start_time: float = 0.0

    @property
    def config(self) -> ProfilingConfig:
        """Public accessor for profiling configuration."""
        return self._config

    def record(self, stage: str, elapsed_ms: float) -> None:
        """Record a stage execution timing.

        Args:
            stage: Name of the pipeline stage.
            elapsed_ms: Execution time in milliseconds.
        """
        if not self._config.enabled:
            return

        with self._lock:
            # Update current sentence timing
            self._current_sentence[stage] = elapsed_ms

            # Update aggregate stats
            if stage not in self._stats.stages:
                self._stats.stages[stage] = StageMetrics()
            self._stats.stages[stage].record(elapsed_ms)
            self._stats.total_pipeline_ms += elapsed_ms

    def start_sentence(self) -> None:
        """Mark the start of a new sentence processing cycle.

        Should be called at the beginning of processing each sentence.
        """
        if not self._config.enabled:
            return

        import time

        with self._lock:
            self._current_sentence = {}
            self._sentence_start_time = time.perf_counter()

    def end_sentence(self) -> dict[str, float]:
        """Mark the end of the current sentence processing cycle.

        Logs the sentence summary and periodic aggregate statistics.

        Returns:
            Dictionary of stage timings for the completed sentence,
            including a "_total" key with the total processing time.
        """
        if not self._config.enabled:
            return {}

        import time

        with self._lock:
            # Calculate total time for this sentence
            total_ms = (time.perf_counter() - self._sentence_start_time) * 1000.0
            self._current_sentence["_total"] = total_ms

            self._stats.sentences_processed += 1

            # Log sentence summary
            if self._config.log_individual_stages:
                stage_strs = [
                    f"{k}={v:.1f}ms" for k, v in self._current_sentence.items() if k != "_total"
                ]
                logger.info(
                    "Sentence #%d: %s total=%.1fms",
                    self._stats.sentences_processed,
                    " ".join(stage_strs),
                    total_ms,
                )

            # Log aggregate summary at intervals
            if (
                self._config.log_summary
                and self._stats.sentences_processed % self._config.summary_interval == 0
            ):
                self._log_summary()

            result = self._current_sentence.copy()
            self._current_sentence = {}
            return result

    def get_stats(self) -> ProfilingStats:
        """Get a snapshot of current profiling statistics.

        Returns:
            ProfilingStats with current aggregate metrics.
        """
        with self._lock:
            stages_copy = {
                k: StageMetrics(
                    count=v.count, total_ms=v.total_ms, min_ms=v.min_ms, max_ms=v.max_ms
                )
                for k, v in self._stats.stages.items()
            }
            return ProfilingStats(
                stages=stages_copy,
                sentences_processed=self._stats.sentences_processed,
                total_pipeline_ms=self._stats.total_pipeline_ms,
            )

    def reset(self) -> None:
        """Reset all profiling statistics to initial state."""
        with self._lock:
            self._stats = ProfilingStats()
            self._current_sentence = {}
            self._sentence_start_time = 0.0
        logger.debug("Profiling statistics reset")

    def _log_summary(self) -> None:
        """Log aggregate statistics summary."""
        logger.info(
            "=== Performance Summary (%d sentences) ===",
            self._stats.sentences_processed,
        )
        for stage_name, metrics in sorted(self._stats.stages.items()):
            logger.info(
                "%s: avg=%.1fms min=%.1fms max=%.1fms total=%.1fms",
                stage_name,
                metrics.avg_ms,
                metrics.min_ms,
                metrics.max_ms,
                metrics.total_ms,
            )
        logger.info("Total pipeline time: %.1fms", self._stats.total_pipeline_ms)
        logger.info("=" * 42)
