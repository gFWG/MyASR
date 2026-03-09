## Task 2: WAL/SHM SQLite connection cleanup

- `_cleanup()` in `src/main.py` is a standalone function — it doesn't have direct access to `_learning_panel` (which is a `nonlocal` inside `main()`). Solution: add `learning_panel: LearningPanel | None = None` optional param and update the lambda in `aboutToQuit`.
- WAL checkpoint must be done BEFORE `conn.close()`, using `conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")`.
- `LearningPanel.closeEvent` must import `QCloseEvent` from `PySide6.QtGui` (not `PySide6.QtWidgets`).
- When mocking `init_db` for `LearningPanel` tests, must also stub `mock_conn.execute` return since `__init__` calls `conn.execute("PRAGMA journal_mode=WAL")`.

## Task 3 — GlobalShortcutManager with pynput

- pynput 1.8.1 is in the venv. `GlobalHotKeys(hotkeys_dict, suppress=False)` is the correct API.
- `GlobalHotKeys` key format: `"<ctrl>+<left>"`, `"<ctrl>+t"` — lowercase, modifiers in `<>`.
- `HotKey.parse` expects either single-char (`"t"`) or `"<name>"` bracketed identifiers.
- `QMetaObject.invokeMethod(obj, "slot_name", Qt.ConnectionType.QueuedConnection)` — works with string method names; methods must be decorated with `@Slot()`.
- `suppress=False` is the default for pynput `Listener`, so passing it explicitly is harmless but explicit.
- `GlobalHotKeys` is a `Thread` subclass — use `.start()` / `.stop()` / `.join()`.
- mocker.patch path must be `"src.ui.shortcuts.keyboard.GlobalHotKeys"` (where it's imported), not the pynput module path.

## Task 4: Shortcuts Tab Extraction (2026-03-09)

- Moved 3 shortcut QLineEdit widgets (`_shortcut_prev_edit`, `_shortcut_next_edit`, `_shortcut_toggle_edit`) from `_build_appearance_tab()` to new `_build_shortcuts_tab()` method
- New tab inserted at index 3 (4th tab), named "Shortcuts", before "Templates"
- Tab order: General (0), Appearance (1), Model (2), Shortcuts (3), Templates (4)
- `_populate_from_config()` and `_collect_config()` needed no changes — widget names unchanged, just moved
- Test rename: `test_settings_dialog_has_four_tabs` → `test_settings_dialog_has_five_tabs` (count 4→5)
- All 24 tests pass after change

## Task 5: QComboBox → QPushButton Segmented Controls (2026-03-09)

- Replaced `_llm_mode_combo` (QComboBox) in `_build_general_tab()` with two `QPushButton`s: `_llm_mode_btn_translation` + `_llm_mode_btn_explanation`. State stored in `self._llm_mode_value: str`.
- Replaced `_display_mode_combo` (QComboBox) in `_build_appearance_tab()` with two `QPushButton`s: `_display_mode_btn_both` + `_display_mode_btn_single`. State stored in `self._display_mode_value: str`.
- Added helper methods `_select_llm_mode(mode: str)` and `_select_display_mode(mode: str)` that update `_value` and `setChecked()` on both buttons.
- Lambda connects in `_build_*` methods referencing `_select_llm_mode`/`_select_display_mode` cause LSP "attribute unknown" false positives (methods defined later in the class). These are runtime-safe.
- `type: ignore[arg-type]` still needed on `_collect_config()` for `llm_mode=self._llm_mode_value` and `overlay_display_mode=self._display_mode_value` since those fields are `Literal[...]`.
- Tests updated: `test_display_mode_combo_populated` → `test_display_mode_segmented_populated`, `test_collect_config_includes_display_mode` now calls `dialog._select_display_mode("single")`.
- Added 3 new tests: `test_llm_mode_segmented_populated`, `test_llm_mode_segmented_default_is_translation`, `test_collect_config_includes_llm_mode`.
- 27 tests pass. Qt segfault at teardown is a known PySide6 cleanup issue, not a test failure.

## Task 6: Settings Dialog Regex Validation

### Pattern: Validation before save in PySide6 dialog
- When adding inline validation to `_on_save()`, validate first → early return on error → clear error and proceed on success
- `re.compile(text)` with empty string check (`if parse_format:`) avoids false negatives — empty string is valid (means "no regex")
- `QLabel` with `setStyleSheet("color: red;")` is the standard pattern for inline error display
- Add label via `layout.addRow("", self._regex_error_label)` to place it in the field column without a label

### Pattern: Concurrent task coordination
- T5 and T6 both modified `settings.py` simultaneously; T6 was strictly scoped to `_build_model_tab()` and `_on_save()` 
- T5 touched `_build_general_tab()`, `_build_appearance_tab()`, `_populate_from_config()`, `_collect_config()` — no conflicts

### Test approach for "dialog stays open"
- `d.show()` then `d._on_save()` then `assert d.isVisible()` — straightforward
- Qt's `close()` sets visibility to False, so `isVisible()` is the right assertion

### Segfault on pytest exit
- Known Qt/PySide6 cleanup issue on Linux — does NOT indicate test failure (30 passed)
