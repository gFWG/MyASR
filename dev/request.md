Existing bugs running in Windows 11:

1. Shortcuts still do not work and no error is thrown in the console.

Checklist:

1. [x] Fix the bug causing shortcuts to not work in Windows 11. Logging the pressed shrotcuts in the console can help identify the issue.
4. [x] Test the application thoroughly to ensure all bugs are fixed and improvements are working as intended.
5. [x] No mypy/ruff errors should be present in the codebase after the changes.
6. [x] Update documentation to reflect any changes made to the application.

## Changes Made

### Global Shortcuts Fix (Windows 11)

**Root cause**: `pynput.keyboard.GlobalHotKeys` silently fails on Windows 11 due to
key-state de-synchronization and canonical-key mismatches. When the OS or other
applications interfere with the low-level keyboard hook chain, `GlobalHotKeys`
loses track of which keys are pressed and callbacks never fire — with no errors.

**Fix**: Replaced `GlobalHotKeys` with a manual `keyboard.Listener` +
`keyboard.HotKey` approach in `src/ui/shortcuts.py`:

- A `keyboard.Listener` captures all key press/release events
- Each event is normalized via `listener.canonical(key)` before being forwarded
  to `keyboard.HotKey` instances — this ensures consistent key matching across
  platforms and keyboard layouts
- Added `logging.debug()` for every key press/release (canonical form) so
  shortcut issues can be diagnosed from console output
- Added `logging.info()` when a shortcut activates

**Files changed**:
- `src/ui/shortcuts.py` — Rewritten to use `Listener` + `HotKey` instead of `GlobalHotKeys`
- `tests/test_shortcuts.py` — Updated tests to cover the new implementation
  (16 tests: key conversion, lifecycle, restart, canonical dispatch, edge cases)

**Public API unchanged**: `GlobalShortcutManager` still exposes the same
`start()`, `stop()`, `update_shortcuts()` methods and
`toggle_display_triggered`, `prev_sentence_triggered`, `next_sentence_triggered`
signals. No changes needed in `overlay.py`, `settings.py`, or `config.py`.

