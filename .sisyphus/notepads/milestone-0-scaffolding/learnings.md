## [2026-03-04] Task 2: Package Structure
Created 10 empty package marker files:
- src/__init__.py (0 bytes)
- src/audio/__init__.py (0 bytes)
- src/vad/__init__.py (0 bytes)
- src/asr/__init__.py (0 bytes)
- src/analysis/__init__.py (0 bytes)
- src/llm/__init__.py (0 bytes)
- src/ui/__init__.py (0 bytes)
- src/db/__init__.py (0 bytes)
- tests/__init__.py (0 bytes)
- data/.gitkeep (0 bytes)

All packages verified importable. No forbidden files (src/grammar/, __main__.py, conftest.py) present.
## [2026-03-04] Task 1: Tooling Config

Created 4 files:
- `.gitignore`: Replaced whitelist approach (`*.*` / `!*.md` / `!*.py`) with standard Python gitignore
- `pyproject.toml`: Tool config only (ruff, mypy, pytest) - NO [project] or [build-system]
- `requirements.txt`: 10 bare package names (torch, torchaudio, sounddevice, silero-vad, fugashi, unidic-lite, jreadability, PySide6, requests, numpy)
- `requirements-dev.txt`: 4 bare dev package names (ruff, mypy, pytest, pytest-mock)

Verifications passed:
- `git check-ignore pyproject.toml` → NOT ignored ✓
- `git check-ignore requirements.txt` → NOT ignored ✓
- `git check-ignore data/.gitkeep` → NOT ignored ✓
- `git check-ignore __pycache__/foo.pyc` → IS ignored ✓
- `python3 -c "import tomllib..."` → Valid TOML ✓

## [2026-03-04] Task 3: Exception Hierarchy
Created `src/exceptions.py` with 10 exception classes:
- Base: `MyASRError`
- Direct subclasses: `AudioCaptureError`, `VADError`, `ASRError`, `PreprocessingError`, `LLMError`, `DatabaseError`
- `ASRError` subclass: `ModelLoadError`
- `LLMError` subclasses: `LLMTimeoutError`, `LLMUnavailableError`

All classes are bare subclasses with only docstrings. Verified with:
- `python3 -c` imports: OK
- Hierarchy assertions: OK
- `mypy` check: OK (no errors)
## [2026-03-04] Task 4: Config Module
Created src/config.py with AppConfig dataclass (10 fields), load_config(), and save_config(). 
Created tests/test_config.py with 6 tests covering defaults, missing file, malformed JSON, roundtrip, partial JSON, and parent dir creation.
All 6 tests pass. mypy strict mode passes with no errors. No type: ignore needed for AppConfig(**defaults) pattern.

