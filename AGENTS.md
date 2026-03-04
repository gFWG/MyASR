# AGENTS.md — MyASR Japanese Learning Overlay

## Project Overview

Desktop overlay app for Japanese language learning. Captures system audio → VAD → ASR → morphological analysis → JLPT vocab/grammar lookup → LLM translation → transparent PySide6 overlay UI with SQLite learning records.

**Stack**: Python 3.12+, CUDA 12.x, PySide6, Silero VAD, Qwen3-ASR (0.6B), fugashi, Ollama (qwen3-4b), SQLite  
**Platform**: Windows 11 (target), developed in WSL2 + Ubuntu 22.04  
**GPU**: 12GB VRAM minimum  

## Environment Setup

```bash
# Virtual environment (project convention)
python3.12 -m venv ~/.venvs/myasr
source ~/.venvs/myasr/bin/activate

# Install dependencies (when requirements.txt exists)
pip install -r requirements.txt

# Ollama must be running for LLM features
# ollama serve  (localhost:11434)
```

## API compatibility rule
- If you call any 3rd-party API you are not 100% sure about:
  1) Verify installed version with importlib.metadata.version(pkg)
  2) Verify the callable via help() / inspect.signature() in THIS env
  3) If still uncertain, search the OFFICIAL docs/release notes for that exact version;
     if you cannot find version-matching docs, stop and ask me.

## Build / Lint / Test Commands

```bash
# Lint
ruff check .                       # lint all
ruff check path/to/file.py        # lint single file
ruff check --fix .                 # auto-fix

# Format
ruff format .                      # format all
ruff format path/to/file.py       # format single file

# Type checking
mypy .                             # check all
mypy path/to/file.py              # check single file

# Tests
pytest                             # run all tests
pytest tests/test_foo.py           # run single test file
pytest tests/test_foo.py::test_bar # run single test function
pytest -x                          # stop on first failure
pytest -x --tb=short               # stop on first failure, short traceback
pytest --co                        # list tests without running (dry run)

# Quick validation cycle
ruff check . && ruff format --check . && mypy . && pytest
```

## Project Structure (Planned)

```
MyASR/
├── AGENTS.md
├── docs/
│   └── PRD.md              # Product requirements (source of truth)
├── src/                    # Main application source
│   ├── audio/              # Audio capture (sounddevice/pyaudiowpatch)
│   ├── vad/                # Voice Activity Detection (Silero)
│   ├── asr/                # Speech recognition (Qwen3-ASR 0.6B)
│   ├── analysis/           # Morphological analysis (fugashi), JLPT lookup
│   ├── grammar/            # Grammar pattern matching (regex, CSV→JSON rules)
│   ├── llm/                # Ollama client (qwen3-4b, localhost:11434)
│   ├── ui/                 # PySide6 overlay, tooltip, settings
│   ├── db/                 # SQLite learning records
│   └── main.py             # Entry point
├── tests/                  # Mirror src/ structure
├── data/                   # JLPT vocab dict, grammar rules CSV/JSON
└── requirements.txt
```

## Code Style

### Formatting & Linting

- **Formatter/Linter**: ruff (replaces black + isort + flake8)
- **Line length**: 99 characters
- **Quotes**: Double quotes (`"string"`)
- **Trailing commas**: Always in multi-line structures
- **Type checker**: mypy in strict mode

### Imports

```python
# Order: stdlib → third-party → local, separated by blank lines
# Use absolute imports. No relative imports except within a package.
import os
import sys
from pathlib import Path

import numpy as np
import torch
from PySide6.QtWidgets import QApplication

from src.audio.capture import AudioCapture
from src.vad.silero import SileroVAD
```

### Typing

```python
# All public functions MUST have type annotations
# Use modern syntax (Python 3.12+): list[], dict[], tuple[], X | None
def process_audio(samples: np.ndarray, sample_rate: int = 16000) -> list[str]:
    ...

# Use TypeAlias or type statement for complex types
type AudioCallback = Callable[[np.ndarray, int], None]

# Avoid Any. If truly needed, comment why.
```

### Naming Conventions

```python
# Modules/files: snake_case
# Classes: PascalCase
# Functions/methods/variables: snake_case
# Constants: UPPER_SNAKE_CASE
# Private: single underscore prefix (_internal_method)
# Type aliases: PascalCase

SAMPLE_RATE = 16000
MAX_AUDIO_BUFFER_SEC = 30

class AudioCapture:
    def __init__(self, device_id: int | None = None) -> None:
        self._buffer: list[np.ndarray] = []

    def start_capture(self) -> None: ...
```

### Error Handling

```python
# Use specific exceptions, never bare except
# Create custom exceptions in src/exceptions.py when needed
# Let unexpected errors propagate — don't swallow them
# Log errors with context before re-raising when appropriate

class ASRError(Exception):
    """Base exception for ASR pipeline errors."""

class ModelLoadError(ASRError):
    """Failed to load ASR/VAD model."""

try:
    model = load_model(path)
except FileNotFoundError:
    logger.error("Model not found: %s", path)
    raise ModelLoadError(f"Model file missing: {path}") from None
```

### Logging

```python
# Use stdlib logging, not print()
# Module-level logger: logger = logging.getLogger(__name__)
# Use lazy formatting (logger.info("x=%s", x) not f-strings)
import logging

logger = logging.getLogger(__name__)
logger.info("Processing %d samples at %dHz", len(samples), rate)
```

### Docstrings

```python
# Google style. Required for public classes and non-trivial public functions.
# Skip for obvious one-liners, test functions, and private helpers.
def lookup_jlpt(word: str) -> JLPTEntry | None:
    """Look up a word in the JLPT vocabulary dictionary.

    Args:
        word: Dictionary form of the Japanese word.

    Returns:
        JLPT entry with level and readings, or None if not found.
    """
```

### Testing

```python
# Use pytest. No unittest.TestCase classes.
# File naming: tests/test_<module>.py
# Function naming: test_<what>_<condition>_<expected>
# Use fixtures for shared setup. Parametrize for variants.
# Mock external I/O (models, Ollama API, audio devices, SQLite)

def test_vad_detect_speech_returns_segments():
    samples = load_test_audio("speech_sample.wav")
    segments = vad.detect(samples)
    assert len(segments) > 0
    assert all(s.start < s.end for s in segments)

@pytest.mark.parametrize("word,expected_level", [
    ("食べる", 5),
    ("概念", 1),
])
def test_jlpt_lookup_returns_correct_level(word, expected_level):
    entry = lookup_jlpt(word)
    assert entry is not None
    assert entry.level == expected_level
```

## Architecture Guidelines

- **No complex architecture**. Simple modules with clear interfaces. No abstract base classes unless genuinely needed by 3+ implementations.
- **Pipeline is sequential**: Audio → VAD → ASR → Analysis → LLM → UI. Each stage is a separate module with a clean function/class interface.
- **Offline-first**: ASR and VAD run locally on GPU. Only Ollama (localhost) for LLM.
- **UI thread separation**: PySide6 main thread for UI only. Audio pipeline runs in separate thread(s). Use Qt signals/slots for thread communication.
- **Data files**: JLPT vocab as dict for O(1) lookup. Grammar rules: CSV source → JSON at build time. Load once at startup.
- **SQLite**: Use stdlib `sqlite3`. No ORM. Keep schema in a migration file.

## Git Conventions

- Keep commits atomic and descriptive
- Do not commit model weights, audio files, or binary data

## Key Technical Decisions (from PRD)

- ASR: Qwen3-ASR 0.6B (offline, batch mode, not streaming)
- VAD: Silero VAD (lightweight, CPU-friendly)
- Morphological analysis: fugashi + unidic-lite
- LLM: Ollama qwen3-4b-2507 via REST API (localhost:11434)
- UI: PySide6 transparent frameless overlay with rounded tooltip
- Audio: sounddevice (Linux/dev) + pyaudiowpatch (Windows loopback)
