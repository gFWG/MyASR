"""Pipeline stage metrics types."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PipelineStageMetrics:
    """Metrics for a single pipeline stage execution.

    Attributes:
        stage: Name of the pipeline stage.
        start_time: Start time in seconds (from time.perf_counter()).
        end_time: End time in seconds (from time.perf_counter()).
        elapsed_ms: Elapsed time in milliseconds.
    """

    stage: str
    start_time: float
    end_time: float
    elapsed_ms: float
