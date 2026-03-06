# Task List — MyASR Japanese Learning Overlay

> Function-level tasks organized by milestone. Each task specifies files involved, definition of done, and verification command.

---

## Milestone 0 — Project Scaffolding

### Task 0.1: Initialize project structure and tooling config

**Files**: `pyproject.toml`, `requirements.txt`, `src/__init__.py`, `tests/__init__.py`, all `__init__.py` files in subpackages, `data/` directory

**Work**:
- Create `pyproject.toml` with ruff config (line-length=99, double quotes, isort), mypy strict config, pytest config
- Create `requirements.txt` with all dependencies: `torch`, `torchaudio`, `sounddevice`, `silero-vad`, `fugashi`, `unidic-lite`, `jreadability`, `PySide6`, `requests` (for Ollama), `numpy`
- Create dev dependencies section: `ruff`, `mypy`, `pytest`, `pytest-mock`
- Create all `src/` and `tests/` subdirectory `__init__.py` files
- Create empty `data/` directory with `.gitkeep` or initial data files

**Done when**: `pip install -r requirements.txt` succeeds, `ruff check .` runs (may be clean/no files), `mypy .` runs, `pytest --co` runs

**Verify**:
```bash
ruff check . && ruff format --check . && mypy . && pytest --co
```

### Task 0.2: Create exception hierarchy

**Files**: `src/exceptions.py`

**Work**:
- Define base `MyASRError(Exception)` 
- Define `AudioCaptureError(MyASRError)`, `VADError(MyASRError)`, `ASRError(MyASRError)`, `ModelLoadError(ASRError)`, `PreprocessingError(MyASRError)`, `LLMError(MyASRError)`, `LLMTimeoutError(LLMError)`, `LLMUnavailableError(LLMError)`, `DatabaseError(MyASRError)`

**Done when**: Module imports cleanly, mypy clean

**Verify**:
```bash
python -c "from src.exceptions import *" && mypy src/exceptions.py
```

### Task 0.3: Create app config module

**Files**: `src/config.py`, `tests/test_config.py`

**Work**:
- Define `AppConfig` dataclass with fields: `user_jlpt_level: int` (default 3), `llm_mode: Literal["translation", "explanation"]` (default "translation"), `translation_template: str` (default `DEFAULT_TRANSLATION_TEMPLATE`), `explanation_template: str` (default `DEFAULT_EXPLANATION_TEMPLATE`), `ollama_url: str` (default "http://localhost:11434"), `ollama_model: str` (default "qwen3.5:4b"), `ollama_timeout_sec: float` (default 30.0), `sample_rate: int` (default 16000), `db_path: str` (default "data/myasr.db")
- Function `load_config() -> AppConfig` that loads from JSON file if exists, else returns defaults
- Function `save_config(config: AppConfig) -> None` that writes to JSON

**Done when**: Config loads/saves correctly, defaults are sensible, tests pass

**Verify**:
```bash
pytest tests/test_config.py -x && mypy src/config.py
```

---

## Milestone 1 — Preprocessing Pipeline

### Task 1.1: Create database schema and models

**Files**: `src/db/schema.py`, `src/db/models.py`, `tests/test_db_schema.py`

**Work**:
- `schema.py`: Define `SCHEMA_SQL` string with CREATE TABLE statements for `sentence_records`, `highlight_vocab`, `highlight_grammar`, `app_settings`. Function `init_db(db_path: str) -> sqlite3.Connection` that creates tables if not exist (with WAL mode, foreign keys on).
- `models.py`: Define dataclasses `SentenceRecord`, `HighlightVocab`, `HighlightGrammar` matching the schema in `docs/api-data.md`. Define pipeline dataclasses: `Token`, `VocabHit`, `GrammarHit`, `AnalysisResult`, `SentenceResult`.

**Done when**: `init_db()` creates a valid SQLite DB, all dataclasses import cleanly, tests verify table creation and schema correctness

**Verify**:
```bash
pytest tests/test_db_schema.py -x && mypy src/db/schema.py src/db/models.py
```

### Task 1.2: Create database repository (CRUD)

**Files**: `src/db/repository.py`, `tests/test_db_repository.py`

**Work**:
- Class `LearningRepository`:
  - `__init__(self, conn: sqlite3.Connection) -> None`
  - `insert_sentence(self, record: SentenceRecord, vocab: list[HighlightVocab], grammar: list[HighlightGrammar]) -> int` — Insert record + highlights in a transaction, return record ID
  - `get_sentences(self, limit: int = 50, offset: int = 0) -> list[SentenceRecord]` — Fetch recent records
  - `search_sentences(self, query: str) -> list[SentenceRecord]` — Full-text search on japanese_text and chinese_translation
  - `mark_tooltip_shown(self, highlight_type: str, highlight_id: int) -> None` — Set tooltip_shown=1
  - `export_records(self, format: str = "json") -> str` — Export all records as JSON or CSV string
  - `delete_before(self, cutoff_date: str) -> int` — Delete records before ISO date, return count

**Done when**: All CRUD operations work correctly with in-memory SQLite, no duplicate writes, tests pass

**Verify**:
```bash
pytest tests/test_db_repository.py -x && mypy src/db/repository.py
```

### Task 1.3: Implement fugashi tokenizer wrapper

**Files**: `src/analysis/tokenizer.py`, `tests/test_tokenizer.py`

**Work**:
- Class `FugashiTokenizer`:
  - `__init__(self) -> None` — Initialize fugashi.GenericTagger with unidic-lite
  - `tokenize(self, text: str) -> list[Token]` — Return list of `Token(surface, lemma, pos)`. Handle empty input. Filter out punctuation-only tokens.

**Done when**: Tokenizer correctly splits known Japanese sentences into tokens with accurate lemma and POS. Tests with ≥3 sample sentences.

**Verify**:
```bash
pytest tests/test_tokenizer.py -x && mypy src/analysis/tokenizer.py
```

### Task 1.4: Implement JLPT vocabulary lookup

**Files**: `src/analysis/jlpt_vocab.py`, `tests/test_jlpt_vocab.py`, `data/jlpt_vocab.json` (stub with ≥20 entries for testing)

**Work**:
- Class `JLPTVocabLookup`:
  - `__init__(self, vocab_path: str) -> None` — Load JSON dict from file into memory
  - `lookup(self, lemma: str) -> int | None` — Return JLPT level (1-5) or None
  - `find_beyond_level(self, tokens: list[Token], user_level: int) -> list[VocabHit]` — Return list of tokens whose JLPT level exceeds user's level (lower number = harder, so level < user_level means beyond)

**Done when**: Lookup returns correct levels for known words, `find_beyond_level` correctly identifies beyond-level vocab for different user levels. Tests pass.

**Verify**:
```bash
pytest tests/test_jlpt_vocab.py -x && mypy src/analysis/jlpt_vocab.py
```

### Task 1.5: Implement grammar pattern matcher

**Files**: `src/analysis/grammar.py`, `tests/test_grammar.py`, `data/grammar_rules.json` (stub with ≥10 rules for testing)

**Work**:
- Class `GrammarMatcher`:
  - `__init__(self, rules_path: str) -> None` — Load JSON rules, compile regex patterns once
  - `match(self, text: str, user_level: int) -> list[GrammarHit]` — Run all patterns against text, return matches that exceed user's level. Include confidence_type.

**Done when**: Matcher correctly identifies grammar patterns in sample sentences, distinguishes high/ambiguous confidence, filters by user level. Tests with ≥5 patterns.

**Verify**:
```bash
pytest tests/test_grammar.py -x && mypy src/analysis/grammar.py
```

### Task 1.6: ~~Implement complexity scorer~~ **REMOVED**

> Complexity scoring has been removed. LLM behavior is now controlled by user-selected mode (`translation` or `explanation`) in `AppConfig.llm_mode`, not by automatic sentence complexity analysis. Files `src/analysis/complexity.py` and `tests/test_complexity.py` have been deleted.

### Task 1.7: Assemble preprocessing pipeline

**Files**: `src/analysis/pipeline.py`, `tests/test_analysis_pipeline.py`

**Work**:
- Class `PreprocessingPipeline`:
  - `__init__(self, config: AppConfig) -> None` — Initialize FugashiTokenizer, JLPTVocabLookup, GrammarMatcher
  - `process(self, text: str) -> AnalysisResult` — Run tokenize → vocab lookup → grammar match. Return `AnalysisResult`.
- Verify latency: add timing log. Target < 50ms per sentence.

**Done when**: Pipeline end-to-end produces correct `AnalysisResult` for ≥3 test sentences. Latency logged. Tests pass.

**Verify**:
```bash
pytest tests/test_analysis_pipeline.py -x && mypy src/analysis/pipeline.py
```

---

## Milestone 2 — ASR Integration

### Task 2.1: Implement audio capture

**Files**: `src/audio/capture.py`, `tests/test_audio_capture.py`

**Work**:
- Class `AudioCapture`:
  - `__init__(self, device_id: int | None = None, sample_rate: int = 16000) -> None`
  - `start(self, callback: Callable[[np.ndarray], None]) -> None` — Start capturing system audio, call callback with chunks
  - `stop(self) -> None` — Stop capture
  - `list_devices(cls) -> list[dict[str, Any]]` — Class method to list available audio devices
- Use `sounddevice.InputStream`. Handle device not found errors → raise `AudioCaptureError`.

**Done when**: Audio capture starts/stops cleanly, callback receives numpy arrays, device listing works. Tests with mocked sounddevice.

**Verify**:
```bash
pytest tests/test_audio_capture.py -x && mypy src/audio/capture.py
```

### Task 2.2: Implement Silero VAD wrapper

**Files**: `src/vad/silero.py`, `tests/test_silero_vad.py`

**Work**:
- Class `SileroVAD`:
  - `__init__(self, threshold: float = 0.5, min_silence_ms: int = 500, min_speech_ms: int = 250) -> None` — Load Silero model
  - `process_chunk(self, audio: np.ndarray) -> list[AudioSegment] | None` — Feed audio chunk, return complete segment(s) when sentence boundary detected, else None
  - `reset(self) -> None` — Clear internal state

**Done when**: VAD correctly detects speech boundaries in test audio. No false triggers on silence-only input. Tests with mocked model.

**Verify**:
```bash
pytest tests/test_silero_vad.py -x && mypy src/vad/silero.py
```

### Task 2.3: Implement Qwen3-ASR wrapper

**Files**: `src/asr/qwen_asr.py`, `tests/test_qwen_asr.py`

**Work**:
- Class `QwenASR`:
  - `__init__(self, model_path: str | None = None) -> None` — Load Qwen3-ASR 0.6B to GPU. Raise `ModelLoadError` on failure.
  - `transcribe(self, audio: np.ndarray, sample_rate: int = 16000) -> str` — Run inference on audio segment, return Japanese text. Raise `ASRError` on failure.
  - `unload(self) -> None` — Free GPU memory

**Done when**: ASR wrapper loads model, transcribes audio, handles errors gracefully. Tests with mocked model inference.

**Verify**:
```bash
pytest tests/test_qwen_asr.py -x && mypy src/asr/qwen_asr.py
```

### Task 2.4: Create pipeline worker (Audio → VAD → ASR → Preprocessing)

**Files**: `src/pipeline.py`, `tests/test_pipeline.py`

**Work**:
- Class `PipelineWorker(QThread)`:
  - Signal: `sentence_ready = Signal(SentenceResult)`
  - `__init__(self, config: AppConfig) -> None` — Initialize AudioCapture, SileroVAD, QwenASR, PreprocessingPipeline
  - `run(self) -> None` — Start audio capture, process through VAD → ASR → preprocessing, emit `sentence_ready` signal
  - `stop(self) -> None` — Stop pipeline gracefully
- Wire audio callback → VAD → ASR → preprocessing → signal emission

**Done when**: Pipeline worker runs in thread, processes audio through all stages, emits signals. Clean shutdown. Tests with mocked components.

**Verify**:
```bash
pytest tests/test_pipeline.py -x && mypy src/pipeline.py
```

---

## Milestone 3 — LLM Translation

### Task 3.1: Implement Ollama client

**Files**: `src/llm/ollama_client.py`, `tests/test_ollama_client.py`

**Work**:
- Class `OllamaClient`:
  - `__init__(self, config: AppConfig) -> None` — Store URL, model, timeout, mode (`config.llm_mode`), and prompt templates (`config.translation_template`, `config.explanation_template`)
  - `translate(self, japanese_text: str) -> tuple[str | None, str | None]` — Call Ollama API. Uses `self._mode` to select prompt template and response parsing. In "translation" mode → returns `(translation, None)`. In "explanation" mode → returns `(None, explanation)`. Returns `(None, None)` on failure (subtitle-only fallback).
  - `_build_prompt(self, japanese_text: str) -> str` — Construct prompt from the mode-appropriate template, substituting `{japanese_text}`
  - `_parse_response(self, response_text: str) -> tuple[str | None, str | None]` — Parse LLM response based on current mode. Translation mode: entire response is the translation, returns `(translation, None)`. Explanation mode: entire response is the explanation, returns `(None, explanation)`.
  - `health_check(self) -> bool` — Check if Ollama is reachable

**Done when**: Client sends correct prompts per mode, parses responses, handles timeout/connection errors gracefully (returns None, no crash). Tests with mocked HTTP responses for success, timeout, and connection refused, covering both translation and explanation modes.

**Verify**:
```bash
pytest tests/test_ollama_client.py -x && mypy src/llm/ollama_client.py
```

### Task 3.2: Integrate LLM into pipeline worker

**Files**: `src/pipeline.py` (update), `tests/test_pipeline.py` (update)

**Work**:
- Add `OllamaClient` to `PipelineWorker.__init__`
- After preprocessing, call `ollama_client.translate(text)` 
- Populate `SentenceResult.chinese_translation` and `SentenceResult.explanation` based on the configured LLM mode
- On LLM failure: emit `SentenceResult` with `chinese_translation=None` (subtitle-only fallback)
- Write completed `SentenceResult` to DB via `LearningRepository`

**Done when**: Pipeline produces full `SentenceResult` with translation. Fallback works when Ollama is mocked as unavailable. DB records written. Tests pass.

**Verify**:
```bash
pytest tests/test_pipeline.py -x && mypy src/pipeline.py
```

---

## Milestone 4 — UI Overlay

### Task 4.1: Implement highlight renderer

**Files**: `src/ui/highlight.py`, `tests/test_highlight.py`

**Work**:
- Class `HighlightRenderer`:
  - `JLPT_COLORS: dict` — Color mapping per level/type as defined in `docs/api-data.md`
  - `build_rich_text(self, japanese_text: str, analysis: AnalysisResult, user_level: int) -> str` — Return HTML-formatted string with `<span>` color tags for highlighted segments. Grammar priority over vocab when overlapping.
  - `get_highlight_at_position(self, position: int, analysis: AnalysisResult) -> VocabHit | GrammarHit | None` — For tooltip: identify which highlight is at a text cursor position

**Done when**: Rich text output has correct HTML color spans. Grammar-over-vocab priority works. Position lookup correct. Tests with known sentences.

**Verify**:
```bash
pytest tests/test_highlight.py -x && mypy src/ui/highlight.py
```

### Task 4.2: Implement overlay window

**Files**: `src/ui/overlay.py`, `tests/test_overlay.py`

**Work**:
- Class `OverlayWindow(QWidget)`:
  - Transparent, frameless, always-on-top window
  - Display modes: two-line (JP top, CN bottom) or single-line toggle
  - Slot: `on_sentence_ready(self, result: SentenceResult) -> None` — Update display with new sentence
  - Show status indicators: "Initializing...", "No speech detected", "Translation unavailable"
  - Draggable via mouse events

**Done when**: Window renders as transparent overlay, displays formatted text, updates on signal, shows status states. Tests verify signal connection and display update logic.

**Verify**:
```bash
pytest tests/test_overlay.py -x && mypy src/ui/overlay.py
```

### Task 4.3: Implement tooltip popup

**Files**: `src/ui/tooltip.py`, `tests/test_tooltip.py`

**Work**:
- Class `TooltipPopup(QWidget)`:
  - Rounded-corner popup showing JLPT level + explanation for hovered highlight
  - `show_for_vocab(self, hit: VocabHit, position: QPoint) -> None`
  - `show_for_grammar(self, hit: GrammarHit, position: QPoint) -> None`
  - Signal: `record_triggered = Signal(str, int)` — Emitted when tooltip shown (highlight_type, highlight_id) to trigger DB write
  - Deduplication: track shown highlights per sentence to prevent duplicate writes (set of `(sentence_id, highlight_type, highlight_id)`)

**Done when**: Tooltip displays correct content for vocab/grammar hits, emits signal for record write, deduplication prevents repeat writes. Tests pass.

**Verify**:
```bash
pytest tests/test_tooltip.py -x && mypy src/ui/tooltip.py
```

### Task 4.4: Create main entry point

**Files**: `src/main.py`

**Work**:
- Initialize `QApplication`
- Load `AppConfig`
- Initialize `LearningRepository` (call `init_db`)
- Create `PipelineWorker` with config
- Create `OverlayWindow`
- Connect `PipelineWorker.sentence_ready` → `OverlayWindow.on_sentence_ready`
- Connect tooltip record signals → `LearningRepository.mark_tooltip_shown`
- Start pipeline worker thread
- Run Qt event loop
- Clean shutdown on exit (stop pipeline, close DB)

**Done when**: `python -m src.main` starts the application, shows overlay, pipeline runs. Clean exit on Ctrl+C or window close.

**Verify**:
```bash
mypy src/main.py && python -c "from src.main import main"
```

---

## Full Verification (Run After Each Milestone)

```bash
ruff check . && ruff format --check . && mypy . && pytest -x --tb=short
```
