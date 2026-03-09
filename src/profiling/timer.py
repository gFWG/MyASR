"""Context manager for measuring stage execution duration."""

import logging
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.profiling.profiler import PipelineProfiler

logger = logging.getLogger(__name__)


class StageTimer:
    """Context manager for measuring and logging stage execution time.

    Records timing to an optional PipelineProfiler and logs individual
    stage durations. Exception-safe: timing is recorded even if the
    stage raises an exception.

    Args:
        stage_name: Name of the pipeline stage being measured.
        profiler: Optional PipelineProfiler to record timing to.
        slow_threshold_ms: Threshold in ms for slow stage warnings.
            If None, uses the profiler's threshold or no warning.

    Example:
        with StageTimer("asr", profiler) as timer:
            text = asr.transcribe(audio)
        # Timer automatically records to profiler and logs
    """

    def __init__(
        self,
        stage_name: str,
        profiler: "PipelineProfiler | None" = None,
        slow_threshold_ms: float | None = None,
    ) -> None:
        self._stage_name = stage_name
        self._profiler = profiler
        self._slow_threshold_ms = slow_threshold_ms
        self._start_time: float = 0.0
        self._elapsed_ms: float = 0.0

    def __enter__(self) -> "StageTimer":
        """Start timing on context entry."""
        self._start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        """Stop timing and record on context exit."""
        end_time = time.perf_counter()
        self._elapsed_ms = (end_time - self._start_time) * 1000.0

        # Record to profiler if available
        if self._profiler is not None:
            self._profiler.record(self._stage_name, self._elapsed_ms)

        # Log individual stage timing
        if self._profiler is not None and self._profiler._config.log_individual_stages:
            self._log_stage()

    def _log_stage(self) -> None:
        """Log the stage timing, with warning if slow."""
        threshold = self._slow_threshold_ms
        if threshold is None and self._profiler is not None:
            threshold = self._profiler._config.slow_threshold_ms

        if threshold is not None and self._elapsed_ms > threshold:
            logger.warning(
                "Stage '%s' slow: %.1f ms (threshold: %.1f ms)",
                self._stage_name,
                self._elapsed_ms,
                threshold,
            )
        else:
            logger.debug(
                "Stage '%s' completed in %.1f ms",
                self._stage_name,
                self._elapsed_ms,
            )

    @property
    def elapsed_ms(self) -> float:
        """Get the elapsed time in milliseconds.

        Returns 0.0 if the timer hasn't been used yet, or the actual
        elapsed time after the context exits.
        """
        return self._elapsed_ms
