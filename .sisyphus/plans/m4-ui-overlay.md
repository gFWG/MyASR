# Milestone 4 — UI Overlay

## TL;DR

> **Quick Summary**: Build the PySide6 transparent overlay UI with JLPT-colored highlights, hover tooltips, and main entry point. Includes two pre-requisite upstream fixes (adding position data to models, reordering pipeline signal emission after DB write).
> 
> **Deliverables**:
> - `src/db/models.py` — Updated VocabHit/GrammarHit/SentenceResult with position fields + sentence_id
> - `src/analysis/jlpt_vocab.py`, `src/analysis/grammar.py` — Updated to populate start_pos/end_pos
> - `src/analysis/pipeline.py` — Updated to pass positions through
> - `src/pipeline.py` — Updated to emit sentence_ready AFTER DB write (with sentence_id + highlight IDs)
> - `src/ui/highlight.py` — HighlightRenderer (JLPT color spans, grammar>vocab priority, position lookup)
> - `src/ui/overlay.py` — OverlayWindow (transparent, frameless, draggable, two-line display, Ctrl+T toggle)
> - `src/ui/tooltip.py` — TooltipPopup (rounded corners, vocab/grammar display, dedup recording)
> - `src/main.py` — Entry point wiring everything together
> - Updated tests for all modified and new modules
> 
> **Estimated Effort**: Medium-Large
> **Parallel Execution**: YES — 3 waves
> **Critical Path**: Task 1 (models) → Task 2a/2b (upstream fixes) → Task 3 (pipeline fix) → Task 4 (highlight) → Task 5 (overlay) → Task 6 (tooltip) → Task 7 (main.py)

---

## Context

### Original Request
Complete all tasks under Milestone 4 — UI Overlay: HighlightRenderer, OverlayWindow, TooltipPopup, and main.py entry point.

### Interview Summary
**Key Discussions**:
- WSL/Windows: WSL-only testing via WSLg. README note for Windows adjustments.
- Toggle shortcut: Hard-coded Ctrl+T for M4. Configurable in P1.
- Overlay position: Bottom-center default, no persistence. Draggable per session.
- Design: Windows-native feel — Fluent Design, Segoe UI, semi-transparent dark background, standard shadows.
- Test strategy: Mock-based unit tests (WSLg QTest optional).

**Research Findings**:
- PySide6 overlay: `Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool` + `WA_TranslucentBackground` + `WA_ShowWithoutActivating`
- Qt6 dragging: `event.globalPosition().toPoint()` (NOT deprecated `globalPos()`)
- Hover detection: QTextBrowser with `cursorForPosition()` — QLabel cannot detect per-span hover
- WSLg supports PySide6 + transparency. Fallback: `QT_QPA_PLATFORM=xcb`
- Qt6 Per-Monitor DPI V2 by default on Windows 11

### Metis Review
**Identified Gaps** (addressed):
- **Position mapping**: VocabHit/GrammarHit have no start_pos/end_pos → Added as pre-requisite Task 1+2
- **Tooltip DB IDs**: UI receives SentenceResult without DB IDs → Reorder pipeline to emit after DB write (Task 3) 
- **Hover detection**: QLabel can't detect per-span hover → Use QTextBrowser with cursorForPosition() (Task 5)
- **Focus stealing**: Overlay could steal focus from active app → Add `WA_ShowWithoutActivating` (Task 5)

---

## Work Objectives

### Core Objective
Build a transparent PySide6 overlay that displays JLPT-color-highlighted Japanese text with Chinese translation, hover tooltips for vocabulary/grammar explanations, and automatic learning record persistence.

### Concrete Deliverables
- Updated data models with position fields (`VocabHit.start_pos/end_pos`, `GrammarHit.start_pos/end_pos`, `SentenceResult.sentence_id`)
- Updated analysis modules populating position data
- Updated pipeline worker emitting after DB write
- `src/ui/highlight.py` — HighlightRenderer
- `src/ui/overlay.py` — OverlayWindow
- `src/ui/tooltip.py` — TooltipPopup
- `src/main.py` — Application entry point
- Tests for all new and modified modules

### Definition of Done
- [ ] `ruff check . && ruff format --check . && mypy . && pytest -x --tb=short` passes
- [ ] `python -c "from src.main import main"` imports cleanly
- [ ] All existing M0-M3 tests still pass (no regressions)

### Must Have
- Transparent frameless overlay, always-on-top, no taskbar entry
- JLPT color highlighting per api-data.md scheme (N4 green, N3 blue, N2 yellow, N1 red)
- Grammar priority over vocab when overlapping
- Hover tooltip showing JLPT level + description
- Tooltip-triggered DB recording with per-sentence deduplication
- Two display modes (two-line JP/CN and single-line toggle via Ctrl+T)
- Status indicators: "Initializing...", "No speech detected", "Translation unavailable"
- Draggable overlay (mouse drag)
- Bottom-center default position
- Clean shutdown (stop pipeline, close DB, exit gracefully)

### Must NOT Have (Guardrails)
- NO Settings panel UI (P1 scope)
- NO Learning panel / history viewer (P1 scope)
- NO position persistence between sessions
- NO configurable shortcut keys (hard-coded Ctrl+T only)
- NO configurable fonts/colors (hard-coded defaults)
- NO streaming/real-time character display (batch sentence display only)
- NO `@ts-ignore` or `type: ignore` without explicit justification comment
- NO bare `except:` clauses — always catch specific exceptions
- NO `print()` for logging — use `logging.getLogger(__name__)`
- NO deprecated Qt5 API (`globalPos()`, `exec_()`) — use Qt6 equivalents

---

## Verification Strategy (MANDATORY)

> **ZERO HUMAN INTERVENTION** — ALL verification is agent-executed. No exceptions.

### Test Decision
- **Infrastructure exists**: YES
- **Automated tests**: YES (Tests-after — write implementation, then tests)
- **Framework**: pytest (configured in pyproject.toml)
- **Test approach**: Mock-based unit tests for UI components. PySide6 QApplication initialized in conftest.py fixture. Signal/slot behavior tested via mock connections.

### QA Policy
Every task MUST include agent-executed QA scenarios.
Evidence saved to `.sisyphus/evidence/task-{N}-{scenario-slug}.{ext}`.

- **UI Components**: Use `QT_QPA_PLATFORM=offscreen` for headless testing via pytest
- **Logic modules**: Use Bash (python/pytest) — import, call functions, verify output
- **Integration**: Use pytest with mocked pipeline components

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Start Immediately — model + upstream fixes):
├── Task 1: Update data models (add position fields + sentence_id) [quick]
├── Task 2a: Update grammar.py to populate start_pos/end_pos [quick]
├── Task 2b: Update jlpt_vocab.py to populate start_pos/end_pos [quick]
└── Task 2c: Update analysis/pipeline.py to pass positions through [quick]

Wave 2 (After Wave 1 — pipeline fix + UI core):
├── Task 3: Update pipeline.py — emit after DB write with IDs [unspecified-high]
├── Task 4: Implement HighlightRenderer [unspecified-high]
└── Task 5: Implement OverlayWindow [unspecified-high]

Wave 3 (After Wave 2 — tooltip + entry point):
├── Task 6: Implement TooltipPopup [unspecified-high]
└── Task 7: Create main.py entry point [unspecified-high]

Wave FINAL (After ALL tasks — verification):
├── Task F1: Plan compliance audit [deep]
├── Task F2: Code quality review [unspecified-high]
├── Task F3: Integration QA [unspecified-high]
└── Task F4: Scope fidelity check [deep]

Critical Path: Task 1 → Task 2a → Task 3 → Task 4 → Task 5 → Task 6 → Task 7 → F1-F4
Parallel Speedup: ~40% faster than sequential
Max Concurrent: 4 (Wave 1)
```

### Dependency Matrix

| Task | Depends On | Blocks | Wave |
|------|-----------|--------|------|
| 1 | — | 2a, 2b, 2c, 3, 4, 5, 6 | 1 |
| 2a | 1 | 3, 4 | 1 |
| 2b | 1 | 3, 4 | 1 |
| 2c | 1, 2a, 2b | 3, 4 | 1 |
| 3 | 2c | 5, 6, 7 | 2 |
| 4 | 2c | 5, 6 | 2 |
| 5 | 3, 4 | 6, 7 | 2 |
| 6 | 4, 5 | 7 | 3 |
| 7 | 3, 5, 6 | F1-F4 | 3 |
| F1-F4 | 7 | — | FINAL |

### Agent Dispatch Summary

- **Wave 1**: **4 tasks** — T1 → `quick`, T2a → `quick`, T2b → `quick`, T2c → `quick`
- **Wave 2**: **3 tasks** — T3 → `unspecified-high`, T4 → `unspecified-high`, T5 → `unspecified-high`
- **Wave 3**: **2 tasks** — T6 → `unspecified-high`, T7 → `unspecified-high`
- **FINAL**: **4 tasks** — F1 → `deep`, F2 → `unspecified-high`, F3 → `unspecified-high`, F4 → `deep`

---

## TODOs

- [ ] 1. Update data models — add position fields and sentence_id

  **What to do**:
  - Add `start_pos: int` and `end_pos: int` fields to `VocabHit` dataclass in `src/db/models.py`
  - Add `start_pos: int` and `end_pos: int` fields to `GrammarHit` dataclass in `src/db/models.py`
  - Add `sentence_id: int | None = None` field to `SentenceResult` dataclass in `src/db/models.py`
  - Add `highlight_vocab_ids: list[int] | None = None` and `highlight_grammar_ids: list[int] | None = None` fields to `SentenceResult` to carry DB-assigned IDs for tooltip recording
  - Update all existing call sites that construct `VocabHit` and `GrammarHit` to provide the new position fields (search with `lsp_find_references` or `grep`)
  - Update tests that construct these dataclasses to include the new fields
  - Ensure all existing tests still pass after model changes

  **Must NOT do**:
  - Do NOT change the database schema (highlight_vocab/highlight_grammar tables) — positions are runtime-only for UI rendering, not persisted
  - Do NOT change HighlightVocab or HighlightGrammar DB models — these are separate from the pipeline dataclasses

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Small dataclass field additions with straightforward ripple updates
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - `playwright`: No browser interaction needed

  **Parallelization**:
  - **Can Run In Parallel**: NO (must complete before 2a, 2b, 2c)
  - **Parallel Group**: Wave 1 — starts first
  - **Blocks**: Tasks 2a, 2b, 2c, 3, 4, 5, 6
  - **Blocked By**: None (can start immediately)

  **References**:

  **Pattern References**:
  - `src/db/models.py` — VocabHit (line ~24), GrammarHit (line ~32), SentenceResult (line ~44): Current dataclass definitions to modify
  
  **API/Type References**:
  - `src/db/models.py:AnalysisResult` — Contains `vocab_hits: list[VocabHit]` and `grammar_hits: list[GrammarHit]` — verify these still work after field additions

  **Test References**:
  - `tests/test_jlpt_vocab.py` — Constructs VocabHit instances, must add start_pos/end_pos
  - `tests/test_grammar.py` — Constructs GrammarHit instances, must add start_pos/end_pos
  - `tests/test_analysis_pipeline.py` — End-to-end pipeline test, verify still passes

  **WHY Each Reference Matters**:
  - models.py is THE source of truth for all dataclasses. Every downstream consumer must be updated.
  - Tests construct these dataclasses directly — they'll fail with TypeError if new required fields aren't provided.

  **Acceptance Criteria**:

  - [ ] `VocabHit` has `start_pos: int` and `end_pos: int` fields
  - [ ] `GrammarHit` has `start_pos: int` and `end_pos: int` fields
  - [ ] `SentenceResult` has `sentence_id: int | None = None`, `highlight_vocab_ids: list[int] | None = None`, `highlight_grammar_ids: list[int] | None = None`
  - [ ] `mypy src/db/models.py` passes
  - [ ] `pytest -x --tb=short` — all existing tests still pass

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: VocabHit construction with positions
    Tool: Bash (python)
    Preconditions: Virtual environment activated
    Steps:
      1. Run: python -c "from src.db.models import VocabHit; v = VocabHit(surface='食べる', lemma='食べる', pos='動詞', jlpt_level=5, user_level=3, start_pos=0, end_pos=3); print(f'pos={v.start_pos}-{v.end_pos}')"
      2. Assert output contains: "pos=0-3"
    Expected Result: VocabHit instantiates with start_pos=0, end_pos=3
    Failure Indicators: TypeError (unexpected keyword argument) or AttributeError
    Evidence: .sisyphus/evidence/task-1-vocabhit-positions.txt

  Scenario: SentenceResult with sentence_id defaults to None
    Tool: Bash (python)
    Preconditions: Virtual environment activated
    Steps:
      1. Run: python -c "from src.db.models import SentenceResult, AnalysisResult; r = SentenceResult(japanese_text='test', chinese_translation=None, explanation=None, analysis=AnalysisResult(tokens=[], vocab_hits=[], grammar_hits=[])); print(f'id={r.sentence_id}, vids={r.highlight_vocab_ids}')"
      2. Assert output contains: "id=None, vids=None"
    Expected Result: sentence_id and highlight IDs default to None
    Evidence: .sisyphus/evidence/task-1-sentenceresult-defaults.txt

  Scenario: Existing tests pass without regression
    Tool: Bash (pytest)
    Preconditions: Virtual environment activated
    Steps:
      1. Run: pytest -x --tb=short
      2. Assert exit code 0
    Expected Result: All existing tests pass
    Failure Indicators: Any test failure mentioning VocabHit, GrammarHit, or SentenceResult
    Evidence: .sisyphus/evidence/task-1-regression.txt
  ```

  **Commit**: YES (groups with 2a, 2b, 2c)
  - Message: `feat(models): add position fields to VocabHit/GrammarHit and sentence_id to SentenceResult`
  - Files: `src/db/models.py`, `tests/test_jlpt_vocab.py`, `tests/test_grammar.py`, `tests/test_analysis_pipeline.py`
  - Pre-commit: `ruff check . && mypy . && pytest -x`

- [ ] 2a. Update grammar.py — populate start_pos/end_pos from regex matches

  **What to do**:
  - In `GrammarMatcher.match()`, the `pattern.finditer(text)` loop already has `m.start()` and `m.end()`. Pass these as `start_pos=m.start()` and `end_pos=m.end()` when constructing `GrammarHit`.
  - Update tests in `tests/test_grammar.py` to verify position fields are populated correctly

  **Must NOT do**:
  - Do NOT change the regex patterns or matching logic — only add position population

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Single-line additions in existing method + test updates
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES — with 2b (after Task 1 completes)
  - **Parallel Group**: Wave 1 (with Tasks 2b, 2c — but 2c depends on 2a+2b)
  - **Blocks**: Tasks 2c, 3, 4
  - **Blocked By**: Task 1

  **References**:

  **Pattern References**:
  - `src/analysis/grammar.py` — `GrammarMatcher.match()` method: look for `finditer()` loop where `GrammarHit` is constructed. `m.start()` and `m.end()` are already available from the regex match object.

  **Test References**:
  - `tests/test_grammar.py` — Existing grammar tests. Add assertions for `hit.start_pos` and `hit.end_pos` on matched patterns.

  **WHY Each Reference Matters**:
  - grammar.py already does finditer() — the position data EXISTS but isn't stored. This is a 2-line change.
  - Tests must verify the positions match the actual regex match locations.

  **Acceptance Criteria**:

  - [ ] `GrammarHit` instances from `GrammarMatcher.match()` have correct `start_pos` and `end_pos` corresponding to regex match positions
  - [ ] Tests verify: for known input text and pattern, start_pos/end_pos match expected character offsets
  - [ ] `mypy src/analysis/grammar.py` passes
  - [ ] `pytest tests/test_grammar.py -x` passes

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Grammar match returns correct positions
    Tool: Bash (python)
    Preconditions: Virtual environment activated, grammar_rules.json exists with test patterns
    Steps:
      1. Run: python -c "
from src.analysis.grammar import GrammarMatcher
gm = GrammarMatcher('data/grammar_rules.json')
hits = gm.match('これは食べている', user_level=5)
for h in hits:
    print(f'{h.matched_text} at {h.start_pos}-{h.end_pos}')
"
      2. Assert each hit's start_pos/end_pos correspond to the actual character positions of matched_text in the input string
      3. For each hit: verify input_text[hit.start_pos:hit.end_pos] == hit.matched_text
    Expected Result: All hits have correct positions matching their text location
    Failure Indicators: start_pos/end_pos are 0/0 or don't match actual positions
    Evidence: .sisyphus/evidence/task-2a-grammar-positions.txt

  Scenario: Grammar tests pass
    Tool: Bash (pytest)
    Steps:
      1. Run: pytest tests/test_grammar.py -x --tb=short
      2. Assert exit code 0
    Expected Result: All grammar tests pass including new position assertions
    Evidence: .sisyphus/evidence/task-2a-grammar-tests.txt
  ```

  **Commit**: YES (groups with 1, 2b, 2c)
  - Files: `src/analysis/grammar.py`, `tests/test_grammar.py`
  - Pre-commit: `ruff check . && mypy . && pytest tests/test_grammar.py -x`

- [ ] 2b. Update jlpt_vocab.py — populate start_pos/end_pos from token positions

  **What to do**:
  - In `JLPTVocabLookup.find_beyond_level()`, the method receives `list[Token]` but Token has no position info. Two approaches:
    1. **Preferred**: Change `find_beyond_level` signature to accept the original text as well: `find_beyond_level(self, tokens: list[Token], user_level: int, text: str) -> list[VocabHit]`. Use `text.find(token.surface, search_start)` to calculate positions sequentially, advancing search_start after each token to handle duplicates.
    2. Alternative: Add start_pos/end_pos to Token dataclass and populate in tokenizer.
  - Update `PreprocessingPipeline.process()` in `src/analysis/pipeline.py` to pass `text` to `find_beyond_level()` (or update Token if using alternative approach)
  - Update tests to verify position fields

  **Must NOT do**:
  - Do NOT change the JLPT lookup logic itself (level comparison)
  - Do NOT break the existing `find_beyond_level` API for callers that don't need positions — use `text: str = ""` default parameter if needed

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Small signature change + position calculation logic
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES — with 2a (after Task 1 completes)
  - **Parallel Group**: Wave 1 (with Task 2a)
  - **Blocks**: Tasks 2c, 3, 4
  - **Blocked By**: Task 1

  **References**:

  **Pattern References**:
  - `src/analysis/jlpt_vocab.py` — `JLPTVocabLookup.find_beyond_level()`: Currently receives tokens and user_level. Constructs VocabHit with surface/lemma/pos/jlpt_level/user_level but no positions.
  - `src/analysis/pipeline.py` — `PreprocessingPipeline.process()`: Calls `self._vocab.find_beyond_level(tokens, self._config.user_jlpt_level)` — must add `text` argument.

  **Test References**:
  - `tests/test_jlpt_vocab.py` — Existing vocab tests. Add position verification.
  - `tests/test_analysis_pipeline.py` — Pipeline end-to-end test. Verify VocabHit positions in pipeline output.

  **WHY Each Reference Matters**:
  - jlpt_vocab.py needs text to calculate positions — token.surface alone doesn't tell you WHERE in the original string the token appeared.
  - pipeline.py is the caller that must pass text to the updated method.

  **Acceptance Criteria**:

  - [ ] `find_beyond_level` populates `start_pos` and `end_pos` on every returned `VocabHit`
  - [ ] For a known input text, positions are correct: `text[hit.start_pos:hit.end_pos] == hit.surface`
  - [ ] Duplicate words get different positions (e.g., "食べる" appearing twice gets distinct start_pos values)
  - [ ] `mypy src/analysis/jlpt_vocab.py` passes
  - [ ] `pytest tests/test_jlpt_vocab.py -x` passes

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Vocab hits have correct positions
    Tool: Bash (python)
    Preconditions: Virtual environment activated, jlpt_vocab.json exists
    Steps:
      1. Run: python -c "
from src.analysis.tokenizer import FugashiTokenizer
from src.analysis.jlpt_vocab import JLPTVocabLookup
tok = FugashiTokenizer()
vocab = JLPTVocabLookup('data/jlpt_vocab.json')
text = '彼は食べている'
tokens = tok.tokenize(text)
hits = vocab.find_beyond_level(tokens, user_level=5, text=text)
for h in hits:
    print(f'{h.surface} at {h.start_pos}-{h.end_pos}, verify: {text[h.start_pos:h.end_pos]}')
"
      2. Assert each hit's text[start_pos:end_pos] equals hit.surface
    Expected Result: All vocab hits have positions that correctly index into the original text
    Failure Indicators: IndexError, or text[start:end] doesn't match surface
    Evidence: .sisyphus/evidence/task-2b-vocab-positions.txt

  Scenario: Existing vocab tests pass
    Tool: Bash (pytest)
    Steps:
      1. Run: pytest tests/test_jlpt_vocab.py -x --tb=short
      2. Assert exit code 0
    Expected Result: All vocab tests pass
    Evidence: .sisyphus/evidence/task-2b-vocab-tests.txt
  ```

  **Commit**: YES (groups with 1, 2a, 2c)
  - Files: `src/analysis/jlpt_vocab.py`, `tests/test_jlpt_vocab.py`
  - Pre-commit: `ruff check . && mypy . && pytest tests/test_jlpt_vocab.py -x`

- [ ] 2c. Update analysis pipeline — pass text to vocab lookup and verify positions flow through

  **What to do**:
  - In `PreprocessingPipeline.process()`, update the call to `self._vocab.find_beyond_level()` to pass the `text` parameter
  - Verify that the returned `AnalysisResult` contains `VocabHit` and `GrammarHit` instances with populated `start_pos`/`end_pos`
  - Update `tests/test_analysis_pipeline.py` to assert position fields are present and correct in pipeline output

  **Must NOT do**:
  - Do NOT change pipeline logic beyond adding the `text` parameter

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: One-line caller update + test assertion additions
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO — depends on 2a and 2b completing first
  - **Parallel Group**: Wave 1 (after 2a + 2b)
  - **Blocks**: Tasks 3, 4
  - **Blocked By**: Tasks 1, 2a, 2b

  **References**:

  **Pattern References**:
  - `src/analysis/pipeline.py` — `PreprocessingPipeline.process()`: The main caller of both `GrammarMatcher.match()` and `JLPTVocabLookup.find_beyond_level()`. Update the vocab call to include `text=text`.

  **Test References**:
  - `tests/test_analysis_pipeline.py` — End-to-end pipeline test. Add assertions that `result.vocab_hits[*].start_pos` and `result.grammar_hits[*].start_pos` are populated.

  **Acceptance Criteria**:

  - [ ] `PreprocessingPipeline.process(text)` returns `AnalysisResult` with position-populated hits
  - [ ] `mypy src/analysis/pipeline.py` passes
  - [ ] `pytest tests/test_analysis_pipeline.py -x` passes
  - [ ] Full test suite passes: `pytest -x --tb=short`

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Pipeline produces positioned hits end-to-end
    Tool: Bash (python)
    Preconditions: Virtual environment activated
    Steps:
      1. Run: python -c "
from src.config import AppConfig
from src.analysis.pipeline import PreprocessingPipeline
p = PreprocessingPipeline(AppConfig())
result = p.process('彼は食べている')
for vh in result.vocab_hits:
    print(f'V: {vh.surface} at {vh.start_pos}-{vh.end_pos}')
for gh in result.grammar_hits:
    print(f'G: {gh.matched_text} at {gh.start_pos}-{gh.end_pos}')
"
      2. Assert all hits have non-negative start_pos and end_pos > start_pos
    Expected Result: Both vocab and grammar hits have populated positions
    Failure Indicators: AttributeError on start_pos/end_pos, or positions are 0-0
    Evidence: .sisyphus/evidence/task-2c-pipeline-positions.txt

  Scenario: Full regression test
    Tool: Bash (pytest)
    Steps:
      1. Run: pytest -x --tb=short
      2. Assert exit code 0
    Expected Result: All tests pass (M0-M3 + updated pipeline tests)
    Evidence: .sisyphus/evidence/task-2c-regression.txt
  ```

  **Commit**: YES (groups with 1, 2a, 2b — single commit for all Wave 1)
  - Message: `feat(models): add position fields to VocabHit/GrammarHit and sentence_id to SentenceResult`
  - Files: `src/db/models.py`, `src/analysis/grammar.py`, `src/analysis/jlpt_vocab.py`, `src/analysis/pipeline.py`, `tests/test_grammar.py`, `tests/test_jlpt_vocab.py`, `tests/test_analysis_pipeline.py`
  - Pre-commit: `ruff check . && mypy . && pytest -x`

- [ ] 3. Update PipelineWorker — emit sentence_ready AFTER DB write with assigned IDs

  **What to do**:
  - In `PipelineWorker.run()`, currently the flow is: process → emit `sentence_ready(result)` → write to DB. Reorder to: process → write to DB → populate `result.sentence_id` and `result.highlight_vocab_ids` / `result.highlight_grammar_ids` from the DB insert return values → emit `sentence_ready(result)`.
  - `LearningRepository.insert_sentence()` already returns the sentence_id (int). Need to also return the inserted highlight IDs. Update `insert_sentence()` to return `tuple[int, list[int], list[int]]` — `(sentence_id, vocab_ids, grammar_ids)` using `cursor.lastrowid` after each highlight insert.
  - Update `_to_db_records()` to use the new position data from VocabHit/GrammarHit when constructing HighlightVocab/HighlightGrammar
  - When `db_conn` is None (no DB), emit with `sentence_id=None` and empty ID lists (graceful degradation)
  - Update tests: verify signal is emitted with populated IDs when DB is connected, and with None when DB is not connected

  **Must NOT do**:
  - Do NOT change the pipeline processing logic (Audio → VAD → ASR → Preprocessing → LLM)
  - Do NOT add new signals — reuse existing `sentence_ready` signal
  - Do NOT make DB write blocking on the main thread — it already runs in the QThread worker

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Touches pipeline orchestration (signal ordering) and DB layer (return type change) — needs careful understanding of both
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO — depends on Wave 1 completing
  - **Parallel Group**: Wave 2 (with Tasks 4, 5 — but 5 depends on 3)
  - **Blocks**: Tasks 5, 6, 7
  - **Blocked By**: Tasks 2c (needs position fields in models)

  **References**:

  **Pattern References**:
  - `src/pipeline.py:PipelineWorker.run()` — Main processing loop. Look for `self.sentence_ready.emit(result)` and `self._repo.insert_sentence()`. Currently emit happens BEFORE DB write — reverse the order.
  - `src/pipeline.py:PipelineWorker._to_db_records()` — Converts SentenceResult to DB models. Already maps VocabHit→HighlightVocab and GrammarHit→HighlightGrammar. Verify it handles new position fields (positions are NOT stored in DB, so just skip them in conversion).

  **API/Type References**:
  - `src/db/repository.py:LearningRepository.insert_sentence()` — Currently returns `int` (sentence_id). Must change to return `tuple[int, list[int], list[int]]`.
  - `src/db/models.py:SentenceResult` — Has new `sentence_id`, `highlight_vocab_ids`, `highlight_grammar_ids` fields (from Task 1).

  **Test References**:
  - `tests/test_pipeline.py` — Extensive pipeline tests with mocked components. Look at how `sentence_ready` signal is tested — update to verify IDs are populated.
  - `tests/test_db_repository.py` — Existing insert_sentence tests. Update to verify return type includes highlight IDs.

  **WHY Each Reference Matters**:
  - The signal emission reorder is critical — the UI needs DB IDs to call mark_tooltip_shown(). Without this change, tooltip recording is impossible.
  - repository.py return type change is a contract change that affects both pipeline.py and its tests.

  **Acceptance Criteria**:

  - [ ] `insert_sentence()` returns `tuple[int, list[int], list[int]]` — (sentence_id, vocab_ids, grammar_ids)
  - [ ] `sentence_ready` signal is emitted AFTER DB write (not before)
  - [ ] Emitted `SentenceResult` has `sentence_id` populated when DB is connected
  - [ ] Emitted `SentenceResult` has `highlight_vocab_ids` and `highlight_grammar_ids` populated
  - [ ] When `db_conn=None`, emitted result has `sentence_id=None` (graceful degradation)
  - [ ] `mypy src/pipeline.py src/db/repository.py` passes
  - [ ] `pytest tests/test_pipeline.py tests/test_db_repository.py -x` passes

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Pipeline emits result with DB IDs
    Tool: Bash (pytest)
    Preconditions: Virtual environment activated
    Steps:
      1. Run: pytest tests/test_pipeline.py -x --tb=short -v
      2. Look for tests that verify sentence_ready signal emission
      3. Assert that emitted SentenceResult has sentence_id != None when DB is mocked
    Expected Result: Tests pass, signal carries populated IDs
    Failure Indicators: sentence_id is None when DB is connected, or signal emitted before DB write
    Evidence: .sisyphus/evidence/task-3-pipeline-ids.txt

  Scenario: Repository returns highlight IDs
    Tool: Bash (python)
    Preconditions: Virtual environment activated
    Steps:
      1. Run: python -c "
import sqlite3
from src.db.schema import init_db
from src.db.repository import LearningRepository
from src.db.models import SentenceRecord, HighlightVocab, HighlightGrammar
conn = init_db(':memory:')
repo = LearningRepository(conn)
rec = SentenceRecord(id=None, japanese_text='テスト', chinese_translation='测试', explanation=None, source_context=None, created_at='2024-01-01')
vocab = [HighlightVocab(id=None, sentence_id=0, surface='テスト', lemma='テスト', pos='名詞', jlpt_level=4, is_beyond_level=True, tooltip_shown=False)]
result = repo.insert_sentence(rec, vocab, [])
print(f'type={type(result)}, values={result}')
"
      2. Assert result is a tuple of (int, list[int], list[int])
      3. Assert sentence_id > 0 and vocab_ids has one element > 0
    Expected Result: insert_sentence returns tuple with valid IDs
    Failure Indicators: Returns bare int, or IDs are 0/None
    Evidence: .sisyphus/evidence/task-3-repo-ids.txt

  Scenario: Graceful degradation without DB
    Tool: Bash (pytest)
    Steps:
      1. Run: pytest tests/test_pipeline.py -k "no_db or without_db" -x --tb=short
      2. If no such test exists, verify in pipeline code that db_conn=None path emits with sentence_id=None
    Expected Result: Pipeline works without DB, emits results with None IDs
    Evidence: .sisyphus/evidence/task-3-no-db.txt
  ```

  **Commit**: YES
  - Message: `feat(pipeline): emit sentence_ready after DB write with assigned IDs`
  - Files: `src/pipeline.py`, `src/db/repository.py`, `tests/test_pipeline.py`, `tests/test_db_repository.py`
  - Pre-commit: `ruff check . && mypy . && pytest -x`

- [ ] 4. Implement HighlightRenderer

  **What to do**:
  - Create `src/ui/highlight.py` with class `HighlightRenderer`:
    - `JLPT_COLORS: dict` — Class-level constant mapping JLPT levels to color codes:
      ```
      {4: {"vocab": "#C8E6C9", "grammar": "#4CAF50"},
       3: {"vocab": "#BBDEFB", "grammar": "#1976D2"},
       2: {"vocab": "#FFF9C4", "grammar": "#F9A825"},
       1: {"vocab": "#FFCDD2", "grammar": "#D32F2F"}}
      ```
    - `build_rich_text(self, japanese_text: str, analysis: AnalysisResult, user_level: int) -> str`:
      - Return HTML string with `<span style="color: #hex; font-weight: bold;">` tags for highlighted segments
      - Grammar takes priority over vocab when ranges overlap (grammar span replaces any vocab spans it fully covers)
      - Non-highlighted text rendered without spans
      - Handle edge cases: empty text, no highlights, overlapping highlights
    - `get_highlight_at_position(self, position: int, analysis: AnalysisResult) -> VocabHit | GrammarHit | None`:
      - Given a character position, return the highlight (if any) at that position
      - Grammar priority: if both vocab and grammar cover the position, return grammar
      - Used by tooltip hover detection
  - Create `tests/test_highlight.py` with thorough tests:
    - Test color mapping for each JLPT level
    - Test grammar-over-vocab priority with overlapping ranges
    - Test position lookup with grammar priority
    - Test edge cases: empty text, no hits, adjacent non-overlapping highlights
    - Test HTML output is valid (parseable by basic HTML parser)

  **Must NOT do**:
  - Do NOT import or use any PySide6/Qt modules — this is PURE LOGIC, no UI dependency
  - Do NOT add custom fonts or styling beyond color — keep it minimal
  - Do NOT handle non-beyond-level tokens (only beyond-level vocab/grammar get highlighted)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Non-trivial interval-merging logic (grammar priority over vocab with overlapping ranges) + HTML generation
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES — with Task 3 (both depend on Wave 1, independent of each other)
  - **Parallel Group**: Wave 2 (with Tasks 3, 5 — but 5 depends on 3 and 4)
  - **Blocks**: Tasks 5, 6
  - **Blocked By**: Task 2c (needs position data in models)

  **References**:

  **Pattern References**:
  - `docs/api-data.md` lines 262-271 — JLPT color scheme table. Exact hex codes for each level/type.

  **API/Type References**:
  - `src/db/models.py:VocabHit` — Has `surface`, `start_pos`, `end_pos`, `jlpt_level`
  - `src/db/models.py:GrammarHit` — Has `matched_text`, `start_pos`, `end_pos`, `jlpt_level`
  - `src/db/models.py:AnalysisResult` — Contains `vocab_hits` and `grammar_hits` lists

  **Test References**:
  - `tests/test_grammar.py` — Example of how grammar test data is structured
  - `tests/test_jlpt_vocab.py` — Example of how vocab test data is structured

  **External References**:
  - Qt HTML subset: https://doc.qt.io/qt-6/richtext-html-subset.html — What HTML tags QTextBrowser supports

  **WHY Each Reference Matters**:
  - api-data.md has the EXACT color codes — do not guess or approximate
  - VocabHit/GrammarHit start_pos/end_pos are used to determine span boundaries in the text
  - Qt HTML subset determines what HTML tags are actually renderable — don't use unsupported tags

  **Acceptance Criteria**:

  - [ ] `HighlightRenderer.JLPT_COLORS` matches api-data.md exactly
  - [ ] `build_rich_text()` produces valid HTML with correct color spans
  - [ ] Grammar highlights take priority over overlapping vocab highlights
  - [ ] `get_highlight_at_position()` returns correct highlight (grammar priority)
  - [ ] Edge cases handled: empty text returns empty string, no hits returns plain text
  - [ ] `mypy src/ui/highlight.py` passes
  - [ ] `pytest tests/test_highlight.py -x` passes

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Rich text with grammar-over-vocab priority
    Tool: Bash (python)
    Preconditions: Virtual environment activated
    Steps:
      1. Run: python -c "
from src.ui.highlight import HighlightRenderer
from src.db.models import AnalysisResult, VocabHit, GrammarHit
renderer = HighlightRenderer()
# Create overlapping hits: vocab on '食べ' (0-2), grammar on '食べている' (0-5)
vocab = [VocabHit(surface='食べ', lemma='食べる', pos='動詞', jlpt_level=3, user_level=4, start_pos=0, end_pos=2)]
grammar = [GrammarHit(rule_id='g1', matched_text='食べている', jlpt_level=2, confidence_type='high', description='ている form', start_pos=0, end_pos=5)]
analysis = AnalysisResult(tokens=[], vocab_hits=vocab, grammar_hits=grammar)
html = renderer.build_rich_text('食べている', analysis, user_level=4)
print(html)
"
      2. Assert HTML contains grammar color (#F9A825 for N2 grammar) NOT vocab color (#BBDEFB for N3 vocab)
      3. Assert '食べている' is wrapped in a single grammar-colored span (not split)
    Expected Result: Grammar span covers entire matched text, vocab span suppressed
    Failure Indicators: Both colors present, or vocab color appears where grammar should
    Evidence: .sisyphus/evidence/task-4-priority.txt

  Scenario: Position lookup returns grammar when overlapping
    Tool: Bash (python)
    Steps:
      1. Using same analysis as above, call: renderer.get_highlight_at_position(1, analysis)
      2. Assert returned object is GrammarHit (not VocabHit)
      3. Call: renderer.get_highlight_at_position(10, analysis) — assert returns None
    Expected Result: Position 1 → GrammarHit, position 10 → None
    Evidence: .sisyphus/evidence/task-4-position-lookup.txt

  Scenario: Empty text edge case
    Tool: Bash (python)
    Steps:
      1. Run: renderer.build_rich_text('', AnalysisResult(tokens=[], vocab_hits=[], grammar_hits=[]), 3)
      2. Assert returns empty string or plain empty HTML
    Expected Result: No crash, returns empty/trivial result
    Evidence: .sisyphus/evidence/task-4-empty.txt
  ```

  **Commit**: YES
  - Message: `feat(ui): implement HighlightRenderer with JLPT color mapping`
  - Files: `src/ui/highlight.py`, `tests/test_highlight.py`
  - Pre-commit: `ruff check . && mypy . && pytest tests/test_highlight.py -x`

- [ ] 5. Implement OverlayWindow

  **What to do**:
  - Create `src/ui/overlay.py` with class `OverlayWindow(QWidget)`:
    - **Window setup** (`__init__`):
      - `setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)`
      - `setAttribute(Qt.WA_TranslucentBackground)`
      - `setAttribute(Qt.WA_ShowWithoutActivating)` — prevent stealing focus
      - Set initial size: ~800x120 px (wide subtitle bar)
      - Position: bottom-center of primary screen using `QApplication.primaryScreen().geometry()`
      - Background: semi-transparent dark (`rgba(30, 30, 30, 200)`) via stylesheet or paintEvent
    - **Layout**:
      - Use `QVBoxLayout` with two `QTextBrowser` widgets (read-only):
        - Top: Japanese text with JLPT color highlights (from HighlightRenderer)
        - Bottom: Chinese translation or explanation text
      - Both QTextBrowsers: transparent background, no border, no scrollbar, read-only
      - Font: "Segoe UI" with fallback to "Yu Gothic UI", "Noto Sans CJK JP", sans-serif. Size ~16pt for JP, ~14pt for CN.
    - **Display modes** (Ctrl+T toggle):
      - Mode 1 (default): Two-line — JP top, CN/explanation bottom
      - Mode 2: Single-line — JP only (translation hidden)
      - Store current mode in instance variable, toggle with `QShortcut(QKeySequence("Ctrl+T"), self)`
    - **Slot** `on_sentence_ready(self, result: SentenceResult) -> None`:
      - Use `HighlightRenderer.build_rich_text()` to format JP text
      - Set JP QTextBrowser HTML content
      - Set CN/explanation text (plain text or with minimal formatting)
      - Store `result` (including analysis, sentence_id, highlight IDs) for tooltip use
      - Update window size to fit content (adjustSize or sizeHint)
    - **Status indicators**: Show status text when no sentence is active:
      - "Initializing..." — on startup
      - "Listening..." — pipeline running, no speech
      - "Translation unavailable" — when `result.chinese_translation is None` and `result.explanation is None`
    - **Dragging**:
      - `mousePressEvent` / `mouseMoveEvent` using `event.globalPosition().toPoint()` (Qt6 API)
      - Only drag when clicking on the background area (not on text)
    - **Hover detection** (for tooltip):
      - Connect `QTextBrowser.mouseMoveEvent` (with `setMouseTracking(True)`)
      - On hover over JP text: use `cursorForPosition()` to get character position → `HighlightRenderer.get_highlight_at_position()` → if hit found, emit signal or call tooltip
      - Signal: `highlight_hovered = Signal(object, object)` — emits `(VocabHit|GrammarHit, QPoint)` for tooltip to consume
  - Create `tests/test_overlay.py`:
    - Test with `QT_QPA_PLATFORM=offscreen` (set in conftest.py or test file)
    - Test `on_sentence_ready` updates internal state
    - Test display mode toggling
    - Test status indicator text changes
    - Mock signals for hover detection
    - Do NOT test visual rendering (offscreen can't verify pixels)

  **Must NOT do**:
  - Do NOT use deprecated Qt5 API: `globalPos()` → use `globalPosition().toPoint()`; `exec_()` → use `exec()`
  - Do NOT add QSystemTrayIcon or system tray integration (P1)
  - Do NOT persist window position
  - Do NOT add font size controls or settings UI
  - Do NOT make the window resizable (fixed width, height adjusts to content)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Core UI widget with PySide6 window management, signals, event handling, hover detection. Needs careful Qt6 API usage.
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO — depends on Tasks 3 (SentenceResult with IDs) and 4 (HighlightRenderer)
  - **Parallel Group**: Wave 2 (after Tasks 3+4)
  - **Blocks**: Tasks 6, 7
  - **Blocked By**: Tasks 3, 4

  **References**:

  **Pattern References**:
  - `src/pipeline.py:PipelineWorker` — `sentence_ready = Signal(object)` emits SentenceResult. This is the signal that OverlayWindow.on_sentence_ready connects to.
  - `src/ui/highlight.py:HighlightRenderer` (from Task 4) — `build_rich_text()` returns HTML string for QTextBrowser. `get_highlight_at_position()` returns hit for tooltip.

  **API/Type References**:
  - `src/db/models.py:SentenceResult` — `japanese_text: str`, `chinese_translation: str | None`, `explanation: str | None`, `analysis: AnalysisResult`, `sentence_id: int | None`, `highlight_vocab_ids: list[int] | None`, `highlight_grammar_ids: list[int] | None`
  - `src/config.py:AppConfig` — `user_jlpt_level: int`, `llm_mode: str` (to know which field to display — translation vs explanation)

  **External References**:
  - Qt6 QTextBrowser: https://doc.qt.io/qt-6/qtextbrowser.html — setHtml(), cursorForPosition()
  - Qt6 Rich Text HTML subset: https://doc.qt.io/qt-6/richtext-html-subset.html — supported tags
  - Microsoft Fluent Design: https://learn.microsoft.com/en-us/windows/apps/design/ — visual style reference

  **WHY Each Reference Matters**:
  - PipelineWorker's signal signature tells you exactly what data arrives in the slot
  - HighlightRenderer is the dependency for formatting — overlay doesn't do its own HTML generation
  - SentenceResult shape determines what fields to display and what to store for tooltip use
  - AppConfig.llm_mode determines whether to show translation or explanation in the bottom line

  **Acceptance Criteria**:

  - [ ] Window is frameless, transparent, always-on-top, no taskbar entry
  - [ ] `WA_ShowWithoutActivating` is set (verified by reading setAttribute calls)
  - [ ] JP text displayed with JLPT color highlights via HighlightRenderer
  - [ ] CN/explanation text displayed below JP text
  - [ ] Ctrl+T toggles between two-line and single-line mode
  - [ ] `on_sentence_ready(result)` updates display correctly
  - [ ] Status indicators shown for initializing, no speech, translation unavailable states
  - [ ] Window is draggable via mouse events
  - [ ] Hover over highlighted text emits `highlight_hovered` signal with correct hit + position
  - [ ] `mypy src/ui/overlay.py` passes
  - [ ] `pytest tests/test_overlay.py -x` passes (with offscreen platform)

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Overlay window imports and initializes without crash
    Tool: Bash (python)
    Preconditions: Virtual environment activated
    Steps:
      1. Run: QT_QPA_PLATFORM=offscreen python -c "
from PySide6.QtWidgets import QApplication
import sys
app = QApplication.instance() or QApplication(sys.argv)
from src.ui.overlay import OverlayWindow
from src.config import AppConfig
w = OverlayWindow(AppConfig())
print(f'flags={int(w.windowFlags())}, visible={w.isVisible()}')
print('SUCCESS')
"
      2. Assert output contains "SUCCESS"
      3. Assert no ImportError or AttributeError
    Expected Result: OverlayWindow instantiates without error
    Failure Indicators: ImportError, crash on window flag setting, missing Qt attribute
    Evidence: .sisyphus/evidence/task-5-init.txt

  Scenario: on_sentence_ready updates display state
    Tool: Bash (pytest)
    Preconditions: Virtual environment activated, QT_QPA_PLATFORM=offscreen
    Steps:
      1. Run: QT_QPA_PLATFORM=offscreen pytest tests/test_overlay.py -x --tb=short -v
      2. Assert tests covering on_sentence_ready pass
    Expected Result: Slot correctly stores result and updates text browsers
    Failure Indicators: Test failures related to text content or state
    Evidence: .sisyphus/evidence/task-5-sentence-ready.txt

  Scenario: Display mode toggle
    Tool: Bash (pytest)
    Steps:
      1. Run test that verifies Ctrl+T toggle changes display mode
      2. Assert two-line → single-line → two-line cycle works
    Expected Result: Display mode toggles correctly
    Evidence: .sisyphus/evidence/task-5-toggle.txt
  ```

  **Commit**: YES
  - Message: `feat(ui): implement transparent overlay window with QTextBrowser`
  - Files: `src/ui/overlay.py`, `tests/test_overlay.py`
  - Pre-commit: `ruff check . && mypy . && pytest -x`

- [ ] 6. Implement TooltipPopup

  **What to do**:
  - Create `src/ui/tooltip.py` with class `TooltipPopup(QWidget)`:
    - **Window setup** (`__init__`):
      - `setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)`
      - `setAttribute(Qt.WA_TranslucentBackground)`
      - `setAttribute(Qt.WA_ShowWithoutActivating)`
      - Fixed max width ~300px, height adjusts to content
    - **Visual style**:
      - Rounded corners via `paintEvent` with `QPainter.drawRoundedRect(self.rect(), 8, 8)` on semi-transparent dark background
      - Content layout: `QVBoxLayout` with:
        - JLPT level badge (e.g., "N2" with level-appropriate background color)
        - Word/pattern text (surface form or matched_text)
        - Description/explanation text
        - For vocab: show lemma, POS, JLPT level
        - For grammar: show pattern, confidence type, description
      - Font: "Segoe UI" with CJK fallbacks, ~12pt
    - **Methods**:
      - `show_for_vocab(self, hit: VocabHit, position: QPoint) -> None` — Populate and show tooltip at position. Emit `record_triggered`.
      - `show_for_grammar(self, hit: GrammarHit, position: QPoint) -> None` — Populate and show tooltip at position. Emit `record_triggered`.
      - `hide_tooltip(self) -> None` — Hide the popup (call on mouse leave or click elsewhere)
    - **Signal**: `record_triggered = Signal(str, int)` — Emits `(highlight_type, highlight_id)` when tooltip shown. `highlight_type` is "vocab" or "grammar". `highlight_id` is the DB-assigned ID from `SentenceResult.highlight_vocab_ids` / `highlight_grammar_ids`.
    - **Deduplication**: Track shown highlights per sentence using `set[tuple[int | None, str, int]]` of `(sentence_id, highlight_type, highlight_id)`. Only emit `record_triggered` if not already shown for current sentence. Reset on new sentence.
    - **Positioning**: Show tooltip above the hovered word (position.y() - tooltip_height - 8px gap). If that would go off-screen top, show below instead.
  - Create `tests/test_tooltip.py`:
    - Test `show_for_vocab` populates correct content
    - Test `show_for_grammar` populates correct content
    - Test `record_triggered` signal emitted with correct type and ID
    - Test deduplication: second show for same highlight does NOT emit signal
    - Test dedup reset on new sentence (different sentence_id)
    - Use `QT_QPA_PLATFORM=offscreen` for headless testing

  **Must NOT do**:
  - Do NOT add animation or fade effects (keep simple for MVP)
  - Do NOT add click-to-pin or persistent tooltip features
  - Do NOT fetch additional data from DB — tooltip shows only what's in VocabHit/GrammarHit
  - Do NOT use QToolTip (native) — we need custom styling

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Custom QPainter rendering, signal/slot wiring, deduplication logic
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO — needs OverlayWindow (Task 5) for integration context, and HighlightRenderer (Task 4) for hit types
  - **Parallel Group**: Wave 3 (with Task 7)
  - **Blocks**: Task 7
  - **Blocked By**: Tasks 4, 5

  **References**:

  **Pattern References**:
  - `src/ui/overlay.py:OverlayWindow` (from Task 5) — Emits `highlight_hovered(hit, position)` signal. TooltipPopup connects to this to show/hide.
  - `src/ui/highlight.py:HighlightRenderer.JLPT_COLORS` (from Task 4) — Reuse same color mapping for JLPT level badge in tooltip.

  **API/Type References**:
  - `src/db/models.py:VocabHit` — `surface`, `lemma`, `pos`, `jlpt_level`, `user_level`
  - `src/db/models.py:GrammarHit` — `rule_id`, `matched_text`, `jlpt_level`, `confidence_type`, `description`
  - `src/db/repository.py:LearningRepository.mark_tooltip_shown(highlight_type, highlight_id)` — Called when `record_triggered` signal fires. `highlight_type` must be "vocab" or "grammar".

  **Test References**:
  - `tests/test_overlay.py` (from Task 5) — Similar QT_QPA_PLATFORM=offscreen testing pattern
  - `tests/test_db_repository.py` — Shows how mark_tooltip_shown is tested

  **WHY Each Reference Matters**:
  - OverlayWindow's hover signal is the trigger for showing tooltips — must match signature
  - VocabHit/GrammarHit fields determine what content to display
  - LearningRepository.mark_tooltip_shown is the downstream consumer of record_triggered
  - JLPT_COLORS reuse ensures consistent color scheme between highlights and tooltip badge

  **Acceptance Criteria**:

  - [ ] `show_for_vocab` displays lemma, POS, JLPT level with correct color badge
  - [ ] `show_for_grammar` displays pattern, confidence, description with correct color badge
  - [ ] `record_triggered` signal emitted with correct `("vocab", vocab_id)` or `("grammar", grammar_id)`
  - [ ] Dedup: showing same highlight twice does NOT emit signal twice
  - [ ] Dedup reset: new sentence_id resets the tracking set
  - [ ] Tooltip positioned above hovered word (or below if near screen top)
  - [ ] Rounded corners rendered via QPainter
  - [ ] `mypy src/ui/tooltip.py` passes
  - [ ] `pytest tests/test_tooltip.py -x` passes

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Tooltip shows correct vocab content
    Tool: Bash (python)
    Preconditions: QT_QPA_PLATFORM=offscreen, virtual environment activated
    Steps:
      1. Run: QT_QPA_PLATFORM=offscreen python -c "
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QPoint
import sys
app = QApplication.instance() or QApplication(sys.argv)
from src.ui.tooltip import TooltipPopup
from src.db.models import VocabHit
tooltip = TooltipPopup()
hit = VocabHit(surface='食べる', lemma='食べる', pos='動詞', jlpt_level=3, user_level=4, start_pos=0, end_pos=3)
# Connect signal to capture emission
emissions = []
tooltip.record_triggered.connect(lambda t, i: emissions.append((t, i)))
tooltip.show_for_vocab(hit, QPoint(100, 100), sentence_id=1, highlight_id=5)
print(f'emissions={emissions}')
print('SUCCESS')
"
      2. Assert emissions contains ('vocab', 5)
      3. Assert output contains "SUCCESS"
    Expected Result: Tooltip emits record_triggered with correct type and ID
    Failure Indicators: Empty emissions, wrong type/id, crash
    Evidence: .sisyphus/evidence/task-6-vocab-tooltip.txt

  Scenario: Deduplication prevents double emission
    Tool: Bash (python)
    Steps:
      1. Call show_for_vocab twice with same sentence_id + highlight_id
      2. Assert emissions list has exactly 1 entry (not 2)
    Expected Result: Second show does not emit signal
    Evidence: .sisyphus/evidence/task-6-dedup.txt

  Scenario: Dedup reset on new sentence
    Tool: Bash (python)
    Steps:
      1. Show tooltip for sentence_id=1, highlight_id=5
      2. Show tooltip for sentence_id=2, highlight_id=5 (different sentence)
      3. Assert emissions has 2 entries (one per sentence)
    Expected Result: New sentence resets dedup tracking
    Evidence: .sisyphus/evidence/task-6-dedup-reset.txt
  ```

  **Commit**: YES
  - Message: `feat(ui): implement tooltip popup with dedup recording`
  - Files: `src/ui/tooltip.py`, `tests/test_tooltip.py`
  - Pre-commit: `ruff check . && mypy . && pytest -x`

- [ ] 7. Create main.py entry point

  **What to do**:
  - Create `src/main.py` with function `main() -> None`:
    - Configure logging (root logger, INFO level, format: `%(asctime)s %(name)s %(levelname)s %(message)s`)
    - Initialize `QApplication(sys.argv)`
    - Set `QT_QPA_PLATFORM` environment variable check for WSL compatibility (log a warning if running without display)
    - Load `AppConfig` via `load_config()`
    - Initialize database: `conn = init_db(config.db_path)`, `repo = LearningRepository(conn)`
    - Create `HighlightRenderer()`
    - Create `OverlayWindow(config)` — pass config for user_level and llm_mode
    - Create `TooltipPopup()`
    - Create `PipelineWorker(config, db_conn=conn)`
    - **Wire signals**:
      - `pipeline.sentence_ready` → `overlay.on_sentence_ready`
      - `overlay.highlight_hovered` → tooltip show logic (connect to a lambda or method that calls `tooltip.show_for_vocab`/`show_for_grammar` based on hit type, passing sentence_id and highlight_id from the stored SentenceResult)
      - `tooltip.record_triggered` → `repo.mark_tooltip_shown` (connect signal to repository method)
    - Start pipeline worker: `pipeline.start()`
    - Show overlay: `overlay.show()`
    - Set up clean shutdown:
      - `app.aboutToQuit.connect(cleanup)` where cleanup stops pipeline, closes DB conn
      - Handle `SIGINT` (Ctrl+C) gracefully — call `app.quit()`
    - Run event loop: `sys.exit(app.exec())`
  - Add `if __name__ == "__main__": main()` block
  - Ensure `python -m src.main` entry point works (verify `src/__init__.py` exists)
  - NO test file for main.py — verification is import check + integration in Final Wave

  **Must NOT do**:
  - Do NOT add CLI argument parsing (not needed for MVP)
  - Do NOT add splash screen or loading animation
  - Do NOT add system tray icon (P1)
  - Do NOT start Ollama or check Ollama health in main — pipeline handles that internally
  - Do NOT create QApplication if one already exists (use `QApplication.instance() or QApplication(sys.argv)`)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Integration task wiring multiple modules. Needs understanding of Qt event loop, signal connections, and shutdown patterns.
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO — depends on all previous tasks
  - **Parallel Group**: Wave 3 (after Tasks 5, 6)
  - **Blocks**: F1-F4
  - **Blocked By**: Tasks 3, 5, 6

  **References**:

  **Pattern References**:
  - `src/pipeline.py:PipelineWorker` — Constructor: `__init__(config, db_conn=None)`. Signals: `sentence_ready = Signal(object)`, `error_occurred = Signal(str)`. Methods: `start()`, `stop()`.
  - `src/ui/overlay.py:OverlayWindow` (from Task 5) — Slot: `on_sentence_ready(result)`. Signal: `highlight_hovered(hit, position)`.
  - `src/ui/tooltip.py:TooltipPopup` (from Task 6) — Methods: `show_for_vocab()`, `show_for_grammar()`. Signal: `record_triggered(str, int)`.

  **API/Type References**:
  - `src/config.py:load_config()` — Returns `AppConfig` with all configuration
  - `src/db/schema.py:init_db(db_path)` — Returns `sqlite3.Connection` with WAL mode
  - `src/db/repository.py:LearningRepository` — Constructor takes `sqlite3.Connection`. Method: `mark_tooltip_shown(highlight_type, highlight_id)`.

  **Test References**:
  - `tests/test_pipeline.py` — Shows how PipelineWorker is instantiated and tested with mocks

  **External References**:
  - Qt6 application lifecycle: https://doc.qt.io/qt-6/qapplication.html — exec(), aboutToQuit signal

  **WHY Each Reference Matters**:
  - PipelineWorker is the data source — must know its exact signal signature and constructor args
  - OverlayWindow and TooltipPopup are the consumers — must match their slot/signal signatures exactly
  - load_config and init_db are the initialization functions — must call in correct order
  - aboutToQuit is the only reliable shutdown hook in Qt — cleanup must be registered here

  **Acceptance Criteria**:

  - [ ] `python -c "from src.main import main"` imports without error
  - [ ] `main()` creates QApplication, loads config, initializes DB, creates all components
  - [ ] All signal connections wired: pipeline→overlay, overlay→tooltip, tooltip→repository
  - [ ] Clean shutdown on `aboutToQuit`: pipeline stopped, DB closed
  - [ ] SIGINT (Ctrl+C) triggers clean shutdown
  - [ ] `mypy src/main.py` passes
  - [ ] `ruff check src/main.py` passes

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: main.py imports cleanly
    Tool: Bash (python)
    Preconditions: Virtual environment activated
    Steps:
      1. Run: python -c "from src.main import main; print('IMPORT OK')"
      2. Assert output contains "IMPORT OK"
    Expected Result: No ImportError or circular import issues
    Failure Indicators: ImportError, ModuleNotFoundError
    Evidence: .sisyphus/evidence/task-7-import.txt

  Scenario: main.py module execution check
    Tool: Bash (python)
    Preconditions: Virtual environment activated, QT_QPA_PLATFORM=offscreen
    Steps:
      1. Run: QT_QPA_PLATFORM=offscreen timeout 5 python -c "
import sys
import signal
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
# Verify main creates app and components without crashing
from src.main import main
# We can't fully run main() (it enters event loop), but we can verify imports and setup
print('ALL IMPORTS OK')
" 2>&1 || true
      2. Assert output contains "ALL IMPORTS OK"
    Expected Result: All dependencies resolve, no circular imports
    Failure Indicators: ImportError, missing module
    Evidence: .sisyphus/evidence/task-7-module-check.txt

  Scenario: Signal wiring verification
    Tool: Bash (python)
    Steps:
      1. Read src/main.py source
      2. Verify these connection patterns exist:
         - pipeline.sentence_ready.connect(overlay.on_sentence_ready)
         - overlay.highlight_hovered.connect(...)
         - tooltip.record_triggered.connect(...)
      3. Verify cleanup function stops pipeline and closes DB
    Expected Result: All 3 signal connections present, cleanup handles shutdown
    Evidence: .sisyphus/evidence/task-7-wiring.txt

  Scenario: Full lint and type check
    Tool: Bash
    Steps:
      1. Run: ruff check src/main.py && mypy src/main.py
      2. Assert exit code 0
    Expected Result: No lint or type errors
    Evidence: .sisyphus/evidence/task-7-lint.txt
  ```

  **Commit**: YES
  - Message: `feat(app): create main.py entry point wiring full pipeline`
  - Files: `src/main.py`
  - Pre-commit: `ruff check . && mypy . && pytest -x`

---

## Final Verification Wave (MANDATORY — after ALL implementation tasks)

> 4 review agents run in PARALLEL. ALL must APPROVE. Rejection → fix → re-run.

- [ ] F1. **Plan Compliance Audit** — `deep`
  Read the plan end-to-end. For each "Must Have": verify implementation exists (read file, import module, check class/method). For each "Must NOT Have": search codebase for forbidden patterns — reject with file:line if found. Check evidence files exist in .sisyphus/evidence/. Compare deliverables against plan.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [ ] F2. **Code Quality Review** — `unspecified-high`
  Run `ruff check . && ruff format --check . && mypy . && pytest -x --tb=short`. Review all changed files for: bare `except:`, `print()` in prod code, unused imports, deprecated Qt5 API usage (`globalPos()`, `exec_()`), `type: ignore` without justification. Check AI slop: excessive comments, over-abstraction, generic variable names.
  Output: `Ruff [PASS/FAIL] | Mypy [PASS/FAIL] | Tests [N pass/N fail] | Files [N clean/N issues] | VERDICT`

- [ ] F3. **Integration QA** — `unspecified-high`
  Run `QT_QPA_PLATFORM=offscreen python -c "from src.main import main"` to verify clean import. Run full test suite. Verify all signal connections by inspecting main.py wiring. Check that HighlightRenderer output is valid HTML by parsing it. Verify tooltip dedup logic with test cases.
  Output: `Import [PASS/FAIL] | Tests [N/N pass] | Signals [N/N connected] | VERDICT`

- [ ] F4. **Scope Fidelity Check** — `deep`
  For each task: read "What to do", read actual implementation. Verify 1:1 — everything in spec was built (no missing), nothing beyond spec was built (no creep). Check "Must NOT do" compliance. Flag unaccounted changes. Verify no Settings panel, Learning panel, or position persistence was added.
  Output: `Tasks [N/N compliant] | Scope [CLEAN/N issues] | Unaccounted [CLEAN/N files] | VERDICT`

---

## Commit Strategy

| After Tasks | Commit Message | Files | Pre-commit |
|-------------|---------------|-------|------------|
| 1, 2a, 2b, 2c | `feat(models): add position fields to VocabHit/GrammarHit and sentence_id to SentenceResult` | src/db/models.py, src/analysis/grammar.py, src/analysis/jlpt_vocab.py, src/analysis/pipeline.py, tests/* | `ruff check . && mypy . && pytest -x` |
| 3 | `feat(pipeline): emit sentence_ready after DB write with assigned IDs` | src/pipeline.py, tests/test_pipeline.py | `ruff check . && mypy . && pytest -x` |
| 4 | `feat(ui): implement HighlightRenderer with JLPT color mapping` | src/ui/highlight.py, tests/test_highlight.py | `ruff check . && mypy . && pytest -x` |
| 5 | `feat(ui): implement transparent overlay window with QTextBrowser` | src/ui/overlay.py, tests/test_overlay.py | `ruff check . && mypy . && pytest -x` |
| 6 | `feat(ui): implement tooltip popup with dedup recording` | src/ui/tooltip.py, tests/test_tooltip.py | `ruff check . && mypy . && pytest -x` |
| 7 | `feat(app): create main.py entry point wiring full pipeline` | src/main.py | `ruff check . && mypy . && pytest -x` |

---

## Success Criteria

### Verification Commands
```bash
ruff check . && ruff format --check . && mypy . && pytest -x --tb=short  # Expected: all pass
python -c "from src.main import main"  # Expected: clean import, no errors
python -c "from src.ui.highlight import HighlightRenderer"  # Expected: clean import
python -c "from src.ui.overlay import OverlayWindow"  # Expected: clean import
python -c "from src.ui.tooltip import TooltipPopup"  # Expected: clean import
```

### Final Checklist
- [ ] All "Must Have" present
- [ ] All "Must NOT Have" absent
- [ ] All tests pass (including existing M0-M3 tests — no regressions)
- [ ] mypy clean across entire project
- [ ] ruff clean across entire project
