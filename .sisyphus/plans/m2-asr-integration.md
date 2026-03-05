# Milestone 2 — ASR Integration

## TL;DR

> **Quick Summary**: Implement the audio→VAD→ASR→preprocessing pipeline: capture system audio via sounddevice, detect speech boundaries with Silero VAD, transcribe with Qwen3-ASR 0.6B, and wire everything through a QThread-based pipeline worker that emits `SentenceResult` signals to the UI thread.
> 
> **Deliverables**:
> - `AudioSegment` dataclass in `src/db/models.py`
> - `src/audio/capture.py` — AudioCapture (sounddevice wrapper)
> - `src/vad/silero.py` — SileroVAD (Silero VAD + audio buffering)
> - `src/asr/qwen_asr.py` — QwenASR (Qwen3-ASR 0.6B wrapper)
> - `src/pipeline.py` — PipelineWorker (QThread orchestrator)
> - `tests/test_audio_capture.py`, `tests/test_silero_vad.py`, `tests/test_qwen_asr.py`, `tests/test_pipeline.py`
> 
> **Estimated Effort**: Medium (4 implementation modules + 4 test modules + 1 dataclass addition)
> **Parallel Execution**: YES — 3 waves
> **Critical Path**: Task 1 (AudioSegment) → Tasks 2,3,4 (parallel) → Task 5 (PipelineWorker)

---

## Context

### Original Request
Complete all Milestone 2 tasks for MyASR Japanese Learning Overlay — implement AudioCapture, SileroVAD, QwenASR, and PipelineWorker to create a working Audio→VAD→ASR→Preprocessing pipeline.

### Interview Summary
**Key Discussions**:
- DB writes deferred to M3 — PipelineWorker only emits Qt signal with SentenceResult, no LearningRepository integration
- AudioSegment dataclass goes in `src/db/models.py` alongside existing pipeline dataclasses
- Tests-after strategy — implement module first, then write tests with mocked external dependencies
- WSL/Linux dev constraint — PyAudioWPatch is Windows-only, sounddevice for dev, all tests use mocked audio

**Research Findings**:
- Qwen3-ASR API verified: `from qwen_asr import Qwen3ASRModel`, `model.transcribe(audio=(np_array, sr), language="Japanese")` → `[ASRTranscription(text, language)]`
- Silero VAD `VADIterator` only returns `{'start': idx}` / `{'end': idx}` — does NOT buffer audio. Wrapper must buffer internally.
- `import sounddevice` fails in WSL2 without PortAudio — must use lazy import pattern
- `Qwen3ASRModel` has no `unload()` method — implement via `del self._model; torch.cuda.empty_cache()`
- PySide6 `Signal(object)` is required instead of `Signal(SentenceResult)` to avoid type registration issues

### Metis Review
**Identified Gaps** (all addressed):
- VADIterator buffering gap → SileroVAD must maintain internal audio buffer
- sounddevice import failure → lazy import inside `start()` method
- Thread safety → `queue.Queue` between sounddevice callback and PipelineWorker
- Signal type registration → `Signal(object)` pattern
- VAD blocksize alignment → AudioCapture must use `blocksize=512` (or multiple)
- No `unload()` on model → manual `del` + `torch.cuda.empty_cache()`
- Edge cases → max speech duration cutoff, min speech filter, concurrent start guard

---

## Work Objectives

### Core Objective
Build the real-time audio processing pipeline: capture system audio, detect speech boundaries, transcribe Japanese speech, and feed transcriptions through the existing preprocessing pipeline — all running in a background QThread that emits results to the UI thread via Qt signals.

### Concrete Deliverables
- `AudioSegment` dataclass added to `src/db/models.py`
- `src/audio/capture.py` — `AudioCapture` class
- `src/vad/silero.py` — `SileroVAD` class
- `src/asr/qwen_asr.py` — `QwenASR` class
- `src/pipeline.py` — `PipelineWorker(QThread)` class
- `tests/test_audio_capture.py` — AudioCapture tests (mocked sounddevice)
- `tests/test_silero_vad.py` — SileroVAD tests (mocked Silero model)
- `tests/test_qwen_asr.py` — QwenASR tests (mocked qwen-asr model)
- `tests/test_pipeline.py` — PipelineWorker tests (all components mocked)

### Definition of Done
- [ ] `ruff check . && ruff format --check . && mypy . && pytest -x --tb=short` passes cleanly
- [ ] All 4 new test files pass
- [ ] No top-level `import sounddevice` in capture.py (lazy import only)
- [ ] PipelineWorker emits `SentenceResult` via signal (verified in test)

### Must Have
- AudioCapture with callback-based audio streaming via sounddevice
- SileroVAD with internal audio buffering and speech boundary detection
- QwenASR with GPU model loading, batch transcription, and manual unload
- PipelineWorker QThread wiring Audio→VAD→ASR→Preprocessing with signal emission
- Thread-safe `queue.Queue` between audio callback and pipeline processing
- Lazy sounddevice import for WSL/CI compatibility
- All public methods type-annotated (mypy strict)

### Must NOT Have (Guardrails)
- **No DB writes** — deferred to M3 (no LearningRepository usage in PipelineWorker)
- **No LLM integration** — deferred to M3 (no OllamaClient in PipelineWorker)
- **No streaming ASR** — batch mode only (`model.transcribe()`, not `streaming_transcribe()`)
- **No new AppConfig fields** — use existing `config.sample_rate`, hardcode other defaults in classes
- **No audio format conversion** — no resampling, no stereo-to-mono, no file I/O
- **No model downloading/management** — no auto-download, no progress bars, no version checking
- **No error recovery/retry logic** — if ASR fails, log and skip; no retry queues
- **No metrics/monitoring** — simple `logger.debug()` only
- **No top-level `import sounddevice`** — must be lazy import inside methods
- **No VAD logic inside AudioCapture** — callback only captures raw audio
- **No AudioCapture/VAD coupling** — SileroVAD receives `np.ndarray`, knows nothing about audio devices

---

## Verification Strategy (MANDATORY)

> **ZERO HUMAN INTERVENTION** — ALL verification is agent-executed. No exceptions.

### Test Decision
- **Infrastructure exists**: YES (pytest, pytest-mock in dev deps)
- **Automated tests**: Tests-after (implement module, then write tests)
- **Framework**: pytest + pytest-mock
- **Pattern**: M2 tests use `unittest.mock` / `pytest-mock` extensively since all external deps (sounddevice, silero-vad, qwen-asr, PySide6) must be mocked

### QA Policy
Every task MUST include agent-executed QA scenarios.
Evidence saved to `.sisyphus/evidence/task-{N}-{scenario-slug}.{ext}`.

- **Module imports**: Use Bash (python -c "from src.X import Y")
- **Tests**: Use Bash (pytest tests/test_X.py -x)
- **Type checking**: Use Bash (mypy src/X.py)
- **Lint**: Use Bash (ruff check src/X.py)

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Foundation — must complete first):
└── Task 1: Add AudioSegment dataclass to models.py [quick]

Wave 2 (Core modules — MAX PARALLEL, all independent):
├── Task 2: Implement AudioCapture + tests (depends: 1) [unspecified-high]
├── Task 3: Implement SileroVAD + tests (depends: 1) [unspecified-high]
└── Task 4: Implement QwenASR + tests (depends: 1) [unspecified-high]

Wave 3 (Integration — depends on all Wave 2):
└── Task 5: Implement PipelineWorker + tests (depends: 2, 3, 4) [deep]

Wave FINAL (Verification — after ALL tasks):
├── Task F1: Plan compliance audit [oracle]
├── Task F2: Code quality review (ruff + mypy + pytest) [unspecified-high]
├── Task F3: Integration QA with all mocks [unspecified-high]
└── Task F4: Scope fidelity check [deep]

Critical Path: Task 1 → Task 3 (longest) → Task 5 → F1-F4
Parallel Speedup: ~40% faster than sequential (Wave 2 parallelism)
Max Concurrent: 3 (Wave 2)
```

### Dependency Matrix

| Task | Depends On | Blocks | Wave |
|------|-----------|--------|------|
| 1 | — | 2, 3, 4 | 1 |
| 2 | 1 | 5 | 2 |
| 3 | 1 | 5 | 2 |
| 4 | 1 | 5 | 2 |
| 5 | 2, 3, 4 | F1-F4 | 3 |
| F1-F4 | 5 | — | FINAL |

### Agent Dispatch Summary

- **Wave 1**: 1 task — T1 → `quick`
- **Wave 2**: 3 tasks — T2 → `unspecified-high`, T3 → `unspecified-high`, T4 → `unspecified-high`
- **Wave 3**: 1 task — T5 → `deep`
- **Wave FINAL**: 4 tasks — F1 → `oracle`, F2 → `unspecified-high`, F3 → `unspecified-high`, F4 → `deep`

---

## TODOs

> Implementation + Tests = ONE Task. Never separate.
> EVERY task MUST have: Recommended Agent Profile + Parallelization info + QA Scenarios.

- [ ] 1. Add AudioSegment dataclass to models.py

  **What to do**:
  - Add `import numpy as np` to `src/db/models.py` imports (if not already present)
  - Add `AudioSegment` dataclass after the existing `SentenceResult` class:
    ```python
    @dataclass
    class AudioSegment:
        """A segment of audio detected by VAD as containing speech."""
        samples: np.ndarray  # float32, mono, 16kHz
        duration_sec: float
    ```
  - Verify the module imports cleanly and existing tests still pass

  **Must NOT do**:
  - Do NOT modify any existing dataclasses
  - Do NOT add any audio processing methods to AudioSegment

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Single-file, ~5 line addition to existing module
  - **Skills**: []
    - No special skills needed for a simple dataclass addition

  **Parallelization**:
  - **Can Run In Parallel**: NO (foundation for all other tasks)
  - **Parallel Group**: Wave 1 (solo)
  - **Blocks**: Tasks 2, 3, 4, 5
  - **Blocked By**: None (can start immediately)

  **References**:

  **Pattern References** (existing code to follow):
  - `src/db/models.py:SentenceResult` — Follow the same `@dataclass` pattern, placed after SentenceResult

  **API/Type References** (contracts to implement against):
  - `docs/architecture.md` — Specifies `AudioSegment(samples: np.ndarray, duration_sec: float)` as the VAD→ASR handoff type

  **WHY Each Reference Matters**:
  - `models.py` already has all pipeline dataclasses — AudioSegment belongs here for consistency
  - Architecture doc defines the exact fields and their semantics (float32, mono, 16kHz)

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: AudioSegment imports and instantiates correctly
    Tool: Bash
    Preconditions: Virtual env active
    Steps:
      1. Run: python -c "from src.db.models import AudioSegment; import numpy as np; seg = AudioSegment(samples=np.zeros(16000, dtype=np.float32), duration_sec=1.0); print(f'duration={seg.duration_sec}, shape={seg.samples.shape}, dtype={seg.samples.dtype}')"
      2. Assert output contains: "duration=1.0, shape=(16000,), dtype=float32"
    Expected Result: AudioSegment instantiates with numpy array and float duration
    Failure Indicators: ImportError, TypeError, unexpected output
    Evidence: .sisyphus/evidence/task-1-audiosegment-import.txt

  Scenario: Existing model tests still pass after addition
    Tool: Bash
    Preconditions: Virtual env active
    Steps:
      1. Run: pytest tests/test_db_schema.py -x --tb=short
      2. Assert exit code 0
      3. Run: mypy src/db/models.py
      4. Assert exit code 0
    Expected Result: No regressions from adding AudioSegment
    Failure Indicators: Test failures, mypy errors
    Evidence: .sisyphus/evidence/task-1-no-regression.txt
  ```

  **Commit**: YES
  - Message: `feat(models): add AudioSegment dataclass for VAD→ASR handoff`
  - Files: `src/db/models.py`
  - Pre-commit: `mypy src/db/models.py && pytest tests/test_db_schema.py -x`

- [ ] 2. Implement AudioCapture with sounddevice

  **What to do**:
  - Create `src/audio/capture.py` with class `AudioCapture`:
    - `__init__(self, device_id: int | None = None, sample_rate: int = 16000) -> None`
      - Store config. Initialize `self._stream = None`, `self._queue: queue.Queue[np.ndarray] = queue.Queue()`
      - Do NOT import sounddevice here (lazy import)
    - `start(self, callback: Callable[[np.ndarray], None]) -> None`
      - Guard against double-start (if `self._stream` is not None, raise `AudioCaptureError("Already capturing")`)
      - Lazy import: `import sounddevice as sd` inside this method
      - Create `sd.InputStream(samplerate=self._sample_rate, blocksize=512, device=self._device_id, channels=1, dtype="float32", callback=self._audio_callback)`
      - Store user callback in `self._user_callback`
      - Start the stream
      - Wrap sounddevice exceptions in `AudioCaptureError`
    - `_audio_callback(self, indata: np.ndarray, frames: int, time: Any, status: Any) -> None`
      - If status, log warning
      - Call `self._user_callback(indata[:, 0].copy())` — flatten (N,1)→(N,) and copy to decouple from sounddevice buffer
    - `stop(self) -> None`
      - Stop and close the stream if running, set `self._stream = None`
      - Handle errors gracefully (log, don't crash)
    - `list_devices(cls) -> list[dict[str, Any]]` — classmethod
      - Lazy import sounddevice
      - Return `sd.query_devices()` as list of dicts
      - Wrap errors in `AudioCaptureError`
  - Use `logging.getLogger(__name__)` for all logging
  - Import exceptions from `src.exceptions`

  - Create `tests/test_audio_capture.py`:
    - Mock `sounddevice` module using `unittest.mock.patch.dict("sys.modules", ...)` or `pytest-mock`
    - Test `start()` creates InputStream with correct params
    - Test `stop()` closes stream cleanly
    - Test `_audio_callback` flattens and copies audio data, calls user callback
    - Test double `start()` raises AudioCaptureError
    - Test `start()` with invalid device raises AudioCaptureError
    - Test `list_devices()` returns device list
    - Test `stop()` when not started is safe (no crash)

  **Must NOT do**:
  - No top-level `import sounddevice` — MUST be inside methods only
  - No VAD logic in callback — only raw audio forwarding
  - No audio format conversion (resampling, stereo-to-mono)
  - No file I/O (WAV recording/playback)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Non-trivial mock testing of system-level audio library with lazy import pattern
  - **Skills**: []
    - No special skills needed — standard Python + mocking

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 3, 4)
  - **Blocks**: Task 5
  - **Blocked By**: Task 1

  **References**:

  **Pattern References** (existing code to follow):
  - `src/analysis/pipeline.py` — Module structure pattern: imports, logger, class with `__init__`, methods
  - `tests/test_analysis_pipeline.py` — Test file structure: docstring, imports, fixtures, test functions
  - `src/exceptions.py:AudioCaptureError` — Exception to raise on audio capture failures

  **API/Type References** (contracts to implement against):
  - `src/db/models.py:AudioSegment` — The downstream type that VAD produces from captured audio
  - sounddevice API: `sd.InputStream(samplerate, blocksize, device, channels, dtype, callback)`, `sd.query_devices()`
  - Callback signature: `callback(indata: np.ndarray, frames: int, time: CData, status: CallbackFlags) -> None`

  **External References**:
  - sounddevice docs: https://python-sounddevice.readthedocs.io/en/latest/api/streams.html#sounddevice.InputStream

  **WHY Each Reference Matters**:
  - `pipeline.py` shows the project's module structure convention (logger, class, methods)
  - `AudioCaptureError` is the pre-defined exception for this module — must use it
  - sounddevice callback signature must be exact or audio capture will fail silently
  - `blocksize=512` is critical for Silero VAD compatibility (512 samples = 32ms at 16kHz)

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: AudioCapture module imports without sounddevice installed
    Tool: Bash
    Preconditions: Virtual env active
    Steps:
      1. Run: python -c "from src.audio.capture import AudioCapture; print('import OK')"
      2. Assert output: "import OK"
    Expected Result: Module importable without PortAudio/sounddevice being functional
    Failure Indicators: ImportError mentioning sounddevice or PortAudio
    Evidence: .sisyphus/evidence/task-2-lazy-import.txt

  Scenario: All AudioCapture tests pass
    Tool: Bash
    Preconditions: Virtual env active
    Steps:
      1. Run: pytest tests/test_audio_capture.py -x -v --tb=short
      2. Assert exit code 0
      3. Assert at least 6 tests pass (start, stop, callback, double-start, invalid-device, list-devices, stop-when-not-started)
    Expected Result: All tests pass with mocked sounddevice
    Failure Indicators: Test failures, import errors
    Evidence: .sisyphus/evidence/task-2-tests.txt

  Scenario: No top-level sounddevice import
    Tool: Bash
    Preconditions: None
    Steps:
      1. Run: python -c "import ast, sys; tree = ast.parse(open('src/audio/capture.py').read()); imports = [n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom)) and any(getattr(a, 'name', getattr(n, 'module', '')) == 'sounddevice' for a in getattr(n, 'names', [{'name': getattr(n, 'module', '')}]))]; top_level = [i for i in imports if isinstance(i, (ast.Import, ast.ImportFrom)) and any(i.lineno == n.lineno for n in ast.iter_child_nodes(tree))]; print(f'Top-level sd imports: {len(top_level)}')"
      2. Alternatively, simpler check: Run: grep -n "^import sounddevice\|^from sounddevice" src/audio/capture.py | wc -l
      3. Assert count is 0
    Expected Result: No top-level sounddevice imports found
    Failure Indicators: Count > 0
    Evidence: .sisyphus/evidence/task-2-no-toplevel-import.txt

  Scenario: mypy passes on capture.py
    Tool: Bash
    Preconditions: Virtual env active
    Steps:
      1. Run: mypy src/audio/capture.py
      2. Assert exit code 0 or only expected "missing stubs" warnings
    Expected Result: Type annotations are correct
    Failure Indicators: Type errors in public method signatures
    Evidence: .sisyphus/evidence/task-2-mypy.txt
  ```

  **Commit**: YES
  - Message: `feat(audio): implement AudioCapture with lazy sounddevice import`
  - Files: `src/audio/capture.py`, `tests/test_audio_capture.py`
  - Pre-commit: `ruff check src/audio/capture.py tests/test_audio_capture.py && mypy src/audio/capture.py && pytest tests/test_audio_capture.py -x`

- [ ] 3. Implement SileroVAD wrapper

  **What to do**:
  - Create `src/vad/silero.py` with class `SileroVAD`:
    - `__init__(self, threshold: float = 0.5, min_silence_ms: int = 500, min_speech_ms: int = 250, sample_rate: int = 16000) -> None`
      - Load Silero model: `from silero_vad import load_silero_vad; model = load_silero_vad(onnx=False)`
      - Create `VADIterator(model, threshold=threshold, sampling_rate=sample_rate, min_silence_duration_ms=min_silence_ms, speech_pad_ms=30)`
      - Initialize internal buffer: `self._audio_buffer: list[np.ndarray] = []`
      - Initialize tracking: `self._is_speech = False`, `self._max_speech_samples = 30 * sample_rate` (30s cutoff)
      - Store `self._min_speech_samples = int(min_speech_ms * sample_rate / 1000)`
      - Wrap model loading errors in `VADError`
    - `process_chunk(self, audio: np.ndarray) -> list[AudioSegment] | None`
      - **CRITICAL**: VADIterator only returns `{'start': idx}` / `{'end': idx}` / `None` — it does NOT buffer audio. This method MUST:
        1. Append `audio` to `self._audio_buffer`
        2. Convert audio to `torch.Tensor` and feed to `self._vad_iterator(chunk)`
        3. On `{'start': ...}`: set `self._is_speech = True`, mark buffer start position
        4. On `{'end': ...}`: concatenate buffered audio from start to end, create `AudioSegment(samples=segment, duration_sec=len(segment)/sample_rate)`, reset buffer tracking. If segment duration < min_speech_ms, discard.
        5. On `None`: if `self._is_speech` and total buffered speech exceeds `_max_speech_samples` (30s), force-cut and return segment.
        6. Return list of completed `AudioSegment`s (usually 0 or 1), or `None` if no complete segment yet.
      - Convert np.ndarray to `torch.FloatTensor` before feeding to VADIterator
    - `reset(self) -> None`
      - Call `self._vad_iterator.reset_states()`
      - Clear `self._audio_buffer`, reset `self._is_speech`
  - Use `logging.getLogger(__name__)` for logging
  - Import `AudioSegment` from `src.db.models`, `VADError` from `src.exceptions`

  - Create `tests/test_silero_vad.py`:
    - Mock `silero_vad.load_silero_vad` and `VADIterator`
    - Test speech detection: feed mock chunks where VADIterator returns `{'start':0}` then `{'end':512}` → verify returns AudioSegment with correct samples and duration
    - Test silence-only: VADIterator returns `None` for all chunks → verify returns None
    - Test short segment filtering: segment < min_speech_ms → discarded
    - Test max speech duration cutoff: force-cut at 30s
    - Test reset clears state
    - Test VADError on model load failure

  **Must NOT do**:
  - No dependency on AudioCapture — receives raw `np.ndarray` chunks only
  - No audio format conversion (assumes 16kHz float32 mono input)
  - No configuration UI or dynamic parameter changes
  - No use of `get_speech_timestamps()` — MUST use `VADIterator` for chunk-by-chunk streaming

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Complex stateful buffer management with VADIterator's non-obvious API (returns indices, not audio). Core correctness challenge of the milestone.
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 2, 4)
  - **Blocks**: Task 5
  - **Blocked By**: Task 1

  **References**:

  **Pattern References** (existing code to follow):
  - `src/analysis/pipeline.py` — Module structure pattern (logger, class, methods)
  - `src/analysis/tokenizer.py` — Wrapper class pattern: `__init__` loads external library, method processes input and returns structured output

  **API/Type References** (contracts to implement against):
  - `src/db/models.py:AudioSegment` — Output type: `AudioSegment(samples: np.ndarray, duration_sec: float)`
  - `src/exceptions.py:VADError` — Exception to raise on VAD failures
  - silero-vad API: `load_silero_vad(onnx=False)` → model, `VADIterator(model, threshold, sampling_rate, min_silence_duration_ms, speech_pad_ms)`, `vad_iterator(x: torch.Tensor)` → `{'start': int}` | `{'end': int}` | `None`, `vad_iterator.reset_states()`

  **External References**:
  - Silero VAD GitHub: https://github.com/snakers4/silero-vad — VADIterator usage examples in README

  **WHY Each Reference Matters**:
  - `AudioSegment` is the output contract — VAD must produce this exact type
  - `VADError` is the pre-defined exception for VAD failures
  - VADIterator API is the critical detail: it returns sample indices, NOT audio data. The wrapper must buffer and slice.
  - `tokenizer.py` shows the project convention for wrapping an external NLP library

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: SileroVAD detects speech boundary and returns AudioSegment
    Tool: Bash
    Preconditions: Virtual env active, mocked tests
    Steps:
      1. Run: pytest tests/test_silero_vad.py::test_process_chunk_returns_segment_on_speech -x -v --tb=short
      2. Assert test passes
      3. Verify test checks: AudioSegment.samples is concatenated audio, AudioSegment.duration_sec matches
    Expected Result: VAD correctly buffers audio and produces AudioSegment on speech end
    Failure Indicators: Test failure, incorrect segment duration, missing audio data
    Evidence: .sisyphus/evidence/task-3-speech-detection.txt

  Scenario: SileroVAD returns None on silence-only input
    Tool: Bash
    Preconditions: Virtual env active
    Steps:
      1. Run: pytest tests/test_silero_vad.py::test_process_chunk_silence_returns_none -x -v --tb=short
      2. Assert test passes
    Expected Result: No AudioSegment produced for silence
    Failure Indicators: Unexpected AudioSegment returned
    Evidence: .sisyphus/evidence/task-3-silence.txt

  Scenario: Short segments below min_speech_ms are discarded
    Tool: Bash
    Preconditions: Virtual env active
    Steps:
      1. Run: pytest tests/test_silero_vad.py -k "short" -x -v --tb=short
      2. Assert test passes
    Expected Result: Segments shorter than 250ms are filtered out
    Failure Indicators: Short segment not discarded
    Evidence: .sisyphus/evidence/task-3-short-filter.txt

  Scenario: All SileroVAD tests pass with mypy clean
    Tool: Bash
    Preconditions: Virtual env active
    Steps:
      1. Run: pytest tests/test_silero_vad.py -x -v --tb=short
      2. Assert exit code 0 with all tests passing
      3. Run: mypy src/vad/silero.py
      4. Assert exit code 0
    Expected Result: All tests pass, type annotations correct
    Failure Indicators: Test failures, mypy errors
    Evidence: .sisyphus/evidence/task-3-full-tests.txt
  ```

  **Commit**: YES
  - Message: `feat(vad): implement SileroVAD wrapper with chunk buffering`
  - Files: `src/vad/silero.py`, `tests/test_silero_vad.py`
  - Pre-commit: `ruff check src/vad/silero.py tests/test_silero_vad.py && mypy src/vad/silero.py && pytest tests/test_silero_vad.py -x`

- [ ] 4. Implement QwenASR wrapper

  **What to do**:
  - Create `src/asr/qwen_asr.py` with class `QwenASR`:
    - `__init__(self, model_path: str | None = None) -> None`
      - Default `model_path` to `"Qwen/Qwen3-ASR-0.6B"` if None
      - Load model: `from qwen_asr import Qwen3ASRModel; self._model = Qwen3ASRModel.from_pretrained(model_path, dtype=torch.bfloat16, device_map="cuda:0")`
      - Wrap loading errors in `ModelLoadError`
      - Log successful load with model path
    - `transcribe(self, audio: np.ndarray, sample_rate: int = 16000) -> str`
      - Guard: if model is None (unloaded), raise `ASRError("Model not loaded")`
      - Guard: if audio is empty or very short (<0.1s = <1600 samples at 16kHz), return `""`
      - Call `results = self._model.transcribe(audio=(audio, sample_rate), language="Japanese")`
      - Return `results[0].text.strip()`
      - Wrap inference errors in `ASRError`
    - `unload(self) -> None`
      - `del self._model; self._model = None`
      - `torch.cuda.empty_cache()`
      - Log that model has been unloaded
      - Note: `Qwen3ASRModel` has no native unload — this is manual cleanup
  - Use `logging.getLogger(__name__)` for logging
  - Import `ASRError`, `ModelLoadError` from `src.exceptions`

  - Create `tests/test_qwen_asr.py`:
    - Mock `qwen_asr.Qwen3ASRModel` class and its `from_pretrained` / `transcribe` methods
    - Test successful load: verify `from_pretrained` called with correct args
    - Test transcription: mock model returns `[Mock(text="テスト")]` → verify returns `"テスト"`
    - Test empty audio returns empty string (no model call)
    - Test very short audio (<1600 samples) returns empty string
    - Test `ModelLoadError` raised on load failure
    - Test `ASRError` raised on transcribe failure
    - Test `unload()` sets model to None and calls `torch.cuda.empty_cache()`
    - Test transcribe after unload raises `ASRError`

  **Must NOT do**:
  - No streaming ASR (`init_streaming_state`, `streaming_transcribe`) — batch mode only
  - No model downloading/management (assume model already cached or will auto-download on first `from_pretrained`)
  - No dependency on VAD or AudioCapture — pure audio-in, text-out interface
  - No language detection logic — always force `language="Japanese"`
  - No retry logic on failure

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Model wrapper with GPU concerns and non-trivial mocking (mock HuggingFace model loading)
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 2, 3)
  - **Blocks**: Task 5
  - **Blocked By**: Task 1

  **References**:

  **Pattern References** (existing code to follow):
  - `dev/demo.py:4-12` — **EXACT** model loading pattern to follow: `Qwen3ASRModel.from_pretrained("Qwen/Qwen3-ASR-0.6B", dtype=torch.bfloat16, device_map="cuda:0", max_inference_batch_size=32, max_new_tokens=256)`
  - `src/analysis/tokenizer.py` — Wrapper class pattern: __init__ loads model, method processes input

  **API/Type References** (contracts to implement against):
  - `src/exceptions.py:ASRError` — Base exception for transcription failures
  - `src/exceptions.py:ModelLoadError(ASRError)` — Exception for model loading failures
  - qwen-asr API: `Qwen3ASRModel.from_pretrained(model_id, **kwargs)`, `model.transcribe(audio=(np_array, sr), language="Japanese")` → `[ASRTranscription(text=str, language=str)]`

  **External References**:
  - qwen-asr package: `from qwen_asr import Qwen3ASRModel`
  - HuggingFace model: `Qwen/Qwen3-ASR-0.6B`

  **WHY Each Reference Matters**:
  - `dev/demo.py` is THE reference for loading — use exact kwargs (dtype, device_map, max_inference_batch_size, max_new_tokens)
  - `ASRError` / `ModelLoadError` are pre-defined in the exception hierarchy — must use them
  - The transcribe API returns a list — always index `[0]` for single-audio input

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: QwenASR loads model and transcribes successfully
    Tool: Bash
    Preconditions: Virtual env active, mocked tests
    Steps:
      1. Run: pytest tests/test_qwen_asr.py::test_transcribe_returns_text -x -v --tb=short
      2. Assert test passes
      3. Verify test mocks model.transcribe to return known text, asserts wrapper returns it
    Expected Result: Transcription returns cleaned text from model
    Failure Indicators: Test failure, wrong text returned
    Evidence: .sisyphus/evidence/task-4-transcribe.txt

  Scenario: Empty/short audio returns empty string without model call
    Tool: Bash
    Preconditions: Virtual env active
    Steps:
      1. Run: pytest tests/test_qwen_asr.py -k "empty or short" -x -v --tb=short
      2. Assert tests pass
      3. Verify model.transcribe was NOT called for empty/short audio
    Expected Result: Guard clauses prevent unnecessary GPU inference
    Failure Indicators: Model called with empty audio, exception raised
    Evidence: .sisyphus/evidence/task-4-empty-audio.txt

  Scenario: Error handling for load and transcribe failures
    Tool: Bash
    Preconditions: Virtual env active
    Steps:
      1. Run: pytest tests/test_qwen_asr.py -k "error or Error or fail" -x -v --tb=short
      2. Assert tests pass
      3. Verify ModelLoadError raised on load failure, ASRError on transcribe failure, ASRError on transcribe-after-unload
    Expected Result: All error paths produce correct exception types
    Failure Indicators: Wrong exception type, unhandled exception
    Evidence: .sisyphus/evidence/task-4-errors.txt

  Scenario: All QwenASR tests pass with mypy clean
    Tool: Bash
    Preconditions: Virtual env active
    Steps:
      1. Run: pytest tests/test_qwen_asr.py -x -v --tb=short
      2. Assert exit code 0
      3. Run: mypy src/asr/qwen_asr.py
      4. Assert exit code 0
    Expected Result: All tests pass, type annotations correct
    Failure Indicators: Test failures, mypy errors
    Evidence: .sisyphus/evidence/task-4-full-tests.txt
  ```

  **Commit**: YES
  - Message: `feat(asr): implement QwenASR wrapper for Qwen3-ASR-0.6B`
  - Files: `src/asr/qwen_asr.py`, `tests/test_qwen_asr.py`
  - Pre-commit: `ruff check src/asr/qwen_asr.py tests/test_qwen_asr.py && mypy src/asr/qwen_asr.py && pytest tests/test_qwen_asr.py -x`

- [ ] 5. Create PipelineWorker (Audio → VAD → ASR → Preprocessing)

  **What to do**:
  - Create `src/pipeline.py` with class `PipelineWorker(QThread)`:
    - `sentence_ready = Signal(object)` — emits `SentenceResult` (use `object` type for PySide6 compatibility)
    - `error_occurred = Signal(str)` — emits error message string for UI status display
    - `__init__(self, config: AppConfig) -> None`
      - Call `super().__init__()`
      - Initialize components:
        - `self._audio_capture = AudioCapture(sample_rate=config.sample_rate)`
        - `self._vad = SileroVAD(sample_rate=config.sample_rate)`
        - `self._asr = QwenASR()` — loads GPU model
        - `self._preprocessing = PreprocessingPipeline(config)`
      - `self._running = False`
      - `self._audio_queue: queue.Queue[np.ndarray] = queue.Queue()` — thread-safe queue for audio chunks
    - `run(self) -> None` — called by QThread.start()
      - Set `self._running = True`
      - Start audio capture with callback that enqueues chunks: `self._audio_capture.start(lambda chunk: self._audio_queue.put(chunk))`
      - Main loop while `self._running`:
        - Dequeue audio chunk from `self._audio_queue` with timeout (e.g., 0.1s) to allow checking `_running` flag
        - Feed chunk to `self._vad.process_chunk(chunk)`
        - If VAD returns `AudioSegment`(s):
          - For each segment, call `self._asr.transcribe(segment.samples)`
          - If transcription is non-empty, call `self._preprocessing.process(text)` → `AnalysisResult`
          - Build `SentenceResult(japanese_text=text, chinese_translation=None, explanation=None, analysis=analysis)`
          - Emit `self.sentence_ready.emit(result)`
        - Wrap ASR/preprocessing errors in try/except: log error, emit `error_occurred`, continue loop (don't crash thread)
      - On loop exit: cleanup (stop audio, reset VAD, unload ASR)
    - `stop(self) -> None`
      - Set `self._running = False`
      - Call `self.quit()` then `self.wait(timeout=5000)` for graceful shutdown
      - If still running after timeout, log warning
    - Error handling:
      - `AudioCaptureError` → emit `error_occurred("Audio capture failed: ...")`, stop
      - `ASRError` → log and skip that segment (continue processing next)
      - Other exceptions → log, emit error, continue
  - Use `logging.getLogger(__name__)` for logging
  - Imports: `from PySide6.QtCore import QThread, Signal`, all M2 modules, `PreprocessingPipeline`, `AppConfig`, `SentenceResult`, `AnalysisResult`

  - Create `tests/test_pipeline.py`:
    - Mock ALL components: AudioCapture, SileroVAD, QwenASR, PreprocessingPipeline
    - Test signal emission: mock components to produce a complete flow → verify `sentence_ready` signal emitted with correct `SentenceResult`
    - Test ASR failure handling: mock ASR to raise `ASRError` → verify thread continues, `error_occurred` emitted
    - Test empty transcription skipping: ASR returns `""` → verify no `sentence_ready` signal
    - Test stop/shutdown: start worker, call stop, verify `_running` is False and cleanup methods called
    - Test audio queue flow: verify audio callback enqueues, run loop dequeues
    - Use `QSignalSpy` or manual signal connection tracking for signal verification
    - NOTE: Need `QApplication` instance for PySide6 signals in tests — create as session-scoped fixture. For headless/WSL environment, set `QT_QPA_PLATFORM=offscreen` env var or use `QCoreApplication` instead of `QApplication` if no GUI needed.

  **Must NOT do**:
  - No DB writes — `SentenceResult` is emitted via signal only (DB integration deferred to M3)
  - No LLM integration — `chinese_translation=None, explanation=None` always (M3)
  - No error recovery/retry logic — log and skip on failure
  - No pipeline metrics/monitoring beyond basic logging
  - No new AppConfig fields — use existing `config.sample_rate`

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Integration of 4 components with thread safety (queue between PortAudio callback thread and QThread), signal emission, error handling, and graceful shutdown. Most complex task in M2.
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 3 (solo — depends on all Wave 2 tasks)
  - **Blocks**: Final Verification
  - **Blocked By**: Tasks 2, 3, 4

  **References**:

  **Pattern References** (existing code to follow):
  - `src/analysis/pipeline.py` — PreprocessingPipeline interface: `process(text: str) -> AnalysisResult`
  - `src/audio/capture.py` (Task 2) — AudioCapture interface: `start(callback)`, `stop()`, callback receives `np.ndarray`
  - `src/vad/silero.py` (Task 3) — SileroVAD interface: `process_chunk(audio) -> list[AudioSegment] | None`, `reset()`
  - `src/asr/qwen_asr.py` (Task 4) — QwenASR interface: `transcribe(audio, sample_rate) -> str`, `unload()`

  **API/Type References** (contracts to implement against):
  - `src/db/models.py:SentenceResult` — Output type: `SentenceResult(japanese_text, chinese_translation, explanation, analysis, created_at)`
  - `src/db/models.py:AnalysisResult` — From PreprocessingPipeline.process()
  - `src/db/models.py:AudioSegment` — From SileroVAD.process_chunk()
  - `src/config.py:AppConfig` — Configuration with `sample_rate` field
  - `src/exceptions.py` — `AudioCaptureError`, `ASRError`, `VADError` for error handling
  - PySide6 API: `QThread` subclassing, `Signal(object)`, `self.quit()`, `self.wait()`

  **Test References**:
  - `tests/test_analysis_pipeline.py` — Test structure pattern
  - PySide6 testing: Need `QApplication` instance before any `Signal` can be used — create as `@pytest.fixture(scope="session")`

  **WHY Each Reference Matters**:
  - All 4 component interfaces are composed here — exact method signatures must match
  - `SentenceResult` fields must be correctly populated (chinese_translation=None for M2)
  - QThread lifecycle (start→run→quit→wait) must be correct for clean shutdown
  - Error handling must use the exact exception types from the hierarchy
  - Queue-based audio handoff is critical for thread safety between sounddevice callback and QThread

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Full pipeline flow with mocked components
    Tool: Bash
    Preconditions: Virtual env active, all mocks in place
    Steps:
      1. Run: pytest tests/test_pipeline.py::test_pipeline_emits_sentence_result -x -v --tb=short
      2. Assert test passes
      3. Verify test: mock audio→VAD returns AudioSegment→ASR returns "テスト"→preprocessing returns AnalysisResult→signal emitted with SentenceResult containing japanese_text="テスト", chinese_translation=None
    Expected Result: Complete pipeline flow produces correct SentenceResult
    Failure Indicators: Signal not emitted, wrong fields, exception
    Evidence: .sisyphus/evidence/task-5-full-flow.txt

  Scenario: ASR error handling — log and continue
    Tool: Bash
    Preconditions: Virtual env active
    Steps:
      1. Run: pytest tests/test_pipeline.py::test_asr_error_continues_processing -x -v --tb=short
      2. Assert test passes
      3. Verify: ASR raises ASRError → error_occurred signal emitted → thread continues running
    Expected Result: Pipeline survives ASR failure without crashing
    Failure Indicators: Thread dies, unhandled exception
    Evidence: .sisyphus/evidence/task-5-asr-error.txt

  Scenario: Empty transcription skipped
    Tool: Bash
    Preconditions: Virtual env active
    Steps:
      1. Run: pytest tests/test_pipeline.py -k "empty" -x -v --tb=short
      2. Assert test passes
      3. Verify: ASR returns "" → sentence_ready NOT emitted
    Expected Result: No SentenceResult for empty transcriptions
    Failure Indicators: Signal emitted with empty japanese_text
    Evidence: .sisyphus/evidence/task-5-empty-skip.txt

  Scenario: Clean shutdown
    Tool: Bash
    Preconditions: Virtual env active
    Steps:
      1. Run: pytest tests/test_pipeline.py::test_stop_cleans_up -x -v --tb=short
      2. Assert test passes
      3. Verify: stop() → _running=False, audio_capture.stop() called, vad.reset() called, asr.unload() called
    Expected Result: All resources properly cleaned up
    Failure Indicators: Resource leak, hanging thread
    Evidence: .sisyphus/evidence/task-5-shutdown.txt

  Scenario: All PipelineWorker tests pass with mypy clean
    Tool: Bash
    Preconditions: Virtual env active
    Steps:
      1. Run: pytest tests/test_pipeline.py -x -v --tb=short
      2. Assert exit code 0
      3. Run: mypy src/pipeline.py
      4. Assert exit code 0
    Expected Result: All tests pass, type annotations correct
    Failure Indicators: Test failures, mypy errors
    Evidence: .sisyphus/evidence/task-5-full-tests.txt
  ```

  **Commit**: YES
  - Message: `feat(pipeline): implement PipelineWorker Audio→VAD→ASR→Preprocessing`
  - Files: `src/pipeline.py`, `tests/test_pipeline.py`
  - Pre-commit: `ruff check src/pipeline.py tests/test_pipeline.py && mypy src/pipeline.py && pytest tests/test_pipeline.py -x`

---

## Final Verification Wave

> 4 review agents run in PARALLEL. ALL must APPROVE. Rejection → fix → re-run.

- [ ] F1. **Plan Compliance Audit** — `oracle`
  Read the plan end-to-end. For each "Must Have": verify implementation exists (read file, run command). For each "Must NOT Have": search codebase for forbidden patterns — reject with file:line if found. Check evidence files exist in `.sisyphus/evidence/`. Compare deliverables against plan.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [ ] F2. **Code Quality Review** — `unspecified-high`
  Run `ruff check . && ruff format --check . && mypy . && pytest -x --tb=short`. Review all changed files for: `as any`/`# type: ignore` (justify each), empty catches, console.log in prod, commented-out code, unused imports. Check AI slop: excessive comments, over-abstraction, generic names.
  Output: `Build [PASS/FAIL] | Lint [PASS/FAIL] | Tests [N pass/N fail] | Files [N clean/N issues] | VERDICT`

- [ ] F3. **Integration QA** — `unspecified-high`
  Execute EVERY QA scenario from EVERY task — follow exact steps, capture evidence. Test cross-task integration: mock full pipeline flow (audio chunks → VAD segments → ASR text → preprocessing → SentenceResult signal). Save to `.sisyphus/evidence/final-qa/`.
  Output: `Scenarios [N/N pass] | Integration [N/N] | Edge Cases [N tested] | VERDICT`

- [ ] F4. **Scope Fidelity Check** — `deep`
  For each task: read "What to do", read actual diff (git log/diff). Verify 1:1 — everything in spec was built (no missing), nothing beyond spec was built (no creep). Check "Must NOT do" compliance. Detect cross-task contamination. Flag unaccounted changes.
  Output: `Tasks [N/N compliant] | Contamination [CLEAN/N issues] | Unaccounted [CLEAN/N files] | VERDICT`

---

## Commit Strategy

| After Task | Message | Files |
|-----------|---------|-------|
| 1 | `feat(models): add AudioSegment dataclass for VAD→ASR handoff` | `src/db/models.py` |
| 2 | `feat(audio): implement AudioCapture with sounddevice` | `src/audio/capture.py`, `tests/test_audio_capture.py` |
| 3 | `feat(vad): implement SileroVAD with audio buffering` | `src/vad/silero.py`, `tests/test_silero_vad.py` |
| 4 | `feat(asr): implement QwenASR wrapper for Qwen3-ASR 0.6B` | `src/asr/qwen_asr.py`, `tests/test_qwen_asr.py` |
| 5 | `feat(pipeline): implement PipelineWorker QThread orchestrator` | `src/pipeline.py`, `tests/test_pipeline.py` |

Pre-commit for each: `ruff check {files} && mypy {files} && pytest tests/test_{module}.py -x`

---

## Success Criteria

### Verification Commands
```bash
# Per-module verification
pytest tests/test_audio_capture.py -x && mypy src/audio/capture.py
pytest tests/test_silero_vad.py -x && mypy src/vad/silero.py
pytest tests/test_qwen_asr.py -x && mypy src/asr/qwen_asr.py
pytest tests/test_pipeline.py -x && mypy src/pipeline.py

# Full milestone verification
ruff check . && ruff format --check . && mypy . && pytest -x --tb=short
```

### Final Checklist
- [ ] All "Must Have" items present and working
- [ ] All "Must NOT Have" items absent (verified by grep/search)
- [ ] All 4 test files pass (pytest exit code 0)
- [ ] mypy clean on all new files
- [ ] ruff clean on all new files
- [ ] No top-level `import sounddevice` anywhere
- [ ] PipelineWorker emits correct SentenceResult via signal
