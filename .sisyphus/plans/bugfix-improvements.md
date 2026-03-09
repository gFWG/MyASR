# MyASR Bug Fixes & UI Improvements

## TL;DR

> **Quick Summary**: Fix 3 bugs (asyncio cleanup on exit, broken global shortcuts, WAL/SHM file persistence) and implement 6 UI improvements (shortcuts tab, key capture widget, segmented controls, remove auto-close, regex validation, display toggle behavior).
> 
> **Deliverables**:
> - Clean asyncio shutdown with no pending task errors
> - Global system-wide hotkeys via pynput replacing broken QShortcuts
> - Proper SQLite connection lifecycle closing WAL/SHM files
> - Reorganized settings dialog with Shortcuts tab, key capture widgets, segmented controls
> - Regex validation on Parse Format field
> - Corrected display toggle behavior (jp↔cn cycle only in "single" mode)
> 
> **Estimated Effort**: Medium
> **Parallel Execution**: YES - 4 waves
> **Critical Path**: Task 3 → Task 7 → Task 9 → Final Wave

---

## Context

### Original Request
Fix bugs and implement improvements listed in `dev/request.md` for the MyASR Japanese learning overlay app running on Windows 11.

### Interview Summary
**Key Discussions**:
- **Shortcut scope**: User chose global system-wide hotkeys via `pynput` library
- **Settings auto-close**: User REVERSED the request — wants dialog to STAY OPEN after save (remove existing `self.close()`)
- **Display toggle**: Cycle jp→cn→jp only when mode is "single"; do nothing when "both"
- **Toggle style**: Segmented control (side-by-side buttons with active highlighting)
- **Tests**: Tests after implementation, using pytest

**Research Findings**:
- Overlay window uses `WA_ShowWithoutActivating` + `Tool` flags → QShortcuts never fire (no focus)
- `LlmWorker` and `AsrWorker` create `LearningRepository` but never close them in finally blocks
- `AsyncOllamaClient._http` has no standalone `close()` method — only `__aexit__` which is never called
- `orchestrator.on_config_changed()` leaks old httpx client on config change
- `_on_save()` already calls `self.close()` — removal is the fix
- `_toggle_mode()` currently cycles both→single/jp→single/cn→both — needs guard for "both" mode

### Metis Review
**Identified Gaps** (addressed):
- **Orchestrator client leak**: Added to Bug 1 scope — close old client before creating new one in `on_config_changed()`
- **pynput thread safety**: Mandated `QObject` signal bridge in `GlobalShortcutManager` — no direct Qt widget calls from pynput thread
- **pynput key pass-through**: Must use `suppress=False` (default) so hotkeys don't block other apps
- **Key format mapping**: Keep Qt-style config strings + add converter function (no config migration needed)
- **Breaking test coverage**: Tests for tab count, shortcut binding, toggle behavior must all be updated
- **LearningPanel cleanup**: Both `closeEvent` on panel AND cleanup in `_cleanup()` in main.py
- **Pre-existing discrepancy**: `_MAX_HISTORY=10` vs test expecting 100 — OUT OF SCOPE, don't touch

---

## Work Objectives

### Core Objective
Fix all confirmed bugs and implement all requested UI improvements for the MyASR overlay application on Windows 11.

### Concrete Deliverables
- `src/llm/ollama_client.py` — add `close()` method
- `src/pipeline/llm_worker.py` — proper asyncio cleanup + DB close in finally
- `src/pipeline/asr_worker.py` — DB close in finally
- `src/pipeline/orchestrator.py` — close old client on config change
- `src/ui/learning_panel.py` — `closeEvent` to close DB connection
- `src/main.py` — WAL checkpoint + LearningPanel cleanup in `_cleanup()`
- `src/ui/shortcuts.py` — NEW: `GlobalShortcutManager(QObject)` wrapping pynput
- `src/ui/overlay.py` — replace QShortcuts with GlobalShortcutManager, fix `_toggle_mode()`
- `src/ui/settings.py` — new Shortcuts tab, `QKeySequenceEdit`, segmented controls, remove auto-close, regex validation
- `requirements.txt` — add `pynput`
- Updated tests for all changes

### Definition of Done
- [ ] `pytest -x --tb=short` — all tests pass
- [ ] `ruff check . && ruff format --check .` — no lint/format issues
- [ ] `mypy .` — no type errors (beyond pre-existing ones)
- [ ] No "Task was destroyed but it is pending" error on exit
- [ ] Global hotkeys work regardless of which app is focused
- [ ] WAL/SHM files are cleaned up after program exit

### Must Have
- All 3 bug fixes verified
- All 6 improvements implemented
- Tests for every change
- pynput-based global shortcuts with Qt signal bridge
- Thread-safe pynput integration (no direct Qt calls from pynput callbacks)

### Must NOT Have (Guardrails)
- **NO abstract base classes or generic widget frameworks** — segmented control is inline implementation
- **NO changes to `AppConfig` field types or names** — keep `str` type for shortcuts, keep existing field names
- **NO new config fields** — work within existing config structure
- **NO changes to orchestrator stop() order or queue sizes**
- **NO refactoring of `_toggle_mode()` cycling logic beyond the single-mode guard**
- **NO logging configuration changes**
- **NO touching `_MAX_HISTORY` value** — the pre-existing test discrepancy (`_MAX_HISTORY=10` in code but test expects 100) must be handled by adding `@pytest.mark.xfail(reason="pre-existing: _MAX_HISTORY=10 but test expects 100")` to the failing test in `test_overlay.py::test_history_max_size` as part of Task 9 (integration verification)
- **NO manual/visual acceptance criteria** — all verification is automated via pytest/tools

---

## Verification Strategy

> **ZERO HUMAN INTERVENTION** — ALL verification is agent-executed. No exceptions.

### Test Decision
- **Infrastructure exists**: YES (pytest, conftest.py with qapp fixture, 31 test files)
- **Automated tests**: Tests-after (write tests after implementation)
- **Framework**: pytest
- **Run command**: `pytest -x --tb=short`

### QA Policy
Every task MUST include agent-executed QA scenarios (see TODO template below).
Evidence is captured by piping command output to files: `command | tee .sisyphus/evidence/<filename>`.
The executing agent MUST run each QA scenario's command with `| tee <evidence-path>` appended.
Evidence saved to `.sisyphus/evidence/task-{N}-{scenario-slug}.{ext}`.

- **Backend/Pipeline**: Use Bash — run pytest, check exit codes, verify cleanup behavior
- **UI/Settings**: Use pytest with Qt fixtures — verify widget state, signal emission, config values

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Start Immediately — independent backend fixes):
├── Task 1: Bug 1 — Asyncio cleanup + client close [deep]
├── Task 2: Bug 3 — WAL/SHM file cleanup [quick]
└── Task 3: Add pynput dep + create GlobalShortcutManager [deep]

Wave 2 (After Wave 1 — settings UI changes, MAX PARALLEL):
├── Task 4: Shortcuts tab in settings [quick]
├── Task 5: Segmented controls for binary settings [quick]
└── Task 6: Remove auto-close on save + Regex validation [quick]

Wave 3 (After Tasks 3+4 — shortcut wiring + display fix):
├── Task 7: Key capture widget + wire pynput to overlay [deep]
└── Task 8: Display toggle behavior fix [quick]

Wave 4 (After ALL — verification):
└── Task 9: Full integration test + lint + type check [unspecified-high]

Wave FINAL (After ALL tasks — independent review, 4 parallel):
├── Task F1: Plan compliance audit (oracle)
├── Task F2: Code quality review (unspecified-high)
├── Task F3: Real manual QA (unspecified-high)
└── Task F4: Scope fidelity check (deep)

Critical Path: Task 3 → Task 7 → Task 9 → Final
Parallel Speedup: ~60% faster than sequential
Max Concurrent: 3 (Wave 1)
```

### Dependency Matrix

| Task | Depends On | Blocks | Wave |
|------|-----------|--------|------|
| 1 | — | 9 | 1 |
| 2 | — | 9 | 1 |
| 3 | — | 7 | 1 |
| 4 | — | 7 | 2 |
| 5 | — | 8, 9 | 2 |
| 6 | — | 9 | 2 |
| 7 | 3, 4 | 9 | 3 |
| 8 | 5 | 9 | 3 |
| 9 | 1-8 | F1-F4 | 4 |

### Agent Dispatch Summary

- **Wave 1**: **3 tasks** — T1 → `deep`, T2 → `quick`, T3 → `deep`
- **Wave 2**: **3 tasks** — T4 → `quick`, T5 → `quick`, T6 → `quick`
- **Wave 3**: **2 tasks** — T7 → `deep`, T8 → `quick`
- **Wave 4**: **1 task** — T9 → `unspecified-high`
- **FINAL**: **4 tasks** — F1 → `oracle`, F2 → `unspecified-high`, F3 → `unspecified-high`, F4 → `deep`

---

## TODOs

> Implementation + Test = ONE Task. Never separate.
> EVERY task MUST have: Recommended Agent Profile + Parallelization info + QA Scenarios.

- [ ] 1. Bug 1 — Fix asyncio task destruction and resource cleanup on shutdown

  **What to do**:
  - Add `async def close(self)` method to `AsyncOllamaClient` in `src/llm/ollama_client.py` that calls `await self._http.aclose()`. This is needed because the client is never used as an async context manager (`__aexit__` is never called).
  - In `src/pipeline/llm_worker.py` `run()` method, rewrite the `finally` block to:
    1. Cancel all pending asyncio tasks: `for task in asyncio.all_tasks(loop): task.cancel()` then `loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))`
    2. Close the LLM client: `loop.run_until_complete(self._llm_client.close())`
    3. Close the DB repo: `self._db_repo.close()` (if `self._db_repo` is not None)
    4. Then `loop.close()` as last step
  - In `src/pipeline/asr_worker.py` `run()` method, add `self._db_repo.close()` in the `finally` block (before any existing cleanup).
  - In `src/pipeline/orchestrator.py` `on_config_changed()` method, before creating a new `AsyncOllamaClient`, close the old one: create a temporary event loop, run `old_client.close()`, then close the temp loop. Or add a `close_sync()` convenience method to the client.
  - Write tests in `tests/test_llm_worker.py` and `tests/test_asr_worker.py` verifying that `close()` is called on DB repo and LLM client during shutdown.

  **Must NOT do**:
  - Do NOT change the `stop()` method order in `orchestrator.py`
  - Do NOT change queue sizes or timeout values
  - Do NOT add logging configuration changes
  - Do NOT refactor the `_process_loop()` or `_translate_one()` logic

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Asyncio lifecycle management requires careful understanding of event loop state, async generator cleanup, and thread-safe resource management. Complex multi-file change with subtle correctness requirements.
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - `playwright`: No browser interaction
    - `git-master`: Not a git operation

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 2, 3)
  - **Blocks**: Task 9
  - **Blocked By**: None (can start immediately)

  **References**:

  **Pattern References** (existing code to follow):
  - `src/pipeline/llm_worker.py:62-76` — Current `run()` method with `finally` block that needs modification. Shows the asyncio event loop lifecycle: `new_event_loop()` → `run_until_complete()` → `loop.close()`.
  - `src/pipeline/asr_worker.py:64-101` — Current `run()` method, similar pattern. Shows where to add `self._db_repo.close()` in finally block.
  - `src/llm/ollama_client.py:74-83` — Current `__aexit__` method showing `await self._http.aclose()` pattern to replicate in new `close()` method.
  - `src/pipeline/orchestrator.py:205-209` — Current `on_config_changed()` showing client replacement without closing old client.

  **API/Type References**:
  - `src/llm/ollama_client.py:50` — `self._http = httpx.AsyncClient(...)` — the httpx client that needs closing.
  - `src/db/repository.py:57-60` — `LearningRepository.close()` method signature and behavior.

  **Test References**:
  - `tests/test_llm_worker.py` — Existing worker test patterns: start→poll→stop with deadline loops, mock clients/repos.
  - `tests/test_asr_worker.py` — Existing ASR worker test patterns to follow.

  **WHY Each Reference Matters**:
  - `llm_worker.py:62-76`: This is the exact code being modified. The executor must understand the current event loop lifecycle to safely add cleanup steps.
  - `ollama_client.py:74-83`: Shows the existing `aclose()` call in `__aexit__` — the new `close()` method should mirror this.
  - `orchestrator.py:205-209`: Shows where the client leak happens — executor needs to see the exact line to add cleanup before replacement.

  **Acceptance Criteria**:

  - [ ] `AsyncOllamaClient` has a public `async def close(self)` method
  - [ ] `LlmWorker.run()` finally block cancels all pending tasks, closes LLM client, closes DB repo, then closes loop
  - [ ] `AsrWorker.run()` finally block closes DB repo
  - [ ] `orchestrator.on_config_changed()` closes old client before creating new one
  - [ ] `pytest tests/test_llm_worker.py -x --tb=short` — PASS
  - [ ] `pytest tests/test_asr_worker.py -x --tb=short` — PASS

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: LlmWorker cleanup closes DB repo and LLM client on stop
    Tool: Bash (pytest)
    Preconditions: Test file exists with mock LearningRepository and mock AsyncOllamaClient
    Steps:
      1. Run: mkdir -p .sisyphus/evidence && pytest tests/test_llm_worker.py -x --tb=short -v -k "cleanup" 2>&1 | tee .sisyphus/evidence/task-1-llm-cleanup.txt
      2. Verify test passes that asserts mock_db_repo.close() was called
      3. Verify test passes that asserts mock_llm_client.close() was awaited
    Expected Result: All cleanup-related tests PASS (exit code 0)
    Failure Indicators: AssertionError on mock.assert_called_once() for close()
    Evidence: .sisyphus/evidence/task-1-llm-cleanup.txt

  Scenario: AsrWorker cleanup closes DB repo on stop
    Tool: Bash (pytest)
    Preconditions: Test file exists with mock LearningRepository
    Steps:
      1. Run: pytest tests/test_asr_worker.py -x --tb=short -v -k "cleanup" 2>&1 | tee .sisyphus/evidence/task-1-asr-cleanup.txt
      2. Verify test passes that asserts mock_db_repo.close() was called
    Expected Result: All cleanup-related tests PASS (exit code 0)
    Failure Indicators: AssertionError on mock.assert_called_once() for close()
    Evidence: .sisyphus/evidence/task-1-asr-cleanup.txt

  Scenario: Orchestrator closes old client on config change
    Tool: Bash (pytest)
    Preconditions: Test with mock AsyncOllamaClient that tracks close() calls
    Steps:
      1. Run: pytest tests/test_orchestrator.py -x --tb=short -v -k "config_change_closes_old_client" 2>&1 | tee .sisyphus/evidence/task-1-orchestrator-cleanup.txt
      2. Verify old client's close() was called before new client was created
    Expected Result: Test PASS (exit code 0)
    Failure Indicators: close() not called on old client mock
    Evidence: .sisyphus/evidence/task-1-orchestrator-cleanup.txt
  ```

  **Evidence to Capture:**
  - [ ] task-1-llm-cleanup.txt — pytest output for LlmWorker cleanup tests
  - [ ] task-1-asr-cleanup.txt — pytest output for AsrWorker cleanup tests
  - [ ] task-1-orchestrator-cleanup.txt — pytest output for orchestrator client lifecycle test

  **Commit**: YES
  - Message: `fix(pipeline): clean up asyncio tasks, httpx client, and DB connections on shutdown`
  - Files: `src/llm/ollama_client.py`, `src/pipeline/llm_worker.py`, `src/pipeline/asr_worker.py`, `src/pipeline/orchestrator.py`, `tests/test_llm_worker.py`, `tests/test_asr_worker.py`, `tests/test_orchestrator.py`
  - Pre-commit: `pytest -x --tb=short`

- [ ] 2. Bug 3 — Fix WAL/SHM file persistence by closing all SQLite connections

  **What to do**:
  - In `src/ui/learning_panel.py`, override `closeEvent(self, event: QCloseEvent)` to call `self._conn.close()` before `super().closeEvent(event)`.
  - In `src/main.py` `_cleanup()` function:
    1. Add `conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")` before `conn.close()` to force WAL data into the main DB file.
    2. If `_learning_panel` exists and is not None, call `_learning_panel.close()` (which triggers `closeEvent` → `_conn.close()`).
  - Write tests:
    - `tests/test_learning_panel.py`: Test that `closeEvent` closes the DB connection (mock `_conn.close()` and simulate close event).
    - Update/add test in `tests/test_main.py` (or appropriate test file) verifying WAL checkpoint is called in `_cleanup()`.

  **Must NOT do**:
  - Do NOT change the DB schema or WAL mode setting
  - Do NOT touch worker DB connections (already handled in Task 1)
  - Do NOT add connection pooling or change the connection architecture

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Small, well-scoped changes to 2-3 files. Adding closeEvent + WAL checkpoint is straightforward.
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 3)
  - **Blocks**: Task 9
  - **Blocked By**: None (can start immediately)

  **References**:

  **Pattern References**:
  - `src/ui/learning_panel.py:54-59` — Current `__init__` showing `self._conn = init_db(...)` connection creation with no cleanup counterpart.
  - `src/main.py:30-45` — Current `_cleanup()` function showing existing cleanup pattern to extend.
  - `src/main.py:149-156` — `_open_learning_panel()` showing lazy creation of the panel — need to track this reference for cleanup.

  **API/Type References**:
  - `src/db/schema.py:init_db()` — Returns `sqlite3.Connection` with WAL mode enabled.
  - `src/db/repository.py:57-60` — `LearningRepository.close()` method.

  **WHY Each Reference Matters**:
  - `learning_panel.py:54-59`: Executor needs to see exactly how the connection is stored to write correct cleanup.
  - `main.py:30-45`: Shows where to add WAL checkpoint — must go before `conn.close()`.
  - `main.py:149-156`: Shows the `_learning_panel` variable reference needed for cleanup in `_cleanup()`.

  **Acceptance Criteria**:

  - [ ] `LearningPanel.closeEvent()` calls `self._conn.close()`
  - [ ] `_cleanup()` executes `PRAGMA wal_checkpoint(TRUNCATE)` before `conn.close()`
  - [ ] `_cleanup()` closes the learning panel if it exists
  - [ ] `pytest tests/test_learning_panel.py -x --tb=short` — PASS

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: LearningPanel closeEvent closes DB connection
    Tool: Bash (pytest)
    Preconditions: Test with mock init_db returning mock connection
    Steps:
      1. Run: mkdir -p .sisyphus/evidence && pytest tests/test_learning_panel.py -x --tb=short -v -k "close_event" 2>&1 | tee .sisyphus/evidence/task-2-learning-panel-close.txt
      2. Verify test creates panel, simulates QCloseEvent, asserts conn.close() called
    Expected Result: Test PASS (exit code 0)
    Failure Indicators: conn.close() not called on closeEvent
    Evidence: .sisyphus/evidence/task-2-learning-panel-close.txt

  Scenario: Cleanup function performs WAL checkpoint
    Tool: Bash (pytest)
    Preconditions: Test with mock connection tracking execute() calls
    Steps:
      1. Run: pytest -x --tb=short -v -k "wal_checkpoint" 2>&1 | tee .sisyphus/evidence/task-2-wal-checkpoint.txt
      2. Verify conn.execute was called with "PRAGMA wal_checkpoint(TRUNCATE)"
    Expected Result: Test PASS (exit code 0)
    Failure Indicators: PRAGMA not executed before conn.close()
    Evidence: .sisyphus/evidence/task-2-wal-checkpoint.txt
  ```

  **Evidence to Capture:**
  - [ ] task-2-learning-panel-close.txt — pytest output
  - [ ] task-2-wal-checkpoint.txt — pytest output

  **Commit**: YES
  - Message: `fix(db): close all SQLite connections and checkpoint WAL on exit`
  - Files: `src/ui/learning_panel.py`, `src/main.py`, `tests/test_learning_panel.py`
  - Pre-commit: `pytest -x --tb=short`

- [ ] 3. Create GlobalShortcutManager with pynput + add pynput dependency

  **What to do**:
  - Add `pynput` to `requirements.txt`.
  - Create new file `src/ui/shortcuts.py` containing `GlobalShortcutManager(QObject)`:
    - Signals: `toggle_display_triggered = Signal()`, `prev_sentence_triggered = Signal()`, `next_sentence_triggered = Signal()`
    - Constructor takes shortcut config strings (Qt-style like "Ctrl+Left")
    - Internal converter function `_qt_key_to_pynput(key_string: str)` that maps Qt-style key strings to pynput key combinations (e.g., "Ctrl+Left" → `{keyboard.Key.ctrl, keyboard.Key.left}`)
    - Uses `pynput.keyboard.GlobalHotKeys` (or `Listener` with manual combo tracking) with `suppress=False` (pass-through)
    - All pynput callbacks emit Qt Signals via `QMetaObject.invokeMethod(self, "_emit_<signal>", Qt.QueuedConnection)` — **CRITICAL**: never call Qt methods directly from pynput thread
    - `start()` method: starts the pynput listener thread
    - `stop()` method: stops the pynput listener thread, joins it
    - `update_shortcuts(config)` method: stop current listener, update key mappings, restart
  - Write tests in `tests/test_shortcuts.py`:
    - Test key string conversion function
    - Test that start/stop lifecycle works without crash
    - Test that signals are defined correctly (can be connected)
    - Mock `pynput.keyboard.GlobalHotKeys` to avoid actual system hooks in CI

  **Must NOT do**:
  - Do NOT wire this to the overlay yet (that's Task 7)
  - Do NOT add to settings UI yet (that's Task 4 + 7)
  - Do NOT change `AppConfig` field types — keep Qt-style strings
  - Do NOT use `suppress=True` — hotkeys must pass through to other apps

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Thread-safe integration between pynput (background thread) and Qt (main thread) requires careful signal bridging. Key format conversion needs comprehensive mapping. New module creation.
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2)
  - **Blocks**: Task 7
  - **Blocked By**: None (can start immediately)

  **References**:

  **Pattern References**:
  - `src/ui/overlay.py:153-169` — Current `_bind_shortcuts()` showing the Qt-style key strings used in config (e.g., "Ctrl+Left", "Ctrl+Right", "Ctrl+T"). The new module must accept these same strings.
  - `src/config.py` — `AppConfig.shortcut_prev_sentence`, `shortcut_next_sentence`, `shortcut_toggle_display` fields — these are the config values that will be fed to GlobalShortcutManager.

  **External References**:
  - pynput docs: `pynput.keyboard.GlobalHotKeys` — for hotkey combination format and listener lifecycle.
  - pynput docs: `pynput.keyboard.Key` — for special key constants (ctrl, shift, left, right, etc.).

  **WHY Each Reference Matters**:
  - `overlay.py:153-169`: Shows the exact key string format currently in use — the converter must handle these.
  - `config.py`: Shows the field types and defaults — GlobalShortcutManager must accept these without requiring format changes.

  **Acceptance Criteria**:

  - [ ] `src/ui/shortcuts.py` exists with `GlobalShortcutManager(QObject)` class
  - [ ] `_qt_key_to_pynput()` correctly maps "Ctrl+Left", "Ctrl+Right", "Ctrl+T" and similar combos
  - [ ] Signals: `toggle_display_triggered`, `prev_sentence_triggered`, `next_sentence_triggered` exist
  - [ ] `start()`, `stop()`, `update_shortcuts()` methods exist and work
  - [ ] pynput callbacks use `QMetaObject.invokeMethod` with `Qt.QueuedConnection` (NOT direct method calls)
  - [ ] `pynput` added to `requirements.txt`
  - [ ] `pytest tests/test_shortcuts.py -x --tb=short` — PASS

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Key string conversion handles common Qt-style shortcuts
    Tool: Bash (pytest)
    Preconditions: Test file imports _qt_key_to_pynput from src.ui.shortcuts
    Steps:
      1. Run: mkdir -p .sisyphus/evidence && pytest tests/test_shortcuts.py -x --tb=short -v -k "key_conversion" 2>&1 | tee .sisyphus/evidence/task-3-key-conversion.txt
      2. Verify conversions: "Ctrl+Left" → correct pynput combo, "Ctrl+T" → correct combo
      3. Verify edge cases: single keys, modifier-only, unknown keys
    Expected Result: All conversion tests PASS (exit code 0)
    Failure Indicators: Wrong pynput key mapping for any standard Qt key string
    Evidence: .sisyphus/evidence/task-3-key-conversion.txt

  Scenario: GlobalShortcutManager start/stop lifecycle
    Tool: Bash (pytest)
    Preconditions: Mock pynput.keyboard.GlobalHotKeys to avoid system hooks
    Steps:
      1. Run: pytest tests/test_shortcuts.py -x --tb=short -v -k "lifecycle" 2>&1 | tee .sisyphus/evidence/task-3-lifecycle.txt
      2. Verify start() creates and starts listener, stop() stops and joins it
      3. Verify no crash on double-start or double-stop
    Expected Result: Lifecycle tests PASS (exit code 0)
    Failure Indicators: Thread not stopped, listener not created, crash on cleanup
    Evidence: .sisyphus/evidence/task-3-lifecycle.txt

  Scenario: Signal emission is thread-safe
    Tool: Bash (pytest)
    Preconditions: Mock pynput listener, Qt app fixture from conftest
    Steps:
      1. Run: pytest tests/test_shortcuts.py -x --tb=short -v -k "signal" 2>&1 | tee .sisyphus/evidence/task-3-signals.txt
      2. Verify that signals are emitted correctly when pynput callback fires
    Expected Result: Signal tests PASS (exit code 0)
    Failure Indicators: Signal not received, wrong signal emitted, Qt thread crash
    Evidence: .sisyphus/evidence/task-3-signals.txt
  ```

  **Evidence to Capture:**
  - [ ] task-3-key-conversion.txt — pytest output for key conversion tests
  - [ ] task-3-lifecycle.txt — pytest output for start/stop lifecycle tests
  - [ ] task-3-signals.txt — pytest output for signal emission tests

  **Commit**: YES (groups with Task 7 — committed together as shortcut overhaul, or committed separately as foundation)
  - Message: `feat(shortcuts): add GlobalShortcutManager with pynput for system-wide hotkeys`
  - Files: `requirements.txt`, `src/ui/shortcuts.py`, `tests/test_shortcuts.py`
  - Pre-commit: `pytest -x --tb=short`

- [ ] 4. Improvement 4 — Move shortcuts to dedicated Shortcuts tab in settings

  **What to do**:
  - In `src/ui/settings.py`, create a new method `_build_shortcuts_tab(self) -> QWidget` that returns the shortcuts form layout.
  - Move the 3 shortcut fields (`_shortcut_prev_edit`, `_shortcut_next_edit`, `_shortcut_toggle_edit`) from `_build_appearance_tab()` to the new `_build_shortcuts_tab()`.
  - Add the new tab to `self._tabs` as the 5th tab: `self._tabs.addTab(self._build_shortcuts_tab(), "Shortcuts")`.
  - Keep the same field names and widget types (for now — Task 7 will replace with key capture widgets).
  - Remove the shortcut-related rows from `_build_appearance_tab()`.
  - Update `tests/test_settings.py`:
    - Change the test asserting tab count from 4 → 5.
    - Add test verifying shortcuts are in the correct tab (tab index 4).
    - Verify shortcut field values are still correctly populated from config and collected on save.

  **Must NOT do**:
  - Do NOT change the widget types for shortcuts yet (Task 7 does that)
  - Do NOT add new config fields
  - Do NOT change any other tab's content

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Moving existing widgets from one tab to another. Straightforward UI reorganization.
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 5, 6, 7)
  - **Blocks**: Task 7
  - **Blocked By**: None

  **References**:

  **Pattern References**:
  - `src/ui/settings.py:115-158` — Current `_build_appearance_tab()` containing the shortcut QLineEdit fields to be extracted.
  - `src/ui/settings.py:44-54` — Tab setup in `__init__` showing how tabs are added: `self._tabs.addTab(self._build_*_tab(), "TabName")`.
  - `src/ui/settings.py:270-288` — `_populate_from_config()` showing how shortcut values are set into widgets — must still work after move.
  - `src/ui/settings.py:310-332` — `_collect_config()` showing how shortcut values are read from widgets — must still work after move.

  **Test References**:
  - `tests/test_settings.py:25` — Current assertion `assert dialog._tabs.count() == 4` — must change to 5.

  **WHY Each Reference Matters**:
  - `settings.py:115-158`: The exact code to move — executor must identify which lines are shortcut-related vs appearance-related.
  - `settings.py:44-54`: Shows the pattern for adding tabs — executor must insert the new tab in the right position.
  - `settings.py:270-332`: Both populate and collect functions must still find the widgets after the move.

  **Acceptance Criteria**:

  - [ ] Settings dialog has 5 tabs: General, Appearance, Model, Templates, Shortcuts
  - [ ] Shortcut fields appear in the Shortcuts tab
  - [ ] Shortcut fields no longer appear in the Appearance tab
  - [ ] `_populate_from_config()` still correctly populates shortcut fields
  - [ ] `_collect_config()` still correctly reads shortcut values
  - [ ] `pytest tests/test_settings.py -x --tb=short` — PASS

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Settings dialog has 5 tabs with correct names
    Tool: Bash (pytest)
    Preconditions: SettingsDialog instantiated with default AppConfig
    Steps:
      1. Run: mkdir -p .sisyphus/evidence && pytest tests/test_settings.py -x --tb=short -v -k "tabs" 2>&1 | tee .sisyphus/evidence/task-4-tabs.txt
      2. Assert dialog._tabs.count() == 5
      3. Assert tab labels are: "General", "Appearance", "Model", "Templates", "Shortcuts"
    Expected Result: Tab count and names correct (exit code 0)
    Failure Indicators: Count != 5 or wrong tab label
    Evidence: .sisyphus/evidence/task-4-tabs.txt

  Scenario: Shortcut fields populate and collect correctly in new tab
    Tool: Bash (pytest)
    Preconditions: Config with custom shortcut values
    Steps:
      1. Run: pytest tests/test_settings.py -x --tb=short -v -k "shortcut" 2>&1 | tee .sisyphus/evidence/task-4-shortcuts-roundtrip.txt
      2. Assert shortcut fields contain config values after populate
      3. Assert _collect_config() returns correct shortcut values
    Expected Result: Shortcut round-trip works (exit code 0)
    Failure Indicators: Field values empty or wrong after populate/collect
    Evidence: .sisyphus/evidence/task-4-shortcuts-roundtrip.txt
  ```

  **Evidence to Capture:**
  - [ ] task-4-tabs.txt
  - [ ] task-4-shortcuts-roundtrip.txt

  **Commit**: YES
  - Message: `feat(settings): add dedicated Shortcuts tab`
  - Files: `src/ui/settings.py`, `tests/test_settings.py`
  - Pre-commit: `pytest -x --tb=short`

- [ ] 5. Improvement 6 — Replace dropdowns with segmented controls for binary settings

  **What to do**:
  - In `src/ui/settings.py`, replace `QComboBox` for LLM Mode and Display Mode with segmented controls:
    - Create a helper function or inline code: two `QPushButton` widgets in a `QHBoxLayout`, styled so the active button has a highlighted background (use QSS `setStyleSheet`).
    - For **LLM Mode** (in `_build_general_tab()`): Replace `_llm_mode_combo` with two buttons "Translation" / "Explanation". Track active state in `_llm_mode_value: str`.
    - For **Display Mode** (in `_build_appearance_tab()`): Replace `_display_mode_combo` with two buttons "Both" / "Single". Track active state in `_display_mode_value: str`.
    - On button click: update `_*_value` and toggle button styles (active = highlighted, inactive = default).
  - Update `_populate_from_config()` to set the correct active button based on config value.
  - Update `_collect_config()` to read from `_*_value` instead of `QComboBox.currentText()`.
  - Write tests:
    - Test that clicking a segment button updates the tracked value.
    - Test that `_collect_config()` returns the correct value after button click.
    - Test that `_populate_from_config()` sets the correct active button.

  **Must NOT do**:
  - Do NOT create an abstract `SegmentedControl` class or generic widget — keep it inline
  - Do NOT change the config field types (still `Literal["translation", "explanation"]` and `Literal["both", "single"]`)
  - Do NOT add new config fields

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Replacing QComboBox with styled QPushButtons. Simple widget swap with stylesheet toggling.
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 4, 6, 7)
  - **Blocks**: Task 9
  - **Blocked By**: None

  **References**:

  **Pattern References**:
  - `src/ui/settings.py:91-93` — Current `_llm_mode_combo = QComboBox()` with `addItems(["translation", "explanation"])` — replace this.
  - `src/ui/settings.py:142-144` — Current `_display_mode_combo = QComboBox()` with `addItems(["both", "single"])` — replace this.
  - `src/ui/settings.py:270-288` — `_populate_from_config()` — update `setCurrentText` calls to button activation.
  - `src/ui/settings.py:310-332` — `_collect_config()` — update `currentText()` reads to `_*_value` reads.

  **Test References**:
  - `tests/test_settings.py` — Existing settings tests for widget state verification patterns.

  **WHY Each Reference Matters**:
  - Lines 91-93 and 142-144 are the exact widgets to replace — executor must see the current QComboBox pattern.
  - Lines 270-332 show populate/collect methods that must be updated to use the new button state tracking.

  **Acceptance Criteria**:

  - [ ] LLM Mode uses two QPushButtons ("Translation" / "Explanation") instead of QComboBox
  - [ ] Display Mode uses two QPushButtons ("Both" / "Single") instead of QComboBox
  - [ ] Active button is visually distinct (highlighted via QSS)
  - [ ] `_collect_config()` returns correct values from segmented controls
  - [ ] `_populate_from_config()` activates correct button based on config
  - [ ] `pytest tests/test_settings.py -x --tb=short` — PASS

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Segmented control for LLM Mode toggles correctly
    Tool: Bash (pytest)
    Preconditions: SettingsDialog instantiated with default config (llm_mode="translation")
    Steps:
      1. Run: mkdir -p .sisyphus/evidence && pytest tests/test_settings.py -x --tb=short -v -k "segmented_llm" 2>&1 | tee .sisyphus/evidence/task-5-segmented-llm.txt
      2. Assert initial state: "Translation" button is active
      3. Simulate click on "Explanation" button
      4. Assert _collect_config().llm_mode == "explanation"
    Expected Result: Mode switches correctly (exit code 0)
    Failure Indicators: Wrong value from _collect_config() or button state not updated
    Evidence: .sisyphus/evidence/task-5-segmented-llm.txt

  Scenario: Segmented control for Display Mode toggles correctly
    Tool: Bash (pytest)
    Preconditions: SettingsDialog with config (overlay_display_mode="both")
    Steps:
      1. Run: pytest tests/test_settings.py -x --tb=short -v -k "segmented_display" 2>&1 | tee .sisyphus/evidence/task-5-segmented-display.txt
      2. Assert initial state: "Both" button is active
      3. Simulate click on "Single" button
      4. Assert _collect_config().overlay_display_mode == "single"
    Expected Result: Mode switches correctly (exit code 0)
    Evidence: .sisyphus/evidence/task-5-segmented-display.txt
  ```

  **Evidence to Capture:**
  - [ ] task-5-segmented-llm.txt
  - [ ] task-5-segmented-display.txt

  **Commit**: YES
  - Message: `feat(settings): replace dropdowns with segmented controls for binary settings`
  - Files: `src/ui/settings.py`, `tests/test_settings.py`
  - Pre-commit: `pytest -x --tb=short`

- [ ] 6. Improvement 7 — Remove auto-close on save + Improvement 8 — Add regex validation

  **What to do**:
  - **Remove auto-close**: In `src/ui/settings.py` `_on_save()` method, remove the `self.close()` call at the end. The dialog should remain open after saving.
  - **Regex validation**: In `_on_save()`, before calling `save_config()`:
    1. Get the parse format text: `parse_fmt = self._llm_parse_format_edit.text().strip()`
    2. If `parse_fmt` is not empty, try `re.compile(parse_fmt)`.
    3. If `re.error` is raised, show a red "Invalid Regex!" label below the parse format field and **return early** (do NOT save).
    4. If valid or empty, hide the error label.
  - Add a `_regex_error_label = QLabel("Invalid Regex!")` in the Model tab, styled with red text (`setStyleSheet("color: red;")`), initially hidden (`setVisible(False)`). Place it directly below `_llm_parse_format_edit`.
  - Write tests:
    - Test that `_on_save()` does NOT close the dialog.
    - Test that invalid regex shows the error label and prevents save.
    - Test that valid regex hides the error label and allows save.
    - Test that empty regex allows save (no validation needed for empty).

  **Must NOT do**:
  - Do NOT change how `save_config()` works
  - Do NOT add regex validation anywhere outside the settings dialog
  - Do NOT change the `config_changed` signal behavior

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Small focused changes — remove one line + add validation logic and an error label. Well-scoped.
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 4, 5, 7)
  - **Blocks**: Task 9
  - **Blocked By**: None

  **References**:

  **Pattern References**:
  - `src/ui/settings.py:334-339` — Current `_on_save()` showing `self.close()` call to remove, and the save flow to add validation to.
  - `src/ui/settings.py:220-224` — `_llm_parse_format_edit` QLineEdit in Model tab — add the error label below this.

  **Test References**:
  - `tests/test_settings.py` — Existing test patterns using `mock.patch("src.ui.settings.save_config")`.

  **WHY Each Reference Matters**:
  - Line 334-339: The exact method being modified — executor must see what's there to know what to remove and where to add validation.
  - Line 220-224: Shows where the regex field is in the Model tab layout — error label goes right after this.

  **Acceptance Criteria**:

  - [ ] `_on_save()` does NOT call `self.close()` — dialog stays open after save
  - [ ] Invalid regex in parse format shows red "Invalid Regex!" label and prevents save
  - [ ] Valid regex hides error label and allows save
  - [ ] Empty parse format allows save (no validation)
  - [ ] `config_changed` signal is NOT emitted when regex is invalid
  - [ ] `pytest tests/test_settings.py -x --tb=short` — PASS

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Save does not close dialog
    Tool: Bash (pytest)
    Preconditions: SettingsDialog with mocked save_config
    Steps:
      1. Run: mkdir -p .sisyphus/evidence && pytest tests/test_settings.py -x --tb=short -v -k "save_not_close" 2>&1 | tee .sisyphus/evidence/task-6-save-no-close.txt
      2. Call _on_save(), assert dialog.isVisible() is True after save
    Expected Result: Dialog remains visible (exit code 0)
    Failure Indicators: dialog.isVisible() returns False
    Evidence: .sisyphus/evidence/task-6-save-no-close.txt

  Scenario: Invalid regex shows error and prevents save
    Tool: Bash (pytest)
    Preconditions: SettingsDialog with parse format set to "[invalid"
    Steps:
      1. Run: pytest tests/test_settings.py -x --tb=short -v -k "invalid_regex" 2>&1 | tee .sisyphus/evidence/task-6-invalid-regex.txt
      2. Set _llm_parse_format_edit.setText("[invalid")
      3. Call _on_save()
      4. Assert _regex_error_label.isVisible() is True
      5. Assert save_config was NOT called
      6. Assert config_changed signal was NOT emitted
    Expected Result: Error shown, save blocked (exit code 0)
    Failure Indicators: Error label not visible, or save_config was called
    Evidence: .sisyphus/evidence/task-6-invalid-regex.txt

  Scenario: Valid regex allows save and hides error
    Tool: Bash (pytest)
    Preconditions: SettingsDialog with parse format set to "(?P<jp>.+?)\\n(?P<cn>.+)"
    Steps:
      1. Run: pytest tests/test_settings.py -x --tb=short -v -k "valid_regex" 2>&1 | tee .sisyphus/evidence/task-6-valid-regex.txt
      2. Set valid regex, call _on_save()
      3. Assert _regex_error_label.isVisible() is False
      4. Assert save_config WAS called
    Expected Result: Save proceeds, no error (exit code 0)
    Evidence: .sisyphus/evidence/task-6-valid-regex.txt
  ```

  **Evidence to Capture:**
  - [ ] task-6-save-no-close.txt
  - [ ] task-6-invalid-regex.txt
  - [ ] task-6-valid-regex.txt

  **Commit**: YES
  - Message: `fix(settings): remove auto-close on save, add regex validation for parse format`
  - Files: `src/ui/settings.py`, `tests/test_settings.py`
  - Pre-commit: `pytest -x --tb=short`

- [ ] 7. Improvement 5 + Bug 2 — Key capture widget in settings + wire pynput to overlay

  **What to do**:
  - **Key capture widget in Shortcuts tab**: In `src/ui/settings.py`, replace the 3 shortcut `QLineEdit` widgets (now in the Shortcuts tab from Task 4) with `QKeySequenceEdit` widgets:
    - `_shortcut_prev_edit = QKeySequenceEdit()` (replaces QLineEdit)
    - `_shortcut_next_edit = QKeySequenceEdit()` (replaces QLineEdit)
    - `_shortcut_toggle_edit = QKeySequenceEdit()` (replaces QLineEdit)
    - `QKeySequenceEdit` natively captures key combinations when focused — user presses the desired key combo and it records it.
    - Update `_populate_from_config()`: Convert config string (e.g., "Ctrl+Left") to `QKeySequence` and set on the widget via `setKeySequence()`.
    - Update `_collect_config()`: Read from `keySequence().toString()` to get the Qt-style key string back for config storage.
  - **Wire pynput to overlay**: In `src/ui/overlay.py`:
    - Import `GlobalShortcutManager` from `src.ui.shortcuts`.
    - In `__init__`, create `self._shortcut_mgr = GlobalShortcutManager(config)`.
    - Connect signals: `_shortcut_mgr.toggle_display_triggered.connect(self._toggle_mode)`, `_shortcut_mgr.prev_sentence_triggered.connect(self._prev_sentence)`, `_shortcut_mgr.next_sentence_triggered.connect(self._next_sentence)`.
    - Call `self._shortcut_mgr.start()` in `__init__`.
    - Remove the old `_bind_shortcuts()` method and all `QShortcut` usage. Remove `QShortcut` and `QKeySequence` imports if no longer needed.
    - In `on_config_changed()`: call `self._shortcut_mgr.update_shortcuts(config)` instead of `_bind_shortcuts()`.
    - Add cleanup: in a new `closeEvent()` or connect to `destroyed` signal, call `self._shortcut_mgr.stop()`.
  - Update tests:
    - `tests/test_settings.py`: Update shortcut-related tests to work with `QKeySequenceEdit` instead of `QLineEdit`.
    - `tests/test_overlay.py`: Remove tests that assert `QShortcut` creation. Add tests that verify `GlobalShortcutManager` is created, started, signals connected, and stopped on cleanup.

  **Must NOT do**:
  - Do NOT change `AppConfig` field types — shortcut values remain as `str` type
  - Do NOT add new config fields
  - Do NOT change the shortcut manager's internal implementation (done in Task 3)
  - Do NOT change `_toggle_mode()`, `_prev_sentence()`, or `_next_sentence()` logic

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Multi-file change touching settings UI, overlay, and test updates. Requires understanding widget replacement, signal wiring, and test adaptation. Largest single task in the plan.
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Task 9)
  - **Parallel Group**: Wave 3 (with Task 9)
  - **Blocks**: Task 9
  - **Blocked By**: Task 3 (GlobalShortcutManager must exist), Task 4 (Shortcuts tab must exist)

  **References**:

  **Pattern References**:
  - `src/ui/settings.py:146-156` (in Shortcuts tab after Task 4) — Current shortcut QLineEdit widgets to replace with QKeySequenceEdit.
  - `src/ui/settings.py:270-288` — `_populate_from_config()` — update to use `setKeySequence(QKeySequence(value))`.
  - `src/ui/settings.py:310-332` — `_collect_config()` — update to use `.keySequence().toString()`.
  - `src/ui/overlay.py:153-169` — Current `_bind_shortcuts()` to remove entirely.
  - `src/ui/overlay.py:246` — `on_config_changed()` calling `_bind_shortcuts()` — replace with `_shortcut_mgr.update_shortcuts()`.
  - `src/ui/shortcuts.py` (from Task 3) — `GlobalShortcutManager` class to instantiate and wire.

  **Test References**:
  - `tests/test_overlay.py:518-524` — Existing shortcut rebinding tests that must be rewritten for pynput.
  - `tests/test_settings.py` — Shortcut field tests to update for QKeySequenceEdit.

  **WHY Each Reference Matters**:
  - Settings lines 146-156: Exact widgets being replaced — executor must know current field names and layout position.
  - Overlay lines 153-169: Code being removed — executor must understand what to delete and what to replace it with.
  - Overlay line 246: Config change handler — must be updated to call new API.

  **Acceptance Criteria**:

  - [ ] Shortcut fields in settings use `QKeySequenceEdit` (not QLineEdit)
  - [ ] `_populate_from_config()` correctly sets key sequences from config strings
  - [ ] `_collect_config()` correctly reads key sequences back to config strings
  - [ ] Overlay creates and starts `GlobalShortcutManager` in `__init__`
  - [ ] Overlay connects all 3 shortcut signals to their handlers
  - [ ] Old `_bind_shortcuts()` removed, no `QShortcut` usage in overlay
  - [ ] `on_config_changed()` calls `_shortcut_mgr.update_shortcuts()`
  - [ ] `GlobalShortcutManager.stop()` called on overlay close/destroy
  - [ ] `pytest tests/test_overlay.py -x --tb=short` — PASS
  - [ ] `pytest tests/test_settings.py -x --tb=short` — PASS

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Settings shortcut fields use QKeySequenceEdit and round-trip config values
    Tool: Bash (pytest)
    Preconditions: SettingsDialog with config shortcut_prev_sentence="Ctrl+Left"
    Steps:
      1. Run: mkdir -p .sisyphus/evidence && pytest tests/test_settings.py -x --tb=short -v -k "key_sequence" 2>&1 | tee .sisyphus/evidence/task-7-key-sequence-roundtrip.txt
      2. Assert shortcut widget is QKeySequenceEdit (not QLineEdit)
      3. Assert populated key sequence matches config string
      4. Assert _collect_config() returns same config string
    Expected Result: Round-trip works correctly (exit code 0)
    Failure Indicators: Widget type wrong, key sequence empty, wrong string from collect
    Evidence: .sisyphus/evidence/task-7-key-sequence-roundtrip.txt

  Scenario: Overlay uses GlobalShortcutManager instead of QShortcut
    Tool: Bash (pytest)
    Preconditions: Overlay with mocked GlobalShortcutManager
    Steps:
      1. Run: pytest tests/test_overlay.py -x --tb=short -v -k "global_shortcut" 2>&1 | tee .sisyphus/evidence/task-7-overlay-shortcuts.txt
      2. Assert GlobalShortcutManager was instantiated
      3. Assert start() was called
      4. Assert signals are connected to _toggle_mode, _prev_sentence, _next_sentence
    Expected Result: Shortcut manager correctly wired (exit code 0)
    Failure Indicators: Manager not created, signals not connected
    Evidence: .sisyphus/evidence/task-7-overlay-shortcuts.txt

  Scenario: No QShortcut references remain in overlay
    Tool: Bash (grep)
    Preconditions: None
    Steps:
      1. Run: grep -c "QShortcut" src/ui/overlay.py 2>&1 | tee .sisyphus/evidence/task-7-no-qshortcut.txt
      2. Assert output is "0" (no matches)
    Expected Result: No QShortcut usage in overlay.py
    Failure Indicators: Any non-zero count
    Evidence: .sisyphus/evidence/task-7-no-qshortcut.txt
  ```

  **Evidence to Capture:**
  - [ ] task-7-key-sequence-roundtrip.txt
  - [ ] task-7-overlay-shortcuts.txt
  - [ ] task-7-no-qshortcut.txt

  **Commit**: YES
  - Message: `feat(shortcuts): global hotkeys via pynput with key capture widget in settings`
  - Files: `src/ui/overlay.py`, `src/ui/settings.py`, `tests/test_overlay.py`, `tests/test_settings.py`
  - Pre-commit: `pytest -x --tb=short`

- [ ] 8. Improvement 9 — Display toggle shortcut only cycles jp/cn in "single" mode

  **What to do**:
  - In `src/ui/overlay.py` `_toggle_mode()` method:
    - Add an early return guard: `if self._display_mode == "both": return` as the first line.
    - The remaining logic should only cycle between sub-modes: `jp → cn → jp → ...` when `_display_mode == "single"`.
    - Simplify: When in "single" mode, toggle `_single_sub_mode` between "jp" and "cn", then call `_apply_display_mode()`.
    - Remove the `both → single` and `single → both` transitions.
  - Update tests in `tests/test_overlay.py`:
    - Test that `_toggle_mode()` does nothing when `_display_mode == "both"`.
    - Test that `_toggle_mode()` cycles `jp → cn → jp` when `_display_mode == "single"`.
    - Update any existing toggle tests that expected the old `both → single → both` cycle.

  **Must NOT do**:
  - Do NOT change `_apply_display_mode()` logic
  - Do NOT change how `_display_mode` is set from config
  - Do NOT add new config fields or change existing ones
  - Do NOT change `_prev_sentence()` or `_next_sentence()` behavior

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Small logic change in one method + test updates. Clear requirements with well-defined behavior.
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Task 8)
  - **Parallel Group**: Wave 3 (with Task 8)
  - **Blocks**: Task 9
  - **Blocked By**: Task 5 (segmented control must exist so display_mode can be set to "both" or "single" correctly in tests)

  **References**:

  **Pattern References**:
  - `src/ui/overlay.py:290-304` — Current `_toggle_mode()` showing the full cycle `both → single/jp → single/cn → both` to be simplified.
  - `src/ui/overlay.py:171-177` — `_apply_display_mode()` showing how mode is applied to show/hide browsers — this is NOT changed but is called by `_toggle_mode()`.

  **Test References**:
  - `tests/test_overlay.py` — Existing toggle mode tests that test the old cycle behavior — must be updated.

  **WHY Each Reference Matters**:
  - Lines 290-304: The exact method being changed — executor must understand the current cycle to correctly simplify it.
  - Lines 171-177: Executor needs to understand `_apply_display_mode()` to verify the toggle still calls it correctly.

  **Acceptance Criteria**:

  - [ ] `_toggle_mode()` does nothing (returns immediately) when `_display_mode == "both"`
  - [ ] `_toggle_mode()` cycles `jp → cn → jp` when `_display_mode == "single"`
  - [ ] `_toggle_mode()` never changes `_display_mode` itself (no transition to/from "both")
  - [ ] `_apply_display_mode()` is called after each cycle step
  - [ ] `pytest tests/test_overlay.py -x --tb=short` — PASS

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Toggle mode does nothing when display mode is "both"
    Tool: Bash (pytest)
    Preconditions: Overlay with _display_mode="both"
    Steps:
      1. Run: mkdir -p .sisyphus/evidence && pytest tests/test_overlay.py -x --tb=short -v -k "toggle_noop_both" 2>&1 | tee .sisyphus/evidence/task-8-toggle-noop.txt
      2. Set overlay._display_mode = "both"
      3. Call overlay._toggle_mode()
      4. Assert overlay._display_mode == "both" (unchanged)
    Expected Result: No mode change (exit code 0)
    Failure Indicators: _display_mode changed from "both"
    Evidence: .sisyphus/evidence/task-8-toggle-noop.txt

  Scenario: Toggle mode cycles jp→cn→jp in single mode
    Tool: Bash (pytest)
    Preconditions: Overlay with _display_mode="single", _single_sub_mode="jp"
    Steps:
      1. Run: pytest tests/test_overlay.py -x --tb=short -v -k "toggle_cycle_single" 2>&1 | tee .sisyphus/evidence/task-8-toggle-cycle.txt
      2. Set _display_mode="single", _single_sub_mode="jp"
      3. Call _toggle_mode() → assert _single_sub_mode == "cn"
      4. Call _toggle_mode() → assert _single_sub_mode == "jp"
      5. Assert _display_mode is still "single" throughout
    Expected Result: Correct jp↔cn cycling (exit code 0)
    Failure Indicators: Wrong sub_mode or display_mode changed
    Evidence: .sisyphus/evidence/task-8-toggle-cycle.txt
  ```

  **Evidence to Capture:**
  - [ ] task-8-toggle-noop.txt
  - [ ] task-8-toggle-cycle.txt

  **Commit**: YES
  - Message: `fix(overlay): toggle display shortcut only cycles jp/cn in single mode`
  - Files: `src/ui/overlay.py`, `tests/test_overlay.py`
  - Pre-commit: `pytest -x --tb=short`

- [ ] 9. Full integration verification — lint, type check, full test suite

  **What to do**:
  - Run `ruff check .` — fix any lint errors introduced by Tasks 1-9.
  - Run `ruff format --check .` — fix any formatting issues.
  - Run `mypy .` — fix any new type errors (ignore pre-existing ones like fugashi Tagger).
  - Run `pytest -x --tb=short` — ensure ALL tests pass including pre-existing tests.
  - Verify no regressions in existing functionality.
  - If any issues found, fix them directly (within the scope of changes from Tasks 1-9 only).

  **Must NOT do**:
  - Do NOT fix pre-existing lint/type errors outside the scope of Tasks 1-9
  - Do NOT add new features or changes beyond fixing integration issues
  - Do NOT change test expectations for pre-existing behavior

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Integration verification requires running multiple tools and fixing issues across several files. Needs broad understanding of all changes.
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 4 (alone)
  - **Blocks**: F1-F4
  - **Blocked By**: Tasks 1-8 (all must complete first)

  **References**:

  **Pattern References**:
  - All files modified in Tasks 1-9 — this task reviews the aggregate of all changes.

  **Acceptance Criteria**:

  - [ ] `ruff check .` — no errors (or only pre-existing)
  - [ ] `ruff format --check .` — no formatting issues
  - [ ] `mypy .` — no new type errors
  - [ ] `pytest -x --tb=short` — ALL tests pass
  - [ ] No import errors, no circular dependencies

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Full quality gate passes
    Tool: Bash
    Preconditions: All Tasks 1-8 completed
    Steps:
      1. Run: ruff check . 2>&1 | tee .sisyphus/evidence/task-9-ruff-check.txt
      2. Run: ruff format --check . 2>&1 | tee .sisyphus/evidence/task-9-ruff-format.txt
      3. Run: mypy . 2>&1 | tee .sisyphus/evidence/task-9-mypy.txt
      4. Run: pytest -x --tb=short 2>&1 | tee .sisyphus/evidence/task-9-pytest.txt
      5. Verify all four exit codes are 0; if any non-zero, fix issues and re-run
    Expected Result: All four commands exit 0 with no errors
    Failure Indicators: Any non-zero exit code, new type errors, lint violations, or test failures
    Evidence: .sisyphus/evidence/task-9-quality-gate.txt (concatenate all four outputs above)

  Scenario: No circular imports or missing modules
    Tool: Bash
    Preconditions: All Tasks 1-8 completed
    Steps:
      1. Run: python -c "from src.ui.shortcuts import GlobalShortcutManager; from src.ui.overlay import OverlayWindow; from src.ui.settings import SettingsDialog; from src.pipeline.orchestrator import PipelineOrchestrator; print('All imports OK')" 2>&1 | tee .sisyphus/evidence/task-9-imports.txt
      2. Verify output contains "All imports OK" and exit code is 0
    Expected Result: All modified modules import cleanly with no circular dependency errors
    Failure Indicators: ImportError, circular import traceback, ModuleNotFoundError
    Evidence: .sisyphus/evidence/task-9-imports.txt
  ```

  **Evidence to Capture:**
  - [ ] task-9-ruff-check.txt — ruff lint output
  - [ ] task-9-ruff-format.txt — ruff format check output
  - [ ] task-9-mypy.txt — mypy type check output
  - [ ] task-9-pytest.txt — full pytest run output
  - [ ] task-9-quality-gate.txt — concatenated summary of all four checks
  - [ ] task-9-imports.txt — circular import verification output

  **Commit**: YES (if fixes were needed)
  - Message: `chore: fix lint, format, and type issues from bugfix-improvements`
  - Files: (whatever needed fixing)
  - Pre-commit: `pytest -x --tb=short`

---

## Final Verification Wave (MANDATORY — after ALL implementation tasks)

> 4 review agents run in PARALLEL. ALL must APPROVE. Rejection → fix → re-run.

- [ ] F1. **Plan Compliance Audit** — `oracle`
  Read the plan end-to-end. For each "Must Have": verify implementation exists (read file, run command). For each "Must NOT Have": search codebase for forbidden patterns — reject with file:line if found. Check evidence files exist in .sisyphus/evidence/. Compare deliverables against plan.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [ ] F2. **Code Quality Review** — `unspecified-high`
  Run `ruff check .` + `ruff format --check .` + `mypy .` + `pytest -x --tb=short`. Review all changed files for: `as any`/type ignores, empty catches, print statements in prod, commented-out code, unused imports. Check AI slop: excessive comments, over-abstraction, generic names.
  Output: `Lint [PASS/FAIL] | Format [PASS/FAIL] | Types [PASS/FAIL] | Tests [N pass/N fail] | VERDICT`

- [ ] F3. **Automated Integration QA** — `unspecified-high`
  Start from clean state. Re-run ALL QA scenarios from EVERY task by executing the exact pytest commands listed in each task's QA section. Capture evidence output via `pytest ... | tee .sisyphus/evidence/final-qa/<task-slug>.txt`. Test cross-task integration: import all modified modules, verify no circular imports, run `python -c "from src.ui.shortcuts import GlobalShortcutManager; from src.ui.overlay import OverlayWindow; from src.ui.settings import SettingsDialog"`. Save all evidence to `.sisyphus/evidence/final-qa/`.
  Output: `Scenarios [N/N pass] | Integration [N/N] | VERDICT`

- [ ] F4. **Scope Fidelity Check** — `deep`
  For each task: read "What to do", read actual diff (git log/diff). Verify 1:1 — everything in spec was built, nothing beyond spec was built. Check "Must NOT do" compliance. Flag unaccounted changes.
  Output: `Tasks [N/N compliant] | Unaccounted [CLEAN/N files] | VERDICT`

---

## Commit Strategy

| Commit | Scope | Message | Files | Pre-commit |
|--------|-------|---------|-------|------------|
| 1 | Bug 1 | `fix(pipeline): clean up asyncio tasks, httpx client, and DB connections on shutdown` | ollama_client.py, llm_worker.py, asr_worker.py, orchestrator.py, tests | `pytest -x` |
| 2 | Bug 3 | `fix(db): close all SQLite connections and checkpoint WAL on exit` | learning_panel.py, main.py, tests | `pytest -x` |
| 3 | Imp 4 | `feat(settings): add dedicated Shortcuts tab` | settings.py, tests | `pytest -x` |
| 4 | Imp 6 | `feat(settings): replace dropdowns with segmented controls for binary settings` | settings.py, tests | `pytest -x` |
| 5 | Imp 7+8 | `fix(settings): remove auto-close on save, add regex validation for parse format` | settings.py, tests | `pytest -x` |
| 6 | Imp 5+Bug 2 | `feat(shortcuts): global hotkeys via pynput with key capture widget` | requirements.txt, shortcuts.py (NEW), overlay.py, settings.py, tests | `pytest -x` |
| 7 | Imp 9 | `fix(overlay): toggle display shortcut only cycles jp/cn in single mode` | overlay.py, tests | `pytest -x` |

---

## Success Criteria

### Verification Commands
```bash
pytest -x --tb=short          # Expected: all tests pass
ruff check .                  # Expected: no errors
ruff format --check .         # Expected: no formatting issues
mypy .                        # Expected: no new errors
```

### Final Checklist
- [ ] All "Must Have" present
- [ ] All "Must NOT Have" absent
- [ ] All tests pass
- [ ] No asyncio errors on program exit
- [ ] Global hotkeys work system-wide
- [ ] WAL/SHM files cleaned up after exit
- [ ] Settings dialog has 5 tabs
- [ ] Key capture widget captures actual keypresses
- [ ] Segmented controls for LLM Mode and Display Mode
- [ ] Settings dialog stays open after save
- [ ] Invalid regex shows red "Invalid Regex!" error
- [ ] Display toggle does nothing when mode is "both"
