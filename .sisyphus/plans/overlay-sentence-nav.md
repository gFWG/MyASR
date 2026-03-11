# Overlay Sentence Navigation & Dual-Display

## TL;DR

> **Quick Summary**: Fix broken Prev/Next sentence navigation by integrating the analysis pipeline (AnalysisWorker QThread), and add a dual-display mode where new ASR sentences appear in a preview text box above the browsed sentence. When the user navigates forward to the latest sentence, collapse back to single-display.
> 
> **Deliverables**:
> - New `AnalysisWorker` QThread that processes ASR text → JLPT analysis → `SentenceResult`
> - Dual-display overlay: preview browser (latest sentence) + main browser (browsed sentence)
> - Working Prev/Next navigation with full JLPT highlights, tooltips, and DB persistence
> - State machine: LIVE mode (single display) ↔ BROWSE mode (dual display)
> - Full independent tooltip support on both text boxes
> - TDD test suite for all new components
> 
> **Estimated Effort**: Medium
> **Parallel Execution**: YES — 3 waves
> **Critical Path**: Task 1 → Task 3 → Task 5 → Task 7 → Task 8

---

## Context

### Original Request
User wants to fix the broken Prev/Next sentence buttons in the overlay. Currently buttons don't work because the analysis pipeline is never integrated — `on_asr_ready` shows plain text without populating history. Additionally, user wants a dual-display mode: when browsing history, new sentences appear in a preview box above the current sentence, and navigating "next" to the latest sentence collapses back to single display.

### Interview Summary
**Key Discussions**:
- **Analysis threading**: New AnalysisWorker QThread, following existing VadWorker/AsrWorker pattern
- **Preview tooltips**: Full independent tooltip support on both text boxes (Day 1, not deferred)
- **Display mode config**: Remove/modify deprecated `overlay_display_mode` config — always dual when browsing
- **New sentence during browse**: Update preview, keep user's browsing position in main box
- **Collapse rule**: When navigating next to reach the most recent sentence (same as preview), collapse to single display
- **Test strategy**: TDD with existing pytest suite

**Research Findings**:
- Root cause: `main.py:191` wires `pipeline.connect_signals(overlay.on_asr_ready)` only — `on_sentence_ready()` is never called
- `on_asr_ready()` renders plain text, does NOT populate `_history`, does NOT set `_current_result`
- `on_sentence_ready()` IS the correct entry point — manages history, renders rich text — but nothing produces `SentenceResult`
- `PreprocessingPipeline.process(text) -> AnalysisResult` exists (50ms, pure Python) but is unused
- `LearningRepository.insert_sentence()` exists for DB persistence — needs to produce highlight IDs
- Pipeline threading: Audio callback → audio_queue → VadWorker(QThread) → segment_queue → AsrWorker(QThread) → asr_ready Signal(object) → GUI thread
- `AsrWorker` already calls `insert_partial()` on its thread — conflicts with AnalysisWorker persistence
- `_on_highlight_hovered` in main.py directly accesses `overlay._current_result` (encapsulation violation)
- Only ONE QTextBrowser exists currently; need to add a second for preview

### Metis Review
**Identified Gaps** (addressed):
- **`on_asr_ready` fate**: Keep as fast preview — shows immediate plain text, then `on_sentence_ready` replaces it with analyzed rich text. Better perceived latency.
- **DB persistence conflict**: AnalysisWorker will own full persistence (`insert_sentence` with highlight IDs). Remove `insert_partial()` from AsrWorker to avoid duplicate rows.
- **Encapsulation violation**: `_on_highlight_hovered` accesses `overlay._current_result` directly — must be fixed with a public method or signal on OverlayWindow.
- **Dual hover routing**: Two QTextBrowsers each need independent event filters, hover tracking, and `_current_result` tracking for tooltips.
- **Height adjustment**: `_adjust_height_to_content` must account for two text browsers in dual-display mode.

---

## Work Objectives

### Core Objective
Integrate the JLPT analysis pipeline into the ASR → UI flow and implement dual-display sentence navigation with full tooltip support.

### Concrete Deliverables
- `src/pipeline/analysis_worker.py` — New QThread worker
- `src/ui/overlay.py` — Rewritten with dual-display state machine
- `src/pipeline/orchestrator.py` — Extended with AnalysisWorker stage
- `src/main.py` — Rewired signal connections
- `src/config.py` — Cleaned up deprecated `overlay_display_mode`
- Test files for all new/changed modules

### Definition of Done
- [ ] Prev/Next buttons navigate sentence history with JLPT highlights and tooltips
- [ ] New ASR sentence appears in preview text box when user is browsing history
- [ ] Navigating "next" to reach the latest sentence collapses to single display
- [ ] Both text boxes support independent hover → tooltip
- [ ] `bun test` equivalent (`pytest tests/`) passes with 0 failures
- [ ] `ruff check . && ruff format --check .` passes
- [ ] `mypy src/` passes

### Must Have
- AnalysisWorker runs on its own QThread (not blocking GUI or ASR)
- SentenceResult created with analysis + DB highlight IDs before reaching overlay
- Thread-safe signal-based communication (no direct cross-thread method calls)
- Preview box shows the latest sentence at all times when in BROWSE mode
- Navigation buttons correctly enable/disable based on history state
- Independent tooltip hover tracking for each QTextBrowser
- Existing `on_asr_ready` still shows immediate plain text (fast preview before analysis completes)

### Must NOT Have (Guardrails)
- DO NOT merge analysis into AsrWorker thread — must be separate QThread
- DO NOT use `type: ignore` or `as any` to suppress types
- DO NOT add streaming ASR — batch mode is intentional
- DO NOT import heavy ML libs at module level — use lazy imports in AnalysisWorker
- DO NOT use direct method calls across threads — Qt Signals only
- DO NOT break existing tooltip dedup logic (sentence_id-based)
- DO NOT add excessive comments or docstrings beyond Google style
- DO NOT create new config fields unless strictly necessary
- DO NOT modify VAD or ASR model logic

---

## Verification Strategy

> **ZERO HUMAN INTERVENTION** — ALL verification is agent-executed. No exceptions.

### Test Decision
- **Infrastructure exists**: YES (pytest, 29 test files, conftest.py with fixtures)
- **Automated tests**: TDD — RED (failing test) → GREEN (minimal impl) → REFACTOR
- **Framework**: pytest (existing)
- **Test command**: `pytest tests/ -x -q`

### QA Policy
Every task MUST include agent-executed QA scenarios.
Evidence saved to `.sisyphus/evidence/task-{N}-{scenario-slug}.{ext}`.

- **Pipeline/Threading**: Use Bash — run test scripts, check signal emission timing
- **UI/Overlay**: Use Playwright skill or tmux — verify widget layout, button states
- **Analysis**: Use Bash (pytest) — unit tests for data transformations
- **Integration**: Use tmux — run the app briefly, verify end-to-end flow

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Foundation — start immediately, all independent):
├── Task 1: AnalysisWorker QThread (TDD) [deep]
├── Task 2: Clean up config + remove deprecated overlay_display_mode [quick]
└── Task 3: Overlay dual-display state machine + second QTextBrowser (TDD) [deep]

Wave 2 (Integration — after Wave 1):
├── Task 4: Orchestrator integration — add AnalysisWorker stage [deep]
├── Task 5: Dual-browser tooltip routing + encapsulation fix (TDD) [deep]
└── Task 6: Remove insert_partial from AsrWorker + AnalysisWorker owns DB persistence [unspecified-high]

Wave 3 (Wiring + Final — after Wave 2):
├── Task 7: main.py rewiring — connect all signals end-to-end [unspecified-high]
└── Task 8: Integration test — full pipeline→overlay flow [deep]

Wave FINAL (After ALL tasks — independent review, 4 parallel):
├── Task F1: Plan compliance audit (oracle)
├── Task F2: Code quality review (unspecified-high)
├── Task F3: Real manual QA (unspecified-high)
└── Task F4: Scope fidelity check (deep)

Critical Path: Task 1 → Task 4 → Task 7 → Task 8 → F1-F4
Parallel Speedup: ~50% faster than sequential
Max Concurrent: 3 (Wave 1)
```

### Dependency Matrix

| Task | Depends On | Blocks |
|------|-----------|--------|
| 1 | — | 4, 6 |
| 2 | — | 7 |
| 3 | — | 5, 7 |
| 4 | 1 | 7 |
| 5 | 3 | 7 |
| 6 | 1 | 7 |
| 7 | 2, 4, 5, 6 | 8 |
| 8 | 7 | F1-F4 |

### Agent Dispatch Summary

- **Wave 1** (3 tasks): T1 → `deep`, T2 → `quick`, T3 → `deep`
- **Wave 2** (3 tasks): T4 → `deep`, T5 → `deep`, T6 → `unspecified-high`
- **Wave 3** (2 tasks): T7 → `unspecified-high`, T8 → `deep`
- **Wave FINAL** (4 tasks): F1 → `oracle`, F2 → `unspecified-high`, F3 → `unspecified-high`, F4 → `deep`

---

## TODOs

- [x] 1. AnalysisWorker QThread — TDD

  **What to do**:
  - RED: Write `tests/test_analysis_worker.py` with tests covering:
    - Worker processes an `ASRResult` and emits a `SentenceResult` via `sentence_ready` signal
    - Worker creates `SentenceResult` with correct `japanese_text`, `analysis`, `sentence_id`, `highlight_vocab_ids`, `highlight_grammar_ids`
    - Worker handles `PreprocessingPipeline` errors gracefully (emits `error_occurred`, does not crash)
    - Worker stops cleanly when `stop()` is called (no hanging thread)
    - Worker reads from `text_queue` (same `queue.Queue` pattern as VadWorker/AsrWorker)
  - GREEN: Implement `src/pipeline/analysis_worker.py`:
    - `AnalysisWorker(QThread)` with signals: `sentence_ready = Signal(object)`, `error_occurred = Signal(str)`
    - Constructor: `(text_queue: queue.Queue[ASRResult], analysis_pipeline: PreprocessingPipeline, db_path: str, config: dict)`
    - `run()` loop: read `ASRResult` from `text_queue` (timeout=0.1s) → call `analysis_pipeline.process(result.text)` → create thread-local `LearningRepository` → call `repo.insert_sentence(text, analysis)` to get `sentence_id` + highlight IDs → construct `SentenceResult` → emit `sentence_ready`
    - `stop()`: set `_running = False`, `quit()`, `wait(2000)`
    - Lazy import of `PreprocessingPipeline` in constructor or module level (it's pure Python, no heavy deps — standard import is fine)
    - Thread-local `LearningRepository` created in `run()` (same pattern as AsrWorker)
  - REFACTOR: Ensure clean separation, proper logging, type hints

  **Must NOT do**:
  - DO NOT merge into AsrWorker — separate QThread
  - DO NOT import heavy ML libs at module level
  - DO NOT use direct method calls across threads — emit via Signal only
  - DO NOT suppress type errors

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: QThread worker with threading concerns, signal patterns, DB integration — requires careful implementation
  - **Skills**: []
    - No special skills needed — standard Python/Qt patterns
  - **Skills Evaluated but Omitted**:
    - `playwright`: No browser interaction needed

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 2, 3)
  - **Blocks**: Tasks 4, 6
  - **Blocked By**: None (can start immediately)

  **References**:

  **Pattern References** (existing code to follow):
  - `src/pipeline/asr_worker.py` — Follow the EXACT same QThread pattern: `_running` flag, `run()` loop with queue.get(timeout=0.1), `stop()` method, signals `error_occurred = Signal(str)` and output signal. The new worker reads from `_text_queue` (AsrWorker's output queue).
  - `src/pipeline/vad_worker.py` — Second reference for the QThread worker pattern, especially the `stop()` → `quit()` → `wait()` sequence.
  - `src/pipeline/types.py` — `ASRResult(text, segment_id, elapsed_ms, db_row_id)` — this is the INPUT to AnalysisWorker.

  **API/Type References** (contracts to implement against):
  - `src/db/models.py:SentenceResult` — OUTPUT type: `SentenceResult(japanese_text, analysis, created_at, sentence_id, highlight_vocab_ids, highlight_grammar_ids)`. The `sentence_id`, `highlight_vocab_ids`, `highlight_grammar_ids` come from `LearningRepository.insert_sentence()`.
  - `src/db/models.py:AnalysisResult` — OUTPUT of `PreprocessingPipeline.process()`: `AnalysisResult(tokens, vocab_hits, grammar_hits)`.
  - `src/analysis/pipeline.py:PreprocessingPipeline.process(text: str) -> AnalysisResult` — The analysis function to call. Pure Python, ~50ms. Requires `AppConfig` for construction (needs `user_jlpt_level`).

  **DB References**:
  - `src/db/repository.py:LearningRepository.insert_sentence()` — Must check this method's signature and return type. It should return `sentence_id` and highlight IDs. If it doesn't exist, check `insert_partial()` and adapt.
  - `src/db/repository.py:LearningRepository.__init__(conn=)` — Thread-local construction: create new `sqlite3.connect(db_path)` in `run()`, pass to `LearningRepository(conn=conn)`.

  **Test References** (testing patterns to follow):
  - `tests/test_asr_worker.py` (if exists) — Follow existing QThread test patterns. If no existing worker tests, use `QSignalSpy` or manual signal tracking with `QApplication` fixture from conftest.
  - `tests/conftest.py` — Check for `qapp` fixture or similar Qt test infrastructure.

  **WHY Each Reference Matters**:
  - `asr_worker.py` → Copy the exact threading lifecycle pattern to ensure consistency
  - `types.py:ASRResult` → This is the data that comes off `_text_queue` — need exact field names
  - `models.py:SentenceResult` → This is what the overlay expects — must match exactly
  - `analysis/pipeline.py` → The processing function to call — need constructor args and return type
  - `repository.py` → DB persistence — need to know how to get highlight IDs back

  **Acceptance Criteria**:

  **TDD:**
  - [ ] Test file created: `tests/test_analysis_worker.py`
  - [ ] `pytest tests/test_analysis_worker.py -x` → PASS (all tests, 0 failures)

  **QA Scenarios:**

  ```
  Scenario: Worker processes ASRResult and emits SentenceResult
    Tool: Bash (pytest)
    Preconditions: test_analysis_worker.py exists with mock PreprocessingPipeline
    Steps:
      1. Run `pytest tests/test_analysis_worker.py::test_emits_sentence_result -x -v`
      2. Verify test passes — mock pipeline returns AnalysisResult, worker emits SentenceResult with matching japanese_text and non-None analysis
    Expected Result: Test PASSES, signal emitted with correct SentenceResult fields
    Failure Indicators: Test fails, signal never emitted, wrong data in SentenceResult
    Evidence: .sisyphus/evidence/task-1-emit-sentence-result.txt

  Scenario: Worker handles analysis error gracefully
    Tool: Bash (pytest)
    Preconditions: test with mock pipeline that raises RuntimeError
    Steps:
      1. Run `pytest tests/test_analysis_worker.py::test_handles_analysis_error -x -v`
      2. Verify worker emits error_occurred signal, does NOT crash, continues running
    Expected Result: Test PASSES, error_occurred emitted, worker still alive
    Failure Indicators: Worker crashes, test hangs, no error signal
    Evidence: .sisyphus/evidence/task-1-analysis-error-handling.txt
  ```

  **Commit**: YES (Commit 1)
  - Message: `feat(pipeline): add AnalysisWorker QThread for JLPT analysis`
  - Files: `src/pipeline/analysis_worker.py`, `tests/test_analysis_worker.py`
  - Pre-commit: `pytest tests/test_analysis_worker.py -x`

- [x] 2. Clean up config — remove deprecated `overlay_display_mode`

  **What to do**:
  - Search for ALL references to `overlay_display_mode` across the entire codebase
  - Remove the `overlay_display_mode` field from `AppConfig` dataclass in `src/config.py`
  - Remove any usage of `overlay_display_mode` in overlay.py, settings.py, or any other file
  - If `settings.py` has a UI control for this setting, remove that control
  - Update any tests that reference `overlay_display_mode`
  - Run `pytest tests/ -x -q` to verify nothing breaks

  **Must NOT do**:
  - DO NOT add new config fields — just remove the deprecated one
  - DO NOT modify any non-config-related code

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Simple search-and-remove across a few files
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - None needed for simple removal

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 3)
  - **Blocks**: Task 7
  - **Blocked By**: None

  **References**:

  **Pattern References**:
  - `src/config.py` — Contains `AppConfig` dataclass with `overlay_display_mode: Literal['both', 'single'] = 'both'` — REMOVE this field
  - `src/ui/settings.py` — May contain a dropdown/radio for display mode — check and remove

  **Search Strategy**:
  - Run `grep -r "overlay_display_mode" src/ tests/` to find ALL references before removing

  **WHY Each Reference Matters**:
  - `config.py` → Primary removal target
  - `settings.py` → May have UI elements tied to this config field
  - Tests → May assert on this field

  **Acceptance Criteria**:

  **QA Scenarios:**

  ```
  Scenario: Config field removed and no references remain
    Tool: Bash (grep + pytest)
    Preconditions: Changes applied to config.py and any referencing files
    Steps:
      1. Run `grep -r "overlay_display_mode" src/ tests/` — expect 0 matches
      2. Run `pytest tests/ -x -q` — expect all pass
      3. Run `ruff check src/config.py` — expect no errors
      4. Run `mypy src/config.py` — expect no errors
    Expected Result: Zero references to overlay_display_mode, all tests pass
    Failure Indicators: grep finds remaining references, tests fail, type errors
    Evidence: .sisyphus/evidence/task-2-config-cleanup.txt
  ```

  **Commit**: YES (Commit 2)
  - Message: `refactor(config): remove deprecated overlay_display_mode`
  - Files: `src/config.py`, possibly `src/ui/settings.py`, `tests/test_config.py`
  - Pre-commit: `pytest tests/ -x -q`

- [x] 3. Overlay dual-display state machine + second QTextBrowser — TDD

  **What to do**:
  - RED: Write/extend `tests/test_overlay.py` with tests covering:
    - LIVE mode: single `_jp_browser` visible, `_preview_browser` hidden — default state
    - BROWSE mode: both browsers visible — triggered when `_prev_sentence()` is called
    - Transition BROWSE → LIVE: when `_next_sentence()` reaches `_history_index == len(_history) - 1`, collapse to single display
    - `on_sentence_ready()` in LIVE mode: renders in `_jp_browser`, no preview shown
    - `on_sentence_ready()` in BROWSE mode: renders latest in `_preview_browser`, keeps `_jp_browser` at current browsed position
    - `_adjust_height_to_content()` accounts for both browsers when both visible
    - `on_asr_ready()` still works as fast plain-text preview in `_jp_browser` (LIVE mode only)
  - GREEN: Modify `src/ui/overlay.py`:
    - Add `_preview_browser = _make_browser(_JP_FONT_SIZE)` — second QTextBrowser for preview
    - Add layout: `_preview_browser` ABOVE `content_layout` (i.e., between the top stretch and the content HBox). Initially hidden (`_preview_browser.hide()`, or wrap in a container widget that hides)
    - Add state enum or bool: `_browsing: bool = False` (True = BROWSE mode, False = LIVE mode)
    - Add `_latest_result: SentenceResult | None = None` — always tracks the most recent sentence (separate from `_current_result` which tracks what's displayed in main browser)
    - Modify `on_sentence_ready()`:
      - Always update `_latest_result` and append to `_history`
      - If `_browsing is False` (LIVE mode): set `_history_index = len-1`, `_current_result = result`, render in `_jp_browser`, keep `_preview_browser` hidden
      - If `_browsing is True` (BROWSE mode): render latest in `_preview_browser`, keep `_jp_browser` at current browsed index, update arrow visibility
    - Modify `_prev_sentence()`:
      - Enter BROWSE mode if not already (`_browsing = True`)
      - If going from LIVE → BROWSE (first prev click): show `_preview_browser`, render `_latest_result` in preview, decrement index, render in `_jp_browser`
      - Else: just decrement and render in `_jp_browser`
    - Modify `_next_sentence()`:
      - Increment index
      - If `_history_index == len(_history) - 1` (reached latest): collapse to LIVE mode — `_browsing = False`, hide `_preview_browser`, render latest in `_jp_browser`
      - Else: render in `_jp_browser`, stay in BROWSE mode
    - Modify `_update_arrow_visibility()`: unchanged logic — prev enabled if index > 0, next enabled if index < len-1
    - Modify `_adjust_height_to_content()`: sum heights of visible browsers + spacing
    - Add helper: `_render_in_browser(browser: QTextBrowser, result: SentenceResult)` to avoid duplicating render logic
    - Keep `on_asr_ready()` for fast plain-text preview — only renders in `_jp_browser` in LIVE mode, ignored in BROWSE mode
  - REFACTOR: Extract common rendering patterns, ensure clean state transitions

  **Must NOT do**:
  - DO NOT remove `on_asr_ready()` — it's the fast preview path
  - DO NOT add tooltip hover handling here — that's Task 5
  - DO NOT wire any signals — just the overlay widget internals
  - DO NOT touch `_on_highlight_hovered` — Task 5 handles the encapsulation fix

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Complex state machine with dual-display mode, multiple transition paths, height adjustment — needs careful implementation
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - `visual-engineering`: This is widget logic, not visual design
    - `playwright`: No browser testing — Qt widgets tested via pytest

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2)
  - **Blocks**: Tasks 5, 7
  - **Blocked By**: None

  **References**:

  **Pattern References** (existing code to follow):
  - `src/ui/overlay.py:75-84` — `_make_browser()` factory function — reuse for creating `_preview_browser` with identical styling
  - `src/ui/overlay.py:162-188` — Current layout construction: `outer_layout → stretch(1) → content_layout(HBox) → stretch(1)`. The `_preview_browser` should be inserted between the top stretch and `content_layout`.
  - `src/ui/overlay.py:208-223` — `on_sentence_ready()` — current implementation to modify. Must preserve history management logic while adding LIVE/BROWSE branching.
  - `src/ui/overlay.py:308-326` — `_prev_sentence()` / `_next_sentence()` — current navigation logic. Modify to handle mode transitions.
  - `src/ui/overlay.py:339-365` — `_adjust_height_to_content()` — must be updated to account for two visible browsers.
  - `src/ui/overlay.py:244-252` — `on_asr_ready()` — keep as-is for LIVE mode fast preview.

  **API/Type References**:
  - `src/db/models.py:SentenceResult` — The data type rendered by `_render_result()`. Has `japanese_text`, `analysis`, `sentence_id`.
  - `src/ui/highlight.py:HighlightRenderer.build_rich_text()` — Called by `_render_result()` to generate HTML.

  **Test References**:
  - `tests/test_overlay.py` (if exists) — Extend with new dual-display tests. Check conftest.py for Qt fixtures.
  - `tests/conftest.py` — Look for `qapp` or `QApplication` fixture for widget testing.

  **WHY Each Reference Matters**:
  - `overlay.py:162-188` → Layout is the core change — must understand current structure to add preview browser correctly
  - `overlay.py:208-223` → `on_sentence_ready` is the main entry point to bifurcate for LIVE/BROWSE
  - `overlay.py:308-326` → Navigation methods need mode transition logic
  - `overlay.py:339-365` → Height calculation must handle dual-display

  **Acceptance Criteria**:

  **TDD:**
  - [ ] Test file updated: `tests/test_overlay.py`
  - [ ] `pytest tests/test_overlay.py -x` → PASS (all tests, 0 failures)

  **QA Scenarios:**

  ```
  Scenario: LIVE mode — single display by default
    Tool: Bash (pytest)
    Preconditions: OverlayWindow instantiated, no sentences received
    Steps:
      1. Run `pytest tests/test_overlay.py::test_live_mode_default -x -v`
      2. Verify: _preview_browser is hidden, _browsing is False, _jp_browser is visible
    Expected Result: Test PASSES, default state is LIVE (single display)
    Failure Indicators: _preview_browser visible, _browsing is True
    Evidence: .sisyphus/evidence/task-3-live-mode-default.txt

  Scenario: Transition to BROWSE mode on prev click
    Tool: Bash (pytest)
    Preconditions: 3 sentences in history, currently showing latest
    Steps:
      1. Run `pytest tests/test_overlay.py::test_prev_enters_browse_mode -x -v`
      2. Verify: After _prev_sentence(), _browsing is True, _preview_browser visible with latest sentence, _jp_browser shows sentence[1]
    Expected Result: Test PASSES, dual display activated
    Failure Indicators: _preview_browser still hidden, _browsing still False
    Evidence: .sisyphus/evidence/task-3-browse-mode-transition.txt

  Scenario: Collapse back to LIVE when reaching latest via next
    Tool: Bash (pytest)
    Preconditions: In BROWSE mode, _history_index = len-2
    Steps:
      1. Run `pytest tests/test_overlay.py::test_next_collapses_to_live -x -v`
      2. Call _next_sentence(), verify: _history_index == len-1, _browsing is False, _preview_browser hidden
    Expected Result: Test PASSES, collapsed to single display
    Failure Indicators: Still in BROWSE mode, _preview_browser still visible
    Evidence: .sisyphus/evidence/task-3-collapse-to-live.txt

  Scenario: New sentence during BROWSE updates preview only
    Tool: Bash (pytest)
    Preconditions: In BROWSE mode viewing sentence[1] of 3
    Steps:
      1. Run `pytest tests/test_overlay.py::test_new_sentence_during_browse -x -v`
      2. Call on_sentence_ready(new_result), verify: _preview_browser shows new_result, _jp_browser still shows sentence[1], _history_index unchanged relative to browsed sentence
    Expected Result: Test PASSES, preview updated, browse position preserved
    Failure Indicators: _jp_browser content changed, index jumped to latest
    Evidence: .sisyphus/evidence/task-3-new-sentence-during-browse.txt
  ```

  **Commit**: YES (Commit 3)
  - Message: `feat(ui): add dual-display state machine to overlay`
  - Files: `src/ui/overlay.py`, `tests/test_overlay.py`
  - Pre-commit: `pytest tests/test_overlay.py -x`

- [x] 4. Orchestrator integration — add AnalysisWorker stage

  **What to do**:
  - RED: Write/extend `tests/test_orchestrator.py` with tests covering:
    - Orchestrator creates AnalysisWorker with correct queue wiring (`_text_queue` as input)
    - `connect_signals()` accepts `on_sentence_ready` callback and connects to AnalysisWorker's `sentence_ready` signal
    - `start()` starts AnalysisWorker after AsrWorker (capture → VAD → ASR → Analysis)
    - `stop()` stops AnalysisWorker first (before AsrWorker) — drain in-flight analysis before stopping upstream
    - `error_occurred` property includes AnalysisWorker's error signal
    - `on_config_changed()` propagates relevant config to AnalysisWorker (user_jlpt_level changes)
  - GREEN: Modify `src/pipeline/orchestrator.py`:
    - Import `AnalysisWorker` and `PreprocessingPipeline`
    - In `__init__()`: create `PreprocessingPipeline(config)` → create `AnalysisWorker(text_queue=self._text_queue, analysis_pipeline=pipeline, db_path=db_path, config=config)`
    - Need `AppConfig` or equivalent for `PreprocessingPipeline` — either pass full config dict or extract needed fields. Check `PreprocessingPipeline.__init__` signature.
    - Modify `connect_signals()` signature: add `on_sentence_ready: Callable[[SentenceResult], None]` parameter. Connect `analysis_worker.sentence_ready.connect(on_sentence_ready)`. Keep `on_asr_ready` connection for fast preview.
    - Modify `start()`: add `self._analysis_worker.start()` after `self._asr_worker.start()`
    - Modify `stop()`: stop `self._analysis_worker` FIRST (it's downstream), then AsrWorker, then VadWorker, then capture
    - Modify `error_occurred` property: include `self._analysis_worker.error_occurred`
    - Add `sentence_ready` property forwarding from AnalysisWorker
  - REFACTOR: Ensure config is properly threaded through

  **Must NOT do**:
  - DO NOT modify VadWorker or ASR model logic
  - DO NOT change the audio capture flow
  - DO NOT change the queue topology (audio_queue → segment_queue → text_queue is unchanged; AnalysisWorker reads from text_queue)

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Pipeline orchestration with threading lifecycle, signal wiring, shutdown ordering — requires careful sequencing
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - None needed

  **Parallelization**:
  - **Can Run In Parallel**: YES (within Wave 2, alongside T5, T6)
  - **Parallel Group**: Wave 2 (with Tasks 5, 6)
  - **Blocks**: Task 7
  - **Blocked By**: Task 1

  **References**:

  **Pattern References**:
  - `src/pipeline/orchestrator.py:43-87` — Current `__init__()` — follow the same pattern: create model/pipeline → create worker with queues → store as `self._analysis_worker`
  - `src/pipeline/orchestrator.py:91-112` — `start()` / `stop()` lifecycle — add AnalysisWorker to the chain. Start order: capture → VAD → ASR → Analysis. Stop order: Analysis → ASR → VAD → capture (reverse).
  - `src/pipeline/orchestrator.py:136-147` — `connect_signals()` — extend with `on_sentence_ready` parameter
  - `src/pipeline/orchestrator.py:156-169` — `error_occurred` property — add AnalysisWorker's error signal

  **API/Type References**:
  - `src/pipeline/analysis_worker.py` (from Task 1) — `AnalysisWorker(text_queue, analysis_pipeline, db_path, config)` with signals `sentence_ready = Signal(object)`, `error_occurred = Signal(str)`
  - `src/analysis/pipeline.py:PreprocessingPipeline.__init__(config: AppConfig)` — Needs `AppConfig` instance. Currently the orchestrator receives a `dict[str, Any]` config. Need to either pass `AppConfig` to orchestrator or construct `PreprocessingPipeline` with the dict fields it needs. Check what `PreprocessingPipeline.__init__` actually requires.
  - `src/db/models.py:SentenceResult` — Type emitted by `sentence_ready` signal

  **Test References**:
  - `tests/test_orchestrator.py` (if exists) — Extend. Otherwise create with mocked workers.

  **WHY Each Reference Matters**:
  - `orchestrator.py:43-87` → Must follow exact same worker instantiation pattern
  - `orchestrator.py:91-112` → Shutdown ordering is CRITICAL — wrong order causes hanging threads or lost data
  - `analysis/pipeline.py` → Need to know constructor args to create PreprocessingPipeline correctly

  **Acceptance Criteria**:

  **TDD:**
  - [ ] Test file: `tests/test_orchestrator.py` updated
  - [ ] `pytest tests/test_orchestrator.py -x` → PASS

  **QA Scenarios:**

  ```
  Scenario: Orchestrator creates and wires AnalysisWorker
    Tool: Bash (pytest)
    Preconditions: test_orchestrator.py with mocked models
    Steps:
      1. Run `pytest tests/test_orchestrator.py::test_analysis_worker_created -x -v`
      2. Verify orchestrator has _analysis_worker attribute, connected to _text_queue
    Expected Result: Test PASSES, worker properly instantiated
    Failure Indicators: AttributeError on _analysis_worker, wrong queue wiring
    Evidence: .sisyphus/evidence/task-4-orchestrator-analysis-worker.txt

  Scenario: connect_signals wires both ASR and sentence callbacks
    Tool: Bash (pytest)
    Preconditions: Orchestrator instantiated with mocks
    Steps:
      1. Run `pytest tests/test_orchestrator.py::test_connect_signals_both -x -v`
      2. Verify both on_asr_ready and on_sentence_ready callbacks are connected
    Expected Result: Test PASSES, both signals connected
    Failure Indicators: Missing connection, TypeError on connect_signals call
    Evidence: .sisyphus/evidence/task-4-connect-signals.txt
  ```

  **Commit**: YES (groups with Commit 4, alongside T6)
  - Message: `feat(pipeline): integrate AnalysisWorker into orchestrator`
  - Files: `src/pipeline/orchestrator.py`, `tests/test_orchestrator.py`
  - Pre-commit: `pytest tests/ -x -q`

- [x] 5. Dual-browser independent tooltip routing + encapsulation fix — TDD

  **What to do**:
  - RED: Write/extend tests covering:
    - Hovering over `_jp_browser` viewport emits `highlight_hovered` with correct hit + source context
    - Hovering over `_preview_browser` viewport emits `highlight_hovered` with correct hit + source context (different `SentenceResult` than main browser)
    - The signal carries enough info to resolve `sentence_id` and `highlight_id` without accessing `overlay._current_result` directly
    - Tooltip dedup works independently for each browser (hovering same word in preview vs main = two separate tooltips)
  - GREEN: Modify `src/ui/overlay.py`:
    - **Encapsulation fix**: Change `highlight_hovered` signal to `Signal(object, object, object)` — emit `(hit, global_pos, sentence_result)` instead of `(hit, global_pos)`. This eliminates the need for main.py to access `overlay._current_result` directly.
    - **Dual event filter**: Install event filter on `_preview_browser.viewport()` too:
      ```python
      self._preview_browser.setMouseTracking(True)
      self._preview_browser.viewport().setMouseTracking(True)
      self._preview_browser.viewport().installEventFilter(self)
      ```
    - **Modify `eventFilter()`**: Detect WHICH viewport is the source:
      - If `watched is self._jp_browser.viewport()` → use `_current_result` for hit resolution
      - If `watched is self._preview_browser.viewport()` → use `_latest_result` for hit resolution
      - Apply hover handling and drag handling for both viewports
    - **Modify `_handle_hover_at_viewport_pos()`**: Accept additional params: `browser: QTextBrowser, result: SentenceResult | None` — generalized for either browser
    - **Emit enriched signal**: `self.highlight_hovered.emit(hit, global_pos, result)` — now carries the source SentenceResult
    - **Drag support**: Both browser viewports should support drag-to-move (existing pattern in eventFilter)
  - REFACTOR: Ensure event filter is clean with clear viewport identification

  **Must NOT do**:
  - DO NOT modify `TooltipPopup` internals — it already supports `sentence_id`-based dedup
  - DO NOT change the tooltip show/hide logic
  - DO NOT add any new signals beyond modifying the existing `highlight_hovered`

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Event filter routing, viewport identification, signal contract change — subtle and error-prone
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - `playwright`: No browser testing — Qt widget events tested via pytest

  **Parallelization**:
  - **Can Run In Parallel**: YES (within Wave 2)
  - **Parallel Group**: Wave 2 (with Tasks 4, 6)
  - **Blocks**: Task 7
  - **Blocked By**: Task 3

  **References**:

  **Pattern References**:
  - `src/ui/overlay.py:505-531` — Current `eventFilter()` method. Currently checks only `self._jp_browser.viewport()`. Must extend to also handle `self._preview_browser.viewport()`. Note the drag handling pattern: press → store `_drag_pos`, move → `self.move()`, release → clear `_drag_pos`.
  - `src/ui/overlay.py:367-380` — `_handle_hover_at_viewport_pos()` — currently hardcoded to `self._jp_browser` and `self._current_result`. Must generalize to accept browser + result params.
  - `src/ui/overlay.py:190-192` — Mouse tracking setup for `_jp_browser`. Replicate for `_preview_browser`.
  - `src/ui/overlay.py:130` — `highlight_hovered = Signal(object, object)` — change to `Signal(object, object, object)`.

  **API/Type References**:
  - `src/main.py:99-131` — `_on_highlight_hovered()` — CURRENTLY accesses `overlay._current_result` directly (line 100). After this task, it must be rewritten to use the third signal argument (`sentence_result`) instead. This rewrite happens in Task 7 but the signal contract change happens HERE.
  - `src/ui/tooltip.py:show_for_vocab(hit, position, sentence_id, highlight_id)` — Tooltip API — needs `sentence_id` and `highlight_id` which come from `SentenceResult`.
  - `src/db/models.py:SentenceResult` — Has `sentence_id`, `highlight_vocab_ids`, `highlight_grammar_ids`.

  **WHY Each Reference Matters**:
  - `overlay.py:505-531` → This is the core change — event filter must route two viewports correctly
  - `overlay.py:367-380` → Hover handler must be generalized — currently assumes single browser
  - `main.py:99-131` → Shows current encapsulation violation that this task's signal change fixes

  **Acceptance Criteria**:

  **TDD:**
  - [ ] Tests updated: `tests/test_overlay.py`
  - [ ] `pytest tests/test_overlay.py -x` → PASS

  **QA Scenarios:**

  ```
  Scenario: Hover on main browser emits highlight_hovered with correct result
    Tool: Bash (pytest)
    Preconditions: Overlay with sentence loaded in _jp_browser
    Steps:
      1. Run `pytest tests/test_overlay.py::test_hover_main_browser_emits_signal -x -v`
      2. Simulate hover event on _jp_browser viewport at a highlighted character position
      3. Verify highlight_hovered emitted with (hit, pos, sentence_result) where sentence_result is _current_result
    Expected Result: Signal emitted with 3 args, third arg is the correct SentenceResult
    Failure Indicators: Signal has 2 args (old contract), wrong SentenceResult
    Evidence: .sisyphus/evidence/task-5-main-browser-hover.txt

  Scenario: Hover on preview browser emits highlight_hovered with preview result
    Tool: Bash (pytest)
    Preconditions: Overlay in BROWSE mode, different sentences in main vs preview
    Steps:
      1. Run `pytest tests/test_overlay.py::test_hover_preview_browser_emits_signal -x -v`
      2. Simulate hover event on _preview_browser viewport
      3. Verify highlight_hovered emitted with (hit, pos, sentence_result) where sentence_result is _latest_result (NOT _current_result)
    Expected Result: Signal emitted with preview's SentenceResult
    Failure Indicators: Signal carries _current_result instead of _latest_result
    Evidence: .sisyphus/evidence/task-5-preview-browser-hover.txt
  ```

  **Commit**: YES (Commit 5)
  - Message: `feat(ui): dual-browser independent tooltip routing`
  - Files: `src/ui/overlay.py`, `tests/test_overlay.py`
  - Pre-commit: `pytest tests/test_overlay.py -x`

- [x] 6. Remove `insert_partial` from AsrWorker — AnalysisWorker owns DB persistence

  **What to do**:
  - Read `src/pipeline/asr_worker.py` and find all calls to `LearningRepository.insert_partial()` or any DB write operations
  - Remove DB persistence from AsrWorker: remove the `db_path` constructor parameter, remove thread-local `LearningRepository` creation in `run()`, remove `insert_partial()` calls
  - Remove `db_path` from `_text_queue.put_nowait(result)` flow if `db_row_id` was being set — but keep `ASRResult` intact (just don't populate `db_row_id`)
  - Verify AnalysisWorker (Task 1) now owns ALL DB writes — `insert_sentence()` in AnalysisWorker produces `sentence_id` + highlight IDs
  - Update `src/pipeline/orchestrator.py`: remove `db_path` from `AsrWorker` constructor call (it's no longer needed there — only AnalysisWorker needs it)
  - Update any tests that test AsrWorker's DB behavior — remove those assertions or redirect them to AnalysisWorker tests

  **Must NOT do**:
  - DO NOT modify ASR transcription logic — only remove DB writes
  - DO NOT change `ASRResult` data class — keep `db_row_id` field (just leave it as None)
  - DO NOT remove `_text_queue` usage — AsrWorker still puts results on the queue for AnalysisWorker

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Cross-file refactor touching asr_worker, orchestrator, and tests — moderate complexity
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - None needed

  **Parallelization**:
  - **Can Run In Parallel**: YES (within Wave 2)
  - **Parallel Group**: Wave 2 (with Tasks 4, 5)
  - **Blocks**: Task 7
  - **Blocked By**: Task 1

  **References**:

  **Pattern References**:
  - `src/pipeline/asr_worker.py` — Find all DB-related code: `LearningRepository` import, `db_path` parameter, thread-local `conn = sqlite3.connect(db_path)` in `run()`, `repo = LearningRepository(conn=conn)`, `repo.insert_partial()` calls. Remove all of these.
  - `src/pipeline/orchestrator.py:70-76` — `AsrWorker(segment_queue, text_queue, asr, config, db_path=db_path)` — remove `db_path` parameter

  **API/Type References**:
  - `src/pipeline/types.py:ASRResult` — Has `db_row_id: int | None = None`. Keep field, just don't populate it.
  - `src/pipeline/analysis_worker.py` (Task 1) — Now the sole owner of DB persistence.

  **WHY Each Reference Matters**:
  - `asr_worker.py` → Primary removal target — need to identify every DB touchpoint
  - `orchestrator.py:70-76` → Constructor call must be updated to remove `db_path`

  **Acceptance Criteria**:

  **QA Scenarios:**

  ```
  Scenario: AsrWorker no longer performs DB writes
    Tool: Bash (grep + pytest)
    Preconditions: Changes applied
    Steps:
      1. Run `grep -n "insert_partial\|LearningRepository\|db_path\|sqlite3" src/pipeline/asr_worker.py` — expect 0 matches for DB-related code (sqlite3 import gone, LearningRepository gone)
      2. Run `pytest tests/test_asr_worker.py -x -v` (if exists) — expect all remaining tests pass
      3. Run `pytest tests/ -x -q` — expect full suite passes
    Expected Result: Zero DB code in asr_worker.py, all tests pass
    Failure Indicators: DB references remain, tests fail due to missing db_path
    Evidence: .sisyphus/evidence/task-6-asr-worker-no-db.txt

  Scenario: AnalysisWorker is sole DB writer
    Tool: Bash (grep)
    Preconditions: Both Task 1 and Task 6 complete
    Steps:
      1. Run `grep -rn "insert_sentence\|insert_partial" src/pipeline/` — expect only analysis_worker.py has DB writes
      2. Verify: asr_worker.py has ZERO DB write calls
    Expected Result: Only analysis_worker.py contains DB persistence code
    Failure Indicators: Multiple files still writing to DB
    Evidence: .sisyphus/evidence/task-6-single-db-writer.txt
  ```

  **Commit**: YES (groups with Commit 4)
  - Message: `feat(pipeline): integrate AnalysisWorker into orchestrator`
  - Files: `src/pipeline/asr_worker.py`, `src/pipeline/orchestrator.py`, `tests/test_asr_worker.py`
  - Pre-commit: `pytest tests/ -x -q`

- [x] 7. main.py rewiring — connect all signals end-to-end

  **What to do**:
  - Modify `src/main.py` to wire the complete pipeline:
    - **Pipeline config**: Add analysis-related config to `pipeline_config` dict — at minimum `user_jlpt_level` for `PreprocessingPipeline`
    - **connect_signals()**: Change from `pipeline.connect_signals(overlay.on_asr_ready)` to:
      ```python
      pipeline.connect_signals(
          on_asr_ready=overlay.on_asr_ready,
          on_sentence_ready=overlay.on_sentence_ready,
      )
      ```
    - **Fix `_on_highlight_hovered()`**: Rewrite to use the enriched signal `(hit, point, sentence_result)` — no longer access `overlay._current_result` directly:
      ```python
      def _on_highlight_hovered(hit: VocabHit | GrammarHit, point: QPoint, result: SentenceResult | None) -> None:
          sentence_id = result.sentence_id if result is not None else None
          highlight_id = 0
          if result is not None:
              # ... resolve highlight_id from result's highlight_vocab_ids/highlight_grammar_ids
          # ... call tooltip.show_for_vocab/grammar as before
      ```
    - **Update overlay.highlight_hovered.connect()**: Update the handler signature to match the new 3-arg signal
    - **Wire AnalysisWorker errors**: `pipeline.error_occurred` already returns all worker errors (Task 4 extends it) — no change needed here if Task 4 is done correctly
    - **on_config_changed**: Ensure `pipeline.on_config_changed()` passes config through to AnalysisWorker (if the orchestrator's method is updated in Task 4)
  - Write/extend tests if `tests/test_main.py` exists — verify signal connections

  **Must NOT do**:
  - DO NOT modify overlay.py or orchestrator.py here — only main.py wiring
  - DO NOT add new UI components
  - DO NOT change the pipeline startup order (that's orchestrator's responsibility)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Signal wiring across multiple components — moderate complexity, needs to verify all connections work
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - None needed

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 3 (sequential after Wave 2)
  - **Blocks**: Task 8
  - **Blocked By**: Tasks 2, 4, 5, 6

  **References**:

  **Pattern References**:
  - `src/main.py:83-91` — Current pipeline_config dict — extend with analysis-related fields
  - `src/main.py:191` — `pipeline.connect_signals(overlay.on_asr_ready)` — the line to change
  - `src/main.py:99-131` — `_on_highlight_hovered()` — the encapsulation violation to fix. Currently accesses `overlay._current_result` (line 100). After Task 5, the signal carries `SentenceResult` as third arg.
  - `src/main.py:131` — `overlay.highlight_hovered.connect(_on_highlight_hovered)` — update handler signature

  **API/Type References**:
  - `src/pipeline/orchestrator.py:connect_signals()` (after Task 4) — New signature: `connect_signals(on_asr_ready, on_sentence_ready)`
  - `src/ui/overlay.py:highlight_hovered` (after Task 5) — New signal: `Signal(object, object, object)` emitting `(hit, global_pos, sentence_result)`
  - `src/ui/overlay.py:on_sentence_ready()` — The slot to wire for analyzed results
  - `src/ui/overlay.py:on_asr_ready()` — The slot for fast plain-text preview

  **WHY Each Reference Matters**:
  - `main.py:191` → THE critical line to change — currently only wires on_asr_ready
  - `main.py:99-131` → The encapsulation violation fix — must use new signal contract
  - `orchestrator.py:connect_signals` → Need to match the new API from Task 4

  **Acceptance Criteria**:

  **QA Scenarios:**

  ```
  Scenario: All signal connections are wired correctly
    Tool: Bash (pytest + grep)
    Preconditions: All Wave 1+2 tasks complete, main.py updated
    Steps:
      1. Run `grep -n "connect_signals" src/main.py` — verify call includes both on_asr_ready and on_sentence_ready
      2. Run `grep -n "_current_result" src/main.py` — expect 0 matches (encapsulation violation fixed)
      3. Run `pytest tests/ -x -q` — expect all pass
      4. Run `mypy src/main.py` — expect no type errors
    Expected Result: Both callbacks wired, no direct attribute access, all checks pass
    Failure Indicators: Only on_asr_ready wired, _current_result still accessed, type errors
    Evidence: .sisyphus/evidence/task-7-signal-wiring.txt

  Scenario: Hover handler uses enriched signal (3 args)
    Tool: Bash (grep)
    Preconditions: main.py updated
    Steps:
      1. Run `grep -A 5 "def _on_highlight_hovered" src/main.py` — verify function signature has 3 params (hit, point, result)
      2. Verify no access to `overlay._current_result` or `overlay._latest_result`
    Expected Result: Handler uses signal-provided result, no encapsulation violation
    Failure Indicators: Old 2-arg signature, direct overlay attribute access
    Evidence: .sisyphus/evidence/task-7-hover-handler.txt
  ```

  **Commit**: YES (groups with Commit 6, alongside T8)
  - Message: `feat(main): wire analysis pipeline to overlay with full signal flow`
  - Files: `src/main.py`
  - Pre-commit: `pytest tests/ -x -q && ruff check . && mypy src/`

- [x] 8. Integration test — full pipeline → overlay flow

  **What to do**:
  - Create `tests/test_integration_pipeline_overlay.py` — end-to-end test:
    - Mock `QwenASR` to return predetermined Japanese text
    - Mock `SileroVAD` to pass through audio as speech segments
    - Use real `PreprocessingPipeline` (requires `data/jlpt_vocab.json` and `data/grammar_rules.json` — check if test fixtures exist or if files need to be present)
    - Create `PipelineOrchestrator` with mocked models → start → feed audio → verify:
      1. `on_asr_ready` fires with plain text (fast preview)
      2. `on_sentence_ready` fires with `SentenceResult` containing `AnalysisResult` with vocab_hits/grammar_hits
      3. Sentence has `sentence_id` (DB persisted) and `highlight_vocab_ids`/`highlight_grammar_ids`
    - Test overlay state transitions:
      1. LIVE mode: sentence arrives → displayed in `_jp_browser` with highlights
      2. Navigate prev → BROWSE mode → `_preview_browser` visible
      3. New sentence arrives → preview updated, browse position kept
      4. Navigate next to latest → LIVE mode → `_preview_browser` hidden
    - Test tooltip routing:
      1. Simulate hover on `_jp_browser` → `highlight_hovered` emitted with `_current_result`
      2. Simulate hover on `_preview_browser` → `highlight_hovered` emitted with `_latest_result`
    - Test edge cases:
      - First sentence ever (history was empty)
      - Rapid consecutive sentences (queue not backing up)
      - Empty analysis result (text with no JLPT-level words)

  **Must NOT do**:
  - DO NOT require actual GPU/model files — mock ASR and VAD
  - DO NOT require Windows (WASAPI) — mock audio capture
  - DO NOT test audio capture itself — only pipeline → overlay flow
  - DO NOT test tooltip popup rendering — only signal emission

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Complex integration test spanning pipeline threading, overlay state machine, and signal flow — requires careful setup and teardown
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - None needed

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 3 (after Task 7)
  - **Blocks**: F1-F4
  - **Blocked By**: Task 7

  **References**:

  **Pattern References**:
  - `tests/conftest.py` — Check for `qapp` fixture, test DB setup, mock patterns
  - `tests/test_asr_worker.py` — Check for existing QThread test patterns (signal spying, mock models)
  - `tests/test_overlay.py` — Check for existing overlay test patterns (widget instantiation, signal connection)

  **API/Type References**:
  - `src/pipeline/orchestrator.py` (after Task 4) — Full API: `__init__(config)`, `connect_signals(on_asr_ready, on_sentence_ready)`, `start()`, `stop()`
  - `src/ui/overlay.py` (after Task 5) — `on_sentence_ready(SentenceResult)`, `on_asr_ready(ASRResult)`, `_browsing`, `_preview_browser`, `highlight_hovered` signal
  - `src/asr/qwen_asr.py:QwenASR.transcribe_batch()` — Need to know signature for mocking
  - `src/vad/silero.py:SileroVAD` — Need to know interface for mocking

  **Test Data References**:
  - `data/jlpt_vocab.json` — Required by PreprocessingPipeline. Check if test fixtures mock this or if the real file is needed.
  - `data/grammar_rules.json` — Same as above.
  - `dev/` — Check for test audio files or test data that could be reused.

  **WHY Each Reference Matters**:
  - `conftest.py` → Reuse existing test infrastructure (Qt fixtures, DB setup)
  - `orchestrator.py` → Full API to exercise in integration test
  - `overlay.py` → State machine to verify transitions
  - Mock interfaces → Need exact method signatures to create proper mocks

  **Acceptance Criteria**:

  **TDD:**
  - [ ] Test file: `tests/test_integration_pipeline_overlay.py`
  - [ ] `pytest tests/test_integration_pipeline_overlay.py -x` → PASS

  **QA Scenarios:**

  ```
  Scenario: End-to-end pipeline produces SentenceResult with analysis
    Tool: Bash (pytest)
    Preconditions: All previous tasks complete, mocked models available
    Steps:
      1. Run `pytest tests/test_integration_pipeline_overlay.py::test_pipeline_produces_sentence_result -x -v`
      2. Verify: mock ASR text → PreprocessingPipeline → SentenceResult with non-None analysis
    Expected Result: SentenceResult emitted via sentence_ready signal with vocab_hits and grammar_hits
    Failure Indicators: Signal never emitted, analysis is None, missing highlight IDs
    Evidence: .sisyphus/evidence/task-8-e2e-sentence-result.txt

  Scenario: Overlay state transitions work end-to-end
    Tool: Bash (pytest)
    Preconditions: Overlay connected to pipeline signals
    Steps:
      1. Run `pytest tests/test_integration_pipeline_overlay.py::test_overlay_state_transitions -x -v`
      2. Verify: sentence arrives → LIVE mode → prev → BROWSE → new sentence → preview updated → next to latest → LIVE
    Expected Result: All state transitions correct, preview browser visibility toggles correctly
    Failure Indicators: State stuck in BROWSE, preview not updating, collapse not working
    Evidence: .sisyphus/evidence/task-8-state-transitions.txt

  Scenario: Tooltip routing across both browsers in integration
    Tool: Bash (pytest)
    Preconditions: Overlay in BROWSE mode with different sentences in each browser
    Steps:
      1. Run `pytest tests/test_integration_pipeline_overlay.py::test_tooltip_routing_integration -x -v`
      2. Verify: hover main → signal with _current_result, hover preview → signal with _latest_result
    Expected Result: Each browser emits correct SentenceResult in signal
    Failure Indicators: Same result for both, wrong result, signal not emitted
    Evidence: .sisyphus/evidence/task-8-tooltip-routing.txt

  Scenario: Edge case — empty analysis (no JLPT words)
    Tool: Bash (pytest)
    Preconditions: ASR returns text with no JLPT-level vocabulary
    Steps:
      1. Run `pytest tests/test_integration_pipeline_overlay.py::test_empty_analysis -x -v`
      2. Verify: SentenceResult has analysis with empty vocab_hits/grammar_hits, overlay still displays text
    Expected Result: Graceful handling, text displayed without highlights
    Failure Indicators: Crash, blank display, None analysis
    Evidence: .sisyphus/evidence/task-8-empty-analysis.txt
  ```

  **Commit**: YES (groups with Commit 6)
  - Message: `feat(main): wire analysis pipeline to overlay with full signal flow`
  - Files: `tests/test_integration_pipeline_overlay.py`
  - Pre-commit: `pytest tests/ -x -q && ruff check . && mypy src/`

---

## Final Verification Wave

> 4 review agents run in PARALLEL. ALL must APPROVE. Rejection → fix → re-run.

- [ ] F1. **Plan Compliance Audit** — `oracle`
  Read the plan end-to-end. For each "Must Have": verify implementation exists (read file, run command). For each "Must NOT Have": search codebase for forbidden patterns — reject with file:line if found. Check evidence files exist in .sisyphus/evidence/. Compare deliverables against plan.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [ ] F2. **Code Quality Review** — `unspecified-high`
  Run `ruff check . && ruff format --check . && mypy src/ && pytest tests/ -x -q`. Review all changed files for: `type: ignore`, empty catches, `print()` in prod, commented-out code, unused imports. Check AI slop: excessive comments, over-abstraction, generic names.
  Output: `Lint [PASS/FAIL] | Types [PASS/FAIL] | Tests [N pass/N fail] | Files [N clean/N issues] | VERDICT`

- [ ] F3. **Real Manual QA** — `unspecified-high`
  Start from clean state. Execute EVERY QA scenario from EVERY task — follow exact steps, capture evidence. Test cross-task integration (analysis → overlay → tooltip → navigation). Test edge cases: empty history, rapid sentence arrival, browse during new sentence. Save to `.sisyphus/evidence/final-qa/`.
  Output: `Scenarios [N/N pass] | Integration [N/N] | Edge Cases [N tested] | VERDICT`

- [ ] F4. **Scope Fidelity Check** — `deep`
  For each task: read "What to do", read actual diff (git log/diff). Verify 1:1 — everything in spec was built (no missing), nothing beyond spec was built (no creep). Check "Must NOT do" compliance. Detect cross-task contamination. Flag unaccounted changes.
  Output: `Tasks [N/N compliant] | Contamination [CLEAN/N issues] | Unaccounted [CLEAN/N files] | VERDICT`

---

## Commit Strategy

| Commit | Scope | Message | Files | Pre-commit |
|--------|-------|---------|-------|------------|
| 1 | T1 | `feat(pipeline): add AnalysisWorker QThread for JLPT analysis` | analysis_worker.py, test_analysis_worker.py | `pytest tests/test_analysis_worker.py -x` |
| 2 | T2 | `refactor(config): remove deprecated overlay_display_mode` | config.py, test_config.py | `pytest tests/ -x -q` |
| 3 | T3 | `feat(ui): add dual-display state machine to overlay` | overlay.py, test_overlay.py | `pytest tests/test_overlay.py -x` |
| 4 | T4+T6 | `feat(pipeline): integrate AnalysisWorker into orchestrator` | orchestrator.py, asr_worker.py, test_orchestrator.py | `pytest tests/ -x -q` |
| 5 | T5 | `feat(ui): dual-browser independent tooltip routing` | overlay.py, test_overlay.py | `pytest tests/test_overlay.py -x` |
| 6 | T7+T8 | `feat(main): wire analysis pipeline to overlay with full signal flow` | main.py, test files | `pytest tests/ -x -q && ruff check . && mypy src/` |

---

## Success Criteria

### Verification Commands
```bash
pytest tests/ -x -q              # Expected: all pass, 0 failures
ruff check . && ruff format --check .  # Expected: no errors
mypy src/                        # Expected: Success
```

### Final Checklist
- [ ] All "Must Have" present
- [ ] All "Must NOT Have" absent
- [ ] All tests pass
- [ ] Prev/Next buttons work with highlighted text
- [ ] Preview box shows latest sentence during browse
- [ ] Collapse to single display when reaching latest
- [ ] Tooltips work on both text boxes independently
- [ ] No duplicate DB rows (insert_partial removed)
