
## Task 4: SystemTrayManager Wiring (2026-03-07)

### Implementation Pattern
- Import `SystemTrayManager` from `src.ui.tray`
- Add `app.setQuitOnLastWindowClosed(False)` immediately after `QApplication` creation, BEFORE any `window.show()`
- Instantiate `tray = SystemTrayManager()` in main() scope (prevents GC)
- Connect all 4 signals: quit_requested, toggle_overlay, settings_requested, history_requested
- Placeholder functions `_open_settings()` and `_open_learning_panel()` log "not yet implemented"
- Add TODO(F4) comment for review badge timer

### Key Order
1. `app = QApplication(...)`
2. `app.setQuitOnLastWindowClosed(False)` ← MUST be here
3. Create components (overlay, tooltip, pipeline, tray)
4. Connect signals
5. `overlay.show()`

### Files Modified
- `src/main.py` only (no changes to overlay.py, tray.py, config.py)

### Evidence Files
- `.sisyphus/evidence/task-4-tray-wiring-ast.txt`
- `.sisyphus/evidence/task-4-quit-signal.txt`
- `.sisyphus/evidence/task-4-no-timer.txt`

## Task 11: Thread-safe config update + is_beyond_level fix (2026-03-07)

### Pattern: Queue-based thread-safe config update
- `queue.Queue[AppConfig]` (no maxsize) as `self._config_queue`
- `update_config(config)` → `self._config_queue.put_nowait(config)` — callable from UI thread
- `_apply_config(config)` — updates `self._config`, `self._user_level`, recreates `OllamaClient(config)`
- Drain queue at TOP of `while self._running:` loop via `get_nowait()` + `except queue.Empty: pass`
- No `threading.Lock` needed — queue is sufficient for single-consumer pattern

### is_beyond_level fix
- `VocabHit.jlpt_level: int` (non-nullable) — safe for `>` comparison
- `GrammarHit.jlpt_level: int` (non-nullable) — safe for `>` comparison
- `HighlightVocab.jlpt_level: int | None` (DB model, nullable) — but source `vh.jlpt_level` is int
- Pattern: `is_beyond_level=vh.jlpt_level > self._user_level`

### Pre-existing failures (not our problem)
- `tests/test_pipeline.py` fails with `AttributeError: src.pipeline has no attribute 'AudioCapture'` — pre-existed before this task
- `src/audio/backends.py` has 4 mypy errors — pre-existing

## Task 10 — F1.3: on_config_changed live-reload slot

### What was done
- Added `self._enable_vocab` / `self._enable_grammar` init from config in `__init__`
- Added `self.setWindowOpacity(config.overlay_opacity)` call in `__init__`
- Modified `on_sentence_ready()` to create a local `AnalysisResult` copy with vocab_hits/grammar_hits filtered to `[]` when toggles are off — never mutates the original `result.analysis`
- Added `on_config_changed(config: AppConfig)` method: updates opacity, user_level, enable flags, jp/cn font via `_make_font()`, re-renders if `_current_result` is not None
- Fixed pre-existing broken fixture in `tests/test_overlay.py` (was calling `OverlayWindow()` without `config` arg — a pre-existing bug from prior task)
- Added 7 new tests covering on_config_changed and filtering behavior

### Key patterns
- Use `AnalysisResult(tokens=r.tokens, vocab_hits=[] if disabled else r.vocab_hits, grammar_hits=...)` to filter without mutating
- Font size updated via `browser.setFont(_make_font(size))` — same helper as construction
- Do NOT call `_save_size()` from `on_config_changed` — config already saved by settings dialog
- `setWindowOpacity()` must be called both at init and on config change

### Pre-existing broken tests (not introduced by Task 10)
- `tests/test_highlight.py::test_build_rich_text_no_hits_returns_escaped_plain_text` — test expects plain escaped text but `build_rich_text` now wraps in `<table>` (Task 7 change)
- `tests/test_pipeline.py` (13 failures) — `src.pipeline.AudioCapture` attribute missing, from pipeline refactor
