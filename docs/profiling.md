# Performance Profiling Guide

This document describes how to use the performance profiling system to identify bottlenecks in the MyASR pipeline.

## Overview

The profiling module provides lightweight timing measurements for each pipeline stage:

```
Audio Capture → VAD → ASR → Analysis → LLM → DB
```

## Quick Start

Profiling is enabled by default. When you run the application, you'll see timing logs in the console:

```
INFO  [profiling] Sentence #1: vad=12.3ms asr=234.5ms analysis=5.2ms llm=856.7ms db=2.1ms total=1110.9ms
```

## Configuration

Configure profiling in `data/config.json`:

```json
{
  "profiling": {
    "enabled": true,
    "log_individual_stages": true,
    "log_summary": true,
    "summary_interval": 10,
    "slow_threshold_ms": 1000.0
  }
}
```

### Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enabled` | bool | `true` | Enable/disable profiling. When disabled, all timing operations are no-ops. |
| `log_individual_stages` | bool | `true` | Log timing for each stage completion. |
| `log_summary` | bool | `true` | Log aggregate statistics periodically. |
| `summary_interval` | int | `10` | Number of sentences between summary logs. |
| `slow_threshold_ms` | float | `1000.0` | Threshold for slow stage warnings (milliseconds). |

## Log Output

### Individual Stage Timing

Each sentence processing cycle logs the timing for all stages:

```
INFO  [profiling] Sentence #42: vad=12.3ms asr=234.5ms analysis=5.2ms llm=856.7ms db=2.1ms total=1110.9ms
```

### Slow Stage Warnings

When a stage exceeds the configured threshold, a warning is logged:

```
WARN  [profiling] Stage 'llm' slow: 1523.2 ms (threshold: 1000.0 ms)
```

### Aggregate Statistics

At configured intervals, aggregate statistics are logged:

```
INFO  [profiling] === Performance Summary (100 sentences) ===
INFO  [profiling] analysis: avg=4.8ms min=2.1ms max=15.6ms total=480.0ms
INFO  [profiling] asr: avg=245.3ms min=180.2ms max=512.8ms total=24530.0ms
INFO  [profiling] db: avg=2.3ms min=0.8ms max=12.4ms total=230.0ms
INFO  [profiling] llm: avg=923.5ms min=450.2ms max=2345.6ms total=92350.0ms
INFO  [profiling] vad: avg=15.2ms min=8.1ms max=45.3ms total=1520.0ms
INFO  [profiling] Total pipeline time: 119122.3ms
INFO  [profiling] =============================================
```

## Expected Performance

Based on the architecture, here are the expected timing ranges for each stage:

| Stage | Expected Range | Notes |
|-------|---------------|-------|
| VAD | 10-50 ms | Silero VAD, CPU inference |
| ASR | 200-500 ms | Qwen3-ASR-0.6B, GPU inference |
| Analysis | 1-10 ms | Tokenizer + dictionary lookups |
| LLM | 500-2000 ms | Ollama API call + inference |
| DB | 1-5 ms | SQLite inserts |

## Identifying Bottlenecks

### Common Bottlenecks

1. **LLM** - Usually the slowest stage due to network latency and model inference.
   - Check Ollama is running locally (not remote)
   - Consider using a smaller model (e.g., `qwen3.5:1.8b`)

2. **ASR** - GPU-dependent. If slow:
   - Check GPU memory usage
   - Verify CUDA is available and working

3. **VAD** - Should be fast. If slow:
   - Check CPU usage from other processes
   - Verify audio sample rate is 16kHz

### Reading the Logs

Look for:
- Stages with high `avg` values (average time)
- Stages with high `max` values (potential outliers)
- Warnings about slow stages

### Disabling Profiling

For production use, you can disable profiling to eliminate any overhead:

```json
{
  "profiling": {
    "enabled": false
  }
}
```

## Programmatic Usage

You can also use the profiling components programmatically:

```python
from src.profiling import PipelineProfiler, ProfilingConfig, StageTimer

# Create profiler with custom config
config = ProfilingConfig(
    enabled=True,
    log_summary=True,
    summary_interval=5,
)
profiler = PipelineProfiler(config)

# Time a stage
profiler.start_sentence()
with StageTimer("my_stage", profiler):
    # ... do work ...
    pass
profiler.end_sentence()

# Get statistics
stats = profiler.get_stats()
print(f"Average time: {stats.stages['my_stage'].avg_ms:.1f} ms")
```

## Architecture

The profiling module consists of three main components:

1. **`ProfilingConfig`** - Configuration dataclass for behavior settings
2. **`StageTimer`** - Context manager for measuring stage duration
3. **`PipelineProfiler`** - Aggregates metrics and generates reports

The profiler integrates into [`PipelineWorker.run()`](../src/pipeline.py) and wraps each pipeline stage with `StageTimer`:
- VAD processing
- ASR transcription
- Text analysis
- LLM translation
- Database writes