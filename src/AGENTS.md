# SRC PACKAGE KNOWLEDGE BASE

## OVERVIEW

Main application package. Imported as `from src...`. Entry point: main.py.

## STRUCTURE

### Standalone Modules
- `main.py`: App entry point. Wires all Qt signals and initializes components.
- `config.py`: `AppConfig` central frozen dataclass for app-wide settings.
- `exceptions.py`: `MyASRError` hierarchy (AudioCapture, VAD, ASR, ModelLoad, Preprocessing, Database).
- `pipeline_legacy.py`: DEPRECATED monolithic pipeline. Use `src/pipeline/` instead.

### Subpackages
- `pipeline/`: Orchestrator and QThread workers (VAD, ASR, etc.).
- `ui/`: PySide6 windows, settings, tray, and learning panel.
- `asr/`: Qwen3-ASR 0.6B wrapper for offline inference.
- `vad/`: Silero VAD (ONNX) implementation.
- `audio/`: Audio capture backends (WASAPI/SoundDevice).
- `db/`: SQLite schema, models, and repository.
- `analysis/`: Fugashi tokenizer and JLPT highlights logic.
- `profiling/`: Pipeline timing and performance metrics.

## WHERE TO LOOK

- **Wire new signal**: Always in `src/main.py`.
- **Add config field**: Update `AppConfig` in `src/config.py`.
- **New error type**: Add to `src/exceptions.py`.
- **New feature**: Find relevant subpackage or create one if orthogonal.

## CONVENTIONS

- **Imports**: Always use absolute imports starting with `src.` (e.g., `from src.ui.overlay import ...`).
- **Lazy Imports**: Heavy ML or platform-specific libraries must be imported inside methods/functions.
- **Signals**: Qt signals are the primary communication bridge between background threads and UI.

## NOTES

- `pipeline_legacy.py` is kept only for reference during the migration to the modular orchestrator.
- Database operations are abstracted via the repository pattern in `src/db/`.
