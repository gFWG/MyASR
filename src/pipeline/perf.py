"""Pipeline performance instrumentation utilities."""

from __future__ import annotations

import functools
import logging
import time
from typing import Callable, ParamSpec

from src.pipeline.types import PipelineStageMetrics

logger = logging.getLogger(__name__)

P = ParamSpec("P")


class StageTimer:
    """Context manager for timing a pipeline stage.

    Uses time.perf_counter_ns() for nanosecond precision timing.

    Example:
        with StageTimer("vad") as timer:
            # ... do work ...
            pass
        logger.info("elapsed: %.2f ms", timer.result.elapsed_ms)
    """

    def __init__(self, stage_name: str) -> None:
        self._stage_name = stage_name
        self._start_ns: int = 0
        self._end_ns: int = 0
        self._result: PipelineStageMetrics | None = None

    def __enter__(self) -> StageTimer:
        self._start_ns = time.perf_counter_ns()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        self._end_ns = time.perf_counter_ns()
        elapsed_ns = self._end_ns - self._start_ns
        elapsed_ms = elapsed_ns / 1_000_000  # Convert ns to ms
        start_sec = self._start_ns / 1_000_000_000  # Convert ns to seconds

        self._result = PipelineStageMetrics(
            stage=self._stage_name,
            start_time=start_sec,
            end_time=start_sec + (elapsed_ms / 1000),
            elapsed_ms=elapsed_ms,
        )

    @property
    def result(self) -> PipelineStageMetrics:
        """Get the timing result after context exit."""
        if self._result is None:
            raise RuntimeError("StageTimer result not available before __exit__")
        return self._result


class PipelineMetrics:
    """Aggregator for pipeline stage metrics.

    Collects timing results from multiple pipeline stages.
    """

    def __init__(self) -> None:
        self._results: list[PipelineStageMetrics] = []

    def add(self, result: PipelineStageMetrics) -> None:
        self._results.append(result)

    def to_dict(self) -> dict[str, float]:
        """Convert aggregated metrics to a dictionary.

        Returns:
            Dictionary mapping stage names to elapsed times in milliseconds.
        """
        return {result.stage: result.elapsed_ms for result in self._results}

    def log_summary(self, log: logging.Logger) -> None:
        """Log a summary of all pipeline stage timings.

        Uses lazy formatting for log messages.

        Args:
            log: Logger instance to use for output.
        """
        for result in self._results:
            log.info("Stage %s took %.2f ms", result.stage, result.elapsed_ms)


def timed_stage(stage_name: str) -> Callable[[Callable[P, object]], Callable[P, object]]:
    """Decorator to time a function as a pipeline stage.

    Wraps the function with a StageTimer and logs the result.

    Args:
        stage_name: Name of the pipeline stage.

    Returns:
        Decorated function that logs timing on completion.
    """

    def decorator(func: Callable[P, object]) -> Callable[P, object]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> object:
            with StageTimer(stage_name) as timer:
                result = func(*args, **kwargs)
            logger.info("Stage %s took %.2f ms", stage_name, timer.result.elapsed_ms)
            return result

        return wrapper

    return decorator
