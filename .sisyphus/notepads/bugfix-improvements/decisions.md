# Decisions — bugfix-improvements

## [2026-03-09] Session: ses_32d3f026fffe4Ouyt2D97O4BbR
Key architectural decisions from plan:
- Global shortcuts via pynput (NOT Qt QShortcuts) — overlay uses WA_ShowWithoutActivating making QShortcuts non-functional
- pynput thread safety: use QMetaObject.invokeMethod with Qt.QueuedConnection (never direct Qt calls from pynput thread)
- pynput suppress=False so hotkeys pass through to other apps
- GlobalShortcutManager is a QObject subclass (not QWidget)
- Config keeps Qt-style key strings ("Ctrl+Left") — converter function handles mapping to pynput
- NO abstract base classes for segmented controls — inline implementation only
- NO changes to AppConfig field types or names
- pre-existing _MAX_HISTORY discrepancy: mark test_history_max_size as @pytest.mark.xfail in Task 9
