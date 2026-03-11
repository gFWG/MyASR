# ASR MODULE KNOWLEDGE BASE

## OVERVIEW

Offline-first Japanese ASR. Wraps Qwen3-ASR 0.6B model for high-accuracy batch transcription. Prioritizes accuracy over latency.

## STRUCTURE

- `qwen_asr.py`: `QwenASR` wrapper. Loads model once, reuses for inference.
- `__init__.py`: Package marker.

## CONVENTIONS

- **Lazy Imports**: `torch`, `transformers`, and `qwen_asr` are imported inside `QwenASR.__init__` to avoid heavy startup overhead.
- **Offline Mode**: `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1` are set before imports with `# noqa: E402`.
- **GPU Management**: Uses `torch.bfloat16` and `device_map="cuda:0"`.
- **Methods**:
    - `transcribe()`: Single audio segment (NumPy array).
    - `transcribe_batch()`: Multiple `SpeechSegment` objects in one inference call.
    - `unload()`: Moves model to CPU, deletes reference, and clears CUDA cache.

## ANTI-PATTERNS

- **DO NOT** convert to streaming ASR. Batch mode is required for accuracy and JLPT analysis.
- **DO NOT** import heavy ML libraries at module level.
- **DO NOT** use `float32` if `bfloat16` is supported (VRAM efficiency).

## NOTES

- **Requirements**: CUDA 12.x, 12GB+ VRAM.
- **Model Files**: Weights (*.pt, *.bin) are gitignored; expected in HuggingFace cache or local path.
- **Filtering**: `transcribe_batch` filters out segments with empty or whitespace-only results.
- **Analysis**: Performs morphological analysis via `fugashi` during batch processing for logging.
