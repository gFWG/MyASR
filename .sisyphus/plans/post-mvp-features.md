# Post-MVP Features: System Tray, Settings, Resize, Learning Panel, Export

## TL;DR

> **Quick Summary**: Add 5 features to the MyASR overlay — system tray entry point, settings dialog with live-reload, overlay resize with adaptive text, learning history panel with detail view, and filtered CSV/JSON export with highlight inclusion.
> 
> **Deliverables**:
> - System tray icon with context menu (app entry point for all panels)
> - Settings dialog (4 tabs: General, Appearance, Model, Templates) with live config reload
> - Overlay resize via QSizeGrip + debounced config persistence + centered text layout
> - Learning history panel with search/filter, pagination, detail view
> - Filtered export (date range, highlights) in JSON/CSV from panel + quick export from tray
> 
> **Estimated Effort**: Large (38 tasks across 5 features)
> **Parallel Execution**: YES — 4 waves
> **Critical Path**: F0 (Tray) → F1.1 (Config) → F1.2+F1.5.1+F2.1 (parallel) → F1.5+F2.4+F3.2 (wiring)

---

## Context

### Original Request
Implement Features 0, 1, 1.5, 2, 3 from `docs/new_plan.md` — the Post-MVP batch excluding the Review System (Feature 4).

### Interview Summary
**Key Discussions**:
- Scope: F0+F1+F1.5+F2+F3 only. Feature 4 (Review System SM-2) explicitly excluded.
- Test strategy: Tests-after following existing pytest patterns (session-scoped qapp, :memory: SQLite, mock external deps).
- Tray review badge: Stub with TODO — menu item disabled with "(coming soon)".
- SentenceDetailDialog: NO "Add to Review" buttons (F4 scope).

**Research Findings**:
- Pipeline's blocking while-loop has no `processEvents()` — queued signals WILL NOT be delivered. Must use `queue.Queue[AppConfig]` for config updates.
- QTextBrowser doesn't support CSS `display: inline-block` — need table-based or `align="center"` fallback for centered text layout.
- QSizeGrip + FramelessWindowHint interaction is platform-dependent — need fallback to manual edge-resize.
- SQLite cross-thread: LearningPanel (main thread) + PipelineWorker (worker thread) need separate connections. WAL mode handles concurrent access.
- `_center_on_screen()` doesn't exist yet — must extract from inline positioning code in overlay `__init__`.
- `OllamaClient.health_check()` already exists at ollama_client.py:83-88.
- `load_config()` doesn't filter unknown keys — adding fields to AppConfig needs a filter to avoid TypeError on old configs with removed keys.

### Metis Review
**Identified Gaps** (addressed):
- Pipeline config thread safety → queue.Queue approach adopted
- QTextBrowser CSS limitations → table-based centering fallback documented
- QSizeGrip platform risk → manual resize fallback documented
- Config write race condition → both write paths are main-thread, no lock needed
- SQLite cross-thread → separate connections per thread with WAL
- Config backward compat → filter unknown keys before AppConfig construction
- Debounced save lost on quit → flush pending save on closeEvent
- Single SettingsDialog instance pattern → store reference, raise if visible
- Dynamic WHERE clause for filtered queries → conditional clause building
- JLPT numbering: N1=1 (hardest), N5=5 (easiest) → beyond-level = jlpt_level < user_level

---

## Work Objectives

### Core Objective
Add system tray navigation, user-configurable settings with live-reload, overlay resize with adaptive text, a learning history panel with detail view, and filtered export — completing the Post-MVP P1 feature set.

### Concrete Deliverables
- `src/ui/tray.py` — SystemTrayManager with context menu and signals
- `src/ui/settings.py` — SettingsDialog with 4 tabs and config_changed signal
- `src/ui/learning_panel.py` — LearningPanel with table, pagination, SentenceDetailDialog
- Updated `src/config.py` — 8 new AppConfig fields with defaults
- Updated `src/ui/overlay.py` — QSizeGrip resize, config_changed slot, adaptive text
- Updated `src/ui/highlight.py` — Centered container HTML layout
- Updated `src/db/repository.py` — Filtered queries, counts, highlight joins, filtered export
- Updated `src/pipeline.py` — queue.Queue config update mechanism
- Updated `src/main.py` — Tray instantiation, signal wiring, panel lifecycle
- 6 new test files + extensions to 3 existing test files

### Definition of Done
- [ ] `ruff check . && ruff format --check . && mypy . && pytest` passes
- [ ] System tray visible with all menu actions functional
- [ ] Settings dialog opens from tray, saves config, live-reloads overlay
- [ ] Overlay resize via QSizeGrip works, size persists across restarts
- [ ] Learning panel shows sentence history with search, pagination, detail view
- [ ] Export produces valid JSON/CSV with optional date filter and highlights

### Must Have
- System tray as app entry point (keeps app alive when overlay hidden)
- All 8 new config fields with backward-compatible defaults
- Live config reload on overlay (opacity, fonts, highlights)
- Thread-safe config update on pipeline via queue.Queue
- Overlay resize with debounced config persistence
- Centered text layout in overlay (works with multi-line wrapping)
- Learning panel with filtered queries, pagination, detail view
- Export with date range filter and optional highlight inclusion
- Tests for every feature following existing pytest patterns

### Must NOT Have (Guardrails)
- NO Feature 4 code (review_items table, SM-2, ReviewRepository, ReviewPanel, auto-enrollment, build_review_text)
- NO "Add to Review" buttons in SentenceDetailDialog
- NO abstract base classes, event bus, observer pattern, or utility modules
- NO config migration/versioning system — just add fields with defaults
- NO template validation, syntax highlighting, or preview in Settings
- NO full-text search index, fuzzy search, or search-as-you-type in Learning Panel
- NO infinite scroll or variable page size — fixed 50 rows with Previous/Next buttons
- NO streaming export, progress bars, or format selection on Quick Export
- NO multi-monitor position persistence or snap-to-grid on resize
- NO excessive logging, over-documentation, or premature generalization
- NO `WidgetFactory`, `FormBuilder`, `FilterableTableWidget`, `ExportManager`, or similar abstractions

---

## Verification Strategy

> **ZERO HUMAN INTERVENTION** — ALL verification is agent-executed. No exceptions.

### Test Decision
- **Infrastructure exists**: YES (pytest + pytest-mock, 19 test files, ~200 tests)
- **Automated tests**: Tests-after (implementation first, then test tasks)
- **Framework**: pytest with pytest-mock
- **No pytest-qt**: Qt tests use manual qapp fixture + unittest.mock.patch

### QA Policy
Every task MUST include agent-executed QA scenarios.
Evidence saved to `.sisyphus/evidence/task-{N}-{scenario-slug}.{ext}`.

- **Frontend/UI**: Use Playwright (playwright skill) for visual verification where applicable
- **TUI/CLI**: Use interactive_bash (tmux) for runtime testing
- **Library/Module**: Use Bash (python REPL / pytest) for unit verification

### Test Patterns to Follow
- **Qt tests**: Session-scoped `qapp` fixture per test file: `QApplication.instance() or QApplication(sys.argv)`
- **DB tests**: In-memory SQLite via `init_db(":memory:")` → `LearningRepository(conn)`
- **Pipeline tests**: Mock all external deps via `@patch`
- **Validation**: `ruff check . && ruff format --check . && mypy . && pytest` after each feature

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Start Immediately — foundation):
├── Task 1: F0 — SystemTrayManager class + signals [quick]
├── Task 2: F1.1 — Extend AppConfig with new fields [quick]
├── Task 3: F4B.1 — SM-2 pure algorithm (CANCELLED — F4 out of scope)

Wave 2 (After Wave 1 — core modules, MAX PARALLEL):
├── Task 4: F0 — Wire tray into main.py + badge stub [quick]
├── Task 5: F1.2 — Create SettingsDialog with 4 tabs [unspecified-high]
├── Task 6: F1.5.1 — Add resize support to OverlayWindow [deep]
├── Task 7: F1.5.2 — Adaptive text layout (centered HTML) [unspecified-high]
├── Task 8: F2.1 — Extend LearningRepository with filtered queries [unspecified-high]
├── Task 9: F3.1 — Extend export_records with filters + highlights [unspecified-high]

Wave 3 (After Wave 2 — integration + UI panels):
├── Task 10: F1.3 — Live-reload on OverlayWindow [quick]
├── Task 11: F1.4 — Thread-safe config update on PipelineWorker [deep]
├── Task 12: F2.2 — Create LearningPanel with table + pagination [unspecified-high]
├── Task 13: F2.3 — Create SentenceDetailDialog [unspecified-high]
├── Task 14: F3.2 — Export dialog in LearningPanel [quick]
├── Task 15: F3.3 — Quick Export in tray menu [quick]

Wave 4 (After Wave 3 — wiring + tests):
├── Task 16: F1.5 — Wire settings into main.py [quick]
├── Task 17: F2.4 — Wire LearningPanel into main.py [quick]
├── Task 18: F0.4 — Tests for tray [quick]
├── Task 19: F1.6 — Tests for settings + config [unspecified-high]
├── Task 20: F1.5.3 — Tests for resize + text layout [quick]
├── Task 21: F2.5 — Tests for learning panel + repository [unspecified-high]
├── Task 22: F3.4 — Tests for filtered export [unspecified-high]

Wave FINAL (After ALL tasks — independent review, 4 parallel):
├── Task F1: Plan compliance audit (oracle)
├── Task F2: Code quality review (unspecified-high)
├── Task F3: Real manual QA (unspecified-high)
└── Task F4: Scope fidelity check (deep)

Critical Path: Task 1 → Task 4 → Task 5 → Task 10 → Task 16 → Task 19 → F1-F4
Parallel Speedup: ~65% faster than sequential
Max Concurrent: 6 (Wave 2)
```

### Dependency Matrix

| Task | Depends On | Blocks | Wave |
|------|-----------|--------|------|
| 1 (Tray class) | — | 4, 15, 18 | 1 |
| 2 (Config fields) | — | 5, 6, 7, 8, 9, 10, 11 | 1 |
| 4 (Tray wiring) | 1 | 15, 17, 18 | 2 |
| 5 (Settings dialog) | 2 | 10, 11, 16, 19 | 2 |
| 6 (Resize support) | 2 | 10, 16, 20 | 2 |
| 7 (Text layout) | 2 | 10, 13, 20 | 2 |
| 8 (Filtered queries) | 2 | 12, 13, 14, 21 | 2 |
| 9 (Export extension) | 2 | 14, 15, 22 | 2 |
| 10 (Overlay reload) | 5, 6, 7 | 16, 19 | 3 |
| 11 (Pipeline reload) | 5 | 16, 19 | 3 |
| 12 (Learning panel) | 8 | 13, 14, 17, 21 | 3 |
| 13 (Detail dialog) | 7, 8 | 17, 21 | 3 |
| 14 (Export dialog) | 8, 9, 12 | 22 | 3 |
| 15 (Quick export) | 1, 4, 9 | 22 | 3 |
| 16 (Settings wiring) | 4, 5, 10, 11 | 19 | 4 |
| 17 (Panel wiring) | 4, 12, 13 | 21 | 4 |
| 18 (Tray tests) | 1, 4 | — | 4 |
| 19 (Settings tests) | 5, 10, 16 | — | 4 |
| 20 (Resize tests) | 6, 7 | — | 4 |
| 21 (Panel tests) | 8, 12, 13, 17 | — | 4 |
| 22 (Export tests) | 9, 14, 15 | — | 4 |

### Agent Dispatch Summary

| Wave | Count | Tasks |
|------|-------|-------|
| 1 | 2 | T1→`quick`, T2→`quick` |
| 2 | 6 | T4→`quick`, T5→`unspecified-high`, T6→`deep`, T7→`unspecified-high`, T8→`unspecified-high`, T9→`unspecified-high` |
| 3 | 6 | T10→`quick`, T11→`deep`, T12→`unspecified-high`, T13→`unspecified-high`, T14→`quick`, T15→`quick` |
| 4 | 7 | T16→`quick`, T17→`quick`, T18→`quick`, T19→`unspecified-high`, T20→`quick`, T21→`unspecified-high`, T22→`unspecified-high` |
| FINAL | 4 | F1→`oracle`, F2→`unspecified-high`, F3→`unspecified-high`, F4→`deep` |

---

## TODOs

- [ ] 1. F0 — Create SystemTrayManager class with signals

  **What to do**:
  - Create `src/ui/tray.py` with `SystemTrayManager(QObject)` class
  - Create `QSystemTrayIcon` with programmatic icon: `QPixmap(32, 32)` filled with teal/dark color, draw "M" text
  - Guard tray creation with `QSystemTrayIcon.isSystemTrayAvailable()` check — log warning and skip if unavailable
  - Build `QMenu` with actions: Settings, Learning History, Review (disabled, text "Review (coming soon)"), separator, Show/Hide Overlay, Quit
  - Define signals: `settings_requested = Signal()`, `history_requested = Signal()`, `review_requested = Signal()`, `toggle_overlay = Signal()`, `quit_requested = Signal()`
  - Connect menu actions to emit corresponding signals
  - Add method `update_review_badge(count: int)` → updates Review action text to "Review (N due)" — stub for future F4, currently never called
  - Call `tray.show()` at end of `__init__`

  **Must NOT do**:
  - Do NOT load icon from file — generate programmatically
  - Do NOT implement any ReviewRepository polling or timer
  - Do NOT use FramelessWindowHint or WindowStaysOnTopHint

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Single new file, well-defined Qt widget, straightforward signal-based class
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - `frontend-ui-ux`: Not needed — this is a native Qt widget, not web UI

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Task 2)
  - **Blocks**: Tasks 4, 15, 18
  - **Blocked By**: None (can start immediately)

  **References**:

  **Pattern References**:
  - `src/ui/overlay.py:74-78` — Signal definition pattern: `highlight_hovered = Signal(object, object)`
  - `src/ui/tooltip.py:55-60` — QObject-based class with signals pattern
  - `src/main.py:62-107` — How signals are wired in main.py (follow same pattern for tray signals)

  **API/Type References**:
  - `PySide6.QtWidgets.QSystemTrayIcon` — tray icon class
  - `PySide6.QtWidgets.QMenu` — context menu
  - `PySide6.QtGui.QPixmap`, `QPainter` — for programmatic icon generation

  **WHY Each Reference Matters**:
  - overlay.py Signal pattern: Follow exact `Signal()` / `Signal(object)` convention
  - tooltip.py: Shows QObject subclass pattern with signals (tray is same pattern)
  - main.py wiring: Shows how to connect signals — your class will be wired the same way

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Tray icon creates successfully with menu
    Tool: Bash (pytest)
    Preconditions: QApplication instance exists (qapp fixture)
    Steps:
      1. Run: QT_QPA_PLATFORM=offscreen python -c "from PySide6.QtWidgets import QApplication; import sys; app = QApplication(sys.argv); from src.ui.tray import SystemTrayManager; t = SystemTrayManager(); print('actions:', len(t._menu.actions())); print('icon null:', t._icon.icon().isNull())"
      2. Assert output contains "actions: 6" (5 actions + 1 separator)
      3. Assert output contains "icon null: False"
    Expected Result: Tray creates with 6 menu items and non-null icon
    Failure Indicators: ImportError, action count != 6, icon is null
    Evidence: .sisyphus/evidence/task-1-tray-creation.txt

  Scenario: Menu actions emit correct signals
    Tool: Bash (pytest)
    Preconditions: Test file exists
    Steps:
      1. Create test that connects each signal to a list.append
      2. Trigger each menu action via action.trigger()
      3. Assert each signal was emitted exactly once
    Expected Result: All 5 signals (settings_requested, history_requested, review_requested, toggle_overlay, quit_requested) emit on action trigger
    Failure Indicators: Signal not emitted, wrong signal count
    Evidence: .sisyphus/evidence/task-1-signals.txt

  Scenario: Review action is disabled
    Tool: Bash (pytest)
    Preconditions: SystemTrayManager instance
    Steps:
      1. Find the Review action in menu
      2. Assert action.isEnabled() == False
      3. Assert "coming soon" in action.text().lower()
    Expected Result: Review menu item exists but is disabled
    Failure Indicators: Action enabled, text doesn't contain "coming soon"
    Evidence: .sisyphus/evidence/task-1-review-disabled.txt
  ```

  **Evidence to Capture:**
  - [ ] task-1-tray-creation.txt — tray instantiation output
  - [ ] task-1-signals.txt — signal emission test results
  - [ ] task-1-review-disabled.txt — disabled review action verification

  **Commit**: YES (groups with Task 2 — Wave 1 commit)
  - Message: `feat(ui): add SystemTrayManager with context menu and signals`
  - Files: `src/ui/tray.py`
  - Pre-commit: `ruff check src/ui/tray.py && mypy src/ui/tray.py`

- [ ] 2. F1.1 — Extend AppConfig with new settings fields

  **What to do**:
  - Add 8 new fields to `AppConfig` dataclass in `src/config.py`:
    - `overlay_opacity: float = 0.78` (0.0–1.0)
    - `overlay_width: int = 800`
    - `overlay_height: int = 120`
    - `overlay_font_size_jp: int = 16`
    - `overlay_font_size_cn: int = 14`
    - `enable_vocab_highlight: bool = True`
    - `enable_grammar_highlight: bool = True`
    - `audio_device_id: int | None = None`
  - Fix backward compatibility in `load_config()`: After `defaults.update(loaded)`, filter to known AppConfig fields only:
    ```python
    known = {f.name for f in dataclasses.fields(AppConfig)}
    filtered = {k: v for k, v in defaults.items() if k in known}
    return AppConfig(**filtered)
    ```
  - Verify `save_config()` correctly serializes all new fields (no changes needed — `dataclasses.asdict` handles it)
  - Ensure all new fields have defaults so old config.json files load without errors

  **Must NOT do**:
  - Do NOT add config migration or versioning system
  - Do NOT add validation logic in config.py (validation is in SettingsDialog widgets)
  - Do NOT change existing field names or defaults

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Single file edit, adding dataclass fields with defaults, small backward-compat fix
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Task 1)
  - **Blocks**: Tasks 5, 6, 7, 8, 9, 10, 11
  - **Blocked By**: None (can start immediately)

  **References**:

  **Pattern References**:
  - `src/config.py:16-30` — Existing AppConfig dataclass fields (add new fields after existing ones)
  - `src/config.py:48-61` — `load_config()` function (add unknown-key filter after line 59)
  - `src/config.py:64-74` — `save_config()` function (verify no changes needed)

  **Test References**:
  - `tests/test_config.py` — Existing config tests (extend with backward-compat test for unknown keys)

  **WHY Each Reference Matters**:
  - config.py:16-30: Exact insertion point for new fields, follow typing convention (int | None pattern)
  - config.py:48-61: The backward-compat merge logic that needs the unknown-key filter
  - test_config.py: Will be extended in Task 19 to test new fields

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: New config fields have correct defaults
    Tool: Bash (python)
    Preconditions: src/config.py modified
    Steps:
      1. Run: python -c "from src.config import AppConfig; c = AppConfig(); print(c.overlay_opacity, c.overlay_width, c.overlay_height, c.overlay_font_size_jp, c.overlay_font_size_cn, c.enable_vocab_highlight, c.enable_grammar_highlight, c.audio_device_id)"
      2. Assert output: "0.78 800 120 16 14 True True None"
    Expected Result: All 8 new fields return expected defaults
    Failure Indicators: ImportError, wrong default values, missing fields
    Evidence: .sisyphus/evidence/task-2-defaults.txt

  Scenario: Backward compat — old config missing new fields loads OK
    Tool: Bash (python)
    Preconditions: None
    Steps:
      1. Write a temporary config JSON with only old fields: {"user_jlpt_level": 3, "llm_mode": "translation"}
      2. Call load_config(path) with the temp file
      3. Assert returned AppConfig has all new fields with defaults
      4. Assert user_jlpt_level == 3 (old value preserved)
    Expected Result: Old config loads without error, new fields get defaults
    Failure Indicators: TypeError, KeyError, missing fields
    Evidence: .sisyphus/evidence/task-2-backward-compat.txt

  Scenario: Config with unknown keys doesn't crash
    Tool: Bash (python)
    Preconditions: None
    Steps:
      1. Write temp config JSON with unknown key: {"user_jlpt_level": 3, "removed_field": "value"}
      2. Call load_config(path) with the temp file
      3. Assert returned AppConfig loads without error
    Expected Result: Unknown keys filtered out, no TypeError
    Failure Indicators: TypeError: unexpected keyword argument
    Evidence: .sisyphus/evidence/task-2-unknown-keys.txt

  Scenario: Round-trip save/load preserves new fields
    Tool: Bash (python)
    Preconditions: None
    Steps:
      1. Create AppConfig with non-default values: overlay_opacity=0.5, overlay_width=600
      2. save_config(config, tmp_path)
      3. loaded = load_config(tmp_path)
      4. Assert loaded.overlay_opacity == 0.5, loaded.overlay_width == 600
    Expected Result: All new fields survive save→load round-trip
    Failure Indicators: Values revert to defaults
    Evidence: .sisyphus/evidence/task-2-roundtrip.txt
  ```

  **Evidence to Capture:**
  - [ ] task-2-defaults.txt
  - [ ] task-2-backward-compat.txt
  - [ ] task-2-unknown-keys.txt
  - [ ] task-2-roundtrip.txt

  **Commit**: YES (groups with Task 1 — Wave 1 commit)
  - Message: `feat(config): extend AppConfig with overlay, font, and highlight settings`
  - Files: `src/config.py`
  - Pre-commit: `ruff check src/config.py && mypy src/config.py`

- [ ] 4. F0.2+F0.3 — Wire tray into main.py + badge stub

  **What to do**:
  - In `src/main.py`, import and instantiate `SystemTrayManager` after `QApplication` creation
  - Call `QApplication.setQuitOnLastWindowClosed(False)` BEFORE any window is shown (this keeps the app alive when overlay is hidden)
  - Connect `tray.quit_requested` → `QApplication.quit()`
  - Connect `tray.toggle_overlay` → toggle `overlay.setVisible(not overlay.isVisible())`
  - Connect `tray.settings_requested` — leave as placeholder slot `_open_settings()` that does nothing yet (wired in Task 16)
  - Connect `tray.history_requested` — leave as placeholder slot `_open_learning_panel()` that does nothing yet (wired in Task 17)
  - For F0.3 (badge timer): Do NOT implement ReviewRepository polling. Instead add a comment: `# TODO(F4): QTimer(60s) → review_repo.get_queue_count() → tray.update_review_badge(count)`
  - Store tray reference in `main()` local scope so it isn't garbage-collected

  **Must NOT do**:
  - Do NOT import or reference ReviewRepository, review_items, or any F4 code
  - Do NOT create a QTimer for badge polling
  - Do NOT create abstract helper functions for signal wiring

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Single file modification, straightforward signal wiring, well-defined changes
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - `frontend-ui-ux`: Not needed — this is Python signal wiring, not visual work

  **Parallelization**:
  - **Can Run In Parallel**: NO (first in Wave 2 but depends on Task 1 only)
  - **Parallel Group**: Wave 2 (with Tasks 5, 6, 7, 8, 9)
  - **Blocks**: Tasks 15, 17, 18
  - **Blocked By**: Task 1 (SystemTrayManager class must exist)

  **References**:

  **Pattern References**:
  - `src/main.py:62-107` — Current `main()` function: QApp creation, OverlayWindow instantiation, PipelineWorker creation, signal wiring pattern. Insert tray code AFTER QApp creation (line ~66) and BEFORE `overlay.show()` (line ~94)
  - `src/main.py:90-103` — Signal connection pattern: `worker.sentence_ready.connect(overlay.on_sentence_ready)` — follow same pattern for tray signals

  **API/Type References**:
  - `src/ui/tray.py:SystemTrayManager` — Class created in Task 1: signals `settings_requested`, `history_requested`, `toggle_overlay`, `quit_requested`
  - `QApplication.setQuitOnLastWindowClosed(False)` — Must be called before any window `.show()`

  **WHY Each Reference Matters**:
  - main.py:62-107: Exact insertion point for tray code. Must follow the existing init→wire→show sequence
  - main.py:90-103: Signal wiring convention to follow exactly

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Tray instantiated in main.py without errors
    Tool: Bash (python)
    Preconditions: Tasks 1 and 2 complete, src/ui/tray.py exists
    Steps:
      1. Run: QT_QPA_PLATFORM=offscreen python -c "import ast; tree = ast.parse(open('src/main.py').read()); names = [n.id for n in ast.walk(tree) if isinstance(n, ast.Name)]; print('SystemTrayManager' in names, 'setQuitOnLastWindowClosed' in [a.attr for a in ast.walk(tree) if isinstance(a, ast.Attribute)])"
      2. Assert both values are True
    Expected Result: main.py imports and uses SystemTrayManager and calls setQuitOnLastWindowClosed
    Failure Indicators: False for either check
    Evidence: .sisyphus/evidence/task-4-tray-wiring-ast.txt

  Scenario: Quit signal connected
    Tool: Bash (grep)
    Preconditions: src/main.py modified
    Steps:
      1. Run: grep -n "quit_requested" src/main.py
      2. Assert output contains a line with ".connect(" 
    Expected Result: quit_requested signal is connected to QApplication.quit or equivalent
    Failure Indicators: No match found
    Evidence: .sisyphus/evidence/task-4-quit-signal.txt

  Scenario: F4 badge is TODO only — no timer created
    Tool: Bash (grep)
    Preconditions: src/main.py modified
    Steps:
      1. Run: grep -n "QTimer" src/main.py
      2. Assert no results (exit code 1)
      3. Run: grep -n "TODO.*F4" src/main.py
      4. Assert at least one result
    Expected Result: No QTimer instantiation, but TODO comment for F4 exists
    Failure Indicators: QTimer found, or no TODO comment
    Evidence: .sisyphus/evidence/task-4-no-timer.txt
  ```

  **Evidence to Capture:**
  - [ ] task-4-tray-wiring-ast.txt — AST check for tray integration
  - [ ] task-4-quit-signal.txt — quit signal connection verification
  - [ ] task-4-no-timer.txt — no premature F4 timer

  **Commit**: YES (groups with Wave 2)
  - Message: `feat(main): wire SystemTrayManager into main.py with signal connections`
  - Files: `src/main.py`
  - Pre-commit: `ruff check src/main.py && mypy src/main.py`

- [ ] 5. F1.2 — Create SettingsDialog with 4 tabs

  **What to do**:
  - Create `src/ui/settings.py` with `SettingsDialog(QDialog)` class
  - Constructor signature: `__init__(self, config: AppConfig, parent: QWidget | None = None)`
  - Use `QTabWidget` with 4 tabs:
    - **General tab**: `QSpinBox` for JLPT level (range 1–5), `QComboBox` for `llm_mode` (items: "translation", "explanation")
    - **Appearance tab**: `QSlider` for opacity (range 10–100, value = opacity * 100, step 1), `QSpinBox` for JP font size (8–48), `QSpinBox` for CN font size (8–48), `QCheckBox` for vocab highlight, `QCheckBox` for grammar highlight
    - **Model tab**: `QLineEdit` for `ollama_url`, `QLineEdit` for `ollama_model`, `QDoubleSpinBox` for `ollama_timeout_sec` (range 5.0–120.0, step 5.0), `QPushButton` "Test Connection" that constructs a temporary `AppConfig` with current widget values and calls `OllamaClient(temp_config).health_check()` (synchronously since it's fast) and updates a `QLabel` with "✓ Connected" or "✗ Failed: {error}"
    - **Templates tab**: `QPlainTextEdit` for translation template, `QPlainTextEdit` for explanation template, with `QLabel` documentation: "Use {japanese_text} as placeholder"
  - Populate all widgets from `config` parameter in `__init__`
  - **Save button** (`QPushButton`): Read all widget values → construct new `AppConfig` → call `save_config(new_config)` (uses default path `"data/config.json"`) → emit `config_changed` signal → close dialog
  - **Cancel button** (`QPushButton`): Close dialog without saving
  - Signal: `config_changed = Signal(object)` — emits the new AppConfig after save
  - Use `QDialogButtonBox` or manual QPushButtons at bottom
  - Layout: Use `QFormLayout` inside each tab for label+widget pairs

  **Must NOT do**:
  - Do NOT add config validation logic beyond Qt widget constraints (min/max/step)
  - Do NOT add template syntax highlighting or preview
  - Do NOT create a FormBuilder, WidgetFactory, or similar abstraction
  - Do NOT add "Apply" button — only Save and Cancel
  - Do NOT make the dialog modal (use `.show()` not `.exec()`)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Substantial new file (~200-300 lines), multiple Qt widgets, tab layout, signal integration — more than a quick task but no deep algorithmic complexity
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - `frontend-ui-ux`: Not needed — native Qt widgets, not web UI
    - `playwright`: Not needed — Qt dialog, not browser-based

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 4, 6, 7, 8, 9)
  - **Blocks**: Tasks 10, 11, 16, 19
  - **Blocked By**: Task 2 (AppConfig new fields must exist)

  **References**:

  **Pattern References**:
  - `src/ui/overlay.py:28-73` — OverlayWindow.__init__ pattern: QWidget subclass, layout construction, signal definition. Follow same style for SettingsDialog
  - `src/ui/tooltip.py:53-110` — Another UI class pattern with signal definitions and widget construction
  - `src/config.py:16-30` — AppConfig field names and types — MUST match exactly when reading/writing config values

  **API/Type References**:
  - `src/config.py:AppConfig` — All fields (9 existing + 8 new from Task 2). Widget values must map 1:1 to these fields
  - `src/config.py:save_config(config, path="data/config.json")` — Call on Save button press (path has default, no need for get_config_path)
  - `src/llm/ollama_client.py:OllamaClient(config: AppConfig)` — Constructor takes full AppConfig object. `health_check() → bool`. Do NOT pass individual url/model/timeout args

  **External References**:
  - PySide6 QTabWidget: https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QTabWidget.html
  - PySide6 QFormLayout: https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QFormLayout.html

  **WHY Each Reference Matters**:
  - overlay.py/tooltip.py: UI class structure, signal patterns to follow
  - config.py AppConfig: MUST read every field name correctly to populate widgets and construct new config
  - ollama_client.py health_check: Used by "Test Connection" — need constructor args and return type

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: SettingsDialog creates with 4 tabs
    Tool: Bash (python)
    Preconditions: Tasks 1 and 2 complete
    Steps:
      1. Run: QT_QPA_PLATFORM=offscreen python -c "from PySide6.QtWidgets import QApplication; import sys; app = QApplication.instance() or QApplication(sys.argv); from src.config import AppConfig; from src.ui.settings import SettingsDialog; d = SettingsDialog(AppConfig()); print('tabs:', d._tabs.count()); print('tab_names:', [d._tabs.tabText(i) for i in range(d._tabs.count())])"
      2. Assert "tabs: 4" in output
      3. Assert tab names include "General", "Appearance", "Model", "Templates"
    Expected Result: Dialog has exactly 4 tabs with correct names
    Failure Indicators: Tab count != 4, missing tab names
    Evidence: .sisyphus/evidence/task-5-tabs.txt

  Scenario: Widget values populate from config
    Tool: Bash (python)
    Preconditions: SettingsDialog created
    Steps:
      1. Create AppConfig with non-default: user_jlpt_level=3, overlay_opacity=0.5
      2. Create SettingsDialog(config)
      3. Assert JLPT spinbox value == 3
      4. Assert opacity slider value == 50 (0.5 * 100)
    Expected Result: Widgets reflect config values
    Failure Indicators: Widgets show defaults instead of provided values
    Evidence: .sisyphus/evidence/task-5-populate.txt

  Scenario: config_changed signal emitted on save
    Tool: Bash (python)
    Preconditions: SettingsDialog created with test config
    Steps:
      1. Create SettingsDialog(AppConfig(user_jlpt_level=3))
      2. Connect config_changed to a capture list
      3. Simulate save button click
      4. Assert signal emitted with AppConfig where user_jlpt_level == 3
    Expected Result: Signal fires with valid AppConfig on save
    Failure Indicators: Signal not emitted, config values wrong
    Evidence: .sisyphus/evidence/task-5-signal.txt

  Scenario: Cancel closes without emitting signal
    Tool: Bash (python)
    Preconditions: SettingsDialog created
    Steps:
      1. Connect config_changed to a capture list
      2. Call dialog.reject() (cancel)
      3. Assert capture list is empty
    Expected Result: No config_changed signal on cancel
    Failure Indicators: Signal emitted on cancel
    Evidence: .sisyphus/evidence/task-5-cancel.txt
  ```

  **Evidence to Capture:**
  - [ ] task-5-tabs.txt — tab count and names
  - [ ] task-5-populate.txt — widget population from config
  - [ ] task-5-signal.txt — config_changed emission
  - [ ] task-5-cancel.txt — cancel behavior

  **Commit**: YES (groups with Wave 2)
  - Message: `feat(ui): create SettingsDialog with 4 tabs and config_changed signal`
  - Files: `src/ui/settings.py`
  - Pre-commit: `ruff check src/ui/settings.py && mypy src/ui/settings.py`

- [ ] 6. F1.5.1 — Add resize support to OverlayWindow

  **What to do**:
  - In `src/ui/overlay.py`, remove the fixed `self.resize(800, 120)` call
  - Add `self.setMinimumSize(400, 80)` and `self.setMaximumSize(screen_width, 400)` (get screen_width from `QApplication.primaryScreen().availableGeometry().width()`)
  - Read initial size from config: `self.resize(config.overlay_width, config.overlay_height)` where config is obtained from AppConfig (add `config: AppConfig` parameter to `__init__` or read from a passed-in config)
  - Note: OverlayWindow currently takes `user_level: int` in `__init__`. Change signature to `__init__(self, config: AppConfig)` and extract `user_level = config.user_jlpt_level` internally. Update the single call site in `main.py` accordingly
  - Add `QSizeGrip(self)` positioned at bottom-right corner. If QSizeGrip doesn't work with `FramelessWindowHint | WindowStaysOnTopHint | Tool`, implement manual edge-resize with 8px detection zone on right and bottom edges (check `mousePressEvent` hit position)
  - In `mousePressEvent`: Check if click is in QSizeGrip geometry BEFORE setting `_drag_pos` — if click is on grip, let QSizeGrip handle it (don't start drag)
  - Override `resizeEvent(self, event)`: On resize, start/restart a debounce timer: `QTimer.singleShot(500, self._save_size)`. `_save_size()` saves `self.width()` and `self.height()` to config via `save_config()`
  - Add `_center_on_screen()` helper method: Position overlay at bottom-center of primary screen. Extract existing inline positioning code from `__init__` into this method

  **Must NOT do**:
  - Do NOT add drag-to-resize handles on all 4 edges (right and bottom only)
  - Do NOT add visual resize indicators or cursor changes beyond what QSizeGrip provides
  - Do NOT debounce with QTimer(parent=self).start() — use QTimer.singleShot() pattern
  - Do NOT change the overlay's transparent frameless window flags

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Modifying existing complex widget with tricky window flag interactions (QSizeGrip + FramelessWindowHint), mouse event coordination, config integration
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - `frontend-ui-ux`: Not needed — native Qt resize, not CSS/web
    - `playwright`: Not needed — Qt widget, not browser

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 4, 5, 7, 8, 9)
  - **Blocks**: Tasks 10, 20
  - **Blocked By**: Task 2 (AppConfig overlay_width, overlay_height fields must exist)

  **References**:

  **Pattern References**:
  - `src/ui/overlay.py:28-73` — Current `__init__`: Fixed `resize(800, 120)` at line ~38, drag setup with `_drag_pos` at line ~70, window flags at line ~32. All need modification
  - `src/ui/overlay.py:150-175` — `mousePressEvent`/`mouseMoveEvent` for drag — must add QSizeGrip geometry check BEFORE `_drag_pos` assignment
  - `src/ui/overlay.py:34-40` — Window positioning code (inline in __init__) — extract to `_center_on_screen()`

  **API/Type References**:
  - `src/config.py:AppConfig` — New fields from Task 2: `overlay_width: int = 800`, `overlay_height: int = 120`
  - `src/config.py:save_config(config, path="data/config.json")` — For persisting resize (uses default path)
  - `QSizeGrip` — May not render with Tool flag; prepare fallback
  - `QApplication.primaryScreen().availableGeometry()` — For screen dimensions

  **WHY Each Reference Matters**:
  - overlay.py:28-73: Exact code being modified — must understand current init flow
  - overlay.py:150-175: Mouse event handlers that MUST NOT conflict with resize grip
  - AppConfig fields: Exact field names for config read/write

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: OverlayWindow accepts AppConfig in constructor
    Tool: Bash (python)
    Preconditions: Task 2 complete (AppConfig has new fields)
    Steps:
      1. Run: QT_QPA_PLATFORM=offscreen python -c "from PySide6.QtWidgets import QApplication; import sys; app = QApplication.instance() or QApplication(sys.argv); from src.config import AppConfig; from src.ui.overlay import OverlayWindow; o = OverlayWindow(AppConfig()); print('size:', o.width(), o.height()); print('min:', o.minimumWidth(), o.minimumHeight())"
      2. Assert size is 800 120 (defaults)
      3. Assert min is 400 80
    Expected Result: OverlayWindow uses config defaults and has minimum size constraints
    Failure Indicators: TypeError on constructor, wrong dimensions
    Evidence: .sisyphus/evidence/task-6-resize-init.txt

  Scenario: Custom size from config
    Tool: Bash (python)
    Preconditions: AppConfig with overlay_width/height available
    Steps:
      1. Create AppConfig(overlay_width=600, overlay_height=100)
      2. Create OverlayWindow(config)
      3. Assert o.width() == 600 and o.height() == 100
    Expected Result: Initial size matches config values
    Failure Indicators: Size still 800x120
    Evidence: .sisyphus/evidence/task-6-custom-size.txt

  Scenario: No fixed resize(800,120) remaining
    Tool: Bash (grep)
    Preconditions: overlay.py modified
    Steps:
      1. Run: grep -n "resize(800" src/ui/overlay.py
      2. Assert no results (exit code 1)
    Expected Result: Hardcoded 800x120 removed
    Failure Indicators: Match found
    Evidence: .sisyphus/evidence/task-6-no-hardcoded.txt

  Scenario: _center_on_screen method exists
    Tool: Bash (grep)
    Preconditions: overlay.py modified
    Steps:
      1. Run: grep -n "_center_on_screen" src/ui/overlay.py
      2. Assert at least one definition (def _center_on_screen)
    Expected Result: Helper method extracted
    Failure Indicators: Method not found
    Evidence: .sisyphus/evidence/task-6-center-method.txt
  ```

  **Evidence to Capture:**
  - [ ] task-6-resize-init.txt
  - [ ] task-6-custom-size.txt
  - [ ] task-6-no-hardcoded.txt
  - [ ] task-6-center-method.txt

  **Commit**: YES (groups with Wave 2)
  - Message: `feat(overlay): add resizable overlay with config-driven sizing and QSizeGrip`
  - Files: `src/ui/overlay.py`, `src/main.py` (constructor call change)
  - Pre-commit: `ruff check src/ui/overlay.py && mypy src/ui/overlay.py`

- [ ] 7. F1.5.2 — Adaptive text layout (centered HTML)

  **What to do**:
  - In `src/ui/highlight.py`, modify `HighlightRenderer.build_rich_text()` method's return value:
    - Wrap the existing highlighted spans in a centered layout: `<div align="center"><table cellpadding="0" cellspacing="0" width="100%"><tr><td align="center"><div style="text-align: left; display: inline;">` ... existing spans ... `</div></td></tr></table></div>`
    - Note: `display: inline-block` is NOT supported by QTextBrowser CSS engine. Use the table-based centering fallback described above
    - If `display: inline` also doesn't constrain width, try: `<table align="center"><tr><td>` ... spans ... `</td></tr></table>` (simpler approach)
  - In `src/ui/overlay.py`, modify `on_sentence_ready()`:
    - The translation line should also be wrapped in the same centering pattern
    - Ensure the full HTML body has no extra margins/padding causing misalignment
  - Text should: be visually centered in the overlay, but left-aligned within its own block (i.e., multi-line text wraps left-aligned, but the block itself is centered)
  - Add a max-width constraint of ~95% of overlay width to prevent text touching edges

  **Must NOT do**:
  - Do NOT use `display: inline-block` in CSS — QTextBrowser doesn't support it
  - Do NOT use JavaScript or complex HTML5 features
  - Do NOT change the font-size logic or color scheme in highlight.py
  - Do NOT modify get_highlight_at_position() logic

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Small HTML template change in 2 files, well-defined CSS constraint (table-based centering)
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - `frontend-ui-ux`: Not needed — QTextBrowser HTML, not web CSS

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 4, 5, 6, 8, 9)
  - **Blocks**: Task 20
  - **Blocked By**: None (modifies existing files, no new dependencies)

  **References**:

  **Pattern References**:
  - `src/ui/highlight.py:52-110` — `HighlightRenderer.build_rich_text()` instance method: Constructs HTML spans with JLPT color highlighting. The return value is a string of `<span>` elements. Wrap this return value with centering table structure
  - `src/ui/overlay.py:120-145` — `on_sentence_ready()`: Sets HTML on QTextBrowser via `.setHtml()`. Translation line is appended as separate HTML. Both need centering wrapper

  **API/Type References**:
  - QTextBrowser CSS subset: Supports `text-align`, `margin`, `padding`, `color`, `background-color`, `font-size`, `font-weight`. Does NOT support `display: inline-block`, `flexbox`, `grid`
  - HTML table centering: `<table align="center">` is the most reliable centering method in Qt rich text

  **WHY Each Reference Matters**:
   - highlight.py:52-110: Exact instance method whose return value must be wrapped — must not break existing span construction
  - overlay.py:120-145: Where HTML is assembled and set — the centering must work at this level

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: build_rich_text output contains centering structure
    Tool: Bash (python)
    Preconditions: highlight.py modified
    Steps:
      1. Run: python -c "from src.ui.highlight import HighlightRenderer; from src.db.models import AnalysisResult, Token; renderer = HighlightRenderer(); ar = AnalysisResult(tokens=[Token(surface='テスト', lemma='テスト', pos='名詞')], vocab_hits=[], grammar_hits=[]); html = renderer.build_rich_text(ar, 5); print('table' in html.lower(), 'align' in html.lower(), 'center' in html.lower())"
      2. Assert all three are True
    Expected Result: HTML contains table-based centering structure
    Failure Indicators: Any False — centering wrapper missing
    Evidence: .sisyphus/evidence/task-7-centered-html.txt

  Scenario: No display:inline-block in HTML output
    Tool: Bash (python)
    Preconditions: highlight.py modified
    Steps:
      1. Run: python -c "from src.ui.highlight import HighlightRenderer; from src.db.models import AnalysisResult, Token; renderer = HighlightRenderer(); ar = AnalysisResult(tokens=[Token(surface='テスト', lemma='テスト', pos='名詞')], vocab_hits=[], grammar_hits=[]); html = renderer.build_rich_text(ar, 5); print('inline-block' not in html)"
      2. Assert True
    Expected Result: No unsupported CSS in output
    Failure Indicators: inline-block found in HTML
    Evidence: .sisyphus/evidence/task-7-no-inline-block.txt

  Scenario: get_highlight_at_position still works after wrapping
    Tool: Bash (python)
    Preconditions: highlight.py modified
    Steps:
      1. Run a basic get_highlight_at_position test with known token positions
      2. Assert positions still map correctly to highlights
    Expected Result: Position mapping unaffected by centering wrapper
    Failure Indicators: Positions shifted or no matches
    Evidence: .sisyphus/evidence/task-7-position-intact.txt
  ```

  **Evidence to Capture:**
  - [ ] task-7-centered-html.txt
  - [ ] task-7-no-inline-block.txt
  - [ ] task-7-position-intact.txt

  **Commit**: YES (groups with Wave 2)
  - Message: `feat(ui): add table-based centering for highlighted text in overlay`
  - Files: `src/ui/highlight.py`, `src/ui/overlay.py`
  - Pre-commit: `ruff check src/ui/highlight.py src/ui/overlay.py && mypy src/ui/highlight.py src/ui/overlay.py`

- [ ] 8. F2.1 — Extend LearningRepository with filtered queries

  **What to do**:
  - In `src/db/repository.py`, add three new methods:
    1. `get_sentences_filtered(self, limit: int = 50, offset: int = 0, sort_by: str = "created_at", sort_order: str = "DESC", query: str | None = None, date_from: str | None = None, date_to: str | None = None) -> list[SentenceRecord]`
       - Build SQL dynamically with parameterized WHERE clauses
       - `query` filters on `japanese_text LIKE ?` or `chinese_translation LIKE ?` (OR)
       - `date_from`/`date_to` filter on `created_at >= ?` / `created_at <= ?`
       - `sort_by` MUST be whitelisted: `{"created_at", "japanese_text"}` — reject others with ValueError
       - `sort_order` MUST be whitelisted: `{"ASC", "DESC"}` — reject others with ValueError
       - Apply `LIMIT ? OFFSET ?` for pagination
    2. `get_sentence_count(self, query: str | None = None, date_from: str | None = None, date_to: str | None = None) -> int`
       - Same WHERE logic as above but `SELECT COUNT(*)`
       - Used by LearningPanel for page count calculation
    3. `get_sentence_with_highlights(self, sentence_id: int) -> tuple[SentenceRecord, list[HighlightVocab], list[HighlightGrammar]] | None`
       - Fetch sentence + JOIN highlight_vocab and highlight_grammar
       - Return None if sentence_id not found
       - Used by SentenceDetailDialog
  - All SQL must use parameterized queries (?) — NO f-strings or .format() in SQL

  **Must NOT do**:
  - Do NOT use ORM or query builder library
  - Do NOT modify existing `get_sentences()` or `search_sentences()` methods
  - Do NOT add full-text search (FTS) — LIKE is sufficient
  - Do NOT add SQL injection via string formatting

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: New SQL methods with dynamic WHERE construction, parameter validation, JOIN queries — needs careful SQL construction
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - `playwright`: Not needed — pure Python/SQL, no UI

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 4, 5, 6, 7, 9)
  - **Blocks**: Tasks 12, 13, 14, 21
  - **Blocked By**: None (extends existing repository.py, no new type dependencies)

  **References**:

  **Pattern References**:
  - `src/db/repository.py:86-120` — `get_sentences(self, limit, offset)`: Existing pagination pattern with LIMIT/OFFSET. Follow same row→SentenceRecord mapping
  - `src/db/repository.py:122-160` — `search_sentences(self, query)`: Existing LIKE search pattern. Follow same parameterized WHERE style
  - `src/db/repository.py:200-240` — `export_records()`: Shows JOIN pattern for getting highlights per sentence

  **API/Type References**:
  - `src/db/models.py:SentenceRecord` — Returned by all get methods
  - `src/db/models.py:HighlightVocab` — Fields: `id, sentence_id, surface, lemma, pos, jlpt_level, is_beyond_level, tooltip_shown`
  - `src/db/models.py:HighlightGrammar` — Fields: `id, sentence_id, pattern, jlpt_level, description`
  - `src/db/schema.py:3-45` — Table definitions: sentences, highlight_vocab, highlight_grammar column names

  **WHY Each Reference Matters**:
  - repository.py:86-120: Row→dataclass mapping pattern to reuse
  - repository.py:200-240: JOIN pattern for highlights — critical for get_sentence_with_highlights
  - models.py types: Exact field names for constructing return values
  - schema.py: Column names for SQL construction

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: get_sentences_filtered returns paginated results
    Tool: Bash (python)
    Preconditions: Test DB with ≥5 sentences inserted
    Steps:
      1. Create LearningRepository with :memory: DB, init_db, insert 5 sentences
      2. Call get_sentences_filtered(limit=2, offset=0)
      3. Assert len(result) == 2
      4. Call get_sentences_filtered(limit=2, offset=4)
      5. Assert len(result) == 1 (only 1 left)
    Expected Result: Pagination works with limit/offset
    Failure Indicators: Wrong count, SQL error
    Evidence: .sisyphus/evidence/task-8-pagination.txt

  Scenario: get_sentences_filtered with query filter
    Tool: Bash (python)
    Preconditions: Test DB with sentences containing "テスト" and "勉強"
    Steps:
      1. Insert sentences with different japanese_text values
      2. Call get_sentences_filtered(query="テスト")
      3. Assert only sentences containing "テスト" returned
    Expected Result: LIKE filter works on japanese_text
    Failure Indicators: All sentences returned, or SQL error
    Evidence: .sisyphus/evidence/task-8-query-filter.txt

  Scenario: get_sentence_count matches filtered results
    Tool: Bash (python)
    Preconditions: Test DB with mixed sentences
    Steps:
      1. count = get_sentence_count(query="テスト")
      2. results = get_sentences_filtered(query="テスト", limit=1000)
      3. Assert count == len(results)
    Expected Result: Count and filtered list agree
    Failure Indicators: count != len(results)
    Evidence: .sisyphus/evidence/task-8-count-match.txt

  Scenario: Invalid sort_by raises ValueError
    Tool: Bash (python)
    Preconditions: Repository initialized
    Steps:
      1. Call get_sentences_filtered(sort_by="DROP TABLE sentences")
      2. Assert ValueError raised
    Expected Result: SQL injection attempt rejected
    Failure Indicators: No error, or SQL executed
    Evidence: .sisyphus/evidence/task-8-sort-validation.txt

  Scenario: get_sentence_with_highlights returns joined data
    Tool: Bash (python)
    Preconditions: Test DB with sentence + vocab/grammar highlights
    Steps:
      1. Insert a sentence, then insert highlight_vocab and highlight_grammar rows for it
      2. Call get_sentence_with_highlights(sentence_id)
      3. Assert tuple[SentenceRecord, list[HighlightVocab], list[HighlightGrammar]]
      4. Assert vocab and grammar lists are non-empty
    Expected Result: JOIN query returns sentence with its highlights
    Failure Indicators: None returned, empty highlight lists
    Evidence: .sisyphus/evidence/task-8-joined-data.txt
  ```

  **Evidence to Capture:**
  - [ ] task-8-pagination.txt
  - [ ] task-8-query-filter.txt
  - [ ] task-8-count-match.txt
  - [ ] task-8-sort-validation.txt
  - [ ] task-8-joined-data.txt

  **Commit**: YES (groups with Wave 2)
  - Message: `feat(db): add filtered/paginated queries and sentence-with-highlights to repository`
  - Files: `src/db/repository.py`
  - Pre-commit: `ruff check src/db/repository.py && mypy src/db/repository.py`

- [ ] 9. F3.1 — Extend export_records with filters and highlight details

  **What to do**:
  - In `src/db/repository.py`, modify existing `export_records()` method signature:
    - New: `export_records(self, format: str = "json", date_from: str | None = None, date_to: str | None = None, include_highlights: bool = True) -> str`
    - Add optional date range filtering with parameterized WHERE on `created_at`
    - Keep existing format support (json, csv)
  - **JSON format changes** (when include_highlights=True):
    - Each sentence dict gets nested `"vocab_highlights": [{"surface": ..., "lemma": ..., "jlpt_level": ..., "pos": ...}]` and `"grammar_highlights": [{"pattern": ..., "jlpt_level": ..., "description": ...}]`
    - Fetch highlights via LEFT JOIN or separate query per sentence
  - **CSV format changes** (when include_highlights=True):
    - Add columns: `vocab_count`, `grammar_count`, `vocab_lemmas` (semicolon-separated list of lemmas), `grammar_rules` (semicolon-separated list of patterns)
    - These are summary columns — don't try to nest full highlight data in CSV
  - When `include_highlights=False`, return same format as current (no highlight columns/nesting)

  **Must NOT do**:
  - Do NOT break existing export_records callers (current signature has no parameters beyond self and format)
  - Do NOT add new export formats (markdown, XML, etc.)
  - Do NOT load all sentences into memory then filter in Python — filter in SQL

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Extending existing method with new parameters and SQL, well-defined changes to 1 function
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - `playwright`: Not needed — pure Python/SQL

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 4, 5, 6, 7, 8)
  - **Blocks**: Tasks 14, 15, 22
  - **Blocked By**: None (modifies existing function, all types already defined)

  **References**:

  **Pattern References**:
  - `src/db/repository.py:200-271` — Current `export_records(self, format)`: JSON and CSV generation with cursor.fetchall(). This is the EXACT function being modified — preserve existing behavior as default
  - `src/db/repository.py:86-120` — `get_sentences()` pagination pattern with LIMIT/OFFSET as reference for parameterized SQL

  **API/Type References**:
  - `src/db/models.py:HighlightVocab` — Fields: `surface, lemma, pos, jlpt_level, is_beyond_level`
  - `src/db/models.py:HighlightGrammar` — Fields: `pattern, jlpt_level, description`
  - `src/db/schema.py:20-45` — highlight_vocab and highlight_grammar table columns

  **WHY Each Reference Matters**:
  - repository.py:200-271: This IS the function being modified. Must understand current JSON/CSV generation to extend without breaking
  - models.py types: Field names for JSON nesting and CSV summary columns

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: export_records still works without new params (backward compat)
    Tool: Bash (python)
    Preconditions: Repository with test data
    Steps:
      1. Call export_records("json") — no new params
      2. Assert valid JSON string returned
      3. Call export_records("csv") — no new params
      4. Assert valid CSV string with header row
    Expected Result: Existing callers unaffected
    Failure Indicators: TypeError on missing params
    Evidence: .sisyphus/evidence/task-9-backward-compat.txt

  Scenario: JSON with highlights includes nested arrays
    Tool: Bash (python)
    Preconditions: DB with sentence + highlights
    Steps:
      1. Call export_records("json", include_highlights=True)
      2. Parse JSON, get first sentence
      3. Assert "vocab_highlights" key exists and is a list
      4. Assert "grammar_highlights" key exists and is a list
    Expected Result: Nested highlight data in JSON
    Failure Indicators: Keys missing, not lists
    Evidence: .sisyphus/evidence/task-9-json-highlights.txt

  Scenario: CSV with highlights includes summary columns
    Tool: Bash (python)
    Preconditions: DB with sentence + highlights
    Steps:
      1. Call export_records("csv", include_highlights=True)
      2. Parse CSV header
      3. Assert "vocab_count" and "grammar_count" in header
      4. Assert "vocab_lemmas" and "grammar_rules" in header
    Expected Result: Summary columns present in CSV
    Failure Indicators: Columns missing from header
    Evidence: .sisyphus/evidence/task-9-csv-highlights.txt

  Scenario: Date filtering works
    Tool: Bash (python)
    Preconditions: DB with sentences on different dates
    Steps:
      1. Insert sentences with created_at spanning multiple dates
      2. Call export_records("json", date_from="2026-01-01", date_to="2026-01-02")
      3. Parse JSON, assert all sentences within date range
    Expected Result: Only sentences in date range exported
    Failure Indicators: Sentences outside range included
    Evidence: .sisyphus/evidence/task-9-date-filter.txt
  ```

  **Evidence to Capture:**
  - [ ] task-9-backward-compat.txt
  - [ ] task-9-json-highlights.txt
  - [ ] task-9-csv-highlights.txt
  - [ ] task-9-date-filter.txt

  **Commit**: YES (groups with Wave 2)
  - Message: `feat(db): extend export_records with date filtering and highlight details`
  - Files: `src/db/repository.py`
  - Pre-commit: `ruff check src/db/repository.py && mypy src/db/repository.py`

- [ ] 10. F1.3 — Live-reload config on OverlayWindow

  **What to do**:
  - In `src/ui/overlay.py`, add a public slot method: `on_config_changed(self, config: AppConfig) -> None`
  - This method applies config changes to the overlay WITHOUT restarting the app:
    - `self.setWindowOpacity(config.overlay_opacity)`
    - Update internal `_user_level = config.user_jlpt_level`
    - Update JP font size: Store `config.overlay_font_size_jp` and `config.overlay_font_size_cn` as instance vars, used when `on_sentence_ready()` calls `self._renderer.build_rich_text()`
    - Update highlight toggles: Store `config.enable_vocab_highlight` and `config.enable_grammar_highlight` as instance vars
    - Re-render current sentence if one is displayed: call `self.on_sentence_ready(self._current_result)` where `_current_result` is already saved from the last `on_sentence_ready()` call (it already exists in the codebase)
  - Note: `_current_result: SentenceResult | None` instance variable already exists in OverlayWindow — no need to add it
  - Modify `on_sentence_ready()` to respect `enable_vocab_highlight` and `enable_grammar_highlight`:
     - If vocab highlight disabled, pass empty `vocab_hits` to `self._renderer.build_rich_text()`
     - If grammar highlight disabled, pass empty `grammar_hits` to `self._renderer.build_rich_text()`
   - Pass font size parameters to `self._renderer.build_rich_text()` (will need to add `overlay_font_size_jp` parameter to `HighlightRenderer.build_rich_text()` or apply via stylesheet on QTextBrowser)

  **Must NOT do**:
  - Do NOT recreate the window or re-init — update properties in-place
  - Do NOT add a debounce/timer for config changes — apply immediately
  - Do NOT modify the resize-related config handling (that's in Task 6)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
     - Reason: Modifying core display logic, threading font size through to HighlightRenderer.build_rich_text(), conditional highlight toggling — interconnected changes across display pipeline
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - `frontend-ui-ux`: Not needed — Qt property updates, not visual design

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Tasks 11, 12, 13, 14, 15)
  - **Blocks**: Tasks 16, 19, 20
  - **Blocked By**: Tasks 5 (SettingsDialog emits config_changed), 6 (overlay uses AppConfig constructor)

  **References**:

  **Pattern References**:
  - `src/ui/overlay.py:120-145` — `on_sentence_ready()`: Current rendering pipeline. `_current_result` already saved here. Add highlight toggle logic
  - `src/ui/highlight.py:52-110` — `HighlightRenderer.build_rich_text(analysis, user_level)`: Instance method on HighlightRenderer. Current signature. May need `overlay_font_size_jp` parameter, OR font size can be applied via QTextBrowser stylesheet

  **API/Type References**:
  - `src/config.py:AppConfig` — Fields: `overlay_opacity`, `user_jlpt_level`, `overlay_font_size_jp`, `overlay_font_size_cn`, `enable_vocab_highlight`, `enable_grammar_highlight` (new from Task 2)
  - `src/db/models.py:SentenceResult` — Type of `_current_result`. Fields: `japanese_text`, `chinese_translation`, `explanation`, `analysis`

  **WHY Each Reference Matters**:
  - overlay.py on_sentence_ready: Exact method being modified — must understand data flow for re-rendering
  - highlight.py HighlightRenderer.build_rich_text: Called by on_sentence_ready via renderer instance — font size integration point
  - AppConfig: Field names to read for each visual property

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: on_config_changed updates opacity
    Tool: Bash (python)
    Preconditions: OverlayWindow created with default config
    Steps:
      1. Create OverlayWindow(AppConfig())
      2. Assert initial opacity == 0.85 (default)
      3. Call on_config_changed(AppConfig(overlay_opacity=0.5))
      4. Assert windowOpacity() == 0.5
    Expected Result: Opacity updates in-place
    Failure Indicators: Opacity unchanged
    Evidence: .sisyphus/evidence/task-10-opacity.txt

  Scenario: Highlight toggle suppresses vocab colors
    Tool: Bash (python)
    Preconditions: OverlayWindow with displayed sentence
    Steps:
      1. Create overlay, display a sentence with vocab_hits
      2. Get HTML content from QTextBrowser
      3. Assert vocab color spans present
      4. Call on_config_changed(AppConfig(enable_vocab_highlight=False))
      5. Get HTML content again
      6. Assert vocab color spans absent (tokens shown plain)
    Expected Result: Toggling vocab_highlight removes color spans
    Failure Indicators: Colors still present after disable
    Evidence: .sisyphus/evidence/task-10-highlight-toggle.txt

  Scenario: _current_result already exists and is used for re-render
    Tool: Bash (python)
    Preconditions: OverlayWindow created
    Steps:
      1. Assert overlay._current_result is None initially
      2. Call on_sentence_ready(mock_sentence_result)
      3. Assert overlay._current_result is not None
    Expected Result: Current result saved for re-rendering on config change
    Failure Indicators: _current_result still None after display
    Evidence: .sisyphus/evidence/task-10-current-sentence.txt
  ```

  **Evidence to Capture:**
  - [ ] task-10-opacity.txt
  - [ ] task-10-highlight-toggle.txt
  - [ ] task-10-current-sentence.txt

  **Commit**: YES (groups with Wave 3)
  - Message: `feat(overlay): add live-reload config with opacity, font size, and highlight toggles`
  - Files: `src/ui/overlay.py`, possibly `src/ui/highlight.py` (font size param)
  - Pre-commit: `ruff check src/ui/overlay.py src/ui/highlight.py && mypy src/ui/overlay.py src/ui/highlight.py`

- [ ] 11. F1.4 — Thread-safe config update on PipelineWorker

  **What to do**:
  - In `src/pipeline.py`, add a `queue.Queue[AppConfig]` as instance variable: `self._config_queue: queue.Queue[AppConfig] = queue.Queue()`
  - Add public method: `update_config(self, config: AppConfig) -> None` — puts config into the queue (thread-safe, called from main thread)
  - In the main `run()` while-loop, at the TOP of each iteration (before audio capture), check the queue:
    ```python
    try:
        new_config = self._config_queue.get_nowait()
        self._apply_config(new_config)
    except queue.Empty:
        pass
    ```
  - `_apply_config(self, config: AppConfig)` method:
    - Update `self._user_level = config.user_jlpt_level`
    - Update LLM client: Construct new AppConfig with updated fields, then `self._llm_client = OllamaClient(new_config)` — OllamaClient takes a full AppConfig object, NOT individual parameters
    - Update templates: `self._translation_template = config.translation_template` and `self._explanation_template = config.explanation_template`
    - Fix the existing `is_beyond_level=True` hardcoded bug: Change to use `self._user_level` for comparison
  - Do NOT use `QMetaObject.invokeMethod()` — the pipeline worker's while-loop has no event loop, so Qt cross-thread invocation won't work. `queue.Queue` is the correct approach

  **Must NOT do**:
  - Do NOT use QMetaObject.invokeMethod — pipeline has no event loop
  - Do NOT use threading.Lock for config — queue.Queue is simpler and sufficient
  - Do NOT restart the pipeline thread on config change
  - Do NOT add processEvents() to the worker loop

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Thread safety is tricky. Must understand PipelineWorker's blocking loop, queue.Queue semantics, and when config takes effect. The is_beyond_level bug fix needs careful attention
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - `playwright`: Not needed — backend thread logic

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Tasks 10, 12, 13, 14, 15)
  - **Blocks**: Tasks 16, 19
  - **Blocked By**: Task 5 (SettingsDialog emits config_changed) — although pipeline.py can be modified independently, the wiring happens in Task 16

  **References**:

  **Pattern References**:
  - `src/pipeline.py:55-120` — `run()` method: Main while-loop structure. The queue check goes at TOP of loop, before `self._vad.detect()` call
  - `src/pipeline.py:35-53` — `__init__`: Where instance variables are initialized. Add `_config_queue` here
  - `src/pipeline.py:130-160` — Where `is_beyond_level=True` is hardcoded — THIS IS THE BUG to fix. Change to use `self._user_level`

  **API/Type References**:
  - `queue.Queue[AppConfig]` — stdlib, thread-safe. Methods: `.put(item)`, `.get_nowait()` raises `queue.Empty`
  - `src/config.py:AppConfig` — Fields used: `user_jlpt_level`, `ollama_url`, `ollama_model`, `ollama_timeout_sec`, `translation_template`, `explanation_template`
  - `src/llm/ollama_client.py:OllamaClient(config: AppConfig)` — Constructor takes full AppConfig. To update, pass the new config directly

  **WHY Each Reference Matters**:
  - pipeline.py:55-120 run(): Exact insertion point for queue check — must go before audio processing
  - pipeline.py:130-160: The is_beyond_level bug — must find exact line and fix
  - queue.Queue: Thread-safe approach because pipeline loop has NO Qt event loop

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: update_config is thread-safe (queue-based)
    Tool: Bash (python)
    Preconditions: pipeline.py modified
    Steps:
      1. Run: python -c "from src.pipeline import PipelineWorker; import inspect; src = inspect.getsource(PipelineWorker); print('queue.Queue' in src or 'Queue' in src, '_config_queue' in src, 'get_nowait' in src)"
      2. Assert all True
    Expected Result: Queue-based config update mechanism present
    Failure Indicators: Any False — queue not implemented
    Evidence: .sisyphus/evidence/task-11-queue-present.txt

  Scenario: No QMetaObject usage in pipeline
    Tool: Bash (grep)
    Preconditions: pipeline.py modified
    Steps:
      1. Run: grep -n "QMetaObject\|invokeMethod" src/pipeline.py
      2. Assert no results (exit code 1)
    Expected Result: No Qt cross-thread invocation (would deadlock)
    Failure Indicators: QMetaObject found
    Evidence: .sisyphus/evidence/task-11-no-qmeta.txt

  Scenario: is_beyond_level bug fixed
    Tool: Bash (grep)
    Preconditions: pipeline.py modified
    Steps:
      1. Run: grep -n "is_beyond_level=True" src/pipeline.py
      2. Assert no results (hardcoded True removed)
      3. Run: grep -n "is_beyond_level" src/pipeline.py
      4. Assert results exist (dynamic calculation present)
    Expected Result: is_beyond_level now computed dynamically from user_level
    Failure Indicators: Hardcoded True still present
    Evidence: .sisyphus/evidence/task-11-bug-fix.txt

  Scenario: update_config method exists with correct signature
    Tool: Bash (python)
    Preconditions: pipeline.py modified
    Steps:
      1. Run: python -c "from src.pipeline import PipelineWorker; import inspect; sig = inspect.signature(PipelineWorker.update_config); print(sig); print(list(sig.parameters.keys()))"
      2. Assert 'config' in parameters
    Expected Result: update_config(self, config) method exists
    Failure Indicators: AttributeError or wrong signature
    Evidence: .sisyphus/evidence/task-11-method-sig.txt
  ```

  **Evidence to Capture:**
  - [ ] task-11-queue-present.txt
  - [ ] task-11-no-qmeta.txt
  - [ ] task-11-bug-fix.txt
  - [ ] task-11-method-sig.txt

  **Commit**: YES (groups with Wave 3)
  - Message: `feat(pipeline): add thread-safe config update via queue and fix is_beyond_level bug`
  - Files: `src/pipeline.py`
  - Pre-commit: `ruff check src/pipeline.py && mypy src/pipeline.py`

- [ ] 12. F2.2 — Create LearningPanel with table and pagination

  **What to do**:
  - Create `src/ui/learning_panel.py` with `LearningPanel(QWidget)` class
  - Constructor: `__init__(self, repo: LearningRepository, parent: QWidget | None = None)`
  - **CRITICAL**: LearningPanel runs in the main (GUI) thread but LearningRepository may have been created in another thread. Create a NEW `sqlite3.Connection` for the panel using the SAME database path. SQLite WAL mode handles concurrent reads. Alternatively, accept the repo object and call its methods (since all Qt slots run on the GUI thread, and the repo is created once in main.py with a single connection — this is safe as long as pipeline doesn't write concurrently via the same connection object). Safest approach: Accept `db_path: str | Path` in constructor, create `LearningRepository(db_path)` internally
  - **Top bar** (QHBoxLayout):
    - `QLineEdit` for search (placeholder: "Search sentences...")
    - `QDateEdit` for date_from (with calendar popup, default: 30 days ago)
    - `QDateEdit` for date_to (with calendar popup, default: today)
    - `QPushButton` "Search" that triggers `_refresh_table()`
  - **Table** (QTableWidget):
    - Columns: "Created At", "Japanese Text", "Translation" (truncated to 40 chars + "..."), "Vocab Count"
    - Selection mode: single row
    - Double-click row → open SentenceDetailDialog (Task 13)
    - Populate via `repo.get_sentences_filtered()` with current filter/page state
  - **Pagination bar** (QHBoxLayout at bottom):
    - `QPushButton` "← Previous" (disabled on page 1)
    - `QLabel` "Page X of Y" (Y computed from `repo.get_sentence_count() / page_size`)
    - `QPushButton` "Next →" (disabled on last page)
    - `page_size = 50`, `_current_page = 1`
  - **Bottom bar**:
    - `QPushButton` "Export..." → opens export dialog (Task 14, leave as placeholder `_open_export_dialog()`)
    - `QPushButton` "Delete by Date..." → `QInputDialog` or date picker → confirmation `QMessageBox` → `repo.delete_before(date)` → refresh
  - Public method: `refresh(self)` — re-fetches data with current filters. Can be connected to `pipeline.sentence_ready` to auto-refresh when new sentences arrive

  **Must NOT do**:
  - Do NOT use QTableView with a custom model — QTableWidget is simpler and sufficient
  - Do NOT add inline editing of table cells (read-only)
  - Do NOT add sorting by clicking column headers (use filter bar sort_by instead) — unless trivially supported by QTableWidget built-in sorting
  - Do NOT create a custom pagination widget class — inline the prev/next/label

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Substantial new UI file (~250-350 lines) with table, pagination logic, search integration, date filtering, and dialog triggers. Complex but no deep algorithmic challenge
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - `frontend-ui-ux`: Qt widget layout, not web UI
    - `playwright`: Qt panel, not browser

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Tasks 10, 11, 13, 14, 15)
  - **Blocks**: Tasks 14, 17, 21
  - **Blocked By**: Task 8 (get_sentences_filtered and get_sentence_count must exist)

  **References**:

  **Pattern References**:
  - `src/ui/overlay.py:28-73` — QWidget subclass pattern, layout construction
  - `src/ui/tooltip.py:53-110` — Signal definitions, widget setup pattern

  **API/Type References**:
  - `src/db/repository.py:get_sentences_filtered()` — Method from Task 8: `(limit, offset, sort_by, sort_order, query, date_from, date_to) -> list[SentenceRecord]`
  - `src/db/repository.py:get_sentence_count()` — Method from Task 8: `(query, date_from, date_to) -> int`
  - `src/db/repository.py:delete_before()` — Existing method for delete by date
  - `src/db/models.py:SentenceRecord` — Fields: `id, japanese_text, chinese_translation, created_at, ...`

  **WHY Each Reference Matters**:
  - overlay.py/tooltip.py: Follow existing QWidget patterns for consistency
  - repository methods: API contract — exact parameter names and return types to call
  - SentenceRecord: Field names for table column mapping

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: LearningPanel creates with all UI elements
    Tool: Bash (python)
    Preconditions: Tasks 2, 8 complete
    Steps:
      1. QT_QPA_PLATFORM=offscreen python -c "from PySide6.QtWidgets import QApplication; import sys; app = QApplication.instance() or QApplication(sys.argv); from src.ui.learning_panel import LearningPanel; p = LearningPanel(':memory:'); print('table_cols:', p._table.columnCount()); print('has_search:', hasattr(p, '_search_input')); print('has_prev:', hasattr(p, '_prev_btn')); print('has_next:', hasattr(p, '_next_btn'))"
      2. Assert table_cols == 4
      3. Assert all has_* are True
    Expected Result: Panel has table with 4 columns, search, pagination buttons
    Failure Indicators: Wrong column count, missing UI elements
    Evidence: .sisyphus/evidence/task-12-panel-ui.txt

  Scenario: Pagination shows correct page info
    Tool: Bash (python)
    Preconditions: Panel with test DB containing 120 sentences (page_size=50 → 3 pages)
    Steps:
      1. Create panel with DB containing 120 sentences
      2. Assert page label shows "Page 1 of 3"
      3. Click next button
      4. Assert page label shows "Page 2 of 3"
      5. Assert table shows rows 51-100
    Expected Result: Pagination calculates correctly and navigates
    Failure Indicators: Wrong page count, same data on page 2
    Evidence: .sisyphus/evidence/task-12-pagination.txt

  Scenario: Search filters table results
    Tool: Bash (python)
    Preconditions: Panel with mixed test sentences
    Steps:
      1. Set search input to "テスト"
      2. Trigger search (click Search button or emit)
      3. Assert all table rows contain "テスト" in Japanese Text column
    Expected Result: Table filtered by search query
    Failure Indicators: Unfiltered results shown
    Evidence: .sisyphus/evidence/task-12-search.txt

  Scenario: refresh() method callable from external signal
    Tool: Bash (python)
    Preconditions: Panel created
    Steps:
      1. Assert hasattr(panel, 'refresh') and callable
      2. Call panel.refresh() — no error
    Expected Result: refresh is a public method for signal connection
    Failure Indicators: AttributeError or crash
    Evidence: .sisyphus/evidence/task-12-refresh.txt
  ```

  **Evidence to Capture:**
  - [ ] task-12-panel-ui.txt
  - [ ] task-12-pagination.txt
  - [ ] task-12-search.txt
  - [ ] task-12-refresh.txt

  **Commit**: YES (groups with Wave 3)
  - Message: `feat(ui): create LearningPanel with table, search, date filter, and pagination`
  - Files: `src/ui/learning_panel.py`
  - Pre-commit: `ruff check src/ui/learning_panel.py && mypy src/ui/learning_panel.py`

- [ ] 13. F2.3 — Create SentenceDetailDialog

  **What to do**:
  - Create `src/ui/sentence_detail.py` with `SentenceDetailDialog(QDialog)` class
  - Constructor: `__init__(self, sentence: SentenceRecord, vocab_hits: list[HighlightVocab], grammar_hits: list[HighlightGrammar], parent: QWidget | None = None)`
  - **Layout** (QVBoxLayout):
    - **Timestamp** (QLabel): `sentence.created_at` formatted nicely
    - **Japanese text** (QTextBrowser): Full highlighted text using `HighlightRenderer().build_rich_text()` (reuse existing highlight rendering from `src/ui/highlight.py`)
    - **Translation** (QLabel or QTextBrowser): `sentence.chinese_translation` — full text, word-wrapped
    - **Explanation** (QLabel or QTextBrowser): `sentence.explanation` — full text, word-wrapped (if not None/empty)
    - **Vocab hits section** (QGroupBox "Vocabulary"):
      - For each HighlightVocab: Show JLPT badge (`QLabel` with N{level} text + colored background matching JLPT_COLORS), surface, lemma, POS
      - Use `QGridLayout` or `QVBoxLayout` with rows
    - **Grammar hits section** (QGroupBox "Grammar"):
      - For each HighlightGrammar: Show JLPT badge, pattern, description
      - Same layout style as vocab section
    - **Close button** (QPushButton) → `self.accept()`
  - For JLPT badges, reference `src/ui/highlight.py:JLPT_COLORS` dict for consistent color scheme
  - Dialog should be sized to content with a reasonable minimum size (e.g., 500x400)

  **Must NOT do**:
  - Do NOT add "Add to Review" buttons (Feature 4 scope)
  - Do NOT add edit/delete functionality
  - Do NOT add navigation (previous/next sentence)
  - Do NOT add audio playback

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: New dialog with multiple sections, highlight reuse, JLPT badge styling — moderate complexity UI construction
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - `frontend-ui-ux`: Qt dialog, not web design
    - `playwright`: Qt dialog, not browser

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Tasks 10, 11, 12, 14, 15)
  - **Blocks**: Tasks 12 (if detail dialog is opened from panel — but actually Task 12 can stub `_open_detail` and Task 13 creates the dialog independently), 21
  - **Blocked By**: Task 8 (get_sentence_with_highlights for data retrieval pattern)

  **References**:

  **Pattern References**:
  - `src/ui/highlight.py:10-25` — `JLPT_COLORS` dict: Color mapping for N1-N5 badges. Reuse these exact colors
  - `src/ui/highlight.py:52-110` — `HighlightRenderer.build_rich_text()`: Instance method — reuse for rendering highlighted Japanese text in the dialog. Instantiate `HighlightRenderer()` and call `renderer.build_rich_text(analysis, user_level)`
  - `src/ui/tooltip.py:53-110` — QDialog-style popup pattern (though this is QWidget, similar layout)

  **API/Type References**:
  - `src/db/models.py:SentenceRecord` — Fields: `id, japanese_text, chinese_translation, explanation, created_at, ...`
  - `src/db/models.py:HighlightVocab` — Fields: `surface, lemma, pos, jlpt_level, is_beyond_level`
  - `src/db/models.py:HighlightGrammar` — Fields: `pattern, jlpt_level, description`
  - `src/ui/highlight.py:HighlightRenderer.build_rich_text(analysis, user_level)` — Instance method. Pass reconstructed AnalysisResult or pass raw tokens/hits

  **WHY Each Reference Matters**:
  - JLPT_COLORS: Badge colors must be consistent with overlay highlighting
  - HighlightRenderer.build_rich_text: Reuse via instance instead of reimplementing highlight rendering
  - Model types: Exact field names for displaying each detail section

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Dialog displays all sections
    Tool: Bash (python)
    Preconditions: Models and highlight modules available
    Steps:
      1. QT_QPA_PLATFORM=offscreen python -c "create SentenceDetailDialog with mock data, check that timestamp_label, japanese_text widget, translation widget, vocab group, grammar group all exist"
      2. Assert all widgets present (no AttributeError)
    Expected Result: All 5 sections rendered
    Failure Indicators: Missing widgets, AttributeError
    Evidence: .sisyphus/evidence/task-13-sections.txt

  Scenario: Vocab hits display JLPT badge + lemma + POS
    Tool: Bash (python)
    Preconditions: Dialog with vocab_hits containing 2 entries
    Steps:
      1. Create dialog with vocab_hits=[HighlightVocab(lemma="食べる", pos="動詞", jlpt_level=5, ...), HighlightVocab(lemma="概念", pos="名詞", jlpt_level=1, ...)]
      2. Find vocab group children
      3. Assert "食べる" and "概念" text appears in widgets
      4. Assert "N5" and "N1" badge labels present
    Expected Result: Each vocab hit shown with badge, lemma, POS
    Failure Indicators: Missing entries, wrong badge levels
    Evidence: .sisyphus/evidence/task-13-vocab-display.txt

  Scenario: No "Add to Review" button exists
    Tool: Bash (grep)
    Preconditions: sentence_detail.py created
    Steps:
      1. Run: grep -ni "review\|add to" src/ui/sentence_detail.py
      2. Assert no results (no F4 elements)
    Expected Result: No review functionality — F4 excluded
    Failure Indicators: Review-related text found
    Evidence: .sisyphus/evidence/task-13-no-review.txt
  ```

  **Evidence to Capture:**
  - [ ] task-13-sections.txt
  - [ ] task-13-vocab-display.txt
  - [ ] task-13-no-review.txt

  **Commit**: YES (groups with Wave 3)
  - Message: `feat(ui): create SentenceDetailDialog with highlighted text and JLPT badges`
  - Files: `src/ui/sentence_detail.py`
  - Pre-commit: `ruff check src/ui/sentence_detail.py && mypy src/ui/sentence_detail.py`

- [ ] 14. F3.2 — Export dialog in LearningPanel

  **What to do**:
  - In `src/ui/learning_panel.py`, implement the `_open_export_dialog()` method (placeholder from Task 12):
  - Show a `QDialog` with:
    - `QDateEdit` × 2 for date range (prefilled with panel's current filter dates)
    - `QRadioButton` × 2 for format: "JSON" (default) and "CSV"
    - `QCheckBox` "Include vocabulary/grammar highlights" (default: checked)
    - `QPushButton` "Export" and "Cancel"
  - On "Export" click:
    1. Determine format from radio buttons
    2. Open `QFileDialog.getSaveFileName(filter=...)` with appropriate file extension
    3. Call `self._repo.export_records(format=format, date_from=..., date_to=..., include_highlights=...)`
    4. Write returned string to chosen file path
    5. Show `QMessageBox.information("Export complete", f"Exported to {path}")`
    6. On error: `QMessageBox.critical("Export failed", str(error))`
  - The dialog can be a local function/class inside `_open_export_dialog()` or a small inner class — no need for a separate file

  **Must NOT do**:
  - Do NOT add markdown, XML, or other export formats
  - Do NOT add preview of exported data
  - Do NOT add async/threaded export (file write is fast enough synchronously)
  - Do NOT create a separate ExportDialog file — keep it in learning_panel.py

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Small dialog with radio buttons, checkbox, and file save — straightforward Qt code in existing file
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - `playwright`: Qt dialog, not browser

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Tasks 10, 11, 12, 13, 15)
  - **Blocks**: Task 22
  - **Blocked By**: Tasks 8 (filtered queries), 9 (export_records with filters), 12 (LearningPanel exists with placeholder)

  **References**:

  **Pattern References**:
  - `src/ui/learning_panel.py:_open_export_dialog()` — Placeholder method from Task 12. Implement here
  - `src/ui/settings.py` — SettingsDialog from Task 5: Similar dialog construction pattern with buttons and layouts

  **API/Type References**:
  - `src/db/repository.py:export_records(format, date_from, date_to, include_highlights)` — From Task 9. Returns `str` (JSON or CSV content)
  - `QFileDialog.getSaveFileName(parent, caption, dir, filter)` — Returns `(path, selected_filter)`. Filter example: `"JSON Files (*.json);;CSV Files (*.csv)"`

  **WHY Each Reference Matters**:
  - learning_panel.py placeholder: Exact insertion point
  - export_records: API contract for generating export content
  - QFileDialog: Correct usage for file save

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Export dialog has all controls
    Tool: Bash (python)
    Preconditions: Tasks 8, 9, 12 complete
    Steps:
      1. QT_QPA_PLATFORM=offscreen: Create LearningPanel, inspect _open_export_dialog method exists
      2. Call it (mock QFileDialog to return a temp path)
      3. Assert dialog has date fields, radio buttons for format, highlights checkbox
    Expected Result: Dialog shows all export configuration options
    Failure Indicators: Missing controls, method not found
    Evidence: .sisyphus/evidence/task-14-export-controls.txt

  Scenario: Export writes file to disk
    Tool: Bash (python)
    Preconditions: Panel with test DB data, mocked QFileDialog
    Steps:
      1. Mock QFileDialog.getSaveFileName to return /tmp/test_export.json
      2. Trigger export with JSON format, include_highlights=True
      3. Assert /tmp/test_export.json exists
      4. Assert file content is valid JSON with sentence data
    Expected Result: Export produces valid file on disk
    Failure Indicators: File not created, invalid content
    Evidence: .sisyphus/evidence/task-14-file-write.txt

  Scenario: Export error shows QMessageBox
    Tool: Bash (python)
    Preconditions: Panel with repo that raises on export
    Steps:
      1. Mock repo.export_records to raise RuntimeError("DB locked")
      2. Mock QMessageBox.critical to capture call
      3. Trigger export
      4. Assert QMessageBox.critical was called with error message
    Expected Result: Error handled gracefully with user message
    Failure Indicators: Unhandled exception, no message box
    Evidence: .sisyphus/evidence/task-14-error-handling.txt
  ```

  **Evidence to Capture:**
  - [ ] task-14-export-controls.txt
  - [ ] task-14-file-write.txt
  - [ ] task-14-error-handling.txt

  **Commit**: YES (groups with Wave 3)
  - Message: `feat(ui): implement export dialog with date range, format selection, and file save`
  - Files: `src/ui/learning_panel.py`
  - Pre-commit: `ruff check src/ui/learning_panel.py && mypy src/ui/learning_panel.py`

- [ ] 15. F3.3 — Quick Export in tray menu

  **What to do**:
  - In `src/ui/tray.py` (created in Task 1), add a "Quick Export" action to the tray context menu
  - Add a new signal: `quick_export_requested = Signal()` — emitted when "Quick Export" is clicked
  - In `src/main.py` (wired in Task 4), connect `tray.quick_export_requested` to a handler:
    - The handler opens `QFileDialog.getSaveFileName(filter="JSON Files (*.json)")` for file selection
    - Calls `repo.export_records("json")` (no filters — exports ALL data as JSON)
    - Writes to selected file
    - Shows `QMessageBox.information()` on success or `.critical()` on error
  - The handler function can be defined inline in main.py as `_quick_export()`

  **Must NOT do**:
  - Do NOT add format selection for quick export — always JSON
  - Do NOT add date filtering — quick export exports everything
  - Do NOT add include_highlights option — always True (include highlights)
  - Do NOT create a dialog for quick export — just file picker + export

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Small addition: one menu action + one signal + one short handler in main.py
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - `playwright`: Not browser-related

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Tasks 10, 11, 12, 13, 14)
  - **Blocks**: Task 22
  - **Blocked By**: Tasks 1 (tray.py exists), 4 (tray wired into main.py), 9 (export_records with highlights)

  **References**:

  **Pattern References**:
  - `src/ui/tray.py` (from Task 1) — Context menu construction, signal definitions. Add "Quick Export" action after existing menu items
  - `src/main.py` (from Task 4) — Signal connection pattern for tray signals

  **API/Type References**:
  - `src/db/repository.py:export_records("json")` — Returns JSON string with all sentences + highlights
  - `QFileDialog.getSaveFileName(parent, caption, dir, filter)` — For file selection

  **WHY Each Reference Matters**:
  - tray.py: Where to add the menu item and signal
  - main.py: Where to add the handler and signal connection
  - export_records: API to call for generating export content

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: quick_export_requested signal exists on tray
    Tool: Bash (python)
    Preconditions: tray.py modified
    Steps:
      1. QT_QPA_PLATFORM=offscreen: from src.ui.tray import SystemTrayManager; check hasattr for quick_export_requested
      2. Assert signal exists
    Expected Result: Signal defined on SystemTrayManager
    Failure Indicators: AttributeError
    Evidence: .sisyphus/evidence/task-15-signal.txt

  Scenario: Tray menu has "Quick Export" action
    Tool: Bash (python)
    Preconditions: tray.py modified
    Steps:
      1. Create SystemTrayManager, get context menu
      2. List all action texts
      3. Assert "Quick Export" in action texts
    Expected Result: Menu item present
    Failure Indicators: Action not found
    Evidence: .sisyphus/evidence/task-15-menu-action.txt

  Scenario: Quick export writes all data to JSON file
    Tool: Bash (python)
    Preconditions: main.py handler wired, DB with test data
    Steps:
      1. Mock QFileDialog to return /tmp/quick_export.json
      2. Trigger quick_export_requested signal (or call handler directly)
      3. Assert file exists and contains valid JSON
      4. Assert JSON contains all sentences (no date filter applied)
    Expected Result: Full database exported as JSON
    Failure Indicators: File missing, partial data, or format != JSON
    Evidence: .sisyphus/evidence/task-15-full-export.txt
  ```

  **Evidence to Capture:**
  - [ ] task-15-signal.txt
  - [ ] task-15-menu-action.txt
  - [ ] task-15-full-export.txt

  **Commit**: YES (groups with Wave 3)
  - Message: `feat(tray): add Quick Export menu action for one-click JSON export`
  - Files: `src/ui/tray.py`, `src/main.py`
  - Pre-commit: `ruff check src/ui/tray.py src/main.py && mypy src/ui/tray.py src/main.py`

- [ ] 16. F1.5 — Wire settings into main.py

  **What to do**:
  - In `src/main.py`, implement the `_open_settings()` placeholder (from Task 4):
    - Create or show existing `SettingsDialog`:
      - Store reference: `settings_dialog: SettingsDialog | None = None` in main scope (or as closure variable)
      - If dialog exists and is visible, raise it (`dialog.raise_()` + `dialog.activateWindow()`)
      - If dialog doesn't exist, create it: `SettingsDialog(current_config)` and connect signals
    - Connect `settings_dialog.config_changed` → two handlers:
      1. `overlay.on_config_changed(new_config)` — live-reload visual properties (Task 10)
      2. `pipeline.update_config(new_config)` — thread-safe pipeline update (Task 11)
    - Also update the `current_config` reference so next settings open shows updated values
  - Connect `tray.settings_requested` → `_open_settings()` (replace placeholder from Task 4)

  **Must NOT do**:
  - Do NOT make SettingsDialog modal (use .show(), not .exec())
  - Do NOT create a new dialog every time settings is opened — reuse if visible
  - Do NOT add config validation in main.py — SettingsDialog handles validation via widget constraints

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Small wiring changes in main.py — connect signals, manage dialog instance. No complex logic
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 4 (with Tasks 17, 18, 19, 20, 21, 22)
  - **Blocks**: Task 19 (tests for settings wiring)
  - **Blocked By**: Tasks 4 (tray wired), 5 (SettingsDialog exists), 10 (overlay.on_config_changed), 11 (pipeline.update_config)

  **References**:

  **Pattern References**:
  - `src/main.py:90-107` — Signal connection pattern from Tasks 1/4
  - `src/main.py:_open_settings()` — Placeholder from Task 4

  **API/Type References**:
  - `src/ui/settings.py:SettingsDialog(config: AppConfig)` — From Task 5. Signal: `config_changed(AppConfig)`
  - `src/ui/overlay.py:on_config_changed(config: AppConfig)` — From Task 10
  - `src/pipeline.py:update_config(config: AppConfig)` — From Task 11

  **WHY Each Reference Matters**:
  - main.py placeholder: Exact insertion point
  - SettingsDialog API: Constructor and signal to connect
  - on_config_changed/update_config: Two receivers for config changes

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Settings dialog opens from tray
    Tool: Bash (python)
    Preconditions: All dependency tasks complete
    Steps:
      1. AST-parse main.py to verify settings_requested is connected
      2. Verify SettingsDialog import exists
      3. Verify config_changed is connected to both overlay and pipeline
    Expected Result: Full signal chain: tray→settings→overlay+pipeline
    Failure Indicators: Missing connections
    Evidence: .sisyphus/evidence/task-16-wiring.txt

  Scenario: Single instance enforcement
    Tool: Bash (grep)
    Preconditions: main.py modified
    Steps:
      1. Search for raise_() or activateWindow in main.py near settings code
      2. Assert pattern exists (reuse logic)
    Expected Result: Dialog reuses existing instance
    Failure Indicators: No reuse logic found
    Evidence: .sisyphus/evidence/task-16-single-instance.txt
  ```

  **Evidence to Capture:**
  - [ ] task-16-wiring.txt
  - [ ] task-16-single-instance.txt

  **Commit**: YES (groups with Wave 4)
  - Message: `feat(main): wire SettingsDialog to tray with live-reload to overlay and pipeline`
  - Files: `src/main.py`
  - Pre-commit: `ruff check src/main.py && mypy src/main.py`

- [ ] 17. F2.4 — Wire LearningPanel into main.py

  **What to do**:
  - In `src/main.py`, implement the `_open_learning_panel()` placeholder (from Task 4):
    - Store reference: `learning_panel: LearningPanel | None = None` in main scope
    - If panel exists and is visible, raise it
    - If not, create: `LearningPanel(db_path)` — pass the database path so panel creates its own connection
    - Show panel as a standalone window (`panel.show()`)
  - Connect `tray.history_requested` → `_open_learning_panel()`
  - Optionally connect `pipeline.sentence_ready` → `panel.refresh()` (if panel exists) so new sentences auto-appear
  - Get `db_path` from the same path used to create the main repository (likely `get_db_path()` or a shared path variable)

  **Must NOT do**:
  - Do NOT make LearningPanel a child of OverlayWindow — it's a separate top-level window
  - Do NOT pass the same LearningRepository instance from main to panel (cross-thread concern)
  - Do NOT add panel to overlay layout

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Small wiring change in main.py — signal connection, instance management. Very similar to Task 16
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 4 (with Tasks 16, 18, 19, 20, 21, 22)
  - **Blocks**: Task 21 (tests for panel wiring)
  - **Blocked By**: Tasks 4 (tray wired), 12 (LearningPanel exists)

  **References**:

  **Pattern References**:
  - `src/main.py:_open_learning_panel()` — Placeholder from Task 4
  - `src/main.py` — Task 16 settings wiring pattern (same raise_/activateWindow pattern)

  **API/Type References**:
  - `src/ui/learning_panel.py:LearningPanel(db_path: str | Path)` — From Task 12. Public method: `refresh()`
  - `src/db/repository.py` — `get_db_path()` or similar for database path (check existing code)

  **WHY Each Reference Matters**:
  - main.py placeholder: Exact insertion point
  - LearningPanel constructor: Must know if it takes repo or db_path
  - DB path: Needed to pass to LearningPanel

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: History requested opens LearningPanel
    Tool: Bash (python)
    Preconditions: All dependency tasks complete
    Steps:
      1. AST-parse main.py for history_requested connection
      2. Verify LearningPanel import exists
      3. Verify _open_learning_panel contains LearningPanel construction
    Expected Result: tray.history_requested → LearningPanel.show()
    Failure Indicators: Missing connection or construction
    Evidence: .sisyphus/evidence/task-17-wiring.txt

  Scenario: Panel is standalone window (not child of overlay)
    Tool: Bash (grep)
    Preconditions: main.py modified
    Steps:
      1. Verify LearningPanel constructor does NOT pass overlay as parent
      2. Check for .show() call on panel
    Expected Result: Panel shown as independent top-level window
    Failure Indicators: Panel created as child of overlay
    Evidence: .sisyphus/evidence/task-17-standalone.txt
  ```

  **Evidence to Capture:**
  - [ ] task-17-wiring.txt
  - [ ] task-17-standalone.txt

  **Commit**: YES (groups with Wave 4)
  - Message: `feat(main): wire LearningPanel to tray history action`
  - Files: `src/main.py`
  - Pre-commit: `ruff check src/main.py && mypy src/main.py`

- [ ] 18. F0.4 — Tests for SystemTrayManager

  **What to do**:
  - Create `tests/test_tray.py` with pytest tests for `SystemTrayManager`:
    - `test_tray_creates_without_error` — Instantiate with QApplication, assert no crash
    - `test_tray_has_context_menu_actions` — Assert menu has: "Toggle Overlay", "Settings", "Learning History", "Quick Export", "Quit"
    - `test_toggle_overlay_signal_emitted` — Trigger toggle action, assert `toggle_overlay` signal fired (use `qtbot.waitSignal` if pytest-qt available, otherwise manual signal spy)
    - `test_settings_signal_emitted` — Trigger settings action, assert `settings_requested` signal fired
    - `test_quit_signal_emitted` — Trigger quit action, assert `quit_requested` signal fired
    - `test_quick_export_signal_emitted` — Trigger quick export action, assert `quick_export_requested` signal fired
    - `test_update_review_badge_with_zero` — Call `update_review_badge(0)`, assert no error (badge hidden or shows 0)
    - `test_isSystemTrayAvailable_guarded` — If tray not available (CI environment), assert graceful handling
  - Follow existing test patterns: Session-scoped `qapp` fixture, `QT_QPA_PLATFORM=offscreen`
  - If `pytest-qt` is not installed, use manual signal spies: connect signal to a list.append, trigger action, check list

  **Must NOT do**:
  - Do NOT install pytest-qt as a new dependency unless confirmed it's already available
  - Do NOT test visual rendering (icon pixels) — only test signals and menu structure
  - Do NOT test main.py integration here — only SystemTrayManager in isolation

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Straightforward test file following existing patterns, testing signal emissions and menu structure
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 4 (with Tasks 16, 17, 19, 20, 21, 22)
  - **Blocks**: None
  - **Blocked By**: Tasks 1 (SystemTrayManager), 4 (wiring — for context), 15 (quick_export signal)

  **References**:

  **Pattern References**:
  - `tests/test_overlay.py` — Existing Qt widget test pattern: qapp fixture, QT_QPA_PLATFORM=offscreen, signal testing
  - `tests/conftest.py` — Shared fixtures, session-scoped qapp if available

  **API/Type References**:
  - `src/ui/tray.py:SystemTrayManager` — All signals: `settings_requested`, `history_requested`, `toggle_overlay`, `quit_requested`, `quick_export_requested`. Methods: `update_review_badge(count: int)`

  **WHY Each Reference Matters**:
  - test_overlay.py: Qt test patterns to follow exactly
  - SystemTrayManager signals: All signals to test for emission

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: All tray tests pass
    Tool: Bash
    Preconditions: All tray code complete (Tasks 1, 4, 15)
    Steps:
      1. Run: QT_QPA_PLATFORM=offscreen pytest tests/test_tray.py -v
      2. Assert all tests pass (exit code 0)
      3. Assert ≥ 6 tests collected
    Expected Result: All tray tests green
    Failure Indicators: Any test failure, fewer than 6 tests
    Evidence: .sisyphus/evidence/task-18-test-results.txt
  ```

  **Evidence to Capture:**
  - [ ] task-18-test-results.txt

  **Commit**: YES (groups with Wave 4)
  - Message: `test(tray): add tests for SystemTrayManager signals and menu structure`
  - Files: `tests/test_tray.py`
  - Pre-commit: `QT_QPA_PLATFORM=offscreen pytest tests/test_tray.py -v`

- [ ] 19. F1.6 — Tests for SettingsDialog and config integration

  **What to do**:
  - Create `tests/test_settings.py` with pytest tests for `SettingsDialog`:
    - `test_settings_dialog_has_four_tabs` — Assert QTabWidget.count() == 4
    - `test_widgets_populate_from_config` — Create with non-default AppConfig, assert widget values match
    - `test_save_emits_config_changed` — Connect signal spy, click save, assert signal emitted with AppConfig
    - `test_cancel_does_not_emit_signal` — Connect signal spy, reject dialog, assert no emission
    - `test_jlpt_level_spinbox_range` — Assert range 1-5
    - `test_opacity_slider_range` — Assert range 10-100
    - `test_ollama_url_populated` — Assert QLineEdit text matches config.ollama_url
    - `test_template_fields_populated` — Assert translation/explanation templates match config
  - Also add to `tests/test_config.py` (or extend existing):
    - `test_config_new_fields_have_defaults` — Assert AppConfig() has all new fields with expected defaults
    - `test_config_backward_compat_unknown_keys_filtered` — Save config with unknown key, load it, assert no error and unknown key ignored
  - Follow existing test patterns from `tests/test_overlay.py` and `tests/test_config.py`

  **Must NOT do**:
  - Do NOT test SettingsDialog ↔ main.py integration (that's F-level integration)
  - Do NOT test visual rendering/styling
  - Do NOT mock AppConfig — use real instances with test values

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Straightforward test file with well-defined assertions, following existing patterns
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 4 (with Tasks 16, 17, 18, 20, 21, 22)
  - **Blocks**: None
  - **Blocked By**: Tasks 2 (AppConfig new fields), 5 (SettingsDialog), 16 (wiring for context)

  **References**:

  **Pattern References**:
  - `tests/test_overlay.py` — Qt widget test patterns
  - `tests/test_config.py` — Config test patterns, existing test structure

  **API/Type References**:
  - `src/ui/settings.py:SettingsDialog` — From Task 5
  - `src/config.py:AppConfig` — All fields and defaults

  **WHY Each Reference Matters**:
  - Existing test files: Patterns to follow
  - SettingsDialog/AppConfig: APIs under test

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: All settings tests pass
    Tool: Bash
    Preconditions: Tasks 2, 5 complete
    Steps:
      1. Run: QT_QPA_PLATFORM=offscreen pytest tests/test_settings.py tests/test_config.py -v
      2. Assert all tests pass (exit code 0)
      3. Assert ≥ 8 tests collected in test_settings.py
    Expected Result: All settings + config tests green
    Failure Indicators: Any failure, fewer than 8 settings tests
    Evidence: .sisyphus/evidence/task-19-test-results.txt
  ```

  **Evidence to Capture:**
  - [ ] task-19-test-results.txt

  **Commit**: YES (groups with Wave 4)
  - Message: `test(settings): add tests for SettingsDialog tabs, config population, and signals`
  - Files: `tests/test_settings.py`, `tests/test_config.py`
  - Pre-commit: `QT_QPA_PLATFORM=offscreen pytest tests/test_settings.py tests/test_config.py -v`

- [ ] 20. F1.5.3 — Tests for resize and text layout

  **What to do**:
  - In `tests/test_overlay.py` (extend existing file), add tests for resize functionality:
    - `test_overlay_accepts_config_constructor` — OverlayWindow(AppConfig()) doesn't crash
    - `test_overlay_uses_config_dimensions` — OverlayWindow(AppConfig(overlay_width=600, overlay_height=100)) has those dimensions
    - `test_overlay_minimum_size` — Assert minimumWidth() >= 400 and minimumHeight() >= 80
    - `test_overlay_no_hardcoded_800_120` — AST or grep check that resize(800, 120) is not in overlay.py
    - `test_overlay_center_on_screen_method_exists` — Assert hasattr(overlay, '_center_on_screen')
    - `test_on_config_changed_updates_opacity` — Call on_config_changed(config_with_opacity_0.5), assert windowOpacity() == 0.5
  - Create or extend `tests/test_highlight.py` for text layout:
    - `test_build_rich_text_contains_centering_table` — Instantiate `HighlightRenderer()`, call `renderer.build_rich_text(analysis, user_level)`, assert "table" in output HTML (table-based centering)
    - `test_build_rich_text_no_inline_block` — Instantiate `HighlightRenderer()`, call `renderer.build_rich_text(analysis, user_level)`, assert "inline-block" NOT in output HTML
    - `test_get_highlight_at_position_unchanged` — Existing position mapping still works after centering wrapper
  - Note: Some test_overlay tests may need updating since constructor changed from `(user_level: int)` to `(config: AppConfig)`. Update existing tests accordingly

  **Must NOT do**:
  - Do NOT test actual pixel rendering or visual layout
  - Do NOT test QSizeGrip mouse interaction (unreliable in offscreen mode)
  - Do NOT create a new test file for highlight tests if test_highlight.py already exists — extend it

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Adding test functions to existing test files, well-defined assertions
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 4 (with Tasks 16, 17, 18, 19, 21, 22)
  - **Blocks**: None
  - **Blocked By**: Tasks 6 (resize support), 7 (text layout), 10 (on_config_changed)

  **References**:

  **Pattern References**:
  - `tests/test_overlay.py` — Existing overlay tests. Will need to update constructor calls from `OverlayWindow(5)` to `OverlayWindow(AppConfig())`
  - `tests/test_highlight.py` — Existing highlight tests (if file exists)

  **API/Type References**:
  - `src/ui/overlay.py:OverlayWindow(config: AppConfig)` — New constructor from Task 6
  - `src/ui/overlay.py:on_config_changed(config: AppConfig)` — From Task 10
  - `src/ui/highlight.py:HighlightRenderer.build_rich_text(analysis, user_level)` — Instance method modified in Task 7 (centering)

  **WHY Each Reference Matters**:
  - Existing test files: Must update constructor calls and extend, not replace
  - Modified APIs: New signatures to test against

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: All overlay and highlight tests pass
    Tool: Bash
    Preconditions: Tasks 6, 7, 10 complete
    Steps:
      1. Run: QT_QPA_PLATFORM=offscreen pytest tests/test_overlay.py tests/test_highlight.py -v
      2. Assert all tests pass (exit code 0)
      3. Assert ≥ 4 new tests for resize/layout
    Expected Result: All tests green, including new resize/layout tests
    Failure Indicators: Any failure, missing new tests
    Evidence: .sisyphus/evidence/task-20-test-results.txt
  ```

  **Evidence to Capture:**
  - [ ] task-20-test-results.txt

  **Commit**: YES (groups with Wave 4)
  - Message: `test(overlay): add tests for resize, config constructor, and centered text layout`
  - Files: `tests/test_overlay.py`, `tests/test_highlight.py`
  - Pre-commit: `QT_QPA_PLATFORM=offscreen pytest tests/test_overlay.py tests/test_highlight.py -v`

- [ ] 21. F2.5 — Tests for LearningPanel and repository queries

  **What to do**:
  - Create `tests/test_learning_panel.py` with pytest tests:
    - `test_panel_creates_with_db_path` — LearningPanel(":memory:") doesn't crash
    - `test_panel_has_table_with_4_columns` — Assert columnCount() == 4
    - `test_panel_has_search_and_pagination` — Assert search input, prev/next buttons exist
    - `test_pagination_calculates_pages` — Insert 120 records, assert page count == 3 (50/page)
    - `test_search_filters_results` — Set search text, refresh, assert filtered
    - `test_refresh_method_callable` — Assert panel.refresh() runs without error
  - Extend `tests/test_db_repository.py` with tests for new query methods:
    - `test_get_sentences_filtered_pagination` — Insert N records, query with limit/offset, verify counts
    - `test_get_sentences_filtered_query_filter` — Filter by query string, assert LIKE matching
    - `test_get_sentences_filtered_date_range` — Filter by date_from/date_to
    - `test_get_sentences_filtered_invalid_sort_raises` — sort_by="malicious", assert ValueError
    - `test_get_sentence_count_matches_filtered` — Count == len(filtered results)
    - `test_get_sentence_with_highlights_found` — Insert sentence + highlights, query, assert tuple
    - `test_get_sentence_with_highlights_not_found` — Query nonexistent ID, assert None

  **Must NOT do**:
  - Do NOT test SentenceDetailDialog integration here (Task 13 handles its own tests)
  - Do NOT test export dialog here (Task 22)
  - Do NOT use real database files — all tests use :memory:

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Two test files with multiple test functions, DB setup/teardown, pagination math verification. More involved than a quick task
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 4 (with Tasks 16, 17, 18, 19, 20, 22)
  - **Blocks**: None
  - **Blocked By**: Tasks 8 (filtered queries), 12 (LearningPanel), 13 (SentenceDetailDialog)

  **References**:

  **Pattern References**:
  - `tests/test_db_repository.py` — Existing repository tests: :memory: DB setup, insert→query→assert pattern
  - `tests/test_overlay.py` — Qt widget test patterns

  **API/Type References**:
  - `src/ui/learning_panel.py:LearningPanel(db_path)` — From Task 12
  - `src/db/repository.py:get_sentences_filtered()` — From Task 8
  - `src/db/repository.py:get_sentence_count()` — From Task 8
  - `src/db/repository.py:get_sentence_with_highlights()` — From Task 8

  **WHY Each Reference Matters**:
  - Existing test files: Patterns to follow for DB and Qt tests
  - Repository methods: APIs under test with exact signatures

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: All panel and repository tests pass
    Tool: Bash
    Preconditions: Tasks 8, 12, 13 complete
    Steps:
      1. Run: QT_QPA_PLATFORM=offscreen pytest tests/test_learning_panel.py tests/test_db_repository.py -v
      2. Assert all tests pass (exit code 0)
      3. Assert ≥ 6 tests in test_learning_panel.py and ≥ 7 new tests in test_repository.py
    Expected Result: All panel + repository tests green
    Failure Indicators: Any failure, insufficient test count
    Evidence: .sisyphus/evidence/task-21-test-results.txt
  ```

  **Evidence to Capture:**
  - [ ] task-21-test-results.txt

  **Commit**: YES (groups with Wave 4)
  - Message: `test(learning): add tests for LearningPanel and filtered repository queries`
  - Files: `tests/test_learning_panel.py`, `tests/test_db_repository.py`
  - Pre-commit: `QT_QPA_PLATFORM=offscreen pytest tests/test_learning_panel.py tests/test_db_repository.py -v`

- [ ] 22. F3.4 — Tests for filtered export

  **What to do**:
  - Extend `tests/test_db_repository.py` with export tests:
    - `test_export_records_backward_compat` — Call export_records("json") with no new params, assert valid JSON
    - `test_export_records_json_with_highlights` — export_records("json", include_highlights=True), assert "vocab_highlights" key in JSON
    - `test_export_records_csv_with_highlights` — export_records("csv", include_highlights=True), assert "vocab_count" column in header
    - `test_export_records_date_filtering` — Insert sentences with different dates, filter, assert only matching dates
    - `test_export_records_without_highlights` — export_records("json", include_highlights=False), assert no "vocab_highlights" key
  - Create `tests/test_export.py` or extend `tests/test_learning_panel.py` with:
    - `test_export_dialog_has_controls` — Assert date fields, format radios, highlights checkbox exist
    - `test_quick_export_signal_triggers_handler` — Mock QFileDialog + file write, assert JSON file created
  - Use :memory: DB with test fixture data for all export tests

  **Must NOT do**:
  - Do NOT test file I/O with real filesystem in unit tests — mock file writes or use tmp_path fixture
  - Do NOT test QFileDialog interaction directly — mock it

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Adding test functions to existing files, well-defined assertions for export behavior
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 4 (with Tasks 16, 17, 18, 19, 20, 21)
  - **Blocks**: None
  - **Blocked By**: Tasks 9 (export_records with filters), 14 (export dialog), 15 (quick export)

  **References**:

  **Pattern References**:
  - `tests/test_db_repository.py` — Existing export test pattern (if any), DB fixture setup

  **API/Type References**:
  - `src/db/repository.py:export_records(format, date_from, date_to, include_highlights)` — From Task 9
  - Quick export handler in `src/main.py` — From Task 15

  **WHY Each Reference Matters**:
  - Existing test patterns: Follow for consistency
  - export_records: API under test with exact parameters

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: All export tests pass
    Tool: Bash
    Preconditions: Tasks 9, 14, 15 complete
    Steps:
      1. Run: QT_QPA_PLATFORM=offscreen pytest tests/test_db_repository.py tests/test_learning_panel.py -v -k "export"
      2. Assert all export-related tests pass (exit code 0)
      3. Assert ≥ 5 export tests collected
    Expected Result: All export tests green
    Failure Indicators: Any failure, fewer than 5 export tests
    Evidence: .sisyphus/evidence/task-22-test-results.txt
  ```

  **Evidence to Capture:**
  - [ ] task-22-test-results.txt

  **Commit**: YES (groups with Wave 4)
  - Message: `test(export): add tests for filtered export, date range, highlights, and quick export`
  - Files: `tests/test_db_repository.py`, `tests/test_learning_panel.py` or `tests/test_export.py`
  - Pre-commit: `QT_QPA_PLATFORM=offscreen pytest tests/test_db_repository.py -v -k "export"`

---

## Final Verification Wave (MANDATORY — after ALL implementation tasks)

> 4 review agents run in PARALLEL. ALL must APPROVE. Rejection → fix → re-run.

- [ ] F1. **Plan Compliance Audit** — `oracle`
  Read the plan end-to-end. For each "Must Have": verify implementation exists (read file, run command). For each "Must NOT Have": search codebase for forbidden patterns — reject with file:line if found. Check evidence files exist in .sisyphus/evidence/. Compare deliverables against plan.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [ ] F2. **Code Quality Review** — `unspecified-high`
  Run `ruff check . && ruff format --check . && mypy . && pytest`. Review all changed files for: `as any`/`type: ignore`, empty catches, print() in prod, commented-out code, unused imports. Check AI slop: excessive comments, over-abstraction, generic names, utility modules.
  Output: `Build [PASS/FAIL] | Lint [PASS/FAIL] | Tests [N pass/N fail] | Files [N clean/N issues] | VERDICT`

- [ ] F3. **Real Manual QA** — `unspecified-high`
  Start from clean state. Execute EVERY QA scenario from EVERY task — follow exact steps, capture evidence. Test cross-task integration (tray→settings→overlay, panel→export). Test edge cases: empty DB, resize at min/max, cancel dialogs. Save to `.sisyphus/evidence/final-qa/`.
  Output: `Scenarios [N/N pass] | Integration [N/N] | Edge Cases [N tested] | VERDICT`

- [ ] F4. **Scope Fidelity Check** — `deep`
  For each task: read "What to do", read actual diff. Verify 1:1 — everything in spec was built (no missing), nothing beyond spec was built (no creep). Check "Must NOT do" compliance. Flag unaccounted changes. Specifically verify: NO review_items table, NO ReviewRepository, NO build_review_text, NO "Add to Review" buttons.
  Output: `Tasks [N/N compliant] | Scope [CLEAN/N issues] | Unaccounted [CLEAN/N files] | VERDICT`

---

## Commit Strategy

| After Wave | Commit Message | Pre-commit Check |
|------------|---------------|-----------------|
| Wave 1 | `feat(config): add tray manager and extend AppConfig with UI settings fields` | `ruff check . && ruff format --check . && mypy .` |
| Wave 2 | `feat(ui): add settings dialog, overlay resize, filtered repo queries, and export filters` | `ruff check . && ruff format --check . && mypy .` |
| Wave 3 | `feat(ui): add live-reload, learning panel, export dialogs, and pipeline config updates` | `ruff check . && ruff format --check . && mypy .` |
| Wave 4 | `feat: wire all features into main.py and add comprehensive tests` | `ruff check . && ruff format --check . && mypy . && pytest` |
| Final | `test: final QA verification and cleanup` | `ruff check . && ruff format --check . && mypy . && pytest` |

---

## Success Criteria

### Verification Commands
```bash
ruff check .                    # Expected: no errors
ruff format --check .           # Expected: all files formatted
mypy .                          # Expected: no new errors (existing vad/tokenizer errors OK)
pytest                          # Expected: all tests pass
pytest --co | wc -l             # Expected: > 200 (current ~200 + new tests)
```

### Final Checklist
- [ ] All "Must Have" items implemented and verified
- [ ] All "Must NOT Have" items absent from codebase
- [ ] All tests pass (`pytest` exit code 0)
- [ ] No ruff lint errors, no new mypy errors
- [ ] System tray visible with functional menu actions
- [ ] Settings dialog saves and live-reloads all config fields
- [ ] Overlay resize works with size persisted across restarts
- [ ] Learning panel shows filtered, paginated history with detail view
- [ ] Export produces valid JSON/CSV with highlights when requested
