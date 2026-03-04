# Architecture — MyASR Japanese Learning Overlay

## Design Principles

1. **Simple modules, clean interfaces** — No abstract base classes unless genuinely needed by 3+ implementations.
2. **Sequential pipeline** — Audio → VAD → ASR → Preprocessing → LLM → UI. Each stage is a separate module.
3. **Offline-first** — ASR and VAD run locally on GPU. Only Ollama (localhost) for LLM.
4. **UI thread isolation** — PySide6 main thread handles UI only. Pipeline runs in worker thread(s). Communication via Qt signals/slots.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  PySide6 Main Thread (UI)                                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────────┐   │
│  │ Overlay   │  │ Tooltip  │  │ Settings │  │ Learning Panel│   │
│  │ Window    │  │ Popup    │  │ Panel    │  │               │   │
│  └────▲─────┘  └──────────┘  └──────────┘  └───────────────┘   │
│       │ Qt Signal (SentenceResult)                               │
├───────┼─────────────────────────────────────────────────────────┤
│  Worker Thread (Pipeline)                                        │
│       │                                                          │
│  ┌────┴──────────────────────────────────────────────────────┐  │
│  │ Audio Capture (sounddevice / pyaudiowpatch)               │  │
│  │       │                                                    │  │
│  │       ▼                                                    │  │
│  │ Silero VAD  ──── sentence boundary detected ───►          │  │
│  │       │                                                    │  │
│  │       ▼                                                    │  │
│  │ Qwen3-ASR (0.6B, CUDA, batch mode)                       │  │
│  │       │                                                    │  │
│  │       ▼                                                    │  │
│  │ Preprocessing Pipeline (< 50ms)                           │  │
│  │   ├── fugashi tokenizer (surface/lemma/POS)               │  │
│  │   ├── JLPT vocab lookup (dict, O(1))                      │  │
│  │   ├── Grammar regex matching (800+ rules)                 │  │
│  │   └── Complexity scoring (jreadability + JLPT weights)    │  │
│  │       │                                                    │  │
│  │       ▼                                                    │  │
│  │ LLM Client (Ollama qwen3-4b, localhost:11434)             │  │
│  │   simple → translate only                                  │  │
│  │   complex → translate + study-point analysis               │  │
│  │   unavailable → subtitle-only fallback (no crash)         │  │
│  └───────────────────────────────────────────────────────────┘  │
│       │                                                          │
│       ▼                                                          │
│  SQLite (learning records, via stdlib sqlite3)                   │
└─────────────────────────────────────────────────────────────────┘
```

## Module Map

```
src/
├── audio/
│   ├── __init__.py
│   └── capture.py          # AudioCapture: system audio → raw PCM stream
├── vad/
│   ├── __init__.py
│   └── silero.py           # SileroVAD: raw audio → sentence segments
├── asr/
│   ├── __init__.py
│   └── qwen_asr.py         # QwenASR: audio segment → Japanese text
├── analysis/
│   ├── __init__.py
│   ├── tokenizer.py        # FugashiTokenizer: text → Token list (surface/lemma/POS)
│   ├── jlpt_vocab.py       # JLPTVocabLookup: lemma → JLPTLevel | None
│   ├── grammar.py          # GrammarMatcher: text → list[GrammarHit]
│   ├── complexity.py       # ComplexityScorer: tokens + hits → score + is_complex
│   └── pipeline.py         # PreprocessingPipeline: orchestrates above → AnalysisResult
├── llm/
│   ├── __init__.py
│   └── ollama_client.py    # OllamaClient: sentence + analysis → translation [+ study points]
├── ui/
│   ├── __init__.py
│   ├── overlay.py          # OverlayWindow: transparent frameless subtitle display
│   ├── tooltip.py          # TooltipPopup: hover explanation popup
│   ├── highlight.py        # HighlightRenderer: JLPT-level color mapping
│   ├── settings_panel.py   # SettingsPanel: config UI
│   └── learning_panel.py   # LearningPanel: history table UI
├── db/
│   ├── __init__.py
│   ├── schema.py           # DDL statements, migration logic
│   ├── models.py           # Dataclasses: SentenceRecord, HighlightVocab, HighlightGrammar
│   └── repository.py       # CRUD operations for learning records
├── config.py               # App-wide config, defaults, settings persistence
├── exceptions.py           # Custom exception hierarchy
├── pipeline.py             # PipelineWorker: orchestrates full Audio→LLM flow in worker thread
└── main.py                 # Entry point: init app, load resources, start threads
```

## Threading Model

| Thread | Responsibility | Communication |
|--------|---------------|---------------|
| **Main (UI)** | PySide6 event loop, overlay rendering, tooltip, settings/learning panels | Receives `SentenceResult` signal from worker |
| **Pipeline Worker** | Audio capture → VAD → ASR → Preprocessing → LLM → DB write | Emits `SentenceResult` signal to main thread |

Thread communication uses Qt signals/slots exclusively. No shared mutable state between threads.

## Data Flow Types

```python
# Key data structures passed between pipeline stages

@dataclass
class AudioSegment:
    samples: np.ndarray     # float32, mono, 16kHz
    duration_sec: float

@dataclass
class Token:
    surface: str            # 表記形
    lemma: str              # 原形
    pos: str                # 品詞

@dataclass
class AnalysisResult:
    tokens: list[Token]
    vocab_hits: list[VocabHit]      # beyond-level vocab
    grammar_hits: list[GrammarHit]  # matched grammar patterns
    complexity_score: float
    is_complex: bool

@dataclass
class SentenceResult:
    japanese_text: str
    chinese_translation: str | None
    explanation: str | None          # study-point analysis (complex only)
    analysis: AnalysisResult
    created_at: datetime
```

## Complexity Threshold (Tunable Defaults)

A sentence is classified as **complex** if ANY of these conditions is met:

| Condition | Default Threshold | Config Key |
|-----------|------------------|------------|
| Beyond-level vocab count | ≥ 2 | `complexity.vocab_threshold` |
| N1 grammar pattern hit | ≥ 1 | `complexity.n1_grammar_threshold` |
| jreadability score | > 3.0 (scale TBD) | `complexity.readability_threshold` |
| Ambiguous grammar rules | ≥ 1 (confidence_type = "ambiguous") | `complexity.ambiguous_grammar_threshold` |

These thresholds are configurable in the settings panel and stored in app config.

## LLM Degradation Strategy

When Ollama is unavailable or times out:
1. **Subtitle-only fallback**: Display ASR text + preprocessing highlights (vocab/grammar color-coded) without translation.
2. No queuing or retry. User sees partial result immediately.
3. Overlay shows a subtle indicator that translation is unavailable.

## SQLite Schema Overview

Three tables with normalized highlights (see `docs/api-data.md` for full schema):

- **sentence_records**: Core learning records (id INTEGER PRIMARY KEY AUTOINCREMENT, japanese_text, chinese_translation, explanation, complexity_score, created_at)
- **highlight_vocab**: Foreign key → sentence_records (word, lemma, jlpt_level, pos)
- **highlight_grammar**: Foreign key → sentence_records (rule_id, pattern, description, confidence_type)

## Resource Loading

| Resource | Format | Load Strategy |
|----------|--------|--------------|
| JLPT vocab dictionary | JSON | Load into `dict[str, int]` at startup. O(1) lookup. |
| Grammar rules | CSV → JSON (build step) | Load into list at startup. Regex compiled once. |
| ASR model (Qwen3-ASR 0.6B) | Model weights | Load into GPU VRAM at startup. Resident. |
| Silero VAD | ONNX/JIT | Load at startup. CPU inference. |
