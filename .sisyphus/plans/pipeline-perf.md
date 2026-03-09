# Pipeline Performance: Multi-Threaded Architecture Refactor

## TL;DR

> **Quick Summary**: Refactor the single-threaded ASR pipeline into a multi-stage concurrent architecture (Audio+VAD → ASR → LLM threads) with bounded queues, eliminating the "queue Full" audio loss and reducing end-to-end latency from 6-30s to <3s for ASR display.
> 
> **Deliverables**:
> - Multi-threaded pipeline with 3 worker stages connected by bounded queues
> - Progressive UI display (ASR text immediately, translation appears async)
> - Silero VAD optimized (ONNX, ring buffer, no redundant allocations)
> - ASR batch inference using Qwen3-ASR list API
> - Async LLM client with streaming responses (httpx)
> - LRU translation cache
> - Performance instrumentation (timing for every stage)
> - Full TDD test suite for all new workers
> 
> **Estimated Effort**: Large
> **Parallel Execution**: YES — 4 waves
> **Critical Path**: Task 0 (rename) → Task 1 (types) → Task 6 (ASR worker) → Task 10 (orchestrator) → Task 12 (integration) → Final Verification

---

## Context

### Original Request
User reports "almost unacceptable" ASR latency and the audio queue keeps warning "Full". Systematic bottleneck identification revealed 10 issues, with the root cause being a single-threaded pipeline that blocks audio consumption during GPU inference (1-2s) and LLM HTTP calls (5-30s).

### Investigation Summary
**5 parallel research agents** analyzed the codebase and external best practices:

1. **Queue Math Proof**: At 31 chunks/sec incoming, ASR+LLM blocking for 6-17s per segment accumulates 186-527 chunks. Queue overflows (maxsize=1000) after ~2 speech segments.
2. **ASR Batch API**: `Qwen3ASRModel.transcribe()` accepts `List[AudioLike]` but pipeline sends one segment at a time.
3. **LLM Blocking**: `requests.post(stream=False, timeout=30)` freezes entire pipeline. No caching, no connection pooling.
4. **VAD Hotspots**: O(n²) np.concatenate 31×/sec, redundant `.float()` tensor creation, excessive `.copy()`.
5. **WASAPI Backend**: `scipy.signal.resample` (FFT-based) in audio callback (Windows-specific).
6. **Best Practices**: Multi-threaded pipeline with bounded queues is consensus for real-time ASR. ONNX Silero 5× faster. httpx async + streaming for LLM.

### Metis Review
**Guardrails** (addressed in plan):
- G1: Never block audio thread — VAD must complete within 32ms chunk interval
- G2: Graceful degradation — if LLM fails, ASR text still displayed
- G3: Shutdown ordering — reverse startup: stop audio first, drain queues, stop workers
- G4: No shared mutable state — communicate only via queues and Qt signals
- G5: Bounded queue sizes — prevent unbounded memory growth
- G6: Thread-safe config updates — don't mutate worker state from UI thread

**Design Decisions** (Metis-recommended, accepted):
- Preprocessing (fugashi) runs in ASR thread (fast ~2ms, simpler architecture)
- DB writes: INSERT at ASR completion (translation=NULL), UPDATE when LLM completes
- Threading: QThread subclass pattern (consistent with existing codebase)

---

## Work Objectives

### Core Objective
Transform the single-threaded pipeline into a multi-stage concurrent architecture where audio consumption never blocks on ASR inference or LLM generation, achieving <3s ASR display latency and zero audio loss.

### Concrete Deliverables
- `src/pipeline.py` — Refactored into orchestrator managing worker threads
- `src/pipeline/` — New package with: `types.py`, `vad_worker.py`, `asr_worker.py`, `llm_worker.py`, `orchestrator.py`
- `src/vad/silero.py` — Optimized: ONNX mode, ring buffer, zero redundant allocations
- `src/asr/qwen_asr.py` — Batch transcription support, torch.inference_mode
- `src/llm/ollama_client.py` — Async httpx client with streaming and LRU cache
- `src/ui/overlay.py` — Progressive display: ASR text first, translation update later
- `src/db/repository.py` — Two-phase write: INSERT at ASR, UPDATE at LLM
- `tests/` — Full TDD test suite for all workers, queue behavior, shutdown, edge cases
- Performance instrumentation throughout pipeline

### Definition of Done
- [x] Zero "queue Full" warnings during 30-minute continuous audio test
- [x] ASR text displayed within 3 seconds of speech end
- [x] Translation displayed within 8 seconds of speech end
- [x] Zero audio data loss during ASR/LLM processing
- [x] Clean shutdown completes in <5 seconds with no orphan threads
- [x] `ruff check . && ruff format --check . && mypy . && pytest -x` all pass
- [x] Progressive UI: ASR text appears before translation

### Must Have
- Audio consumption never blocks on downstream processing
- Bounded queues between all stages with documented maxsize rationale
- Graceful degradation: ASR works even if LLM is unavailable
- Thread-safe shutdown with proper ordering
- All existing functionality preserved (no feature regression)
- Performance timing logged for every pipeline stage

### Must NOT Have (Guardrails)
- ❌ Streaming ASR (keep batch mode — out of scope)
- ❌ GPU sharing/multiplexing between VAD and ASR
- ❌ Async DB writes (SQLite sync is fast enough)
- ❌ UI redesign (only add progressive display signals, keep existing layout)
- ❌ Model changes (keep Qwen3-ASR-0.6B and qwen3.5:4b)
- ❌ Abstract base classes for workers (simple direct implementations)
- ❌ Over-abstraction — each worker is a concrete QThread subclass, no factory patterns
- ❌ `as any` / `@ts-ignore` equivalents — no `type: ignore` without documented reason
- ❌ Empty except blocks — all errors must be logged with context
- ❌ Shared mutable state between threads — queues and signals only

---

## Verification Strategy

> **ZERO HUMAN INTERVENTION** — ALL verification is agent-executed. No exceptions.

### Test Decision
- **Infrastructure exists**: YES (pytest)
- **Automated tests**: TDD (RED → GREEN → REFACTOR)
- **Framework**: pytest
- **Each task**: Write failing tests FIRST, then implement until tests pass

### QA Policy
Every task MUST include agent-executed QA scenarios.
Evidence saved to `.sisyphus/evidence/task-{N}-{scenario-slug}.{ext}`.

- **Pipeline Workers**: Use Bash (pytest) — Run unit tests, assert pass counts
- **Threading/Concurrency**: Use Bash (pytest) — Stress tests with simulated audio, verify queue behavior
- **UI Progressive Display**: Use Playwright — Navigate overlay, verify ASR text appears before translation
- **Performance**: Use Bash (Python script) — Measure stage timings, assert within thresholds
- **Integration**: Use Bash (pytest + tmux) — Full pipeline with mock audio, verify end-to-end flow

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 0 (Prerequisite — unblocks package creation):
└── Task 0: Rename src/pipeline.py → src/pipeline_legacy.py [quick]

Wave 1 (Foundation — types, interfaces, optimizations):
├── Task 1: Pipeline types & data models [quick]
├── Task 2: Performance instrumentation utility [quick]
├── Task 3: VAD optimization (ONNX + ring buffer) [deep]
└── Task 4: DB repository two-phase write [quick]

Wave 2 (Workers — MAX PARALLEL, all independent after Wave 1):
├── Task 5: VAD Worker thread [deep]
├── Task 6: ASR batch transcription + worker [deep]
├── Task 7: Async LLM client (httpx streaming + cache) [deep]
├── Task 8: LLM Worker thread [deep]
└── Task 9: WASAPI resampling optimization [unspecified-high]

Wave 3 (Integration — connects workers + UI):
├── Task 10: Pipeline Orchestrator [deep]
└── Task 11: Progressive UI display [visual-engineering]

Wave 4 (Verification):
└── Task 12: Integration test & performance validation [deep]

Wave FINAL (Independent review, 4 parallel):
├── Task F1: Plan compliance audit (oracle)
├── Task F2: Code quality review (unspecified-high)
├── Task F3: Real manual QA (unspecified-high)
└── Task F4: Scope fidelity check (deep)

Critical Path: Task 0 → Task 1 → Task 6 → Task 10 → Task 12 → F1-F4
Parallel Speedup: ~60% faster than sequential
Max Concurrent: 5 (Wave 2)
```

### Dependency Matrix

| Task | Depends On | Blocks | Wave |
|------|-----------|--------|------|
| 0 | — | 1,2,3,4,5,6,7,8,9,10,11,12 | 0 |
| 1 | 0 | 2,3,4,5,6,7,8,10 | 1 |
| 2 | 0,1 | 5,6,8,10 | 1 |
| 3 | 0,1 | 5 | 1 |
| 4 | 0,1 | 8,10 | 1 |
| 5 | 1,2,3 | 10 | 2 |
| 6 | 1,2 | 10 | 2 |
| 7 | 1 | 8 | 2 |
| 8 | 1,2,4,7 | 10 | 2 |
| 9 | 0 | — | 2 |
| 10 | 1,2,4,5,6,7,8 | 11,12 | 3 |
| 11 | 10 | 12 | 3 |
| 12 | 10,11 | F1-F4 | 4 |
| F1-F4 | 12 | — | FINAL |
| 10 | 4,5,6,8,9 | 11,13 | 3 |
| 11 | 10 | 13 | 3 |
| 12 | — | 13 | 3 |
| 13 | 10,11,12 | 14,15 | 4 |
| 14 | 2,13 | — | 4 |
| 15 | 13 | — | 4 |

### Agent Dispatch Summary

| Wave | Tasks | Categories |
|------|-------|-----------|
| 0 | 1 | T0→`quick` (+git-master) |
| 1 | 4 | T1→`quick`, T2→`quick`, T3→`deep`, T4→`quick` |
| 2 | 5 | T5→`deep`, T6→`deep`, T7→`deep`, T8→`deep`, T9→`unspecified-high` |
| 3 | 2 | T10→`deep`, T11→`visual-engineering` (+playwright) |
| 4 | 1 | T12→`deep` |
| FINAL | 4 | F1→`oracle`, F2→`unspecified-high`, F3→`unspecified-high` (+playwright), F4→`deep` |

---

## TODOs

> Implementation + Test = ONE Task. Never separate.
> EVERY task has: Recommended Agent Profile + Parallelization + QA Scenarios.

### Wave 0: Prerequisite Rename (Task 0)

- [x] 0. Rename `src/pipeline.py` → `src/pipeline_legacy.py` to Unblock Package Creation

  **What to do**:
  - RED: Write a test that `from src.pipeline_legacy import PipelineWorker` works (migration test).
  - GREEN:
    1. Rename `src/pipeline.py` → `src/pipeline_legacy.py`
    2. Update ALL imports across the codebase: `from src.pipeline import PipelineWorker` → `from src.pipeline_legacy import PipelineWorker` (check `src/main.py` and any test files)
    3. Update any test files that import from `src.pipeline`
    4. This allows creating `src/pipeline/` as a package in subsequent tasks
  - REFACTOR: Verify `ruff check . && mypy . && pytest` still pass after rename.

  **Must NOT do**:
  - Don't change any logic inside the renamed file
  - Don't delete the file (Task 10 will eventually replace it with the orchestrator)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Mechanical rename + import update, no logic changes
  - **Skills**: [`git-master`]
    - `git-master`: For clean rename tracking via `git mv`

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 0 (must complete before any other task)
  - **Blocks**: Tasks 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12
  - **Blocked By**: None

  **References**:

  **Pattern References**:
  - `src/pipeline.py` — File to rename. Contains `PipelineWorker` class.
  - `src/main.py` — Imports `PipelineWorker` from `src.pipeline`. Must update.

  **Test References**:
  - `tests/test_pipeline.py` — Imports from `src.pipeline`. Must update import path.

  **WHY Each Reference Matters**:
  - `pipeline.py`: The rename target — must understand all exports used externally
  - `main.py`: Primary consumer — import must be updated
  - `test_pipeline.py`: Test consumer — import must be updated

  **Acceptance Criteria**:
  - [x] `ls src/pipeline.py` → file does NOT exist (renamed away)
  - [x] `ls src/pipeline_legacy.py` → file exists
  - [x] `from src.pipeline_legacy import PipelineWorker` → works (python -c)
  - [x] `ruff check . && mypy . && pytest -x` → ALL PASS

  **QA Scenarios**:

  ```
  Scenario: Renamed module imports correctly
    Tool: Bash
    Preconditions: Rename completed
    Steps:
      1. Run `python -c "from src.pipeline_legacy import PipelineWorker; print('OK')"`
      2. Assert output is "OK"
      3. Run `python -c "from src.pipeline import PipelineWorker"` — should fail with ImportError
    Expected Result: New path works, old path fails
    Failure Indicators: ImportError on new path, or old path still works
    Evidence: .sisyphus/evidence/task-0-rename-import.txt

  Scenario: Full test suite passes after rename
    Tool: Bash
    Preconditions: All imports updated
    Steps:
      1. Run `ruff check . && mypy . && pytest -x --tb=short`
      2. Assert exit code 0
    Expected Result: Zero errors, all tests pass
    Failure Indicators: Any import error or test failure
    Evidence: .sisyphus/evidence/task-0-full-suite.txt
  ```

  **Commit**: YES
  - Message: `refactor(pipeline): rename pipeline.py to pipeline_legacy.py for package creation`
  - Files: `src/pipeline_legacy.py` (renamed from `src/pipeline.py`), `src/main.py`, `tests/test_pipeline.py`
  - Pre-commit: `ruff check . && mypy . && pytest -x`

### Wave 1: Foundation (Tasks 1-4)

- [x] 1. Pipeline Types & Data Models

  **What to do**:
  - RED: Write tests for all new data types: `SpeechSegment` (audio ndarray + metadata), `ASRResult` (text + timing + segment ref), `TranslationResult` (translation + explanation + ASRResult ref), `PipelineStageMetrics` (stage name, start/end time, duration). Test serialization, equality, field access.
  - GREEN: Create `src/pipeline/types.py` (new package: add `src/pipeline/__init__.py`). Define frozen dataclasses for each type. `SpeechSegment` holds: `audio: np.ndarray`, `sample_rate: int`, `timestamp: float`, `segment_id: str` (uuid4). `ASRResult` holds: `text: str`, `segment_id: str`, `elapsed_ms: float`. `TranslationResult` holds: `translation: str | None`, `explanation: str | None`, `segment_id: str`, `elapsed_ms: float`. Use `__slots__` for memory efficiency.
  - REFACTOR: Ensure type aliases are clean, add `__all__` exports.

  **Must NOT do**:
  - No abstract base classes
  - No Pydantic models (stdlib dataclasses only)
  - Do not modify any existing files yet

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Simple dataclass definitions, no complex logic
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - `playwright`: No UI work
    - `git-master`: Simple single-file commit

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 2, 3, 4)
  - **Blocks**: Tasks 2, 3, 4, 5, 6, 7, 8, 9, 10
  - **Blocked By**: None (can start immediately)

  **References**:

  **Pattern References**:
  - `src/db/models.py` — Existing dataclass patterns in the project (SentenceRecord, VocabRecord). Follow same style: frozen dataclasses with type annotations.
  - `src/analysis/pipeline.py:AnalysisResult` — Existing result dataclass pattern showing how pipeline stages return typed results.

  **API/Type References**:
  - `src/vad/silero.py:AudioSegment` (line ~24) — Existing AudioSegment in VAD module (from `src/db/models.py`). The NEW `SpeechSegment` in pipeline types should wrap or convert from this. Check AudioSegment's fields (it may have `audio`, `start`, `end`, etc.).

  **Test References**:
  - `tests/test_db_repository.py (for dataclass patterns)` — Existing dataclass tests showing pytest patterns used in this project.

  **External References**: None needed.

  **WHY Each Reference Matters**:
  - `db/models.py`: Copy the exact frozen dataclass + `__slots__` pattern to stay consistent
  - `analysis/pipeline.py`: Shows how result types flow between stages — new types must fit same paradigm
  - `vad/silero.py:AudioSegment`: Must decide whether new SpeechSegment wraps or replaces this existing type

  **Acceptance Criteria**:
  - [x] Test file created: `tests/test_pipeline_types.py`
  - [x] `pytest tests/test_pipeline_types.py` → PASS (all type construction, field access, frozen immutability tests)
  - [x] `mypy src/pipeline/types.py` → 0 errors
  - [x] `ruff check src/pipeline/types.py` → 0 issues

  **QA Scenarios**:

  ```
  Scenario: All pipeline types construct correctly with valid data
    Tool: Bash (pytest)
    Preconditions: Virtual env active, pytest installed
    Steps:
      1. Run `python -m pytest tests/test_pipeline_types.py -v`
      2. Verify all test functions pass
      3. Verify test count >= 8 (2 per type minimum)
    Expected Result: All tests PASS, 0 failures, 0 errors
    Failure Indicators: Any FAILED or ERROR in output
    Evidence: .sisyphus/evidence/task-1-types-pytest.txt

  Scenario: Frozen dataclasses reject mutation
    Tool: Bash (pytest)
    Preconditions: test_pipeline_types.py includes mutation test
    Steps:
      1. Run `python -m pytest tests/test_pipeline_types.py::test_speech_segment_immutable -v`
      2. Verify FrozenInstanceError is raised on attribute assignment
    Expected Result: Test passes confirming immutability
    Failure Indicators: No FrozenInstanceError raised
    Evidence: .sisyphus/evidence/task-1-frozen-test.txt
  ```

  **Commit**: YES
  - Message: `refactor(pipeline): add pipeline types and data models`
  - Files: `src/pipeline/__init__.py`, `src/pipeline/types.py`, `tests/test_pipeline_types.py`
  - Pre-commit: `pytest tests/test_pipeline_types.py -x`

- [x] 2. Performance Instrumentation Utility

  **What to do**:
  - RED: Write tests for a `StageTimer` context manager that records stage name, start/end time, and elapsed_ms. Test that it measures real wall-clock time (within 10ms tolerance). Test `PipelineMetrics` class that aggregates timers and exposes `to_dict()` for logging.
  - GREEN: Create `src/pipeline/perf.py`. `StageTimer` uses `time.perf_counter_ns()`. `PipelineMetrics` stores a list of `StageTimerResult(stage: str, elapsed_ms: float)` and provides `log_summary()` using stdlib logging with lazy formatting. Add a `@timed_stage("stage_name")` decorator variant for convenience.
  - REFACTOR: Ensure zero overhead when not actively timing (no allocations in hot path).

  **Must NOT do**:
  - No third-party profiling libraries
  - No global state / singletons
  - No file I/O in the timer itself (logging only)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Small utility module with simple context manager pattern
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 3, 4)
  - **Blocks**: Tasks 5, 6, 8, 10, 14
  - **Blocked By**: Task 1 (uses PipelineStageMetrics type)

  **References**:

  **Pattern References**:
  - `src/analysis/pipeline.py:34-42` — Existing `time.perf_counter()` usage for preprocessing timing. The new utility should replace this ad-hoc pattern with a reusable context manager.

  **API/Type References**:
  - `src/pipeline/types.py:PipelineStageMetrics` — The type this utility populates (created in Task 1).

  **Test References**:
  - `tests/` — Follow existing pytest patterns (no unittest.TestCase).

  **External References**: None.

  **WHY Each Reference Matters**:
  - `analysis/pipeline.py`: Shows what ad-hoc timing looks like now — the new utility must be strictly better (less boilerplate, typed results)
  - `pipeline/types.py`: Timer results must match this type exactly

  **Acceptance Criteria**:
  - [x] Test file: `tests/test_perf.py`
  - [x] `pytest tests/test_perf.py` → PASS
  - [x] `mypy src/pipeline/perf.py` → 0 errors

  **QA Scenarios**:

  ```
  Scenario: StageTimer accurately measures elapsed time
    Tool: Bash (pytest)
    Preconditions: Task 1 complete (types available)
    Steps:
      1. Run `python -m pytest tests/test_perf.py::test_stage_timer_accuracy -v`
      2. Test sleeps 100ms inside timer, asserts elapsed_ms in range [90, 150]
    Expected Result: PASS — timer within 10ms tolerance
    Failure Indicators: elapsed_ms outside [90, 150] range
    Evidence: .sisyphus/evidence/task-2-timer-accuracy.txt

  Scenario: PipelineMetrics aggregates multiple stages
    Tool: Bash (pytest)
    Preconditions: tests include multi-stage aggregation test
    Steps:
      1. Run `python -m pytest tests/test_perf.py -v`
      2. Verify all tests pass including to_dict() and log_summary()
    Expected Result: All tests PASS
    Failure Indicators: Any assertion failure
    Evidence: .sisyphus/evidence/task-2-metrics-test.txt
  ```

  **Commit**: YES
  - Message: `feat(pipeline): add performance instrumentation utility`
  - Files: `src/pipeline/perf.py`, `tests/test_perf.py`
  - Pre-commit: `pytest tests/test_perf.py -x`

- [x] 3. VAD Optimization — ONNX Mode + Ring Buffer

  **What to do**:
  - RED: Write tests for optimized SileroVAD: (a) ONNX model loads successfully, (b) process_chunk uses ring buffer (no np.concatenate), (c) no redundant `.float()` on already-float32 audio, (d) speech detection still works correctly (same segments as before), (e) process_chunk completes within 5ms for a 512-sample block.
  - GREEN: Modify `src/vad/silero.py`:
    1. Change `onnx=False` → `onnx=True` in `torch.hub.load()` call (line ~79). Verify Silero VAD supports ONNX by checking the API first — if `onnx=True` doesn't work, keep PyTorch but still apply buffer optimizations.
    2. Replace `np.concatenate([self._pending, audio])` (line 107) with a `collections.deque`-based ring buffer or pre-allocated numpy array. Append chunks O(1), concatenate only when needed for VAD block processing.
    3. Remove redundant `.float()` in `_process_vad_block` (line 134) — audio is already float32.
    4. Remove unnecessary `.copy()` in `_pre_buffer` append (line 182) — slice already creates new array.
    5. Minimize `audio_buffer` copies during speech: store references not copies where safe.
  - REFACTOR: Verify backward compatibility — same `process_chunk()` API, same `AudioSegment` output format.

  **Must NOT do**:
  - Don't change the VAD public API (process_chunk signature and return type)
  - Don't change VAD config parameters (threshold, min_silence_ms, etc.)
  - Don't move VAD to GPU (keep on CPU)
  - Don't add ONNX Runtime as a new dependency if Silero's onnx=True handles it internally

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Performance-critical optimization requiring careful measurement and backward compatibility
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - `playwright`: No UI work

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2, 4)
  - **Blocks**: Task 5
  - **Blocked By**: Task 1 (pipeline types for AudioSegment compatibility check)

  **References**:

  **Pattern References**:
  - `src/vad/silero.py` — ENTIRE FILE is the modification target. Key lines: 79 (model load, onnx flag), 107 (np.concatenate hotspot), 134 (.float() redundancy), 151/174 (audio_buffer concatenation), 182 (_pre_buffer copy).

  **API/Type References**:
  - `src/vad/silero.py:AudioSegment` — Existing dataclass from `src/db/models.py`. Output format must not change.
  - `src/vad/silero.py:process_chunk()` — Public API: `(audio: np.ndarray) -> list[AudioSegment]`. Signature must not change.

  **Test References**:
  - `tests/test_silero_vad.py` — Existing VAD tests. New tests must coexist, and existing tests must still pass.

  **External References**:
  - Silero VAD repo: `snakers4/silero-vad` — Check if `onnx=True` parameter is still supported in current version. If ONNX mode requires `onnxruntime` package, verify it's installable.

  **WHY Each Reference Matters**:
  - `silero.py` full file: Every optimization target is in this file — executor must read it completely
  - `AudioSegment` type: Output contract — breaking this breaks the entire downstream pipeline
  - `tests/test_silero_vad.py`: Regression safety net — all existing tests must still pass after optimization
  - Silero repo: ONNX flag compatibility varies by version — must verify before assuming it works

  **Acceptance Criteria**:
  - [x] `pytest tests/test_silero_vad.py` → ALL existing tests still pass (regression)
  - [x] New perf test: `process_chunk` < 5ms per 512-sample block
  - [x] `grep -n "np.concatenate.*_pending" src/vad/silero.py` → 0 matches (hotspot eliminated)
  - [x] `grep -n "\.float()" src/vad/silero.py` → 0 matches (redundancy removed)
  - [x] `mypy src/vad/silero.py` → 0 errors

  **QA Scenarios**:

  ```
  Scenario: VAD produces identical segments after optimization
    Tool: Bash (pytest)
    Preconditions: Test audio fixture available
    Steps:
      1. Run `python -m pytest tests/test_silero_vad.py -v`
      2. Verify all existing test cases pass unchanged
      3. Specifically check segment start/end times match expected values
    Expected Result: All tests PASS with identical segment boundaries
    Failure Indicators: Any segment timing difference or missing/extra segments
    Evidence: .sisyphus/evidence/task-3-vad-regression.txt

  Scenario: Buffer hotspot eliminated
    Tool: Bash (grep)
    Preconditions: silero.py modified
    Steps:
      1. Run `grep -n "np.concatenate.*_pending" src/vad/silero.py`
      2. Run `grep -n "\.float()" src/vad/silero.py`
      3. Both should return empty (no matches)
    Expected Result: Zero matches for both patterns
    Failure Indicators: Any match found
    Evidence: .sisyphus/evidence/task-3-hotspot-check.txt

  Scenario: process_chunk performance within threshold
    Tool: Bash (pytest)
    Preconditions: Perf test written
    Steps:
      1. Run `python -m pytest tests/test_silero_vad.py::test_process_chunk_performance -v`
      2. Test feeds 1000 chunks, asserts mean time < 5ms per chunk
    Expected Result: Mean < 5ms, no chunk > 10ms
    Failure Indicators: Mean >= 5ms or any chunk > 10ms
    Evidence: .sisyphus/evidence/task-3-vad-perf.txt
  ```

  **Commit**: YES
  - Message: `perf(vad): optimize Silero to ONNX with ring buffer`
  - Files: `src/vad/silero.py`, `tests/test_silero_vad.py`
  - Pre-commit: `pytest tests/test_silero_vad.py -x`

- [x] 4. DB Repository Two-Phase Write

  **What to do**:
  - RED: Write tests for: (a) `insert_partial(asr_result)` inserts row with `chinese_translation=NULL, explanation=NULL`, returns row_id. (b) `update_translation(row_id, translation, explanation)` fills in the NULL fields. (c) Verify row integrity after both phases. (d) `update_translation` on non-existent row_id raises or returns False.
  - GREEN: Modify `src/db/repository.py` to add `insert_partial()` and `update_translation()` methods. Keep existing `insert_sentence()` working (backward compat). Ensure SQLite WAL mode is enabled for concurrent read/write safety from different threads: `PRAGMA journal_mode=WAL` on connection open.
  - REFACTOR: Add type annotations, verify thread-safety documentation.

  **Must NOT do**:
  - Don't change existing `insert_sentence()` signature or behavior
  - Don't switch to async DB (SQLite sync is fast enough)
  - Don't add an ORM

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Small SQL changes, straightforward test patterns
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2, 3)
  - **Blocks**: Task 10
  - **Blocked By**: Task 1 (uses ASRResult, TranslationResult types)

  **References**:

  **Pattern References**:
  - `src/db/repository.py` — Entire file is modification target. Shows existing `insert_sentence()`, connection handling, SQL patterns.
  - `src/db/schema.py` — Database schema. Check if `chinese_translation` and `explanation` columns already allow NULL.

  **API/Type References**:
  - `src/pipeline/types.py:ASRResult` — Input type for `insert_partial()`
  - `src/pipeline/types.py:TranslationResult` — Input type for `update_translation()`
  - `src/db/models.py:SentenceRecord` — Existing model. New methods must produce valid SentenceRecords.

  **Test References**:
  - `tests/test_db_repository.py` — Existing DB tests. Follow same patterns (in-memory SQLite fixtures).

  **WHY Each Reference Matters**:
  - `repository.py`: Must extend without breaking existing methods
  - `schema.py`: Need to verify NULL constraints on translation columns
  - `models.py`: Return types must match existing conventions

  **Acceptance Criteria**:
  - [x] `pytest tests/test_db_repository.py` → ALL tests pass (existing + new)
  - [x] New test: insert_partial creates row with NULL translation
  - [x] New test: update_translation fills in translation fields
  - [x] `mypy src/db/repository.py` → 0 errors

  **QA Scenarios**:

  ```
  Scenario: Two-phase write produces complete record
    Tool: Bash (pytest)
    Preconditions: In-memory SQLite test fixture
    Steps:
      1. Run `python -m pytest tests/test_db_repository.py::test_two_phase_write -v`
      2. Test calls insert_partial → verifies NULL translation → calls update_translation → verifies complete record
    Expected Result: PASS — record complete after both phases
    Failure Indicators: NULL translation after update, or missing row after insert
    Evidence: .sisyphus/evidence/task-4-two-phase.txt

  Scenario: Existing insert_sentence still works (regression)
    Tool: Bash (pytest)
    Preconditions: Existing test fixtures
    Steps:
      1. Run `python -m pytest tests/test_db_repository.py -v`
      2. Verify ALL existing tests pass unchanged
    Expected Result: Zero regressions
    Failure Indicators: Any existing test failure
    Evidence: .sisyphus/evidence/task-4-regression.txt
  ```

  **Commit**: YES
  - Message: `feat(db): add two-phase write for progressive display`
  - Files: `src/db/repository.py`, `tests/test_db_repository.py`
  - Pre-commit: `pytest tests/test_db_repository.py -x`

### Wave 2: Worker Threads (Tasks 5-9)

- [x] 5. VAD Worker Thread

  **What to do**:
  - RED: Write tests for `VADWorker(QThread)`: (a) constructor accepts audio_queue (input) and segment_queue (output), (b) run() dequeues audio chunks and feeds to SileroVAD.process_chunk(), (c) when AudioSegment detected, converts to pipeline SpeechSegment type and puts on segment_queue, (d) stop() cleanly terminates within 2s, (e) handles empty audio_queue gracefully (no crash on timeout), (f) emits error_occurred signal on exception instead of crashing. Test with mock VAD and mock queues.
  - GREEN: Create `src/pipeline/vad_worker.py`. QThread subclass with:
    - `__init__(audio_queue, segment_queue, config)` — store refs, no processing in init
    - `run()` — loop: `chunk = audio_queue.get(timeout=0.1)`, `segments = vad.process_chunk(chunk)`, for each segment: `segment_queue.put(pipeline_segment)`. Wrap in try/except, emit `error_occurred` signal on failure.
    - `stop()` — set `_running = False`, call `self.quit()`, `self.wait(2000)`
    - Use `StageTimer` from Task 2 to time each VAD call
    - segment_queue maxsize=20 (~20 segments, generous buffer since ASR is faster than speech)
  - REFACTOR: Ensure clean resource management, VAD reset on stop.

  **Must NOT do**:
  - Don't instantiate SileroVAD inside the worker (inject it for testability)
  - Don't block on segment_queue.put() — use put_nowait() with drop + warning if full
  - Don't access audio_queue from multiple threads (only this worker reads it)

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Threading correctness is critical, needs careful shutdown/error handling
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 6, 7, 8, 9)
  - **Blocks**: Task 10
  - **Blocked By**: Tasks 1, 2, 3

  **References**:

  **Pattern References**:
  - `src/pipeline.py:PipelineWorker` — Existing QThread pattern. Shows `run()` loop structure, `_running` flag, `stop()` method, signal definitions. New worker must follow same conventions but with single-responsibility.
  - `src/pipeline.py:92-110` — The VAD portion of the current run() loop. This is exactly the logic being extracted into the VAD worker.

  **API/Type References**:
  - `src/vad/silero.py:SileroVAD` — VAD instance to inject. Key method: `process_chunk(audio: np.ndarray) -> list[AudioSegment]`
  - `src/pipeline/types.py:SpeechSegment` — Output type (from Task 1)
  - `src/pipeline/perf.py:StageTimer` — Instrumentation (from Task 2)

  **Test References**:
  - `tests/test_pipeline.py` — Existing pipeline tests if any. Check for QThread testing patterns.

  **WHY Each Reference Matters**:
  - `pipeline.py:PipelineWorker`: Shows the exact QThread lifecycle pattern (start/stop/signals) to replicate
  - `pipeline.py:92-110`: This is the code being extracted — must replicate behavior exactly
  - `silero.py:SileroVAD`: Must understand the dependency API to mock correctly in tests

  **Acceptance Criteria**:
  - [x] `pytest tests/test_vad_worker.py` → PASS (all unit tests)
  - [x] Test: worker processes 100 chunks without crash
  - [x] Test: worker stops cleanly within 2s
  - [x] Test: worker emits error_occurred on VAD exception
  - [x] Test: full segment_queue triggers drop + warning (not deadlock)
  - [x] `mypy src/pipeline/vad_worker.py` → 0 errors

  **QA Scenarios**:

  ```
  Scenario: VAD worker processes audio chunks and produces segments
    Tool: Bash (pytest)
    Preconditions: Mock VAD that returns a segment every 50 chunks
    Steps:
      1. Run `python -m pytest tests/test_vad_worker.py::test_produces_segments -v`
      2. Feed 200 mock chunks into audio_queue
      3. Assert segment_queue receives exactly 4 segments
      4. Assert each segment has valid audio data and metadata
    Expected Result: 4 segments produced, all with correct fields
    Failure Indicators: Wrong segment count, missing fields, or timeout
    Evidence: .sisyphus/evidence/task-5-vad-worker-segments.txt

  Scenario: VAD worker shuts down cleanly
    Tool: Bash (pytest)
    Preconditions: Worker is running and processing
    Steps:
      1. Run `python -m pytest tests/test_vad_worker.py::test_clean_shutdown -v`
      2. Start worker, feed some chunks, call stop()
      3. Assert thread terminates within 2 seconds
      4. Assert no orphan threads
    Expected Result: Worker stops within 2s, isRunning() == False
    Failure Indicators: Timeout waiting for thread, or isRunning() still True
    Evidence: .sisyphus/evidence/task-5-vad-worker-shutdown.txt

  Scenario: Full segment_queue doesn't deadlock worker
    Tool: Bash (pytest)
    Preconditions: segment_queue maxsize=1, mock VAD returns segments rapidly
    Steps:
      1. Run `python -m pytest tests/test_vad_worker.py::test_full_queue_no_deadlock -v`
      2. Pre-fill segment_queue to capacity
      3. Feed more chunks that produce segments
      4. Assert worker logs warning but continues processing
    Expected Result: Worker continues without deadlock, warning logged
    Failure Indicators: Worker hangs, test times out
    Evidence: .sisyphus/evidence/task-5-vad-worker-backpressure.txt
  ```

  **Commit**: YES
  - Message: `feat(pipeline): add VAD worker thread`
  - Files: `src/pipeline/vad_worker.py`, `tests/test_vad_worker.py`
  - Pre-commit: `pytest tests/test_vad_worker.py -x`

- [x] 6. ASR Batch Transcription & ASR Worker

  **What to do**:
  - RED: Write tests for: (a) `QwenASR.transcribe_batch(segments: list[SpeechSegment]) -> list[ASRResult]` — batch API, (b) `transcribe_batch` uses `torch.inference_mode()` context, (c) `ASRWorker(QThread)` that pulls segments from segment_queue, batches up to 4 (or flushes after 500ms timeout), calls transcribe_batch, runs preprocessing (fugashi), emits asr_ready signal per result, puts ASRResult on text_queue, (d) worker handles empty segment after transcribe (filters blank text), (e) shutdown test.
  - GREEN:
    1. Modify `src/asr/qwen_asr.py`: Add `transcribe_batch()` method that wraps `self._model.transcribe()` with a list of `(audio, sample_rate)` tuples. Wrap in `torch.inference_mode()`. Return list of ASRResult.
    2. Create `src/pipeline/asr_worker.py`: QThread subclass with:
       - `__init__(segment_queue, text_queue, asr_model, preprocessing_pipeline, config)`
       - `run()` loop: collect segments from queue (up to batch_size=4 or 500ms flush timeout), call `transcribe_batch()`, for each result: run preprocessing, put on text_queue, emit `asr_ready(ASRResult)` signal for immediate UI display
       - Instrument with StageTimer for both ASR and preprocessing stages
       - text_queue maxsize=50 (sentences buffer; LLM is slow so this needs more headroom)
  - REFACTOR: Ensure transcribe_batch gracefully handles mixed-length segments.

  **Must NOT do**:
  - Don't remove existing `transcribe()` method (keep backward compat)
  - Don't change ASR model or loading parameters
  - Don't move preprocessing to a separate thread (keep in ASR worker per Metis recommendation)

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: GPU inference batching is tricky, needs careful testing with mock model
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 5, 7, 8, 9)
  - **Blocks**: Task 10
  - **Blocked By**: Tasks 1, 2

  **References**:

  **Pattern References**:
  - `src/asr/qwen_asr.py` — Entire file is modification target. Current `transcribe()` at line 52-74 processes single segment. New `transcribe_batch()` extends this to list input.
  - `src/pipeline.py:114-131` — Current sequential segment loop. This is the logic being extracted: ASR transcribe + preprocessing per segment.
  - `src/analysis/pipeline.py:PreprocessingPipeline` — The preprocessing step to run after ASR in this worker. Key method: `process(text) -> AnalysisResult`.

  **API/Type References**:
  - `src/pipeline/types.py:SpeechSegment` — Input type from segment_queue
  - `src/pipeline/types.py:ASRResult` — Output type to text_queue
  - `src/pipeline/perf.py:StageTimer` — For instrumentation
  - Qwen3-ASR model: `self._model.transcribe()` accepts `list[tuple[np.ndarray, int]]` for batching

  **Test References**:
  - `tests/test_qwen_asr.py` — Existing ASR tests. Must still pass after adding batch method.

  **External References**:
  - Qwen3-ASR package documentation — Verify batch transcription API signature. The model was loaded with `max_inference_batch_size=4`, confirming batch support.

  **WHY Each Reference Matters**:
  - `qwen_asr.py`: Direct modification target — must understand current transcribe() to extend it
  - `pipeline.py:114-131`: The exact code being refactored — batch what was sequential
  - `analysis/pipeline.py`: Preprocessing runs inside this worker — must understand its API
  - Qwen3-ASR docs: Batch API signature varies — must verify list format before implementing

  **Acceptance Criteria**:
  - [x] `pytest tests/test_qwen_asr.py` → ALL existing tests pass (regression)
  - [x] `pytest tests/test_asr_worker.py` → PASS (new worker tests)
  - [x] Test: batch of 4 segments → 4 ASRResults
  - [x] Test: 500ms flush timeout fires when < batch_size segments available
  - [x] Test: blank transcription results filtered (not emitted)
  - [x] `grep -n "inference_mode" src/asr/qwen_asr.py` → at least 1 match
  - [x] `mypy src/asr/qwen_asr.py src/pipeline/asr_worker.py` → 0 errors

  **QA Scenarios**:

  ```
  Scenario: Batch transcription processes multiple segments
    Tool: Bash (pytest)
    Preconditions: Mock ASR model that returns "テスト{i}" for segment i
    Steps:
      1. Run `python -m pytest tests/test_asr_worker.py::test_batch_transcription -v`
      2. Put 4 segments on segment_queue
      3. Assert text_queue receives 4 ASRResults within 2s
      4. Assert each result has non-empty text and valid segment_id
    Expected Result: 4 results, all with correct text and metadata
    Failure Indicators: Wrong count, empty text, or timeout
    Evidence: .sisyphus/evidence/task-6-batch-transcription.txt

  Scenario: Flush timeout fires for partial batch
    Tool: Bash (pytest)
    Preconditions: batch_size=4, flush_timeout=500ms
    Steps:
      1. Run `python -m pytest tests/test_asr_worker.py::test_flush_timeout -v`
      2. Put 2 segments (less than batch_size), wait
      3. Assert both segments processed within 700ms (500ms timeout + processing)
    Expected Result: 2 results produced despite incomplete batch
    Failure Indicators: Results not produced, or produced only after 4th segment
    Evidence: .sisyphus/evidence/task-6-flush-timeout.txt

  Scenario: Blank transcriptions filtered out
    Tool: Bash (pytest)
    Preconditions: Mock ASR returns "" for one segment
    Steps:
      1. Run `python -m pytest tests/test_asr_worker.py::test_blank_filter -v`
      2. Feed 3 segments, mock returns ["テスト", "", "日本語"]
      3. Assert text_queue receives exactly 2 results
    Expected Result: 2 non-blank results
    Failure Indicators: 3 results (blank not filtered) or 1 result
    Evidence: .sisyphus/evidence/task-6-blank-filter.txt
  ```

  **Commit**: YES
  - Message: `feat(asr): add batch transcription and ASR worker`
  - Files: `src/asr/qwen_asr.py`, `src/pipeline/asr_worker.py`, `tests/test_qwen_asr.py`, `tests/test_asr_worker.py`
  - Pre-commit: `pytest tests/test_asr_worker.py tests/test_qwen_asr.py -x`

- [x] 7. Async LLM Client — httpx Streaming + LRU Cache

  **What to do**:
  - RED: Write tests for new `AsyncOllamaClient`: (a) `async translate(text) -> tuple[str|None, str|None]` using httpx.AsyncClient, (b) streaming mode: TTFT < response arrives incrementally, (c) LRU cache: identical text input returns cached result without HTTP call, (d) connection pooling: reuses connections (httpx default), (e) timeout reduced to 15s (was 30s), (f) proper error handling: raises `LLMTimeoutError` on timeout, `LLMUnavailableError` on connection failure (using existing custom exceptions), (g) health_check still works.
  - GREEN: Rewrite `src/llm/ollama_client.py`:
    1. Replace `requests` with `httpx.AsyncClient` (persistent connection pool)
    2. Use `stream=True` — yield partial responses, concatenate final result
    3. Add `@functools.lru_cache(maxsize=256)` on a sync wrapper or use a dict cache keyed by input text hash
    4. Reduce `num_predict` from 512 → 200 (translations are short)
    5. Reduce timeout from 30s → 15s
    6. Raise `LLMTimeoutError` / `LLMUnavailableError` (from `src/exceptions.py`) instead of silently returning None
    7. Keep a synchronous `translate()` wrapper that runs the async version (for backward compat during migration)
  - REFACTOR: Ensure connection cleanup on close(), add `__aenter__`/`__aexit__` support.

  **Must NOT do**:
  - Don't change the Ollama model (keep qwen3.5:4b)
  - Don't change the translation/explanation prompt templates
  - Don't add retry logic (keep simple — fail fast)
  - Don't remove the synchronous API entirely (needed until orchestrator migration)

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Async HTTP with streaming requires careful implementation and testing
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 5, 6, 8, 9)
  - **Blocks**: Task 8
  - **Blocked By**: Task 1

  **References**:

  **Pattern References**:
  - `src/llm/ollama_client.py` — ENTIRE FILE is rewrite target. Current sync implementation with requests. Keep same translate() signature for backward compat.
  - `src/exceptions.py` — `LLMTimeoutError`, `LLMUnavailableError` already defined but unused. These must now be raised.

  **API/Type References**:
  - `src/config.py:AppConfig` — `ollama_url`, `ollama_model`, `ollama_timeout_sec` fields used by client
  - `src/pipeline/types.py:TranslationResult` — Output type for LLM results

  **Test References**:
  - `tests/test_ollama_client.py` — Existing tests. Must update for async + ensure backward compat wrapper still passes.

  **External References**:
  - httpx docs: `https://www.python-httpx.org/async/` — AsyncClient API, streaming responses
  - Ollama API: `https://github.com/ollama/ollama/blob/main/docs/api.md#generate-a-completion` — streaming response format (newline-delimited JSON)

  **WHY Each Reference Matters**:
  - `ollama_client.py`: Rewrite target — must preserve translate() signature while adding async
  - `exceptions.py`: These exception classes exist but are currently dead code — finally put them to use
  - httpx docs: Streaming async response handling is nuanced — must follow correct patterns
  - Ollama API docs: Streaming format (each line is JSON with `response` field) must be parsed correctly

  **Acceptance Criteria**:
  - [x] `pytest tests/test_ollama_client.py` → PASS (updated tests)
  - [x] Test: async translate returns (translation, explanation) tuple
  - [x] Test: LRU cache hit skips HTTP call (mock verifies 1 call for 2 identical inputs)
  - [x] Test: LLMTimeoutError raised on timeout (not silent None)
  - [x] Test: LLMUnavailableError raised on connection failure
  - [x] `grep -n "requests.post" src/llm/ollama_client.py` → 0 matches (fully migrated to httpx)
  - [x] `mypy src/llm/ollama_client.py` → 0 errors

  **QA Scenarios**:

  ```
  Scenario: Async translate returns correct results
    Tool: Bash (pytest)
    Preconditions: Mock httpx server returning Ollama-format streaming JSON
    Steps:
      1. Run `python -m pytest tests/test_ollama_client.py::test_async_translate -v`
      2. Mock returns streaming chunks: {"response":"翻","done":false}, {"response":"译","done":false}, {"response":"","done":true}
      3. Assert translate() returns complete concatenated translation
    Expected Result: ("翻译", explanation_text) tuple
    Failure Indicators: Partial result, None, or exception
    Evidence: .sisyphus/evidence/task-7-async-translate.txt

  Scenario: LRU cache prevents duplicate HTTP calls
    Tool: Bash (pytest)
    Preconditions: Mock httpx client with call counter
    Steps:
      1. Run `python -m pytest tests/test_ollama_client.py::test_cache_hit -v`
      2. Call translate("同じテキスト") twice
      3. Assert mock HTTP was called exactly once
      4. Assert both calls return identical results
    Expected Result: 1 HTTP call, 2 identical results
    Failure Indicators: 2 HTTP calls, or different results
    Evidence: .sisyphus/evidence/task-7-cache-hit.txt

  Scenario: Timeout raises LLMTimeoutError
    Tool: Bash (pytest)
    Preconditions: Mock server with 20s delay, client timeout=15s
    Steps:
      1. Run `python -m pytest tests/test_ollama_client.py::test_timeout_raises -v`
      2. Assert LLMTimeoutError is raised (not None returned)
    Expected Result: LLMTimeoutError raised within 16s
    Failure Indicators: (None, None) returned, or wrong exception type
    Evidence: .sisyphus/evidence/task-7-timeout.txt
  ```

  **Commit**: YES
  - Message: `feat(llm): async httpx client with streaming and cache`
  - Files: `src/llm/ollama_client.py`, `tests/test_ollama_client.py`
  - Pre-commit: `pytest tests/test_ollama_client.py -x`

- [x] 8. LLM Worker Thread

  **What to do**:
  - RED: Write tests for `LLMWorker(QThread)`: (a) pulls ASRResult from text_queue, calls async translate, puts TranslationResult on result_queue, (b) emits `translation_ready(TranslationResult)` signal, (c) handles LLMTimeoutError gracefully — emits result with translation=None, (d) handles Ollama unavailable — logs warning, continues processing next item, (e) runs asyncio event loop internally for httpx async calls, (f) handles DB update_translation via two-phase write, (g) shutdown within 2s.
  - GREEN: Create `src/pipeline/llm_worker.py`: QThread subclass with:
    - `__init__(text_queue, result_queue, llm_client, db_repo, config)` — store refs
    - `run()` — create asyncio event loop, run `_process_loop()` coroutine. Loop: `asr_result = text_queue.get(timeout=0.5)`, call `await llm_client.translate_async(asr_result.text)`, build TranslationResult, call `db_repo.update_translation(row_id, ...)`, put on result_queue, emit `translation_ready` signal
    - Use `StageTimer` for LLM call duration
    - result_queue maxsize=50
    - Graceful degradation: if LLM fails, emit TranslationResult with translation=None (UI handles this)
  - REFACTOR: Ensure event loop cleanup on stop.

  **Must NOT do**:
  - Don't block on LLM failures — skip and continue
  - Don't retry LLM calls (fail fast per guardrail)
  - Don't share AsyncOllamaClient with other threads (each worker gets own client)

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Mixing asyncio with QThread requires careful lifecycle management
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 5, 6, 7, 9)
  - **Blocks**: Task 10
  - **Blocked By**: Tasks 1, 2, 4, 7

  **References**:

  **Pattern References**:
  - `src/pipeline.py:131-145` — Current LLM call + DB write logic being extracted. Shows translate() call, DB insert, signal emission.
  - `src/pipeline/vad_worker.py` (Task 5) — Sibling worker pattern: QThread + queue + signal.

  **API/Type References**:
  - `src/llm/ollama_client.py:AsyncOllamaClient` (from Task 7) — `async translate(text) -> tuple[str|None, str|None]`
  - `src/db/repository.py:update_translation()` (from Task 4) — `update_translation(row_id, translation, explanation)`
  - `src/pipeline/types.py:ASRResult, TranslationResult` — Input/output types
  - `src/exceptions.py:LLMTimeoutError, LLMUnavailableError` — Exceptions to catch

  **Test References**:
  - `tests/test_vad_worker.py` (from Task 5) — Sibling test pattern for QThread workers with mocks.

  **WHY Each Reference Matters**:
  - `pipeline.py:131-145`: Exact logic being refactored — LLM call sequence and error handling
  - `vad_worker.py`: Consistent worker pattern — reuse same QThread lifecycle approach
  - `AsyncOllamaClient`: Must understand async API to drive from within QThread's asyncio loop

  **Acceptance Criteria**:
  - [x] `pytest tests/test_llm_worker.py` → PASS
  - [x] Test: ASRResult in → TranslationResult out within 3s (mock LLM)
  - [x] Test: LLMTimeoutError → TranslationResult with translation=None emitted
  - [x] Test: Ollama unavailable → worker continues processing next item
  - [x] Test: DB update_translation called with correct row_id
  - [x] Test: shutdown within 2s
  - [x] `mypy src/pipeline/llm_worker.py` → 0 errors

  **QA Scenarios**:

  ```
  Scenario: LLM worker processes ASR results into translations
    Tool: Bash (pytest)
    Preconditions: Mock async LLM client returning "Translation"/"Explanation"
    Steps:
      1. Run `python -m pytest tests/test_llm_worker.py::test_translate_flow -v`
      2. Put ASRResult("テスト文") on text_queue
      3. Assert result_queue receives TranslationResult within 2s
      4. Assert translation_ready signal was emitted
      5. Assert DB update_translation was called
    Expected Result: Complete flow: queue→LLM→DB→signal→result_queue
    Failure Indicators: Missing result, signal not emitted, DB not updated
    Evidence: .sisyphus/evidence/task-8-llm-flow.txt

  Scenario: LLM timeout produces graceful degradation
    Tool: Bash (pytest)
    Preconditions: Mock LLM that raises LLMTimeoutError
    Steps:
      1. Run `python -m pytest tests/test_llm_worker.py::test_timeout_degradation -v`
      2. Put ASRResult on text_queue
      3. Assert result_queue receives TranslationResult with translation=None
      4. Assert worker continues (not crashed), put another ASRResult
      5. Assert second result also processed
    Expected Result: Two results: first with None translation, second normal
    Failure Indicators: Worker crash, empty result_queue, or only 1 result
    Evidence: .sisyphus/evidence/task-8-llm-timeout.txt
  ```

  **Commit**: YES
  - Message: `feat(pipeline): add LLM worker thread`
  - Files: `src/pipeline/llm_worker.py`, `tests/test_llm_worker.py`
  - Pre-commit: `pytest tests/test_llm_worker.py -x`

- [x] 9. WASAPI Resampling Optimization (Windows)

  **What to do**:
  - RED: Write tests for optimized resampling: (a) `_resample()` produces identical output to scipy.signal.resample for same input, (b) resampling latency < 2ms per callback block (was FFT-based, slower), (c) module-level import (not inside callback).
  - GREEN: Modify `src/audio/backends.py`:
    1. Move `scipy.signal.resample` import to module level (currently imported inside callback).
    2. Replace FFT-based `scipy.signal.resample()` with `scipy.signal.resample_poly()` (polyphase, much faster for integer ratios like 48000→16000 = 3:1) or `soxr.resample()` if soxr is available.
    3. Pre-compute the resampling ratio and filter coefficients at `__init__` time, not per-callback.
    4. Verify the downmix (multi-channel → mono) is efficient: `np.mean(axis=1)` is fine.
  - REFACTOR: Add type annotations to callback, ensure no allocations in hot path.

  **Must NOT do**:
  - Don't change the audio capture public API
  - Don't add soxr as a hard dependency (optional optimization, fall back to scipy)
  - Don't change Linux AudioCapture (only optimize Windows WASAPI backend)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Audio DSP optimization requires correctness verification
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 5, 6, 7, 8)
  - **Blocks**: None directly (improves audio thread performance)
  - **Blocked By**: None (independent optimization)

  **References**:

  **Pattern References**:
  - `src/audio/backends.py` — ENTIRE FILE is modification target. Key lines: 127-129 (scipy.signal.resample in callback), 115-125 (_pa_callback method).

  **API/Type References**:
  - `src/audio/capture.py:AudioCapture` — Base class / factory pattern. Windows backend must maintain same interface.

  **External References**:
  - scipy docs: `scipy.signal.resample_poly` — polyphase resampling, faster for integer ratios
  - soxr-python: High-quality resampling library, optional dependency

  **WHY Each Reference Matters**:
  - `backends.py`: Direct modification target — must understand WASAPI callback flow
  - `resample_poly` docs: Must verify it produces equivalent quality output

  **Acceptance Criteria**:
  - [x] `pytest tests/test_backends.py` → PASS (if exists, else new tests pass)
  - [x] Test: resampled output matches scipy.signal.resample within 1e-5 tolerance
  - [x] Test: resampling latency < 2ms per 1024-sample block
  - [x] `grep -n "import scipy" src/audio/backends.py` → only at module level (not inside function)
  - [x] `mypy src/audio/backends.py` → 0 errors

  **QA Scenarios**:

  ```
  Scenario: Optimized resampling produces correct output
    Tool: Bash (pytest)
    Preconditions: Test audio at 48kHz available
    Steps:
      1. Run `python -m pytest tests/test_backends.py::test_resample_correctness -v`
      2. Compare resample_poly output vs original resample output
      3. Assert max absolute difference < 1e-4
    Expected Result: Outputs match within tolerance
    Failure Indicators: Difference exceeds tolerance
    Evidence: .sisyphus/evidence/task-9-resample-correctness.txt

  Scenario: Resampling performance within budget
    Tool: Bash (pytest)
    Preconditions: Performance test with timing
    Steps:
      1. Run `python -m pytest tests/test_backends.py::test_resample_performance -v`
      2. Resample 1000 blocks of 1024 samples (48kHz→16kHz)
      3. Assert mean time < 2ms per block
    Expected Result: Mean < 2ms, max < 5ms
    Failure Indicators: Mean >= 2ms
    Evidence: .sisyphus/evidence/task-9-resample-perf.txt
  ```

  **Commit**: YES
  - Message: `perf(audio): optimize WASAPI resampling with resample_poly`
  - Files: `src/audio/backends.py`, `tests/test_backends.py`
  - Pre-commit: `pytest tests/test_backends.py -x`

### Wave 3: Integration (Tasks 10-11)

- [x] 10. Pipeline Orchestrator — Multi-Threaded Coordinator

  **What to do**:
  - RED: Write tests for `PipelineOrchestrator`: (a) creates and wires all workers (VADWorker, ASRWorker, LLMWorker), (b) creates inter-stage queues (audio_queue, segment_queue, text_queue, result_queue), (c) start() launches all workers in correct order, (d) stop() shuts down in reverse order (LLM→ASR→VAD→audio), drains queues, (e) error from any worker propagated via error_occurred signal, (f) asr_ready signal forwarded for progressive display, (g) translation_ready signal forwarded, (h) config update applied to all workers safely (queue new config, apply at safe point).
  - GREEN: Create `src/pipeline/orchestrator.py`: Replaces the monolithic `PipelineWorker`. Key design:
    - `__init__(config)`: Create all components (AudioCapture, SileroVAD, QwenASR, PreprocessingPipeline, AsyncOllamaClient, LearningRepository). Create 4 queues with bounded sizes. Create 3 workers, injecting dependencies.
    - `start()`: Start audio capture → VADWorker → ASRWorker → LLMWorker (order matters: consumers before producers)
    - `stop()`: Stop in reverse order. LLMWorker.stop() → ASRWorker.stop() → VADWorker.stop() → AudioCapture.stop(). Drain all queues. Log final metrics.
    - Wire signals: `vad_worker.error_occurred → self.error_occurred`, `asr_worker.asr_ready → self.asr_ready`, `llm_worker.translation_ready → self.translation_ready`
    - `update_config(config)`: Thread-safe config propagation (emit config_changed signal, workers check at safe points)
    - Performance: Log PipelineMetrics summary every 30s
  - REFACTOR: Delete old `src/pipeline.py` (monolithic worker). Update `src/main.py` to use orchestrator.

  **Must NOT do**:
  - Don't add a watchdog/supervisor thread (keep simple for now)
  - Don't implement hot-reload of ASR model (requires restart)
  - Don't share mutable state between workers — queues and signals only

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Threading coordination with ordered startup/shutdown is error-prone
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 3 (with Task 11 after this)
  - **Blocks**: Tasks 11, 12, Final wave
  - **Blocked By**: Tasks 1, 2, 4, 5, 6, 7, 8

  **References**:

  **Pattern References**:
  - `src/pipeline.py` — OLD monolithic worker to replace. Copy signal definitions (sentence_ready, error_occurred) to orchestrator. Delete after migration.
  - `src/main.py` — Creates PipelineWorker and wires signals. Must update to use PipelineOrchestrator.
  - `src/pipeline/vad_worker.py`, `src/pipeline/asr_worker.py`, `src/pipeline/llm_worker.py` — The workers this orchestrator coordinates.

  **API/Type References**:
  - `src/audio/capture.py:AudioCapture` — `start(callback)`, `stop()` API
  - `src/vad/silero.py:SileroVAD` — Injected into VADWorker
  - `src/asr/qwen_asr.py:QwenASR` — Injected into ASRWorker
  - `src/llm/ollama_client.py:AsyncOllamaClient` — Injected into LLMWorker
  - `src/db/repository.py:LearningRepository` — Injected into LLMWorker

  **Test References**:
  - `tests/test_pipeline.py` — Existing pipeline tests to migrate/update.
  - `tests/test_vad_worker.py`, `tests/test_asr_worker.py`, `tests/test_llm_worker.py` — Worker tests to verify independently.

  **WHY Each Reference Matters**:
  - `pipeline.py`: The code being replaced — must replicate ALL signal emissions and external API
  - `main.py`: The integration point — must update constructor and signal wiring
  - Worker files: Must understand each worker's API to wire correctly

  **Acceptance Criteria**:
  - [x] `pytest tests/test_orchestrator.py` → PASS
  - [x] Test: start() launches 3 workers (all isRunning())
  - [x] Test: stop() terminates all workers within 5s total
  - [x] Test: shutdown order is LLM→ASR→VAD→audio (verified via mock call order)
  - [x] Test: error in VADWorker propagated to orchestrator's error_occurred signal
  - [x] Test: asr_ready signal forwarded from ASRWorker
  - [x] `src/pipeline.py` deleted (old monolithic worker)
  - [x] `mypy src/pipeline/orchestrator.py` → 0 errors

  **QA Scenarios**:

  ```
  Scenario: Orchestrator lifecycle — start and stop cleanly
    Tool: Bash (pytest)
    Preconditions: All worker classes available, mock dependencies
    Steps:
      1. Run `python -m pytest tests/test_orchestrator.py::test_lifecycle -v`
      2. Create orchestrator with mock audio/vad/asr/llm/db
      3. Call start(), assert all workers running
      4. Call stop(), assert all workers stopped within 5s
      5. Assert no orphan threads
    Expected Result: Clean start → clean stop, 0 orphan threads
    Failure Indicators: Any worker still running after stop(), timeout
    Evidence: .sisyphus/evidence/task-10-lifecycle.txt

  Scenario: Error propagation from worker to orchestrator
    Tool: Bash (pytest)
    Preconditions: Mock VAD that raises RuntimeError
    Steps:
      1. Run `python -m pytest tests/test_orchestrator.py::test_error_propagation -v`
      2. Start orchestrator with failing VAD
      3. Assert error_occurred signal emitted with error message
      4. Assert orchestrator remains operational (other workers continue)
    Expected Result: Error signal emitted, orchestrator not crashed
    Failure Indicators: No signal, or orchestrator crashes
    Evidence: .sisyphus/evidence/task-10-error-prop.txt

  Scenario: Ordered shutdown — reverse of startup
    Tool: Bash (pytest)
    Preconditions: Workers with mock stop() that records call order
    Steps:
      1. Run `python -m pytest tests/test_orchestrator.py::test_shutdown_order -v`
      2. Call stop(), capture order of worker.stop() calls
      3. Assert order: LLM → ASR → VAD → audio
    Expected Result: Reverse order verified
    Failure Indicators: Wrong order
    Evidence: .sisyphus/evidence/task-10-shutdown-order.txt
  ```

  **Commit**: YES
  - Message: `refactor(pipeline): multi-threaded orchestrator replaces monolith`
  - Files: `src/pipeline/orchestrator.py`, `src/main.py`, `tests/test_orchestrator.py`
  - Pre-commit: `pytest tests/test_orchestrator.py -x`

- [x] 11. Progressive UI Display — ASR First, Translation Async

  **What to do**:
  - RED: Write tests for: (a) overlay.on_asr_ready() displays transcription text immediately, (b) overlay.on_translation_ready() updates the same sentence card with translation, (c) sentence card shows "Translating..." indicator while waiting for LLM, (d) sentence card with translation=None (LLM failed) shows "Translation unavailable" instead of blank, (e) multiple rapid ASR results display in order without UI glitch.
  - GREEN: Modify `src/ui/overlay.py` (and related UI files):
    1. Add `on_asr_ready(asr_result: ASRResult)` slot: creates/updates sentence card with Japanese text, marks as "pending translation" (show spinner or "Translating..." text)
    2. Add `on_translation_ready(translation_result: TranslationResult)` slot: finds matching sentence card by segment_id, fills in translation + explanation. If translation is None, show "Translation unavailable."
    3. Modify `src/main.py` to wire: `orchestrator.asr_ready → overlay.on_asr_ready`, `orchestrator.translation_ready → overlay.on_translation_ready`
    4. Remove old `on_sentence_ready` connection (replaced by two-phase signals)
  - REFACTOR: Ensure segment_id matching is robust (use dict lookup, not list scan).

  **Must NOT do**:
  - Don't redesign the overlay layout or tooltip styles
  - Don't add animations or transitions (keep simple)
  - Don't change the learning panel or sentence detail UI

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: UI signal handling and display state management
  - **Skills**: [`playwright`]
    - `playwright`: For QA scenarios testing the actual UI rendering

  **Parallelization**:
  - **Can Run In Parallel**: YES (partially — after Task 10 wires orchestrator signals)
  - **Parallel Group**: Wave 3 (after Task 10 completes)
  - **Blocks**: Task 12
  - **Blocked By**: Task 10

  **References**:

  **Pattern References**:
  - `src/ui/overlay.py` — Main overlay widget. Has existing `on_sentence_ready()` slot to replace/augment.
  - `src/ui/tooltip.py` — Tooltip widget showing sentence details. May need update for two-phase display.
  - `src/main.py` — Signal wiring point. Currently: `pipeline.sentence_ready → overlay.on_sentence_ready`.

  **API/Type References**:
  - `src/pipeline/types.py:ASRResult` — First-phase display data (Japanese text)
  - `src/pipeline/types.py:TranslationResult` — Second-phase display data (translation + explanation)
  - `src/pipeline/orchestrator.py` signals: `asr_ready(ASRResult)`, `translation_ready(TranslationResult)`

  **Test References**:
  - `tests/test_overlay.py` — Existing UI tests if any. Check for Qt test patterns (QTest).

  **WHY Each Reference Matters**:
  - `overlay.py`: The widget being modified — must understand current on_sentence_ready to split into two-phase
  - `tooltip.py`: May need changes if tooltip shows translation inline
  - `main.py`: Signal wiring must be updated for new two-signal pattern

  **Acceptance Criteria**:
  - [x] `pytest tests/test_overlay.py` → PASS (new + existing tests)
  - [x] Test: on_asr_ready creates sentence card with Japanese text visible
  - [x] Test: on_translation_ready updates existing card (matched by segment_id)
  - [x] Test: translation=None shows "Translation unavailable"
  - [x] `mypy src/ui/overlay.py` → 0 errors

  **QA Scenarios**:

  ```
  Scenario: Progressive display — ASR text appears before translation
    Tool: Playwright (via playwright skill)
    Preconditions: App running with mock audio input
    Steps:
      1. Launch app with test audio that produces a known Japanese sentence
      2. Wait for overlay to show Japanese text (selector: `.sentence-text` or Qt object name)
      3. Assert text appears within 3s of speech end
      4. Assert "Translating..." indicator is visible
      5. Wait for translation to appear (selector: `.translation-text`)
      6. Assert translation replaces "Translating..." indicator
      7. Screenshot before and after translation
    Expected Result: Japanese text appears first, translation follows 5-10s later
    Failure Indicators: Both appear simultaneously, or Japanese text never appears
    Evidence: .sisyphus/evidence/task-11-progressive-before.png, task-11-progressive-after.png

  Scenario: LLM failure shows graceful degradation in UI
    Tool: Playwright (via playwright skill)
    Preconditions: App running with Ollama stopped (unavailable)
    Steps:
      1. Trigger speech input
      2. Assert Japanese text appears normally
      3. Wait 16s (timeout + buffer)
      4. Assert "Translation unavailable" text visible (not blank)
      5. Screenshot
    Expected Result: "Translation unavailable" shown, no crash
    Failure Indicators: Blank space, crash, or infinite spinner
    Evidence: .sisyphus/evidence/task-11-llm-failure.png
  ```

  **Commit**: YES
  - Message: `feat(ui): progressive display with async translation`
  - Files: `src/ui/overlay.py`, `src/main.py`, `tests/test_overlay.py`
  - Pre-commit: `pytest tests/test_overlay.py -x`

### Wave 4: End-to-End Validation (Task 12)

- [x] 12. Integration Test & Performance Validation

  **What to do**:
  - RED: Write integration tests: (a) end-to-end pipeline with real audio file → VAD → ASR → preprocessing → LLM → UI signals, (b) queue overflow stress test: feed audio at 2× real-time for 60s, assert no "queue Full" warnings, (c) latency test: measure time from speech-end to asr_ready signal (target < 3s), (d) measure time from speech-end to translation_ready signal (target < 10s with real Ollama), (e) concurrent speech: 3 rapid utterances, all processed without data loss.
  - GREEN: Create `tests/test_integration.py`:
    1. Full pipeline integration test with pre-recorded test audio file
    2. Stress test: mock AudioCapture feeding chunks at 2× rate for 60s
    3. Latency measurement: timestamps at speech-end vs signal emission
    4. Verify queue sizes never exceed 80% capacity under load
    5. Verify PipelineMetrics shows all stages with reasonable timing
  - REFACTOR: Add pytest markers (`@pytest.mark.integration`, `@pytest.mark.slow`) for selective running. Add `conftest.py` fixtures for pipeline setup/teardown.

  **Must NOT do**:
  - Don't test UI rendering in integration tests (separate concern)
  - Don't require Ollama running for basic integration tests (mock LLM for core tests, mark real-Ollama tests with `@pytest.mark.requires_ollama`)

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Integration testing with timing constraints and concurrency validation
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 4 (sequential, depends on everything)
  - **Blocks**: Final verification wave
  - **Blocked By**: Tasks 10, 11

  **References**:

  **Pattern References**:
  - `src/pipeline/orchestrator.py` (Task 10) — The system under test. `start()`, `stop()`, signal connections.
  - `src/pipeline.py` (old, deleted) — Reference for what the old monolithic pipeline did, to ensure feature parity.

  **API/Type References**:
  - All pipeline types from `src/pipeline/types.py`
  - All worker APIs from Tasks 5, 6, 8

  **Test References**:
  - `tests/conftest.py` — Existing fixtures. May need new orchestrator fixtures.
  - `tests/test_pipeline.py` — Old pipeline tests to port to new orchestrator.

  **External References**: None.

  **WHY Each Reference Matters**:
  - `orchestrator.py`: Primary test target — must test all public methods and signals
  - Old `pipeline.py`: Feature parity checklist — nothing should be lost in migration

  **Acceptance Criteria**:
  - [x] `pytest tests/test_integration.py -m "not requires_ollama"` → PASS
  - [x] Stress test: 0 "queue Full" warnings in 60s at 2× speed
  - [x] Latency: speech-end → asr_ready < 3s (p95)
  - [x] Latency: speech-end → translation_ready < 10s (p95, with mock LLM)
  - [x] 3 rapid utterances: all 3 processed, 0 data loss
  - [x] `ruff check . && mypy . && pytest` → ALL PASS

  **QA Scenarios**:

  ```
  Scenario: No queue overflow under sustained load
    Tool: Bash (pytest)
    Preconditions: Orchestrator running with mock audio at 2× speed
    Steps:
      1. Run `python -m pytest tests/test_integration.py::test_no_queue_overflow -v --timeout=120`
      2. Feed 60 seconds of audio at 2× real-time rate
      3. Capture all log output
      4. Search for "Full" or "dropping" in logs
    Expected Result: Zero queue overflow warnings
    Failure Indicators: Any "Full" or "dropping" in logs
    Evidence: .sisyphus/evidence/task-12-stress-test.txt

  Scenario: ASR latency meets target
    Tool: Bash (pytest)
    Preconditions: Integration test with timestamped signals
    Steps:
      1. Run `python -m pytest tests/test_integration.py::test_asr_latency -v`
      2. Feed known speech segment, record timestamp at speech end
      3. Record timestamp when asr_ready signal emitted
      4. Assert delta < 3000ms
    Expected Result: p95 latency < 3s
    Failure Indicators: Any measurement > 3s
    Evidence: .sisyphus/evidence/task-12-latency.txt

  Scenario: Full validation cycle passes
    Tool: Bash (ruff + mypy + pytest)
    Preconditions: All code complete
    Steps:
      1. Run `ruff check . && ruff format --check . && mypy . && pytest -x --tb=short`
      2. Assert all 4 commands exit 0
    Expected Result: Zero lint errors, zero type errors, all tests pass
    Failure Indicators: Any non-zero exit code
    Evidence: .sisyphus/evidence/task-12-full-validation.txt
  ```

  **Commit**: YES
  - Message: `test(integration): end-to-end pipeline validation`
  - Files: `tests/test_integration.py`, `tests/conftest.py`
  - Pre-commit: `ruff check . && mypy . && pytest -x`

  **What to do**:
  - RED: Write tests for: (a) `insert_partial(asr_result)` inserts row with `chinese_translation=NULL, explanation=NULL`, returns row_id. (b) `update_translation(row_id, translation, explanation)` fills in the NULL fields. (c) Verify row integrity after both phases. (d) `update_translation` on non-existent row_id raises or returns False.
  - GREEN: Modify `src/db/repository.py` to add `insert_partial()` and `update_translation()` methods. Keep existing `insert_sentence()` working (backward compat). Ensure SQLite WAL mode is enabled for concurrent read/write safety from different threads: `PRAGMA journal_mode=WAL` on connection open.
  - REFACTOR: Add type annotations, verify thread-safety documentation.

  **Must NOT do**:
  - Don't change existing `insert_sentence()` signature or behavior
  - Don't switch to async DB (SQLite sync is fast enough)
  - Don't add an ORM

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Small SQL changes, straightforward test patterns
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2, 3)
  - **Blocks**: Task 10
  - **Blocked By**: Task 1 (uses ASRResult, TranslationResult types)

  **References**:

  **Pattern References**:
  - `src/db/repository.py` — Entire file is modification target. Shows existing `insert_sentence()` method, connection handling, and SQL patterns.
  - `src/db/schema.py` — Database schema. Check if `chinese_translation` and `explanation` columns already allow NULL.

  **API/Type References**:
  - `src/pipeline/types.py:ASRResult` — Input type for `insert_partial()`
  - `src/pipeline/types.py:TranslationResult` — Input type for `update_translation()`
  - `src/db/models.py:SentenceRecord` — Existing model. New methods must produce valid SentenceRecords.

  **Test References**:
  - `tests/test_db_repository.py` — Existing DB tests. Follow same patterns (in-memory SQLite fixtures).

  **WHY Each Reference Matters**:
  - `repository.py`: Must extend without breaking existing methods
  - `schema.py`: Need to verify NULL constraints on translation columns
  - `models.py`: Return types must match existing conventions

  **Acceptance Criteria**:
  - [x] `pytest tests/test_db_repository.py` → ALL tests pass (existing + new)
  - [x] New test: insert_partial creates row with NULL translation
  - [x] New test: update_translation fills in translation fields
  - [x] `mypy src/db/repository.py` → 0 errors

  **QA Scenarios**:

  ```
  Scenario: Two-phase write produces complete record
    Tool: Bash (pytest)
    Preconditions: In-memory SQLite test fixture
    Steps:
      1. Run `python -m pytest tests/test_db_repository.py::test_two_phase_write -v`
      2. Test calls insert_partial → verifies NULL translation → calls update_translation → verifies complete record
    Expected Result: PASS — record complete after both phases
    Failure Indicators: NULL translation after update, or missing row after insert
    Evidence: .sisyphus/evidence/task-4-two-phase.txt

  Scenario: Existing insert_sentence still works (regression)
    Tool: Bash (pytest)
    Preconditions: Existing test fixtures
    Steps:
      1. Run `python -m pytest tests/test_db_repository.py -v`
      2. Verify ALL existing tests pass unchanged
    Expected Result: Zero regressions
    Failure Indicators: Any existing test failure
    Evidence: .sisyphus/evidence/task-4-regression.txt
  ```

  **Commit**: YES
  - Message: `feat(db): add two-phase write for progressive display`
  - Files: `src/db/repository.py`, `tests/test_db_repository.py`
  - Pre-commit: `pytest tests/test_db_repository.py -x`

---

## Final Verification Wave

> 4 review agents run in PARALLEL. ALL must APPROVE. Rejection → fix → re-run.

- [x] F1. **Plan Compliance Audit** — `oracle`
  Read the plan end-to-end. For each "Must Have": verify implementation exists (read file, run command). For each "Must NOT Have": search codebase for forbidden patterns — reject with file:line if found. Check evidence files exist in `.sisyphus/evidence/`. Compare deliverables against plan.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [x] F2. **Code Quality Review** — `unspecified-high`
  Run `ruff check . && ruff format --check . && mypy . && pytest`. Review all changed files for: `type: ignore` without comment, empty excepts, print() in prod code, commented-out code, unused imports. Check AI slop: excessive comments, over-abstraction, generic names (data/result/item/temp).
  Output: `Lint [PASS/FAIL] | Types [PASS/FAIL] | Tests [N pass/N fail] | Files [N clean/N issues] | VERDICT`

- [x] F3. **Real Manual QA** — `unspecified-high` (+ `playwright` skill if UI)
  Start from clean state. Execute EVERY QA scenario from EVERY task — follow exact steps, capture evidence. Test cross-task integration (progressive display end-to-end, multi-segment handling, LLM failure graceful degradation). Test edge cases: rapid speech, silence, Ollama down. Save to `.sisyphus/evidence/final-qa/`.
  Output: `Scenarios [N/N pass] | Integration [N/N] | Edge Cases [N tested] | VERDICT`

- [x] F4. **Scope Fidelity Check** — `deep`
  For each task: read "What to do", read actual diff (git log/diff). Verify 1:1 — everything in spec was built (no missing), nothing beyond spec was built (no creep). Check "Must NOT do" compliance. Detect cross-task contamination: Task N touching Task M's files. Flag unaccounted changes.
  Output: `Tasks [N/N compliant] | Contamination [CLEAN/N issues] | Unaccounted [CLEAN/N files] | VERDICT`

---

## Commit Strategy

| After Task | Commit Message | Key Files | Pre-commit Check |
|-----------|---------------|-----------|-----------------|
| 1 | `refactor(pipeline): add pipeline types and data models` | `src/pipeline/types.py`, tests | `pytest tests/test_pipeline_types.py` |
| 2 | `feat(pipeline): add performance instrumentation utility` | `src/pipeline/perf.py`, tests | `pytest tests/test_perf.py` |
| 3 | `perf(vad): optimize Silero to ONNX with ring buffer` | `src/vad/silero.py`, tests | `pytest tests/test_silero_vad.py` |
| 4 | `feat(db): add two-phase write for progressive display` | `src/db/repository.py`, tests | `pytest tests/test_db_repository.py` |
| 5 | `feat(pipeline): add VAD worker thread` | `src/pipeline/vad_worker.py`, tests | `pytest tests/test_vad_worker.py` |
| 6 | `feat(asr): add batch transcription and ASR worker` | `src/asr/qwen_asr.py`, `src/pipeline/asr_worker.py`, tests | `pytest tests/test_asr_worker.py tests/test_qwen_asr.py` |
| 7 | `feat(llm): async httpx client with streaming and cache` | `src/llm/ollama_client.py`, tests | `pytest tests/test_ollama_client.py` |
| 8 | `feat(pipeline): add LLM worker thread` | `src/pipeline/llm_worker.py`, tests | `pytest tests/test_llm_worker.py` |
| 9 | `perf(audio): optimize WASAPI resampling with resample_poly` | `src/audio/backends.py`, tests | `pytest tests/test_backends.py` |
| 10 | `refactor(pipeline): multi-threaded orchestrator replaces monolith` | `src/pipeline/orchestrator.py`, `src/main.py`, tests | `pytest tests/test_orchestrator.py` |
| 11 | `feat(ui): progressive display with async translation` | `src/ui/overlay.py`, `src/main.py`, tests | `pytest tests/test_overlay.py` |
| 12 | `test(integration): end-to-end pipeline validation` | `tests/test_integration.py`, `tests/conftest.py` | `ruff check . && mypy . && pytest -x` |

---

## Success Criteria

### Verification Commands
```bash
# All tests pass
pytest -x --tb=short

# Lint + format + types clean
ruff check . && ruff format --check . && mypy .

# Integration test (no Ollama required)
python -m pytest tests/test_integration.py -m "not requires_ollama" -v --timeout=120

# Stress test — zero queue overflow warnings
python -m pytest tests/test_integration.py::test_no_queue_overflow -v --timeout=120
```

### Final Checklist
- [x] All "Must Have" requirements present and verified
- [x] All "Must NOT Have" items absent from codebase
- [x] Zero "queue Full" warnings in 60-second stress test at 2× speed
- [x] ASR display latency < 3 seconds (p95)
- [x] Translation display latency < 10 seconds (p95)
- [x] Clean shutdown < 5 seconds with no orphan threads
- [x] All tests pass (unit + integration)
- [x] ruff + mypy clean
- [x] Progressive UI verified: ASR text appears before translation
- [x] Old monolithic `src/pipeline.py` deleted
