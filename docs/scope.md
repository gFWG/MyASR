# Scope — MyASR Japanese Learning Overlay

## Problem Statement

Users watching Japanese content (games, movies, videos) on Windows 11 need a non-intrusive overlay that provides real-time subtitles, translations, and JLPT-aligned study highlights — without interrupting the experience.

## Goals

| ID | Goal | Priority |
|----|------|----------|
| G1 | Capture system audio → VAD segmentation → sentence-level Japanese subtitles | P0 |
| G2 | Preprocess subtitles: morphological analysis, JLPT vocab lookup, grammar matching | P0 |
| G3 | Display transparent overlay: Japanese text + Prev/Next sentence + JLPT highlights; hover tooltip with explanations; auto-write to learning records | P0 |
| G4 | A simplified Anki-style learning record system with export capabilities | P1 |

## Non-Goals

| ID | Non-Goal | Rationale |
|----|----------|-----------|
| NG1 | Complex architecture / over-engineering | Keep modules simple with clean interfaces |
| NG2 | Streaming ASR | VAD-segmented batch inference is more accurate in noisy/complex audio scenes |
| NG3 | Multi-language support | Focus exclusively on Japanese + JLPT system |

## Feature Tiers

### P0 — Core

1. **Audio capture + VAD**: Capture system playback audio via `sounddevice`(For test only)/`pyaudiowpatch`(on Win 11) + Silero VAD sentence segmentation.
2. **ASR**: Qwen3-ASR (0.6B) offline batch inference → sentence-level Japanese text.
3. **Preprocessing pipeline**: fugashi tokenization → JLPT vocab O(1) lookup → grammar regex matching.
4. **Overlay UI**: PySide6 transparent frameless window — Japanese + Buttons, JLPT-level color highlights, hover tooltip with explanations, auto-write to SQLite learning records.

### P1 — Settings & History

6. **Settings panel**: JLPT level selector, font/appearance, resource paths, record export/cleanup.
7. **Learning panel**: Historical records table with search, sort, and filtering.
8. **Export**: CSV/JSON export of learning records.

### P2 — Review

9. **Review system**: Spaced-repetition or other algorithm to resurface sentences for review.

## Target Platform & Environment

| Aspect | Value |
|--------|-------|
| Runtime OS | Windows 11 |
| Dev environment | WSL2 + Ubuntu 22.04 |
| Python | 3.12+ |
| GPU | CUDA 12.x, 12GB VRAM minimum |
| Package management | venv (`source .venv/bin/activate`) |
