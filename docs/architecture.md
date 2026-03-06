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
│  │   └── Grammar regex matching (800+ rules)                 │  │
│  │       │                                                    │  │
│  │       ▼                                                    │  │
│  │ LLM Client (Ollama qwen3.5:4b, localhost:11434)             │  │
│  │   translation mode → translate only                        │  │
│  │   explanation mode → grammar/vocab analysis only           │  │
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
│   └── pipeline.py         # PreprocessingPipeline: orchestrates above → AnalysisResult
├── llm/
│   ├── __init__.py
│   └── ollama_client.py    # OllamaClient: sentence + mode → translation or explanation
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

@dataclass
class SentenceResult:
    japanese_text: str
    chinese_translation: str | None
    explanation: str | None          # study-point analysis (explanation mode only)
    analysis: AnalysisResult
    created_at: datetime
```

## LLM Mode Selection

The user selects **translation** or **explanation** mode in settings. Each mode uses a separate prompt template, both customizable.

| Mode | Behavior | Config Key |
|------|----------|------------|
| `translation` (default) | Chinese translation only | `llm_mode`, `translation_template` |
| `explanation` | Grammar/vocab analysis only (no translation) | `llm_mode`, `explanation_template` |

Mode is set at config level and does not require runtime sentence-by-sentence evaluation.

## LLM Degradation Strategy

When Ollama is unavailable or times out:
1. **Subtitle-only fallback**: Display ASR text + preprocessing highlights (vocab/grammar color-coded) without translation.
2. No queuing or retry. User sees partial result immediately.
3. Overlay shows a subtle indicator that translation is unavailable.

## SQLite Schema Overview

Three tables with normalized highlights (see `docs/api-data.md` for full schema):

- **sentence_records**: Core learning records (id INTEGER PRIMARY KEY AUTOINCREMENT, japanese_text, chinese_translation, explanation, source_context, created_at)
- **highlight_vocab**: Foreign key → sentence_records (word, lemma, jlpt_level, pos)
- **highlight_grammar**: Foreign key → sentence_records (rule_id, pattern, description, confidence_type)

## Resource Loading

| Resource | Format | Load Strategy |
|----------|--------|--------------|
| JLPT vocab dictionary | JSON | Load into `dict[str, int]` at startup. O(1) lookup. |
| Grammar rules | CSV → JSON (build step) | Load into list at startup. Regex compiled once. |
| ASR model (Qwen3-ASR 0.6B) | Model weights | Load into GPU VRAM at startup. Resident. `unload()` moves to CPU, then `gc.collect()` + `torch.cuda.synchronize()` + `empty_cache()`. |
| Silero VAD | ONNX/JIT | Load at startup. CPU inference. |

## Implementation Notes

### VAD Pre-Buffering

Silero VAD uses a 300ms ring buffer (`collections.deque`) to retain audio chunks received *before* speech is detected. When a speech-start event fires, the ring buffer contents are prepended to the speech audio buffer. This prevents clipping the onset of utterances.

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `pre_buffer_ms` | 300 | Captures ~300ms of audio before VAD trigger to avoid clipping sentence beginnings |
| `speech_pad_ms` | 300 | Pads reported speech timestamps by 300ms (Silero default is too low for Japanese sentence boundaries) |
| `min_speech_ms` | 250 | Minimum speech duration to avoid spurious short detections |
| `max_speech_sec` | 30 | Force-cut long utterances to bound memory and latency |

### ASR VRAM Management

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `max_inference_batch_size` | 4 | Balances throughput vs VRAM. batch=1 for single segments; batch=4 sweet spot when model internally chunks long audio (~2.87× throughput, <7GB VRAM) |
| `dtype` | `bfloat16` | Half-precision to reduce VRAM footprint |
| Unload sequence | `.cpu()` → `del` → `gc.collect()` → `synchronize()` → `empty_cache()` | Ensures VRAM is fully reclaimed; prevents memory leaks from lingering GPU tensors |
