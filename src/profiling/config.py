"""Configuration dataclass for profiling behavior."""

from dataclasses import dataclass


@dataclass
class ProfilingConfig:
    """Configuration options for pipeline performance profiling.

    Attributes:
        enabled: Whether profiling is enabled. When False, all timing
            operations are no-ops with minimal overhead.
        log_individual_stages: Log timing for each stage completion.
        log_summary: Log aggregate statistics at summary_interval.
        summary_interval: Number of sentences between summary logs.
        slow_threshold_ms: Threshold in milliseconds for slow stage warnings.
            Stages exceeding this will trigger a WARNING log.
    """

    enabled: bool = True
    log_individual_stages: bool = True
    log_summary: bool = True
    summary_interval: int = 10
    slow_threshold_ms: float = 1000.0
