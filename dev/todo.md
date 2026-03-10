Existing bugs running in Windows 11:

1. "Shortcut: Toggle Display" does not work. There is logging in the console that shows the pressed shortcuts ("src.ui.shortcuts INFO Shortcut activated: _emit_toggle_display"), but it does not trigger the expected behavior (The overlay toggles between jp <-> cn).

2. "Shortcut: Prev" and "Shortcut: Next" do not work. There is no logging in the console when these shortcuts are pressed.

Checklist:

1. [x] Fix the bug causing shortcuts to not work in Windows 11. Logging the pressed shrotcuts in the console can help identify the issue.
2. [x] Test the application thoroughly to ensure all bugs are fixed and improvements are working as intended.
3. [x] No mypy/ruff errors should be present in the codebase after the changes.
4. [x] Update documentation to reflect any changes made to the application.

## Resolution Notes

### Bug 1: Toggle Display shortcut fires but does nothing

**Root cause:** `_toggle_mode()` in `overlay.py` had an early return when `_display_mode == "both"` (the default). The method only toggled between jp/cn sub-modes when already in "single" mode, making it a no-op on fresh start.

**Fix:** Changed `_toggle_mode()` to cycle through all three states: `both → single(jp) → single(cn) → both`. Now the toggle shortcut works regardless of the current display mode.

### Bug 2: Prev/Next sentence shortcuts don't fire at all

**Root cause:** `pynput.keyboard.HotKey.parse()` converts non-modifier special keys (arrows, etc.) to `KeyCode.from_vk(vk)`, but `listener.canonical(key)` returns `Key` enum members (e.g., `Key.left`). These two representations are different types that don't compare equal, so arrow-key hotkeys silently never match. Character keys like `t` and modifiers like `Ctrl` were unaffected because their parse/canonical representations do match.

**Fix:** Replaced `pynput.keyboard.HotKey`-based implementation with manual key-set tracking in `shortcuts.py`. The new approach:
- `_normalise_key()` folds modifier variants (ctrl_l/ctrl_r → ctrl) and lowercases characters
- `_parse_shortcut()` converts Qt-style strings ("Ctrl+Left") into frozensets of normalised `Key`/`KeyCode` objects, using `Key` enum members for special keys (not `KeyCode.from_vk`)
- `_on_press()` / `_on_release()` track normalised pressed keys and compare against registered shortcut sets

### Additional fix: Pre-existing test bug

`test_on_translation_ready_updates_cn_browser` expected both `translation` and `explanation` in the HTML, but `on_llm_ready()` uses `translation or explanation or "LLM unavailable"` — only one value is ever displayed. Split into two tests.

### Files changed
- `src/ui/shortcuts.py` — Rewrote shortcut manager with manual key tracking
- `src/ui/overlay.py` — Fixed `_toggle_mode()` cycling logic
- `tests/test_shortcuts.py` — Rewrote tests for new API
- `tests/test_overlay.py` — Updated toggle tests + fixed translation test

### Validation
- `ruff check .` — All checks passed
- `ruff format --check .` — 75 files already formatted
- `mypy .` — Success: no issues found in 77 source files
- `pytest` — 505 passed, 8 skipped, 1 xfailed, 0 failures
