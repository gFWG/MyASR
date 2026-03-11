# TEST SUITE KNOWLEDGE BASE

**Generated:** 2026-03-11
**Path:** `tests/`

## OVERVIEW

Pytest suite mirroring `src/` structure. Validates pipeline, UI, and analysis in a headless WSL2 environment.

## STRUCTURE

- **Mirroring:** 29 files, e.g., `tests/test_config.py` tests `src/config.py`.
- **`conftest.py`:** Shared session-scope fixtures for Qt and audio.
- **`dev/`:** Source for test artifacts (`short.wav`, `long.wav`).

## CONVENTIONS

- **Imports:** Uses `pythonpath = ["."]` in `pyproject.toml` to allow `from src...`.
- **Async:** `asyncio_mode = "auto"` enabled globally.
- **Headless UI:** PySide6 tests run via `qapp` fixture. No physical display required.
- **Mocks:** Extensive `unittest.mock` usage for GPU models (VAD/ASR) and Windows-only WASAPI backends.
- **Numpy:** `np.testing` for audio buffer comparisons.

## FIXTURES

- `qapp` / `qt_app`: Session-scope `QApplication` for widget/worker event loops.
- `short_wav`: Loads `dev/short.wav` as mono `float32` array + sample rate.
- `long_wav`: Loads `dev/long.wav` for stress/batch testing.

## MARKERS

- `@pytest.mark.slow`: Long-running tests (processing actual wav files).
- `@pytest.mark.gpu`: Tests requiring CUDA (e.g., raw model inference).

## ADDING A TEST

1. Create `tests/test_{module}.py` to match `src/{module}.py`.
2. Mock heavy dependencies (models, capture devices) using `patch`.
3. Use `qapp` fixture if testing any class inheriting from `QObject` or `QWidget`.
4. Ensure `lsp_diagnostics` are clean before committing.

## NOTES

- WSL2 lacks WASAPI; always mock `WasapiLoopbackCapture` or use the `AudioCapture` duck-type interface.
- Pipeline workers communicate via signals; use `MagicMock` to verify signal connections.
- Keep `data/` clean; use `tmp_path` for config/DB write tests.
