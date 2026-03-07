# Learnings — post-mvp-features

## [2026-03-07] Wave 1 + Wave 2: Completed

### API Facts
- `build_rich_text(japanese_text, analysis: AnalysisResult, user_level: int)` — second arg is `AnalysisResult`, NOT `SentenceResult`
- `AnalysisResult` has fields: `tokens`, `vocab_hits`, `grammar_hits`
- `SentenceResult` fields: `japanese_text`, `chinese_translation`, `explanation`, `analysis`, `created_at`, `sentence_id`, `highlight_vocab_ids`, `highlight_grammar_ids`
- DB schema module is `src.db.schema` — `init_db(path)` is in `src/db/schema.py`
- OllamaClient constructor: `OllamaClient(config: AppConfig)` — takes full AppConfig, NOT individual params
- `queue.Queue[AppConfig]` for thread-safe pipeline config update — NOT QMetaObject (pipeline has no Qt event loop)

### Codebase Conventions
- Line length: 99, double quotes, trailing commas in multi-line
- All public functions require type annotations
- mypy strict mode — Google-style docstrings for public classes/functions
- Pre-existing mypy errors (NOT new): `src/vad/silero.py:104` (float→int) and `src/analysis/tokenizer.py:19,22` (fugashi.Tagger) — ignore these

### Qt/PySide6 Patterns
- Qt tests: `QT_QPA_PLATFORM=offscreen`, session-scoped qapp fixture in conftest.py
- `app.setQuitOnLastWindowClosed(False)` must be set before overlay.show()
- Do NOT use QMetaObject.invokeMethod in pipeline thread
- SettingsDialog uses `.show()` (non-modal), not `.exec()`
- QTextBrowser does NOT support `display: inline-block` CSS — use table-based centering
- Thread-safe config: `queue.Queue` in pipeline's while-loop (check at TOP before VAD)

### Feature 4 Exclusion (CRITICAL)
- NO review_items table, SM-2, ReviewRepository, ReviewPanel, auto-enrollment, build_review_text
- NO "Add to Review" buttons anywhere
- NO abstract base classes, event bus, FormBuilder, WidgetFactory abstractions

### Task Completions
- Task 1: `src/ui/tray.py` — SystemTrayManager with 5 signals, 6 menu actions (commit a2a0ed1)
- Task 2: `src/config.py` — 8 new AppConfig fields (commit 3f06065)
- Task 4: `src/main.py` — tray wired, stubs for _open_settings/_open_learning_panel
- Task 5: `src/ui/settings.py` — SettingsDialog(QDialog) with 4 tabs
- Task 6: `src/ui/overlay.py` — OverlayWindow(config), QSizeGrip, _center_on_screen()
- Task 7: `src/ui/highlight.py` — table-based centering in build_rich_text()
- Task 8: `src/db/repository.py` — get_sentences_filtered, get_sentence_count, get_sentence_with_highlights
- Task 9: `src/db/repository.py` — export_records with date filter + highlight details
- Wave 2 commit: ccae34f
