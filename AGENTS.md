# PROJECT KNOWLEDGE BASE

**Generated:** 2026-03-11
**Commit:** 90039ef
**Branch:** main

## OVERVIEW

MyASR — Japanese learning overlay for Windows 11. Real-time audio capture → VAD → ASR → JLPT analysis → transparent PySide6 overlay with color-coded highlights and SQLite learning records. Python 3.12, CUDA 12.x, 12GB+ VRAM.

## STRUCTURE

```
MyASR/
├── src/                    # Main package (imported as `from src...`)
│   ├── main.py             # Entry point: python src/main.py
│   ├── config.py           # AppConfig dataclass + load/save data/config.json
│   ├── exceptions.py       # MyASRError hierarchy
│   ├── pipeline/           # Current pipeline: orchestrator + QThread workers
│   ├── ui/                 # PySide6 overlay, tooltip, settings, tray, learning panel
│   ├── asr/                # Qwen3-ASR 0.6B wrapper (offline, batch)
│   ├── vad/                # Silero VAD (ONNX)
│   ├── audio/              # Audio capture ABC + WASAPI loopback backend
│   ├── db/                 # SQLite schema + models + repository
│   ├── analysis/           # fugashi tokenizer → JLPT vocab O(1) → grammar regex
│   └── profiling/          # Pipeline timing/statistics utilities
├── tests/                  # pytest suite (29 files, mirrors src/ structure)
├── dev/                    # Dev scripts, test audio, project notes
├── docs/                   # scope.md (project spec)
├── data/                   # Runtime state: config.json, myasr.db (gitignored)
├── pyproject.toml          # Ruff + mypy + pytest config (NO [project] metadata)
├── requirements.txt        # Dependencies
└── requirements.lock.txt   # Pinned dependencies
```

## WHERE TO LOOK

| Task | Location | Notes |
|------|----------|-------|
| Add new pipeline stage | `src/pipeline/` | Follow QThread worker pattern (see vad_worker, asr_worker) |
| Modify UI layout | `src/ui/overlay.py` | Transparent QWidget, rich HTML text |
| Add JLPT analysis | `src/analysis/` | PreprocessingPipeline orchestrates tokenizer→vocab→grammar |
| Change DB schema | `src/db/schema.py` | Then update models.py + repository.py |
| Add audio backend | `src/audio/` | Implement `AudioCapture` duck-type interface |
| Wire new signal | `src/main.py` | All signal wiring happens here |
| Add test | `tests/test_{module}.py` | Match existing conftest.py fixtures |

## CONVENTIONS

- **Package name is `src`** — imports are `from src.pipeline.orchestrator import ...`
- **Lazy imports** for heavy/optional deps with `# noqa: PLC0415`
- **Env vars before imports** with `# noqa: E402` (e.g., HF_HUB_OFFLINE=1 in qwen_asr.py)
- **Frozen dataclasses**: `@dataclass(frozen=True, slots=True)` for pipeline DTOs
- **Type hints**: Python 3.12 syntax (`type X = ...`), mypy strict mode
- **Docstrings**: Google style (Args: / Returns:)
- **Ruff**: line-length=99, double quotes, E/F/W/I rules, isort with `src` first-party
- **Qt signals**: QThread workers communicate via Qt signals, never direct method calls
- **Queue pattern**: `queue.Queue` between pipeline stages, non-blocking puts

## ANTI-PATTERNS

- **DO NOT** use streaming ASR — batch mode is intentional (accuracy > latency)
- **DO NOT** add multi-language support — Japanese only by design
- **DO NOT** suppress types with `as any` / `@ts-ignore` / `type: ignore`
- **DO NOT** import heavy ML libs at module level — use lazy imports
- **DO NOT** hardwire Windows-only code without checking `src/audio/capture.py` ABC pattern

## UNIQUE STYLES

- WSL2+Ubuntu dev environment targeting Windows 11 runtime — test with `pytest`, deploy on Windows
- PyAudioWPatch is Windows-only; sounddevice is cross-platform fallback
- UI follows Microsoft Design System principles
- Model files (*.onnx, *.pt, *.bin) and audio (*.wav) are gitignored
- `data/` directory is runtime state (config.json, myasr.db) — created at first run

## COMMANDS

```bash
# Lint
ruff check . && ruff format --check .

# Type check
mypy src/

# Test
pytest tests/

# Run
python src/main.py
```

## NOTES

- No `[project]` section in pyproject.toml — not an installable package
- `pytest` uses `pythonpath = ["."]` to resolve `from src...` imports
- Processing speed must exceed acquisition speed (real-time constraint)
