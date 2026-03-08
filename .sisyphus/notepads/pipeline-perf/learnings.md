# Learnings — pipeline-perf

## Project Setup
- Worktree: /home/yuheng/MyASR-pipeline-perf (detached HEAD from main)
- Main repo: /home/yuheng/MyASR
- Plan: .sisyphus/plans/pipeline-perf.md (1550 lines, 13 tasks + Final wave)
- Venv: source .venv/bin/activate (Python 3.12)
- QA commands: ruff check . && ruff format --check . && mypy . && pytest -x

## Architecture Overview
- Single-threaded pipeline being refactored into 3-stage concurrent architecture
- Wave 0: Rename pipeline.py → pipeline_legacy.py  
- Wave 1: Foundation (types, perf, VAD opt, DB two-phase) — Tasks 1-4 PARALLEL
- Wave 2: Workers (VAD/ASR/LLM threads, WASAPI opt) — Tasks 5-9 MAX PARALLEL
- Wave 3: Integration (Orchestrator, Progressive UI) — Tasks 10-11 SEQUENTIAL
- Wave 4: Integration tests — Task 12
- Final: F1-F4 parallel review

## Code Conventions
- Python 3.12+, type annotations required on all public functions
- Double quotes, 99 char line length
- Frozen dataclasses with __slots__ for pipeline types
- QThread subclass pattern for workers (consistent with existing codebase)
- logger = logging.getLogger(__name__) at module level
- pytest, no unittest.TestCase

## Critical Design Decisions
- Preprocessing (fugashi) runs in ASR thread (fast ~2ms)
- DB writes: INSERT at ASR (translation=NULL), UPDATE when LLM completes
- segment_queue maxsize=20, text_queue maxsize=50, result_queue maxsize=50
- LLM workers create own AsyncOllamaClient (no sharing between threads)
- Shutdown order: LLM→ASR→VAD→audio (reverse of startup)
- All workers use put_nowait() for output queues (drop + warn if full, never block)

## [2026-03-08] Task 2: Performance Instrumentation

### Implementation Details
- `StageTimerResult`: frozen dataclass with `stage` and `elapsed_ms` fields
- `StageTimer`: context manager using `time.perf_counter_ns()` for nanosecond accuracy
- `PipelineMetrics`: aggregates `list[StageTimerResult]`, provides `to_dict()` and `log_summary()`
- `TimedResult[T]`: Generic wrapper for decorator return values with `value` and `stage_result` properties
- `timed_stage(stage_name)`: decorator returning `TimedResult[T]` wrapping function output

### Key Decisions
- Used `perf_counter_ns()` instead of `perf_counter()` for maximum precision
- Timer records time even when exception occurs in timed block (in `__exit__`)
- Decorator wraps return value in `TimedResult` rather than trying to attach attributes (works with all types including immutables)
- Logger uses lazy formatting: `logger.info("Stage %s: %.1f ms", stage, elapsed)` not f-strings
- All public APIs have Python 3.12+ style type annotations

### Test Coverage (18 tests)
- StageTimerResult: construction, immutability, equality
- StageTimer: accuracy (sleep 100ms → [90,150]ms), result() method, exception handling
- PipelineMetrics: record, to_dict, log_summary, duplicate stages
- timed_stage: mutable/immutable returns, exceptions, metadata preservation, arguments

### Verification
- pytest: 18/18 passed
- mypy: 0 errors
- ruff: 0 issues
- Evidence: .sisyphus/evidence/task-2-timer-accuracy.txt
