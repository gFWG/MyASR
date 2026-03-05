# Learnings — m2-asr-integration

## 2026-03-05 Session ses_342f345e4ffebB7MyKH28Xenxo

### Project State
- Python 3.12 venv at ~/.venvs/myasr
- src/analysis/pipeline.py PreprocessingPipeline exists and imports OK
- src/exceptions.py: AudioCaptureError, VADError, ASRError, ModelLoadError all exist
- src/config.py: AppConfig dataclass with sample_rate=16000, db_path fields
- src/db/models.py: SentenceResult exists. NO numpy import yet.
- src/asr/__init__.py exists (empty), src/audio/ and src/vad/ exist but empty
- dev/demo.py shows Qwen3ASRModel.from_pretrained API

### Key Technical Constraints
- NO top-level `import sounddevice` anywhere (lazy import only inside methods)
- Use VADIterator, NOT get_speech_timestamps()
- Signal(object) not Signal(SentenceResult) for PySide6 compat
- Qwen3ASRModel has no unload() — use `del + torch.cuda.empty_cache()`
- blocksize=512 critical for VAD compatibility
- WSL/CI: set QT_QPA_PLATFORM=offscreen for PySide6 tests
- thread-safe queue.Queue between audio callback and QThread

### Qwen3ASR API (from dev/demo.py)
```python
from qwen_asr import Qwen3ASRModel
model = Qwen3ASRModel.from_pretrained('Qwen/Qwen3-ASR-0.6B',
    dtype=torch.bfloat16, device_map='cuda:0',
    max_inference_batch_size=32, max_new_tokens=256)
results = model.transcribe(audio='path_or_(np.ndarray, sr)', language='Japanese')
# results[0].text.strip()
```

### Code Style (from AGENTS.md)
- ruff, line length 99, double quotes, trailing commas in multi-line
- mypy strict, Python 3.12+ type syntax (X | None, list[], dict[])
- Google docstrings for public classes/functions
- Module logger: logger = logging.getLogger(__name__)
- pytest fixtures, mock external I/O
## [2026-03-05] Task 1: AudioSegment

- Added `AudioSegment` dataclass to `src/db/models.py` for VAD → ASR handoff
- Import order: stdlib → third-party (numpy) → local
- Dataclass has two fields: `samples: np.ndarray` and `duration_sec: float`
- Docstring documents expected format (float32 at 16kHz) and purpose
- Ruff passed with no changes needed
- QA test passed: instantiation with np.zeros(16000, dtype='float32') works correctly

## [2026-03-05] Task 2: AudioCapture

### Lazy import pattern
- `sounddevice` is imported inside `start()` and `list_devices()` only — NOT at module top level.
- This allows `from src.audio.capture import AudioCapture` to succeed even if sounddevice is absent.
- ruff rule PLC0415 (import-outside-toplevel) must be suppressed with `# noqa: PLC0415` on lazy imports.

### sys.modules mock pattern for tests
- To mock sounddevice before it is ever imported, use `patch.dict("sys.modules", {"sounddevice": mock})` in a fixture.
- Tests that import `AudioCapture` inside the fixture's `with` block see the mock automatically.
- This avoids needing sounddevice installed in CI.

### sounddevice InputStream callback shape
- `indata` passed by sounddevice has shape `(blocksize, channels)`.
- Mono extraction: `indata[:, 0].copy()` — `.copy()` is required since the buffer is reused.

### Double-start guard
- Check `self._stream is not None` before creating a new stream; raise `AudioCaptureError("already running")`.
- On failure inside `start()`, reset `self._stream = None` and `self._user_callback = None` to stay consistent.

### blocksize=512
- Critical for downstream VAD (Silero chunk-size requirement). Do not change.

## [2026-03-05] Task 3: SileroVAD

### VADIterator Actual API (silero-vad installed version)
- `__init__(self, model, threshold=0.5, sampling_rate=16000, min_silence_duration_ms=100, speech_pad_ms=30)`
- `__call__(self, x, return_seconds=False, time_resolution=1)`
  - `x`: torch.Tensor of raw audio chunk (float32)
  - Returns `{"start": int}`, `{"end": int}`, or `None`
  - `start`/`end` are sample indices when `return_seconds=False`
  - Note: task spec said `min_silence_ms=500` default but VADIterator own default is 100ms; wrapper correctly passes `min_silence_ms` through

### Pattern: SileroVAD wraps VADIterator with internal buffering
- `process_chunk(audio)` → accumulates `np.ndarray` copies in `self._audio_buffer`
- On `"start"` dict: sets `_is_speech=True`, records `_speech_start_sample`
- On `"end"` dict: concatenates buffer, creates `AudioSegment`, clears buffer
- Force-cut at 30s: guards against unbounded speech; calls `reset_states()` after
- Short segment filter: `_min_speech_samples` threshold; discard without returning

### Testing pattern: mock silero_vad module
```python
@pytest.fixture
def mock_silero(monkeypatch):
    mock_model = MagicMock()
    mock_iterator = MagicMock()
    mock_iterator.return_value = None
    with (
        patch("src.vad.silero.load_silero_vad", return_value=(mock_model, None)) as mock_load,
        patch("src.vad.silero.VADIterator", return_value=mock_iterator) as mock_vad_iter,
    ):
        yield mock_load, mock_vad_iter, mock_iterator
```
- Do NOT mock torch — use real `torch.from_numpy().float()` tensors
- Fixture uses `monkeypatch` param but patches via `patch` context manager (both work)
- Import `SileroVAD` INSIDE each test (after mocks applied) to avoid module caching issues

### ruff auto-fix
- `ruff check --fix` resolved I001 (import sort) in test file automatically
- stdlib imports before third-party: `from unittest.mock import ...` must come after stdlib section separator but before numpy/pytest in isort order → ruff reorders correctly

## [2026-03-05] Task 4: QwenASR

### Lazy import pattern for GPU-only packages
- `qwen_asr.Qwen3ASRModel` MUST be imported inside `__init__` (not at module level)
- Reason: package is GPU-only; top-level import would crash on CPU-only test runners
- Pattern: `from qwen_asr import Qwen3ASRModel as _Qwen3ASRModel` inside try/except in __init__

### mypy: Any return value fix
- `results[0].text` is `Any` (dynamic model output) → causes `no-any-return` error
- Fix: wrap with `str(results[0].text).strip()` to explicitly coerce to str
- Type hint `self._model` as `Any | None` (import Any from typing)

### Test isolation for torch re-import issue
- torch has internal state that errors if its module is re-executed in the same process
- Error: `RuntimeError: function '_has_torch_function' already has a docstring`
- Root cause: `from src.asr.qwen_asr import QwenASR` inside each test function caused
  `src.asr.qwen_asr` to be re-loaded (after fixture's patch.dict cleared the mock)
- Fix: fixture pops `src.asr.qwen_asr` from `sys.modules` INSIDE the `patch.dict` context,
  then imports `QwenASR` and yields it — tests receive the class directly
- Import `torch` at top level of test file (not mocked, real torch is installed)

### Mock pattern for sys.modules-level patching
```python
with patch.dict("sys.modules", {"qwen_asr": MagicMock(Qwen3ASRModel=mock_model_cls)}):
    sys.modules.pop("src.asr.qwen_asr", None)   # force fresh module load under mock
    from src.asr.qwen_asr import QwenASR
    yield QwenASR, mock_model_cls, mock_model_inst, mock_result
```

### unload() implementation
- `Qwen3ASRModel` has no built-in unload method
- Pattern: `del self._model; self._model = None; torch.cuda.empty_cache()`

## [2026-03-05] Task 5: PipelineWorker

### QThread Testing Pattern
- Never call `.start()` in tests — run `worker.run()` directly for synchronous execution.
- For `AudioCaptureError` at startup, `run()` emits `error_occurred` and returns — loop never executes.
- Connect signals to `list.append` before calling `run()` to capture emitted values.
- `QT_QPA_PLATFORM=offscreen` must be set at module level (`os.environ[...]`) in the test file, before any PySide6 import.
- Session-scoped `QApplication` fixture prevents multiple QApp creation across tests.

### Signal Mocking Pattern
- Mock at `src.pipeline.AudioCapture` / `src.pipeline.SileroVAD` / `src.pipeline.QwenASR` / `src.pipeline.PreprocessingPipeline` — NOT at their source module paths.
- `mock_audio.start.side_effect = fake_start` lets tests capture the callback passed by `run()`.

### queue.Queue in QThread
- `queue.Queue(timeout=0.1)` in the run loop allows `_running = False` to break the loop within 100ms — avoids blocking test teardown.
- Put chunks into `worker._audio_queue` directly in tests to simulate audio input without real sounddevice.

### _cleanup() design
- Called at end of `run()` regardless of how the loop exits (normal stop or exception).
- Each cleanup step wrapped in its own try/except with `logger.warning` — one failure doesn't block others.
