# Milestones — MyASR Japanese Learning Overlay

## Overview

4 milestones mapping to the PRD success metrics. Each milestone is independently demonstrable.

---

## Milestone 1 — Preprocessing Pipeline (M1)

**Goal**: Run the preprocessing chain end-to-end on hardcoded Japanese text input.

**Deliverables**:
- `src/analysis/tokenizer.py` — FugashiTokenizer
- `src/analysis/jlpt_vocab.py` — JLPTVocabLookup
- `src/analysis/grammar.py` — GrammarMatcher
- `src/analysis/complexity.py` — ComplexityScorer
- `src/analysis/pipeline.py` — PreprocessingPipeline
- `src/db/schema.py`, `src/db/models.py`, `src/db/repository.py` — SQLite layer
- `src/config.py` — App config with complexity thresholds
- `src/exceptions.py` — Exception hierarchy
- `data/jlpt_vocab.json` — JLPT vocabulary dictionary
- `data/grammar_rules.json` — Grammar rules (converted from CSV)
- Full test suite for all above modules

**Demo**: Run preprocessing on sample sentences, verify structured output with correct JLPT tags, grammar matches, and complexity classification.

**Success Criteria**:
- Preprocessing returns correct `AnalysisResult` for known test sentences
- Average latency < 50ms per sentence
- All tests pass, mypy clean, ruff clean

---

## Milestone 2 — ASR Integration (M2)

**Goal**: Capture system audio → VAD segmentation → ASR → Japanese text output.

**Deliverables**:
- `src/audio/capture.py` — AudioCapture (sounddevice/pyaudiowpatch)
- `src/vad/silero.py` — SileroVAD
- `src/asr/qwen_asr.py` — QwenASR
- `src/pipeline.py` — PipelineWorker (Audio→VAD→ASR→Preprocessing, no LLM yet)
- Tests for VAD and ASR modules (with mocked audio input)

**Demo**: Play Japanese audio on system → pipeline outputs preprocessed Japanese text to console/log.

**Success Criteria**:
- VAD correctly segments speech from silence/BGM
- ASR produces readable Japanese text from clear audio
- Pipeline runs without memory leaks for 10+ minutes
- All tests pass, mypy clean, ruff clean

---

## Milestone 3 — LLM Translation (M3)

**Goal**: Integrate Ollama LLM for translation and study-point analysis.

**Deliverables**:
- `src/llm/ollama_client.py` — OllamaClient with prompt templates, response parsing, timeout/fallback
- Update `src/pipeline.py` — Add LLM stage to pipeline
- Tests for LLM client (with mocked HTTP responses)

**Demo**: Full pipeline outputs `SentenceResult` with translation (and analysis for complex sentences). Verify fallback works when Ollama is stopped.

**Success Criteria**:
- Simple sentences get translation only
- Complex sentences get translation + study points
- Graceful fallback when Ollama unavailable (subtitle-only, no crash)
- All tests pass, mypy clean, ruff clean

---

## Milestone 4 — UI Overlay (M4)

**Goal**: Full working application with transparent overlay, tooltip, and learning records.

**Deliverables**:
- `src/ui/overlay.py` — OverlayWindow
- `src/ui/tooltip.py` — TooltipPopup
- `src/ui/highlight.py` — HighlightRenderer (color mapping)
- `src/main.py` — Entry point: init app, load resources, start pipeline thread
- Update `src/db/repository.py` — Tooltip-triggered record writes
- Tests for UI components (where feasible with mock signals)

**Demo**: Launch app → play Japanese content → see overlay with highlighted subtitles → hover for tooltip → verify record in SQLite.

**Success Criteria**:
- Overlay renders correctly as transparent frameless window
- Highlights use correct JLPT color scheme
- Tooltip shows explanation on hover
- Learning records written to SQLite (no duplicates per sentence)
- All tests pass, mypy clean, ruff clean

---

## Milestone Dependencies

```
M1 (Preprocessing) ──► M2 (ASR) ──► M3 (LLM) ──► M4 (UI)
         │                                           ▲
         └──── DB layer reused across all ───────────┘
```

M1 is independent. M2 builds on M1's preprocessing. M3 adds LLM to M2's pipeline. M4 adds UI to the complete pipeline.

---

## Post-MVP (P1/P2)

| Feature | Depends On | Estimated Effort |
|---------|-----------|-----------------|
| Settings panel | M4 | Medium |
| Learning panel (history) | M4 + DB | Medium |
| CSV/JSON export | DB | Small |
| Review system | DB + algorithm design | Large (TBD) |
