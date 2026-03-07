# Post-MVP Task List — MyASR Japanese Learning Overlay

> Generated from `docs/new_plan.md`. Each task is atomic and testable.
> Prefix: F0=Tray, F1=Settings, F1.5=Resize, F2=Learning Panel, F3=Export, F4=Review.

---

## Feature 0 — System Tray Icon

### F0.1 — Create `src/ui/tray.py`
- [ ] `SystemTrayManager(QObject)` class
- [ ] `QSystemTrayIcon` with placeholder app icon
- [ ] `QMenu` with actions: Settings, Learning History, Review, separator, Show/Hide Overlay, Quit
- [ ] Signals: `settings_requested`, `history_requested`, `review_requested`, `toggle_overlay`, `quit_requested`
- [ ] Method: `update_review_badge(count: int)` — update Review menu text to "Review (5 due)"
- [ ] Files: NEW `src/ui/tray.py`

### F0.2 — Wire tray into `main.py`
- [ ] Instantiate `SystemTrayManager` after QApplication
- [ ] Connect `quit_requested` → `QApplication.quit()`
- [ ] Connect `toggle_overlay` → `OverlayWindow.setVisible(not visible)`
- [ ] Ensure app doesn't quit when overlay is hidden (set `QApplication.setQuitOnLastWindowClosed(False)`)
- [ ] Files: MODIFY `src/main.py`

### F0.3 — Tray review badge timer
- [ ] QTimer (60s interval) to poll `ReviewRepository.get_queue_count()` and call `update_review_badge()`
- [ ] Only active after Feature 4 is integrated; until then, badge shows nothing
- [ ] Files: MODIFY `src/main.py`

### F0.4 — Tests
- [ ] Test menu actions emit correct signals
- [ ] Test `update_review_badge` updates menu text
- [ ] Test tray is visible on creation
- [ ] Files: NEW `tests/test_tray.py`

---

## Feature 1 — Settings Panel

### F1.1 — Extend `AppConfig` with new fields
- [ ] Add `overlay_opacity: float = 0.78`
- [ ] Add `overlay_width: int = 800`
- [ ] Add `overlay_height: int = 120`
- [ ] Add `overlay_font_size_jp: int = 16`
- [ ] Add `overlay_font_size_cn: int = 14`
- [ ] Add `enable_vocab_highlight: bool = True`
- [ ] Add `enable_grammar_highlight: bool = True`
- [ ] Add `audio_device_id: int | None = None`
- [ ] Verify `load_config()` handles missing new fields with defaults (backward compat)
- [ ] Verify `save_config()` serializes new fields correctly
- [ ] Files: MODIFY `src/config.py`

### F1.2 — Create `SettingsDialog`
- [ ] `SettingsDialog(QDialog)` with `QTabWidget`
- [ ] **General tab**: QSpinBox for JLPT level (1–5), QComboBox for llm_mode
- [ ] **Appearance tab**: QSlider for opacity (0.1–1.0 step 0.01), QSpinBoxes for font sizes, QCheckBoxes for highlight toggles
- [ ] **Model tab**: QLineEdits for ollama_url/model, QDoubleSpinBox for timeout, "Test Connection" QPushButton calling `OllamaClient.health_check()` with status label
- [ ] **Templates tab**: QPlainTextEdits for translation/explanation templates with `{japanese_text}` placeholder documentation
- [ ] Save button: validate inputs → `save_config()` → emit `config_changed(AppConfig)`
- [ ] Cancel button: discard changes, close dialog
- [ ] Load current config values into widgets on open
- [ ] Signal: `config_changed = Signal(object)` — emits the new AppConfig
- [ ] Files: NEW `src/ui/settings.py`

### F1.3 — Live-reload on OverlayWindow
- [ ] New slot `on_config_changed(config: AppConfig)`
- [ ] Update `setWindowOpacity(config.overlay_opacity)`
- [ ] Update `_jp_browser` font size from `config.overlay_font_size_jp`
- [ ] Update `_cn_browser` font size from `config.overlay_font_size_cn`
- [ ] Update `_user_level` from `config.user_jlpt_level`
- [ ] Update highlight toggles (re-render current sentence if present)
- [ ] Files: MODIFY `src/ui/overlay.py`

### F1.4 — Live-reload on PipelineWorker
- [ ] New slot `on_config_changed(config: AppConfig)`
- [ ] Update `_preprocessing._user_level`
- [ ] Update `_llm_client` fields (mode, templates, url, model, timeout) — reconstruct or update in place
- [ ] Thread-safe: use `QMetaObject.invokeMethod` with `Qt.QueuedConnection` or guard with lock
- [ ] Files: MODIFY `src/pipeline.py`

### F1.5 — Wire settings in `main.py`
- [ ] Connect tray `settings_requested` → create/show `SettingsDialog(config)`
- [ ] Connect `SettingsDialog.config_changed` → `OverlayWindow.on_config_changed`
- [ ] Connect `SettingsDialog.config_changed` → `PipelineWorker.on_config_changed`
- [ ] Files: MODIFY `src/main.py`

### F1.6 — Tests
- [ ] Test config round-trip with new fields (load → save → load)
- [ ] Test backward compatibility (load old config missing new fields → defaults applied)
- [ ] Test SettingsDialog populates widgets from config
- [ ] Test SettingsDialog save emits `config_changed` with correct values
- [ ] Test OverlayWindow.on_config_changed updates opacity, font sizes
- [ ] Files: NEW `tests/test_settings.py`, extend `tests/test_config.py`

---

## Feature 1.5 — Overlay Resize & Adaptive Text Layout

### F1.5.1 — Add resize support to OverlayWindow
- [ ] Remove fixed `resize(800, 120)` call
- [ ] Set `setMinimumSize(400, 80)` and `setMaximumSize(screen_width, 400)`
- [ ] Add `QSizeGrip` widget in bottom-right corner (styled to blend with dark background)
- [ ] Read initial size from `config.overlay_width` / `config.overlay_height`
- [ ] Override `resizeEvent()`: update `_center_on_screen()`, debounce config save (500ms QTimer singleShot)
- [ ] Debounced save: write new width/height to config, call `save_config()`
- [ ] Ensure drag-to-move still works alongside resize
- [ ] Files: MODIFY `src/ui/overlay.py`

### F1.5.2 — Adaptive text layout (centered container, left-aligned text)
- [ ] Modify `build_rich_text()` HTML output to wrap in centered div:
  ```html
  <div style="text-align: center; width: 100%;">
    <span style="display: inline-block; text-align: left; max-width: 95%;">
      ...highlighted spans...
    </span>
  </div>
  ```
- [ ] Apply same layout pattern to translation line in OverlayWindow
- [ ] Ensure multi-line wrapping works when text exceeds viewport width
- [ ] Verify QTextBrowser word-wrap remains enabled (default)
- [ ] Files: MODIFY `src/ui/highlight.py`, MODIFY `src/ui/overlay.py`

### F1.5.3 — Tests
- [ ] Test overlay respects min/max size constraints
- [ ] Test resizeEvent triggers debounced config save
- [ ] Test build_rich_text output contains centered div wrapper
- [ ] Test multi-line text renders correctly (manual/visual — add note in test)
- [ ] Files: NEW `tests/test_overlay_resize.py`, extend `tests/test_highlight.py`

---

## Feature 2 — Learning Panel (History)

### F2.1 — Extend `LearningRepository` with filtered queries
- [ ] `get_sentences_filtered(limit, offset, sort_by, sort_order, date_from, date_to) → list[SentenceRecord]`
- [ ] `get_sentence_count(query, date_from, date_to) → int`
- [ ] `get_sentence_with_highlights(sentence_id) → tuple[SentenceRecord, list[HighlightVocab], list[HighlightGrammar]]`
- [ ] All methods use parameterized SQL (no f-string injection)
- [ ] Files: MODIFY `src/db/repository.py`

### F2.2 — Create `LearningPanel(QWidget)`
- [ ] Top bar: QLineEdit (search), QDateEdit×2 (from/to), QPushButton "Search"
- [ ] QTableWidget with columns: Created At, Japanese Text, Translation (truncated 40 chars), Vocab Count
- [ ] Click row → open `SentenceDetailDialog`
- [ ] Pagination: Previous/Next QPushButtons + QLabel "Page X of Y"
- [ ] Page size: 50 records (configurable constant)
- [ ] Bottom bar: "Export" QPushButton, "Delete by Date Range" QPushButton
- [ ] "Delete by Date Range" → QMessageBox confirmation → `repo.delete_before()`
- [ ] Files: NEW `src/ui/learning_panel.py`

### F2.3 — Create `SentenceDetailDialog(QDialog)`
- [ ] Show full highlighted Japanese text (reuse `HighlightRenderer.build_rich_text`)
- [ ] Show translation and explanation
- [ ] List vocab hits with JLPT badge + lemma + POS
- [ ] List grammar hits with JLPT badge + pattern + description
- [ ] "Add to Review" button per vocab/grammar item (calls `review_repo.add_item()`)
- [ ] Visual indicator (★) for items already in review queue (check via `review_repo`)
- [ ] Timestamp display
- [ ] Files: within `src/ui/learning_panel.py` or NEW `src/ui/sentence_detail.py`

### F2.4 — Wire into `main.py`
- [ ] Connect tray `history_requested` → create/show `LearningPanel(repo)`
- [ ] Optional: connect `pipeline.sentence_ready` → `LearningPanel.refresh()` if visible
- [ ] Files: MODIFY `src/main.py`

### F2.5 — Tests
- [ ] Test `get_sentences_filtered` with various sort/filter combos against test DB
- [ ] Test `get_sentence_count` with and without query
- [ ] Test `get_sentence_with_highlights` returns correct associated records
- [ ] Test pagination logic (page count calculation, boundary conditions)
- [ ] Test panel creation with mocked repository
- [ ] Files: NEW `tests/test_learning_panel.py`

---

## Feature 3 — CSV/JSON Export (with filters)

### F3.1 — Extend `export_records()` with filters
- [ ] New signature: `export_records(format, date_from, date_to, include_highlights) → str`
- [ ] Date range filtering via WHERE clause
- [ ] `include_highlights=True` for JSON: nest `vocab_highlights` and `grammar_highlights` arrays per record
- [ ] `include_highlights=True` for CSV: add columns `vocab_count`, `grammar_count`, `vocab_lemmas`, `grammar_rules`
- [ ] Files: MODIFY `src/db/repository.py`

### F3.2 — Export dialog in Learning Panel
- [ ] "Export" button → dialog with: date range (pre-filled from current filter), format radio (JSON/CSV), "Include highlights" checkbox
- [ ] `QFileDialog.getSaveFileName` with filter `*.json` / `*.csv`
- [ ] Write `export_records()` result to file
- [ ] QMessageBox on success / error
- [ ] Files: MODIFY `src/ui/learning_panel.py`

### F3.3 — Quick Export in tray menu
- [ ] "Quick Export" action in tray context menu
- [ ] Exports all records as JSON to user-chosen file (no filter dialog)
- [ ] Files: MODIFY `src/ui/tray.py`, MODIFY `src/main.py`

### F3.4 — Tests
- [ ] Test filtered export with date_from/date_to
- [ ] Test `include_highlights=True` JSON has nested arrays with correct fields
- [ ] Test `include_highlights=True` CSV has correct additional columns
- [ ] Test export with no records returns empty JSON array / CSV header only
- [ ] Files: NEW `tests/test_export_filtered.py` or extend `tests/test_db_repository.py`

---

## Feature 4 — Review System (SM-2)

### F4A — Database Layer

#### F4A.1 — Add `review_items` table to schema
- [ ] CREATE TABLE with columns: id, item_type, item_key, display, jlpt_level, first_sentence_id (FK), interval_days, ease_factor, repetitions, next_review, last_review, last_grade, total_encounters, created_at
- [ ] UNIQUE constraint on (item_type, item_key)
- [ ] Index on next_review for efficient queue queries
- [ ] FK to sentence_records(id) — but NO CASCADE DELETE (review items survive sentence deletion)
- [ ] Add to `init_db()` CREATE TABLE statements
- [ ] Files: MODIFY `src/db/schema.py`

#### F4A.2 — Add `ReviewItem` model and `ReviewGrade` enum
- [ ] `ReviewItem` dataclass: id, item_type, item_key, display, jlpt_level, first_sentence_id, interval_days, ease_factor, repetitions, next_review, last_review, last_grade, total_encounters, created_at
- [ ] `ReviewGrade(IntEnum)`: AGAIN=0, HARD=1, GOOD=2, EASY=3
- [ ] Files: MODIFY `src/db/models.py`

#### F4A.3 — Tests
- [ ] Test table creation in init_db
- [ ] Test UNIQUE constraint prevents duplicate (item_type, item_key)
- [ ] Test FK allows valid sentence_id, rejects invalid
- [ ] Files: extend `tests/test_db_schema.py`

### F4B — SM-2 Algorithm

#### F4B.1 — Implement `calculate_sm2()`
- [ ] Pure function in `src/review/sm2.py`
- [ ] Signature: `calculate_sm2(repetitions, ease_factor, interval_days, grade) → (new_rep, new_ease, new_interval)`
- [ ] grade < 2 (Again/Hard): reset rep=0, interval=1, ease -= 0.2 (clamp ≥ 1.3)
- [ ] grade == 2 (Good): rep 0→1 day, rep 1→6 days, else→interval*ease; ease unchanged; rep += 1
- [ ] grade == 3 (Easy): same interval as Good; ease += 0.15; rep += 1
- [ ] Ease floor: 1.3
- [ ] Files: NEW `src/review/__init__.py`, NEW `src/review/sm2.py`

#### F4B.2 — Tests (parametrized)
- [ ] AGAIN resets interval to 1, repetitions to 0
- [ ] HARD resets interval to 1, repetitions to 0, decreases ease
- [ ] GOOD on rep=0 → interval=1
- [ ] GOOD on rep=1 → interval=6
- [ ] GOOD on rep=2 with ease=2.5 → interval=6*2.5=15
- [ ] EASY increases ease by 0.15
- [ ] Repeated HARD decreases ease to floor 1.3 (never below)
- [ ] Large repetition counts produce reasonable intervals (no overflow)
- [ ] Files: NEW `tests/test_sm2.py`

### F4C — Review Repository

#### F4C.1 — Create `ReviewRepository`
- [ ] `__init__(self, conn: sqlite3.Connection)`
- [ ] `add_item(item_type, item_key, display, jlpt_level, sentence_id) → int | None` — INSERT with ON CONFLICT(item_type, item_key) DO NOTHING, return id or None if existed
- [ ] `implicit_review(item_type, item_key) → None` — SELECT item, apply `calculate_sm2(grade=GOOD)`, UPDATE, increment total_encounters
- [ ] `get_due_items(limit=20) → list[ReviewItem]` — WHERE next_review <= datetime('now') ORDER BY next_review ASC
- [ ] `get_queue_count() → int` — COUNT WHERE next_review <= datetime('now')
- [ ] `update_after_review(item_id, grade) → None` — apply `calculate_sm2(grade)`, UPDATE all fields
- [ ] `get_item_with_context(item_id) → tuple[ReviewItem, SentenceRecord, HighlightVocab | HighlightGrammar]` — JOIN review_items + sentence_records + highlight table
- [ ] `get_stats() → dict` — total_items, due_today, avg_ease, items_per_level breakdown
- [ ] `increment_encounters(item_type, item_key) → None` — UPDATE total_encounters += 1
- [ ] Files: NEW `src/db/review_repository.py`

#### F4C.2 — Tests
- [ ] Test add_item creates new item with correct defaults (ease=2.5, rep=0, interval=0)
- [ ] Test add_item returns None for duplicate (item_type, item_key)
- [ ] Test implicit_review applies SM-2 GOOD and increments total_encounters
- [ ] Test get_due_items returns only items where next_review <= now
- [ ] Test get_due_items respects limit
- [ ] Test update_after_review correctly updates all SM-2 fields
- [ ] Test get_item_with_context joins correctly for both vocab and grammar types
- [ ] Test get_stats returns correct aggregates
- [ ] Files: NEW `tests/test_review_repository.py`

### F4D — Auto-Enrollment & Implicit Review

#### F4D.1 — Hook into PipelineWorker
- [ ] After `insert_sentence()` in `_process_segment()`, iterate vocab_hits and grammar_hits
- [ ] For each beyond-level vocab hit: `review_repo.add_item(item_type='vocab', item_key=hit.lemma, ...)`. If None → `review_repo.implicit_review('vocab', hit.lemma)`
- [ ] For each beyond-level grammar hit: `review_repo.add_item(item_type='grammar', item_key=hit.rule_id, ...)`. If None → `review_repo.implicit_review('grammar', hit.rule_id)`
- [ ] Fix existing bug: `is_beyond_level` currently hardcoded True — should be `hit.jlpt_level > config.user_jlpt_level` (or `hit.jlpt_level < config.user_jlpt_level` depending on JLPT numbering where N1 > N5)
- [ ] Inject `ReviewRepository` into PipelineWorker.__init__ (optional dependency, None if review not initialized)
- [ ] Files: MODIFY `src/pipeline.py`

#### F4D.2 — Manual enrollment from Learning Panel
- [ ] "Add to Review" button in `SentenceDetailDialog` per vocab/grammar item
- [ ] Calls `review_repo.add_item()` with highlight data
- [ ] Button text changes to "★ In Review" after adding (disabled)
- [ ] On dialog open, check which items are already in review_items and show ★
- [ ] Files: MODIFY `src/ui/learning_panel.py`

#### F4D.3 — Tests
- [ ] Test auto-enrollment creates review item for beyond-level vocab
- [ ] Test auto-enrollment skips at-or-below-level vocab
- [ ] Test re-encounter of same lemma triggers implicit_review (not add_item)
- [ ] Test re-encounter increments total_encounters
- [ ] Test manual enrollment from detail view
- [ ] Files: extend `tests/test_review_repository.py`, extend `tests/test_pipeline.py`

### F4E — Review UI

#### F4E.1 — Selective highlighting in `HighlightRenderer`
- [ ] New method: `build_review_text(japanese_text, analysis, target: VocabHit | GrammarHit) → str`
- [ ] Filter analysis hits to ONLY include the target item (match by start_pos + end_pos)
- [ ] Target gets its JLPT color highlight; everything else rendered as plain white text
- [ ] Wrap in same centered-container HTML layout from Feature 1.5
- [ ] Files: MODIFY `src/ui/highlight.py`

#### F4E.2 — Create `ReviewPanel(QWidget)`
- [ ] Separate top-level window
- [ ] **Header**: QProgressBar "X of Y due" + due count label
- [ ] **Card area**: QFrame containing:
  - JLPT badge (QLabel with colored background)
  - Item display (QLabel: lemma/surface for vocab, pattern for grammar)
  - POS / confidence_type (QLabel)
  - Source sentence (QTextBrowser with `build_review_text()` output — only target highlighted)
  - "Click to reveal" divider (QPushButton or clickable QLabel)
  - Hidden back panel: translation QLabel + explanation QLabel
- [ ] **Grade buttons**: 4 QPushButtons — Again (red), Hard (orange), Good (green), Easy (blue)
- [ ] **Session stats footer**: QLabel with reviewed count, grade distribution
- [ ] Files: NEW `src/ui/review_panel.py`

#### F4E.3 — Card state machine
- [ ] State: FRONT → BACK → GRADED → (next card or SUMMARY)
- [ ] FRONT: card back hidden, grade buttons disabled
- [ ] BACK: reveal translation/explanation, enable grade buttons
- [ ] GRADED: call `review_repo.update_after_review(item_id, grade)`, load next due item
- [ ] SUMMARY: all due items done → show session stats + "next review in X hours" + Close button
- [ ] EMPTY: no due items → show "All caught up!" + next scheduled review time
- [ ] Files: within `src/ui/review_panel.py`

#### F4E.4 — Keyboard shortcuts
- [ ] Space → reveal back (FRONT→BACK transition)
- [ ] 1 → Again (grade 0)
- [ ] 2 → Hard (grade 1)
- [ ] 3 → Good (grade 2)
- [ ] 4 → Easy (grade 3)
- [ ] Esc → close panel
- [ ] Shortcuts only active in appropriate states (e.g., 1-4 only in BACK state)
- [ ] Files: within `src/ui/review_panel.py`

#### F4E.5 — Wire into `main.py`
- [ ] Connect tray `review_requested` → create/show `ReviewPanel(review_repo)`
- [ ] Pass `ReviewRepository` and `LearningRepository` to ReviewPanel
- [ ] Tray badge integration (Feature 0.3 timer polls and updates badge)
- [ ] Files: MODIFY `src/main.py`

#### F4E.6 — Tests
- [ ] Test `build_review_text` highlights only target item (check HTML has exactly 1 colored span)
- [ ] Test `build_review_text` renders other text as plain (no color spans)
- [ ] Test card state machine: FRONT→BACK→GRADED→next card
- [ ] Test EMPTY state shown when no due items
- [ ] Test SUMMARY state after all items reviewed
- [ ] Test keyboard shortcuts trigger correct state transitions
- [ ] Test grade buttons call `update_after_review` with correct grade
- [ ] Files: NEW `tests/test_review_panel.py`, extend `tests/test_highlight.py`

---

## Summary

| Feature | New Files | Modified Files | Tasks | Est. Effort |
|---------|-----------|----------------|-------|-------------|
| F0 Tray | 2 | 1 | 4 | Small |
| F1 Settings | 1 | 4 | 6 | Medium |
| F1.5 Resize | 0 | 3 | 3 | Small-Medium |
| F2 Learning Panel | 1 | 2 | 5 | Medium |
| F3 Export | 0 | 3 | 4 | Small |
| F4A Review DB | 0 | 2 | 3 | Small |
| F4B SM-2 | 2 | 0 | 2 | Small |
| F4C Review Repo | 1 | 0 | 2 | Medium |
| F4D Auto-Enroll | 0 | 2 | 3 | Medium |
| F4E Review UI | 1 | 3 | 6 | Large |
| **Total** | **8** | **9** (unique) | **38** | |
