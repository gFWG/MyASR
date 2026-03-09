## Task 2: WAL/SHM SQLite connection cleanup

- `_cleanup()` in `src/main.py` is a standalone function — it doesn't have direct access to `_learning_panel` (which is a `nonlocal` inside `main()`). Solution: add `learning_panel: LearningPanel | None = None` optional param and update the lambda in `aboutToQuit`.
- WAL checkpoint must be done BEFORE `conn.close()`, using `conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")`.
- `LearningPanel.closeEvent` must import `QCloseEvent` from `PySide6.QtGui` (not `PySide6.QtWidgets`).
- When mocking `init_db` for `LearningPanel` tests, must also stub `mock_conn.execute` return since `__init__` calls `conn.execute("PRAGMA journal_mode=WAL")`.
