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
