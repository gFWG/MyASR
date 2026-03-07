# Learnings — m4-ui-overlay

## [2026-03-06] Session ses_33c40bd4fffeDaiupOGOk32J6z — Initial Setup

### Project Structure
- Worktree: /home/yuheng/MyASR-m4-ui-overlay (branch: m4-ui-overlay)
- Main repo: /home/yuheng/MyASR
- Python venv: /home/yuheng/MyASR/.venv or similar — use `source .venv/bin/activate`

### Source Layout
src/: __init__.py, analysis/, asr/, audio/, config.py, db/, exceptions.py, llm/, pipeline.py, ui/
src/analysis/: __init__.py, grammar.py, jlpt_vocab.py, pipeline.py, tokenizer.py
src/db/: __init__.py, models.py, repository.py, schema.py
src/ui/: __init__.py (exists, empty or minimal)
tests/: conftest.py, test_analysis_pipeline.py, test_audio_capture.py, test_config.py, test_db_repository.py, test_db_schema.py, test_grammar.py, test_integration.py, test_jlpt_vocab.py, test_ollama_client.py, test_pipeline.py, test_qwen_asr.py, test_silero_vad.py, test_tokenizer.py

### Pre-existing LSP Errors (NOT our fault, ignore):
- src/analysis/complexity.py: missing AppConfig attributes (complexity_vocab_threshold etc.) — pre-existing
- tests/test_complexity.py: constructor param error — pre-existing
- tests/test_tokenizer.py: fugashi.Tagger not found — pre-existing

### Key Config/Environment
- Testing UI: QT_QPA_PLATFORM=offscreen required for headless Qt tests
- All tools: activate venv before running python/pytest
- Ruff line length: 99, double quotes, trailing commas
- Mypy: strict mode
- Qt6 API: globalPosition().toPoint() NOT globalPos(); exec() NOT exec_()

### Wave Execution Strategy
Wave 1: Tasks 1, 2a, 2b (parallel) → then 2c (sequential after 1+2a+2b)
Wave 2: Tasks 3 and 4 (parallel) → then 5 (sequential after 3+4)  
Wave 3: Tasks 6 and 7 (parallel, 7 actually independent of 6 for creation)
Final: F1-F4 parallel verification

## Task 1: Data Model Updates (2026-03-06)

### What Changed
- `VocabHit` dataclass: Added `start_pos: int` and `end_pos: int` as REQUIRED fields (no defaults)
- `GrammarHit` dataclass: Added `start_pos: int` and `end_pos: int` as REQUIRED fields (no defaults)
- `SentenceResult` dataclass: Added `sentence_id: int | None = None`, `highlight_vocab_ids: list[int] | None = None`, `highlight_grammar_ids: list[int] | None = None` as OPTIONAL fields with defaults

### Key Decisions
1. **Positions as required fields**: Made `start_pos` and `end_pos` required (no defaults) on VocabHit/GrammarHit to force all callers to explicitly provide position values. This prevents silent bugs where position data is missing.
2. **GrammarHit uses actual match positions**: The grammar matcher already has access to regex match objects (`m.start()` and `m.end()`), so we use the actual positions rather than placeholder zeros.
3. **VocabHit uses temporary zeros**: The vocab lookup currently doesn't track positions (it operates on Token objects without position info), so we use `start_pos=0, end_pos=0` as temporary placeholders. Future enhancement: tokenizer should provide character offsets.
4. **SentenceResult fields are optional**: The `sentence_id` and highlight ID lists are optional with defaults because they're assigned later during database persistence, not during initial pipeline processing.
5. **DB schema unchanged**: Position fields are runtime-only metadata, NOT persisted to database. Only HighlightVocab/HighlightGrammar DB entities store permanent records.

### Files Modified
- `src/db/models.py`: Updated VocabHit, GrammarHit, SentenceResult dataclasses
- `src/analysis/jlpt_vocab.py`: Updated VocabHit construction with `start_pos=0, end_pos=0`
- `src/analysis/grammar.py`: Updated GrammarHit construction with actual `start_pos=m.start(), end_pos=m.end()`
- `tests/test_pipeline.py`: Updated test fixtures for VocabHit and GrammarHit

### Verification
- `mypy src/db/models.py` - passes
- `mypy src/analysis/jlpt_vocab.py src/analysis/grammar.py` - passes  
- `pytest -x --tb=short` - 114 passed, 6 skipped
- Evidence files: `.sisyphus/evidence/task-1-vocabhit-positions.txt`, `task-1-sentenceresult-defaults.txt`, `task-1-regression.txt`

### Notes for Future Tasks
- When implementing UI highlighting, GrammarHit positions can be used directly
- VocabHit positions need tokenizer enhancement to provide character offsets per token
- SentenceResult.highlight_*_ids should be populated by PipelineWorker before emitting, populated from DB insert return values

## Task 2a - Grammar Position Verification (2026-03-06)

### Verified Implementation
- `src/analysis/grammar.py` lines 77-84: `GrammarHit` construction correctly uses `start_pos=m.start(), end_pos=m.end()`
- Regex match positions from `re.Pattern.finditer()` are properly captured

### Test Added
- `tests/test_grammar.py::test_grammar_hit_positions_are_correct()` verifies:
  - `text[hit.start_pos:hit.end_pos] == hit.matched_text`
  - `0 <= hit.start_pos < hit.end_pos <= len(text)`

### Evidence Files
- `.sisyphus/evidence/task-2a-grammar-positions.txt`: QA output showing `'ながら' at 5-8, verify='ながら', match=True`
- `.sisyphus/evidence/task-2a-grammar-tests.txt`: pytest output (15 passed)

### Verification Results
- `pytest tests/test_grammar.py -x --tb=short`: 15 passed ✓
- `mypy src/analysis/grammar.py`: Success ✓

## Task 2b: VocabHit Position Calculation (2026-03-06)

### Implementation Pattern
- Added `text: str = ""` parameter to `JLPTVocabLookup.find_beyond_level()` for backward compatibility
- Position calculation uses `text.find(token.surface, search_start)` with advancing `search_start`
- When text is provided and token is found: `start_pos = pos`, `end_pos = start_pos + len(surface)`
- When text is not provided or token not found: `start_pos = 0`, `end_pos = 0`
- Duplicate tokens get distinct positions because `search_start` advances after each match

### Key Code Pattern
```python
search_start = 0
for token in tokens:
    if is_beyond_level:
        if text:
            pos = text.find(token.surface, search_start)
            if pos >= 0:
                start_pos = pos
                end_pos = start_pos + len(token.surface)
                search_start = end_pos  # advance to prevent matching same occurrence
            else:
                start_pos = 0
                end_pos = 0
        else:
            start_pos = 0
            end_pos = 0
        hits.append(VocabHit(..., start_pos=start_pos, end_pos=end_pos))
```

### Test Coverage
- `test_find_beyond_level_with_positions`: Verifies correct position calculation
- `test_find_beyond_level_with_positions_duplicate_tokens`: Verifies distinct positions for duplicates
- `test_find_beyond_level_without_text_returns_zeros`: Verifies backward compatibility
- All tests assert `text[hit.start_pos:hit.end_pos] == hit.surface`

### Verification
- `pytest tests/test_jlpt_vocab.py -x --tb=short`: 12 passed
- `mypy src/analysis/jlpt_vocab.py`: Success

## Task 2c: Pipeline Position Propagation (2026-03-06)

### Change Summary
Updated `PreprocessingPipeline.process()` to pass the `text` parameter to `find_beyond_level()`, closing the loop on position propagation from text through to VocabHit objects.

### Code Change
File: `src/analysis/pipeline.py` line 44
```python
# Before:
vocab_hits = self._vocab_lookup.find_beyond_level(tokens, self._config.user_jlpt_level)

# After:
vocab_hits = self._vocab_lookup.find_beyond_level(tokens, self._config.user_jlpt_level, text=text)
```

### Test Updates
File: `tests/test_analysis_pipeline.py`
- Enhanced `test_pipeline_vocab_hits_populated()` to assert position fields:
  - `vocab_hit.start_pos >= 0`
  - `vocab_hit.end_pos > vocab_hit.start_pos`
- Added `test_pipeline_grammar_hits_have_positions()` to assert grammar hit positions:
  - `grammar_hit.start_pos >= 0`
  - `grammar_hit.end_pos > grammar_hit.start_pos`

### Evidence
File: `.sisyphus/evidence/task-2c-pipeline-positions.txt`
```
Text: 音楽を聴きながら概念を理解した (user_level=4)
vocab_hits: 1
  V: 概念 lemma=概念 level=1 at 8-10
grammar_hits: 1
  G: ながら rule=N3_nagara level=3 at 5-8
```

### Verification
- `mypy src/analysis/pipeline.py`: Success ✓
- `pytest -x --tb=short`: 119 passed, 6 skipped ✓
- All position assertions pass in both vocab and grammar tests

### Wave 1 Complete
Commit: `feat(models): add position fields to VocabHit/GrammarHit and sentence_id to SentenceResult`
Files changed: 8 files, +116 lines, -2 lines

## [2026-03-07] Task 5: OverlayWindow

### Implementation Summary
- `src/ui/overlay.py`: 185-line `OverlayWindow(QWidget)` with transparent overlay
- `tests/test_overlay.py`: 19 tests, all passing

### Key API Findings (PySide6 6.10.2)
- `QShortcut` is in `PySide6.QtGui`, NOT `PySide6.QtWidgets`
- `eventFilter(self, watched: QObject, event: QEvent) -> bool` — use `QEvent` type, not `object`
- `event.globalPosition().toPoint()` for Qt6 mouse events (not deprecated `globalPos()`)
- `isVisible()` returns False for children when parent window is not shown — use `isHidden()` instead
- `QWidget.setVisible(bool)` sets hidden state; `isHidden()` reflects this even without showing

### Window Flags Pattern
```python
self.setWindowFlags(
    Qt.WindowType.FramelessWindowHint
    | Qt.WindowType.WindowStaysOnTopHint
    | Qt.WindowType.Tool,
)
self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
```

### Hover Detection Pattern
- Install `eventFilter(self)` on `_jp_browser.viewport()` (not on browser itself)
- Use `QTextBrowser.cursorForPosition(viewport_pos)` to get QTextCursor at mouse position
- Use `cursor.position()` to get char index → pass to `HighlightRenderer.get_highlight_at_position()`

### Test Patterns
- Use `scope="session"` for QApplication fixture to ensure single instance
- Mock `HighlightRenderer.build_rich_text` to return simple HTML in tests
- `isHidden()` vs `isVisible()` — prefer `isHidden()` for widget-level visibility checks
- `QApplication.instance() or QApplication(sys.argv)` for safe QApp creation

### Verification
- `QT_QPA_PLATFORM=offscreen pytest tests/test_overlay.py -v`: 19 passed ✓
- `mypy src/ui/overlay.py tests/test_overlay.py`: Success ✓
- `ruff check .`: 0 errors ✓
- Full suite: 163 passed, 6 skipped ✓
- Evidence: `.sisyphus/evidence/task-5-init.txt`, `task-5-tests.txt`

## [2026-03-07] Task 6: TooltipPopup

### Implementation Summary
- `src/ui/tooltip.py`: 200-line `TooltipPopup(QWidget)` - frameless floating tooltip
- `tests/test_tooltip.py`: 21 tests, all passing

### Key Model Facts
- `VocabHit` fields: `surface`, `lemma`, `pos`, `jlpt_level`, `user_level`, `start_pos`, `end_pos`
- `GrammarHit` fields: `rule_id`, `matched_text`, `jlpt_level`, `confidence_type`, `description`, `start_pos`, `end_pos`
  - **`GrammarHit` has `matched_text`, NOT `pattern`** (task spec says `pattern` but actual model uses `matched_text`)
  - **`GrammarHit.description` is `str`, NOT `str | None`** (task spec says `str | None`)
- `JLPT_COLORS` dict keys are 4, 3, 2, 1 (NOT 5 — N5 has no entry, falls back to `_DEFAULT_LEVEL_COLOR`)

### Signal Deduplication Pattern
```python
self._shown: set[tuple[int | None, str, int]] = set()  # (sentence_id, type, highlight_id)

key = (sentence_id, "vocab", highlight_id)
if key not in self._shown:
    self._shown.add(key)
    self.record_triggered.emit("vocab", highlight_id)
```
- Vocab and grammar with same highlight_id are separate keys due to type string differentiator
- `None` sentence_id works correctly as a dict/set key

### Positioning Pattern
```python
def _position_near(self, position: QPoint) -> None:
    y = position.y() - self.sizeHint().height() - _TOOLTIP_OFFSET
    if y < 0:
        y = position.y() + _TOOLTIP_OFFSET
    self.move(position.x(), y)
```
- Call `adjustSize()` before `_position_near()` so sizeHint() is accurate

### Test Pattern for Signal Spy
```python
emissions: list[tuple[str, int]] = []
tooltip.record_triggered.connect(lambda t, i: emissions.append((t, i)))
```
- Use `reset_dedup()` at start of each emission test to clear shared fixture state
- Each test that checks emissions must `reset_dedup()` first since fixture is per-function but signal connections accumulate

### Verification
- `QT_QPA_PLATFORM=offscreen pytest tests/test_tooltip.py -v`: 21 passed ✓
- `ruff check .`: 0 errors ✓
- `mypy .`: Success (44 source files) ✓
- Full suite: 184 passed, 6 skipped ✓
- Evidence: `.sisyphus/evidence/task-6-vocab-tooltip.txt`, `task-6-dedup.txt`, `task-6-tests.txt`

## [2026-03-07] Task 7: main.py

### Implementation Summary
- `src/main.py`: 120-line entry point wiring full pipeline
- No test file needed (verified by import check + lint + full suite)

### Key API Findings
- `OverlayWindow.__init__` takes `parent: QWidget | None = None` — **NO config argument** (task spec warned to check)
- `VocabHit` and `GrammarHit` have **NO `id` field** — derive `highlight_id` from `result.highlight_vocab_ids`/`result.highlight_grammar_ids` lists by finding the hit's index in `result.analysis.vocab_hits`/`grammar_hits`
- `PipelineWorker(config, db_conn=conn)` — correct constructor, db_conn is keyword-only in practice
- `QApplication.instance() or QApplication(sys.argv)` — requires `# type: ignore[assignment]` for mypy strict since `instance()` returns `QCoreApplication | None`

### Initialization Order
1. `logging.basicConfig(level=INFO, format='...')`
2. `app = QApplication.instance() or QApplication(sys.argv)`
3. `config = load_config()`
4. `conn = init_db(config.db_path)` → `repo = LearningRepository(conn)`
5. `overlay = OverlayWindow()` (no config arg!)
6. `tooltip = TooltipPopup()`
7. `pipeline = PipelineWorker(config, db_conn=conn)`

### Signal Wiring
1. `pipeline.sentence_ready` → `overlay.on_sentence_ready`
2. `pipeline.error_occurred` → closure that logs + calls `overlay.set_status(f"Error: {msg}")`
3. `overlay.highlight_hovered` → closure that resolves `highlight_id` via index lookup and calls `tooltip.show_for_vocab/grammar`
4. `tooltip.record_triggered` → `repo.mark_tooltip_shown` (direct connection — signatures match)

### highlight_id Lookup Pattern
```python
result = overlay._current_result
if isinstance(hit, VocabHit):
    vocab_ids = result.highlight_vocab_ids or []
    idx = analysis.vocab_hits.index(hit)  # may raise ValueError
    highlight_id = vocab_ids[idx] if idx < len(vocab_ids) else 0
```
- Wrap `index()` in `try/except ValueError` to handle stale references

### Cleanup Pattern
```python
def _cleanup(pipeline, conn):
    try: pipeline.stop()
    except Exception: logger.exception(...)
    try: conn.close()
    except Exception: logger.exception(...)
```
- Each resource in its own try/except so second cleanup still runs if first fails
- Connected via `app.aboutToQuit.connect(lambda: _cleanup(pipeline, conn))`

### Verification
- `python -c "from src.main import main; print('IMPORT OK')"` → `IMPORT OK` ✓
- `ruff check src/main.py` → `All checks passed!` ✓
- `mypy src/main.py` → `Success: no issues found in 1 source file` ✓
- `QT_QPA_PLATFORM=offscreen pytest -x --tb=short` → `184 passed, 6 skipped` ✓
- Evidence: `.sisyphus/evidence/task-7-import.txt`, `task-7-wiring.txt`, `task-7-lint.txt`
