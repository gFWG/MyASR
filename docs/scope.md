# Scope — MyASR Japanese Learning Overlay

## Problem Statement

Users watching Japanese content (games, movies, videos) on Windows 11 need a non-intrusive overlay that provides real-time subtitles, translations, and JLPT-aligned study highlights — without interrupting the experience.

## Goals

| ID | Goal | Priority |
|----|------|----------|
| G1 | Capture system audio → VAD segmentation → sentence-level Japanese subtitles | P0 |
| G2 | Preprocess subtitles: morphological analysis, JLPT vocab lookup, grammar matching, complexity scoring → decide whether to trigger detailed analysis | P0 |
| G3 | Display transparent overlay: Japanese text + Chinese translation + JLPT highlights; hover tooltip with explanations; auto-write to learning records | P0 |
| G4 | All core capabilities run offline (ASR local inference + Ollama LLM on localhost) | P0 |

## Non-Goals

| ID | Non-Goal | Rationale |
|----|----------|-----------|
| NG1 | Complex architecture / over-engineering | Keep modules simple with clean interfaces |
| NG2 | Streaming ASR | VAD-segmented batch inference is more accurate in noisy/complex audio scenes |
| NG3 | Multi-language support | Focus exclusively on Japanese + JLPT system |

## Feature Tiers

### P0 — Core (MVP)

1. **Audio capture + VAD**: Capture system playback audio via `sounddevice`/`pyaudiowpatch` + Silero VAD sentence segmentation.
2. **ASR**: Qwen3-ASR (0.6B) offline batch inference → sentence-level Japanese text.
3. **Preprocessing pipeline**: fugashi tokenization → JLPT vocab O(1) lookup → grammar regex matching → jreadability complexity scoring.
4. **LLM translation**: Ollama qwen3.5:4b (localhost:11434) — simple sentences get translation only; complex sentences get translation + study-point analysis (single API call).
5. **Overlay UI**: PySide6 transparent frameless window — Japanese + Chinese lines, JLPT-level color highlights, hover tooltip with explanations, auto-write to SQLite learning records.

### P1 — Settings & History

6. **Settings panel**: JLPT level selector, font/appearance, hotkeys, model config, resource paths, record export/cleanup.
7. **Learning panel**: Historical records table with search, sort, and filtering.
8. **Export**: CSV/JSON export of learning records.

### P2 — Review (Future)

9. **Review system**: Spaced-repetition or other algorithm to resurface sentences for review (algorithm TBD).

## Target Platform & Environment

| Aspect | Value |
|--------|-------|
| Runtime OS | Windows 11 |
| Dev environment | WSL2 + Ubuntu 22.04 |
| Python | 3.12+ |
| GPU | CUDA 12.x, 12GB VRAM minimum |
| Package management | venv (`source .venv/bin/activate`) |
