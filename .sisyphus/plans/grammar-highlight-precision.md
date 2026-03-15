# Precise Grammar Highlighting with Capturing Groups

## TL;DR

> **Quick Summary**: Upgrade grammar highlighting from full-match spans to part-specific spans using regex capturing groups. Only grammar keyword parts (e.g., `が`, `なら`) get highlighted; filler text between them remains unhighlighted. Tooltip triggers only on highlighted keyword parts, not filler.
> 
> **Deliverables**:
> - Extended `GrammarHit` DTO with `matched_parts` field for sub-spans
> - Updated `GrammarMatcher.match_all()` to extract capturing group positions
> - Reworked `HighlightRenderer` to produce multiple spans per grammar hit
> - Updated `_is_fully_covered()` to check part-level coverage instead of full-range
> - Updated `get_highlight_at_position()` to detect hover only on keyword parts
> - Updated `TooltipPopup` tooltip title to show grammar word pattern instead of full matched text
> - Comprehensive test updates for all changed modules
> 
> **Estimated Effort**: Medium
> **Parallel Execution**: YES — 3 waves
> **Critical Path**: Task 1 (DTO) → Task 2 (matcher) → Task 3 (renderer) → Task 5 (tests)

---

## Context

### Original Request
Transition from full-match grammar highlighting to precise keyword-part highlighting. Grammar rules like `(が|も).+(なら)` should highlight only `が` and `なら`, not the filler text between them. The grammar JSON already has capturing groups embedded in the `re` field for 63 of 831 rules.

### Interview Summary
**Key Discussions**:
- **Grammar JSON schema**: No change needed — capturing groups are already in `re` field. No new `groups`/`parts` JSON key.
- **Hover detection**: Tooltip triggers ONLY on highlighted keyword parts; filler text is inert (no tooltip).
- **Tooltip display**: Keep current tooltip style unchanged; no sub-part visual distinction inside tooltip.
- **Fallback**: Rules without capturing groups (768 of 831) → highlight entire match as before.

**Research Findings**:
- 63 rules have capturing groups (multi-part: `(A).*(B)`) — highlight only captured parts
- 294 rules have only non-capturing groups `(?:...)` — highlight entire match (fallback)
- 474 rules have no groups at all — highlight entire match (fallback)
- Current `GrammarHit` has no field for sub-spans; `match_all()` ignores `m.groups()`
- `HighlightRenderer` creates exactly one `_Span` per `GrammarHit`
- `_is_fully_covered()` checks if vocab is contained in full grammar range — needs rethinking for multi-part

### Gap Analysis (Self-conducted after Metis)
**Edge cases identified and addressed in plan**:
- Adjacent capturing groups with zero-width gaps → handled by sub-span model
- `_is_fully_covered()` vocab suppression for multi-part grammar → suppress only if vocab overlaps a keyword part
- `matched_parts` must be optional/empty tuple for backward compat with 768 non-capturing rules
- Frozen dataclass constraint on `GrammarHit` → field added with `default=()` (immutable default)
- Test helpers like `_make_grammar()` need updating for new field

---

## Work Objectives

### Core Objective
Enable precise sub-part highlighting for grammar rules with capturing groups, so only grammar keywords are visually highlighted and only those keyword parts trigger tooltips.

### Concrete Deliverables
- `src/models.py`: `GrammarHit` with new `matched_parts: tuple[tuple[int, int], ...]` field
- `src/analysis/grammar.py`: `match_all()` extracts capturing group spans via `m.span(i)`
- `src/ui/highlight.py`: Multiple `_Span`s per grammar hit; updated vocab suppression and hover detection
- `src/ui/tooltip.py`: Tooltip title uses `hit.word` (grammar pattern) instead of full `hit.matched_text`
- `tests/test_grammar.py`: Tests for capturing group extraction + fallback behavior
- `tests/test_highlight.py`: Tests for multi-span rendering, part-level hover detection, updated vocab suppression

### Definition of Done
- [ ] `pytest tests/` passes with 0 failures
- [ ] `ruff check . && ruff format --check .` clean
- [ ] `mypy src/` clean (no new type errors)
- [ ] Grammar rules with capturing groups produce multiple highlight spans
- [ ] Grammar rules without capturing groups produce single span (unchanged behavior)
- [ ] Hovering filler text between grammar parts does NOT trigger tooltip
- [ ] Hovering grammar keyword parts triggers tooltip with correct info

### Must Have
- `matched_parts` field on `GrammarHit` — tuple of `(start, end)` sub-spans
- Fallback: empty `matched_parts` → highlight entire `[start_pos, end_pos)` range (backward compat)
- Vocab suppression only for text overlapping keyword parts, not entire grammar range
- Tooltip triggers only on keyword parts
- All existing tests pass with minimal adaptation

### Must NOT Have (Guardrails)
- **NO changes to grammar JSON schema** — rules are already correct as-is
- **NO changes to `VocabHit`, `AnalysisResult`, or `SentenceResult`** DTOs
- **NO changes to pipeline orchestrator or signal wiring** in `src/main.py`
- **NO changes to audio/VAD/ASR layers**
- **NO visual tooltip redesign** — keep current layout, only change the title text source
- **NO new dependencies** — only use stdlib `re` module features
- **NO `type: ignore` or `as any` suppressions** — proper typing throughout
- **NO over-engineering** — no abstract "span strategy" pattern; simple conditional logic

---

## Verification Strategy

> **ZERO HUMAN INTERVENTION** — ALL verification is agent-executed. No exceptions.

### Test Decision
- **Infrastructure exists**: YES (`pytest`, `conftest.py` with `qapp` fixture)
- **Automated tests**: YES (Tests-after — update existing tests + add new ones)
- **Framework**: `pytest` (already configured in `pyproject.toml`)

### QA Policy
Every task MUST include agent-executed QA scenarios.
Evidence saved to `.sisyphus/evidence/task-{N}-{scenario-slug}.{ext}`.

- **DTO/Backend**: Use Bash (Python REPL) — Import, call functions, compare output
- **UI Rendering**: Use Bash (`pytest`) — Run specific test files, assert pass
- **Integration**: Use Bash (`pytest tests/`) — Full suite must pass

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Foundation — start immediately):
├── Task 1: Extend GrammarHit DTO with matched_parts field [quick]
├── Task 2: Update GrammarMatcher to extract capturing groups [deep]

Wave 2 (UI — after Wave 1):
├── Task 3: Update HighlightRenderer for multi-span grammar [deep]
├── Task 4: Update TooltipPopup + hover detection [quick]

Wave 3 (Verification — after Wave 2):
├── Task 5: Update and extend test suite [unspecified-high]

Wave FINAL (After ALL tasks — independent review, 4 parallel):
├── Task F1: Plan compliance audit (oracle)
├── Task F2: Code quality review (unspecified-high)
├── Task F3: Real manual QA (unspecified-high)
├── Task F4: Scope fidelity check (deep)

Critical Path: Task 1 → Task 2 → Task 3 → Task 5
Parallel Speedup: ~40% faster than sequential (Wave 1 has 2 parallel, Wave 2 has 2 parallel)
Max Concurrent: 2 (Waves 1 & 2)
```

### Dependency Matrix

| Task | Depends On | Blocks | Wave |
|------|-----------|--------|------|
| 1    | —         | 2, 3, 4, 5 | 1 |
| 2    | 1         | 3, 5   | 1 |
| 3    | 1, 2      | 5      | 2 |
| 4    | 1         | 5      | 2 |
| 5    | 1, 2, 3, 4 | F1-F4 | 3 |
| F1-F4 | 5        | —      | FINAL |

### Agent Dispatch Summary

- **Wave 1**: 2 tasks — T1 → `quick`, T2 → `deep`
- **Wave 2**: 2 tasks — T3 → `deep`, T4 → `quick`
- **Wave 3**: 1 task — T5 → `unspecified-high`
- **FINAL**: 4 tasks — F1 → `oracle`, F2 → `unspecified-high`, F3 → `unspecified-high`, F4 → `deep`

---

## TODOs

- [x] 1. Extend `GrammarHit` DTO with `matched_parts` field

  **What to do**:
  - Add a new field `matched_parts: tuple[tuple[int, int], ...] = ()` to the `GrammarHit` dataclass in `src/models.py`
  - Each inner tuple is `(start_pos, end_pos)` representing one capturing group's absolute character span in the original text
  - Default `()` (empty tuple) means "no sub-parts, highlight entire match" (backward compat for 768 rules)
  - The tuple is immutable (works with frozen dataclasses) and hashable
  - No other DTO changes — `AnalysisResult`, `SentenceResult`, `VocabHit` remain untouched

  **Must NOT do**:
  - Do NOT add `matched_parts` to `VocabHit` or any other DTO
  - Do NOT change `SentenceResult.get_display_analysis()` — it passes `GrammarHit` objects through unchanged
  - Do NOT use `list` for `matched_parts` — must be `tuple` for frozen dataclass compatibility

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Single-field addition to a dataclass — trivial change, well-scoped
  - **Skills**: `[]`
  - **Skills Evaluated but Omitted**:
    - `git-master`: Not needed for a code change task

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Task 2, but Task 2 depends on this)
  - **Parallel Group**: Wave 1
  - **Blocks**: Tasks 2, 3, 4, 5
  - **Blocked By**: None (can start immediately)

  **References**:

  **Pattern References**:
  - `src/models.py:29-37` — Current `GrammarHit` dataclass definition. Add `matched_parts` after `end_pos` field (line 37) with default `()`.
  - `src/models.py:17-26` — `VocabHit` dataclass for reference on field ordering and defaults pattern (note `vocab_id: int = 0` as example of default).

  **API/Type References**:
  - `src/models.py:3` — `from dataclasses import dataclass, field` — already imported; `field` available if needed, but `= ()` works directly since tuples are immutable.

  **WHY Each Reference Matters**:
  - `GrammarHit` (lines 29-37) — This is the EXACT location to modify. The new field goes after `end_pos: int` with default `= ()` to maintain backward compat.
  - `VocabHit` (lines 17-26) — Shows the pattern of optional fields with defaults at end of dataclass.

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: GrammarHit with matched_parts creates successfully
    Tool: Bash (python3 -c)
    Preconditions: src/models.py has been modified
    Steps:
      1. Run: python3 -c "from src.models import GrammarHit; gh = GrammarHit(rule_id='1', matched_text='がなら', word='が...なら', jlpt_level=2, description='test', start_pos=0, end_pos=4, matched_parts=((0,1),(2,4))); print(gh.matched_parts); assert gh.matched_parts == ((0,1),(2,4))"
      2. Assert: exit code 0, output is `((0, 1), (2, 4))`
    Expected Result: GrammarHit accepts and stores matched_parts tuple
    Failure Indicators: ImportError, TypeError, AttributeError
    Evidence: .sisyphus/evidence/task-1-gramhit-with-parts.txt

  Scenario: GrammarHit without matched_parts defaults to empty tuple
    Tool: Bash (python3 -c)
    Preconditions: src/models.py has been modified
    Steps:
      1. Run: python3 -c "from src.models import GrammarHit; gh = GrammarHit(rule_id='1', matched_text='ながら', word='ながら', jlpt_level=3, description='test', start_pos=0, end_pos=3); print(gh.matched_parts); assert gh.matched_parts == ()"
      2. Assert: exit code 0, output is `()`
    Expected Result: Default empty tuple — backward compatible with all existing code
    Failure Indicators: TypeError about missing argument, AttributeError
    Evidence: .sisyphus/evidence/task-1-gramhit-default.txt

  Scenario: Existing test suite still passes (backward compat)
    Tool: Bash
    Preconditions: src/models.py modified
    Steps:
      1. Run: pytest tests/test_grammar.py tests/test_highlight.py -v
      2. Assert: all tests pass, 0 failures
    Expected Result: All existing tests pass unchanged (they don't pass matched_parts, so default () is used)
    Failure Indicators: Any test failure
    Evidence: .sisyphus/evidence/task-1-existing-tests.txt
  ```

  **Commit**: YES (groups with Task 2)
  - Message: `feat(analysis): extract capturing group spans in GrammarMatcher`
  - Files: `src/models.py`
  - Pre-commit: `pytest tests/test_grammar.py tests/test_highlight.py`

- [x] 2. Update `GrammarMatcher.match_all()` to extract capturing group spans

  **What to do**:
  - In `src/analysis/grammar.py`, modify the `match_all()` method to detect and extract capturing group positions
  - After each `m = rule.pattern.finditer(text)` match, check `m.lastindex` (not None if capturing groups matched)
  - If capturing groups exist: build `matched_parts` tuple from `m.span(i)` for `i in range(1, m.lastindex + 1)`, filtering out groups that didn't match (i.e., `m.group(i) is not None`)
  - If no capturing groups: leave `matched_parts` as default `()`
  - Pass `matched_parts` to the `GrammarHit` constructor
  - Important: `m.span(i)` returns absolute positions in the text — these are ready to use directly as highlight spans

  **Implementation detail — the key logic**:
  ```python
  # Inside the finditer loop, after m = match:
  parts: tuple[tuple[int, int], ...] = ()
  if m.lastindex:  # has capturing groups
      parts = tuple(
          m.span(i)
          for i in range(1, m.lastindex + 1)
          if m.group(i) is not None
      )
  # Then pass matched_parts=parts to GrammarHit(...)
  ```

  **Must NOT do**:
  - Do NOT change the `_CompiledRule` dataclass — no new fields needed there
  - Do NOT modify how rules are loaded from JSON — the `re` field is already correct
  - Do NOT filter out non-capturing group rules — they simply produce empty `matched_parts`
  - Do NOT change the return type of `match_all()` — still returns `list[GrammarHit]`

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Requires understanding regex group mechanics and careful edge case handling
  - **Skills**: `[]`
  - **Skills Evaluated but Omitted**:
    - `git-master`: Not a git operation

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 1 (after Task 1)
  - **Blocks**: Tasks 3, 5
  - **Blocked By**: Task 1 (needs `matched_parts` field on `GrammarHit`)

  **References**:

  **Pattern References**:
  - `src/analysis/grammar.py:74-101` — Current `match_all()` method. The loop at lines 89-101 is where the change goes. Currently creates `GrammarHit` with `m.group()`, `m.start()`, `m.end()`. Need to add `matched_parts` extraction before the `GrammarHit(...)` constructor call.
  - `src/analysis/grammar.py:52-71` — Rule loading loop. Shows how `_CompiledRule` is created. Note that `re.compile(str(rule["re"]))` preserves capturing groups in the compiled pattern.

  **API/Type References**:
  - `src/models.py:29-38` — `GrammarHit` dataclass with new `matched_parts` field (from Task 1). Constructor signature for passing the field.
  - Python `re` module: `Match.lastindex` returns the index of the last matched capturing group, or `None` if no groups. `Match.span(i)` returns `(start, end)` for group `i`. `Match.group(i)` returns `None` if that alternative didn't participate.

  **Test References**:
  - `tests/test_grammar.py:23-34` — `test_grammar_hit_fields()` validates all field types. This test must still pass with the added `matched_parts`.

  **External References**:
  - Python docs: `re.Match.lastindex` — "The integer index of the last matched capturing group, or None if no group was matched at all."
  - Python docs: `re.Match.span(group)` — "Return a tuple (m.start(group), m.end(group)) for group."

  **WHY Each Reference Matters**:
  - `match_all()` (lines 89-101) is the EXACT method to modify — the only place `GrammarHit` objects are created
  - `_CompiledRule` loading shows that `re.compile()` preserves capturing groups automatically
  - `test_grammar_hit_fields()` validates field types — must be updated or still pass with new field
  - Python `re` docs explain `lastindex` / `span(i)` behavior for capturing vs non-capturing groups

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Rule with capturing groups produces matched_parts
    Tool: Bash (python3 -c)
    Preconditions: Both src/models.py and src/analysis/grammar.py are modified
    Steps:
      1. Run: python3 -c "
from src.analysis.grammar import GrammarMatcher
gm = GrammarMatcher('data/grammar.json')
# Use a sentence that triggers a multi-part rule (rule 164: (なり).*?(なり))
text = 'なりとなり'
hits = gm.match_all(text)
multi = [h for h in hits if h.matched_parts]
print(f'Multi-part hits: {len(multi)}')
for h in multi:
    print(f'  rule={h.rule_id} parts={h.matched_parts} text={h.matched_text}')
assert len(multi) > 0, 'Expected at least one multi-part hit'
for h in multi:
    for s, e in h.matched_parts:
        assert 0 <= s < e <= len(text), f'Bad span ({s},{e})'
        assert text[s:e], f'Empty span text at ({s},{e})'
"
      2. Assert: exit code 0, at least one hit has non-empty matched_parts
    Expected Result: Multi-part rules produce matched_parts with valid (start, end) tuples
    Failure Indicators: AssertionError, no multi-part hits found
    Evidence: .sisyphus/evidence/task-2-capturing-groups.txt

  Scenario: Rule without capturing groups produces empty matched_parts
    Tool: Bash (python3 -c)
    Preconditions: Both files modified
    Steps:
      1. Run: python3 -c "
from src.analysis.grammar import GrammarMatcher
gm = GrammarMatcher('data/grammar.json')
# 'てから' is rule 762, a simple pattern with no capturing groups
hits = gm.match_all('食べてから寝る')
tekara = [h for h in hits if h.rule_id == '762']
assert len(tekara) >= 1
assert tekara[0].matched_parts == (), f'Expected empty tuple, got {tekara[0].matched_parts}'
print(f'Rule 762 matched_parts: {tekara[0].matched_parts} (correct: empty)')
"
      2. Assert: exit code 0, matched_parts is ()
    Expected Result: Simple rules (no capturing groups) have empty matched_parts tuple
    Failure Indicators: matched_parts is not empty tuple
    Evidence: .sisyphus/evidence/task-2-no-capturing-groups.txt

  Scenario: Existing grammar tests still pass
    Tool: Bash
    Preconditions: Both files modified
    Steps:
      1. Run: pytest tests/test_grammar.py -v
      2. Assert: all tests pass, 0 failures
    Expected Result: 100% backward compatible — all existing tests pass
    Failure Indicators: Any test failure
    Evidence: .sisyphus/evidence/task-2-existing-tests.txt
  ```

  **Commit**: YES (groups with Task 1)
  - Message: `feat(analysis): extract capturing group spans in GrammarMatcher`
  - Files: `src/models.py`, `src/analysis/grammar.py`
  - Pre-commit: `pytest tests/test_grammar.py`

- [x] 3. Update `HighlightRenderer` for multi-span grammar highlighting and precise hover

  **What to do**:
  Three changes in `src/ui/highlight.py`:

  **(A) `apply_to_document()` — Multi-span grammar rendering (lines 79-83)**:
  - Currently: one span per grammar hit → `grammar_spans.append((gh.start_pos, gh.end_pos, color, 'grammar'))`
  - New logic: if `gh.matched_parts` is non-empty, create one span PER part; otherwise create one span for the full range (fallback)
  - Pseudocode:
    ```python
    for gh in analysis.grammar_hits:
        color = self._grammar_color(gh.jlpt_level)
        if gh.matched_parts:
            for part_start, part_end in gh.matched_parts:
                grammar_spans.append((part_start, part_end, color, _TYPE_GRAMMAR))
        else:
            grammar_spans.append((gh.start_pos, gh.end_pos, color, _TYPE_GRAMMAR))
    ```

  **(B) `_is_fully_covered()` — Part-aware vocab suppression (lines 157-167)**:
  - Currently: suppresses vocab if `gs_start <= start and end <= gs_end` (full grammar range)
  - Problem: With multi-part grammar, vocab between keyword parts should NOT be suppressed (it's in the filler gap)
  - New logic: vocab is suppressed ONLY if it's fully contained within a single keyword part span, not the full grammar range
  - Since `grammar_spans` now contain per-part spans (from change A), the existing `_is_fully_covered()` logic works **as-is** — each grammar span in the list is already a keyword part, not the full range
  - **No code change needed for `_is_fully_covered()`** — the fix is upstream in how `grammar_spans` are built

  **(C) `get_highlight_at_position()` — Part-level hover detection (lines 120-143)**:
  - Currently: returns `GrammarHit` if `gh.start_pos <= position < gh.end_pos` (full range match)
  - New logic: if `gh.matched_parts` is non-empty, only return hit if position falls within ANY part; if empty (fallback), use full range as before
  - Pseudocode:
    ```python
    for gh in analysis.grammar_hits:
        if gh.matched_parts:
            for part_start, part_end in gh.matched_parts:
                if part_start <= position < part_end:
                    return gh
        else:
            if gh.start_pos <= position < gh.end_pos:
                return gh
    ```

  **Must NOT do**:
  - Do NOT change `_Span` type alias — still `tuple[int, int, str, str]`
  - Do NOT change `_sort_key()` — still sorts by (start, type_priority)
  - Do NOT change `QTextCharFormat` styling (color + bold)
  - Do NOT modify `_grammar_color()` or `_vocab_color()` helpers
  - Do NOT add any new public methods
  - Do NOT modify `_is_fully_covered()` — it works correctly with the new per-part spans from change A

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Three coordinated changes with edge case handling. Understanding of how span model change in (A) makes (B) work for free is critical.
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Task 4)
  - **Parallel Group**: Wave 2 (with Task 4)
  - **Blocks**: Task 5
  - **Blocked By**: Tasks 1, 2 (needs `matched_parts` on `GrammarHit`)

  **References**:

  **Pattern References**:
  - `src/ui/highlight.py:79-83` — Grammar span building loop. THIS is change (A). Currently builds one span per hit; need conditional for `matched_parts`.
  - `src/ui/highlight.py:85-95` — Vocab span building with `_is_fully_covered()` call. This code calls `_is_fully_covered(vh.start_pos, vh.end_pos, grammar_spans)` — since `grammar_spans` will now contain per-part spans, this already works correctly.
  - `src/ui/highlight.py:120-143` — `get_highlight_at_position()`. THIS is change (C). Need to add part-level position check.
  - `src/ui/highlight.py:157-167` — `_is_fully_covered()`. Verify this needs NO changes — the per-part grammar_spans from (A) make it work.

  **API/Type References**:
  - `src/models.py:29-38` — `GrammarHit` with `matched_parts: tuple[tuple[int, int], ...]`. The field to check in all three changes.

  **Test References**:
  - `tests/test_highlight.py:233-250` — `test_apply_to_document_grammar_suppresses_vocab` — Must still pass. This test uses a grammar hit that fully covers a vocab hit. With no capturing groups (fallback), the single grammar span still fully covers vocab.
  - `tests/test_highlight.py:83-92` — `test_get_highlight_at_position_returns_grammar_over_vocab` — Must still pass with fallback (no `matched_parts`).

  **WHY Each Reference Matters**:
  - Lines 79-83 is the exact loop to modify for multi-span rendering
  - Lines 120-143 is the exact method to modify for part-level hover detection
  - Lines 157-167 needs verification that it works as-is (it should, since grammar_spans change)
  - Tests show the contract that must be preserved for backward compat

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Multi-part grammar hit produces multiple highlight spans
    Tool: Bash (python3 -c)
    Preconditions: Tasks 1+2 complete, src/ui/highlight.py modified
    Steps:
      1. Run: python3 -c "
from src.models import GrammarHit, AnalysisResult
from src.ui.highlight import HighlightRenderer
renderer = HighlightRenderer()
# Simulate multi-part grammar: 'がXなら' where が(0,1) and なら(2,4) are parts
gh = GrammarHit(rule_id='47', matched_text='がXなら', word='が...なら',
                jlpt_level=2, description='test', start_pos=0, end_pos=4,
                matched_parts=((0,1),(2,4)))
analysis = AnalysisResult(tokens=[], vocab_hits=[], grammar_hits=[gh])
# Test get_highlight_at_position
hit_at_0 = renderer.get_highlight_at_position(0, analysis)  # が — should match
hit_at_1 = renderer.get_highlight_at_position(1, analysis)  # X — should NOT match
hit_at_2 = renderer.get_highlight_at_position(2, analysis)  # な — should match
assert hit_at_0 is not None, 'Position 0 (keyword part) should return hit'
assert hit_at_1 is None, 'Position 1 (filler) should return None'
assert hit_at_2 is not None, 'Position 2 (keyword part) should return hit'
print('Part-level hover detection: PASS')
"
      2. Assert: exit code 0, all assertions pass
    Expected Result: Hover detects only keyword parts, not filler
    Failure Indicators: AssertionError at filler position 1
    Evidence: .sisyphus/evidence/task-3-part-hover.txt

  Scenario: Fallback grammar hit (no matched_parts) highlights full range
    Tool: Bash (python3 -c)
    Preconditions: src/ui/highlight.py modified
    Steps:
      1. Run: python3 -c "
from src.models import GrammarHit, AnalysisResult
from src.ui.highlight import HighlightRenderer
renderer = HighlightRenderer()
# Fallback: no matched_parts (simple rule like 'ながら')
gh = GrammarHit(rule_id='99', matched_text='ながら', word='ながら',
                jlpt_level=3, description='test', start_pos=0, end_pos=3)
analysis = AnalysisResult(tokens=[], vocab_hits=[], grammar_hits=[gh])
for pos in range(3):
    hit = renderer.get_highlight_at_position(pos, analysis)
    assert hit is not None, f'Position {pos} should return hit (fallback)'
hit_out = renderer.get_highlight_at_position(3, analysis)
assert hit_out is None, 'Position 3 (outside) should be None'
print('Fallback hover detection: PASS')
"
      2. Assert: exit code 0, all positions within range return hit
    Expected Result: Without matched_parts, entire range is hoverable (backward compat)
    Failure Indicators: None returned for position within range
    Evidence: .sisyphus/evidence/task-3-fallback-hover.txt

  Scenario: Vocab in filler gap is NOT suppressed by multi-part grammar
    Tool: Bash (python3 -c)
    Preconditions: src/ui/highlight.py modified
    Steps:
      1. Run: python3 -c "
from src.models import GrammarHit, VocabHit, AnalysisResult
from src.ui.highlight import HighlightRenderer
renderer = HighlightRenderer()
# Grammar: 'がXなら' with parts at (0,1) and (3,5). Vocab 'X' at (1,2) is in filler gap.
gh = GrammarHit(rule_id='47', matched_text='がXなら', word='が...なら',
                jlpt_level=2, description='test', start_pos=0, end_pos=5,
                matched_parts=((0,1),(3,5)))
vh = VocabHit(surface='X', lemma='X', pos='名詞', jlpt_level=3,
              start_pos=1, end_pos=2)
analysis = AnalysisResult(tokens=[], vocab_hits=[vh], grammar_hits=[gh])
# Hover at filler position 1 should return VocabHit, not GrammarHit
hit = renderer.get_highlight_at_position(1, analysis)
assert isinstance(hit, VocabHit), f'Filler position should show vocab, got {type(hit)}'
print('Vocab in filler gap NOT suppressed: PASS')
"
      2. Assert: exit code 0, filler position returns VocabHit
    Expected Result: Vocab in filler gap between grammar parts is visible and hoverable
    Failure Indicators: GrammarHit returned instead of VocabHit
    Evidence: .sisyphus/evidence/task-3-vocab-filler.txt

  Scenario: Existing highlight tests still pass
    Tool: Bash
    Preconditions: src/ui/highlight.py modified
    Steps:
      1. Run: pytest tests/test_highlight.py -v
      2. Assert: all tests pass, 0 failures
    Expected Result: All 18+ existing tests pass unchanged
    Failure Indicators: Any test failure
    Evidence: .sisyphus/evidence/task-3-existing-tests.txt
  ```

  **Commit**: YES (groups with Task 4)
  - Message: `feat(ui): render precise multi-span grammar highlights`
  - Files: `src/ui/highlight.py`
  - Pre-commit: `pytest tests/test_highlight.py`

- [x] 4. Update `TooltipPopup` to show grammar word pattern instead of full matched text

  **What to do**:
  - In `src/ui/tooltip.py`, line 139: change `self._word_label.setText(hit.matched_text)` to `self._word_label.setText(hit.word)`
  - This makes the tooltip title show the grammar pattern name (e.g., `が...なら`) instead of the full matched text (e.g., `がとてもきれいなら`)
  - The `word` field already contains the grammar pattern name from the JSON (e.g., `てから`, `ば...ほど`, `なり...なり`)
  - Line 142 already uses `hit.word or hit.matched_text` for the description prefix — this is already correct for fallback
  - This is a ONE LINE change

  **Must NOT do**:
  - Do NOT change tooltip layout, styling, or positioning
  - Do NOT change `show_for_vocab()` — only grammar tooltip changes
  - Do NOT add any new labels or widgets
  - Do NOT add sub-part visual distinction in tooltip (confirmed in interview)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Single line change — swap `hit.matched_text` → `hit.word`
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Task 3)
  - **Parallel Group**: Wave 2 (with Task 3)
  - **Blocks**: Task 5
  - **Blocked By**: Task 1 (needs `GrammarHit` with updated semantics)

  **References**:

  **Pattern References**:
  - `src/ui/tooltip.py:123-147` — `show_for_grammar()` method. Line 139 is the exact line to change.
  - `src/ui/tooltip.py:139` — `self._word_label.setText(hit.matched_text)` → change to `self._word_label.setText(hit.word)`
  - `src/ui/tooltip.py:142` — `self._desc_label.setText(f"{hit.word or hit.matched_text}: {description}")` — this line is ALREADY correct (uses `hit.word` with fallback).

  **WHY Each Reference Matters**:
  - Line 139 is the ONLY line that needs changing. Shows the exact current code and what to replace.
  - Line 142 shows the description label already prefers `hit.word` — so this change makes title consistent with description.

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Tooltip title shows grammar word pattern, not full matched text
    Tool: Bash (python3 -c)
    Preconditions: src/ui/tooltip.py modified
    Steps:
      1. Run: python3 -c "
import sys
# Read the actual source to verify the change
with open('src/ui/tooltip.py') as f:
    content = f.read()
# Check that line 139 (approximately) uses hit.word instead of hit.matched_text
assert 'self._word_label.setText(hit.word)' in content, 'Expected hit.word in word_label.setText'
assert 'self._word_label.setText(hit.matched_text)' not in content, 'hit.matched_text should be removed from word_label'
print('Tooltip title source check: PASS')
"
      2. Assert: exit code 0, source contains correct code
    Expected Result: `show_for_grammar()` uses `hit.word` for title label
    Failure Indicators: Old `hit.matched_text` still present in word_label
    Evidence: .sisyphus/evidence/task-4-tooltip-source.txt

  Scenario: Tooltip construction does not crash with word field
    Tool: Bash (python3)
    Preconditions: src/ui/tooltip.py modified, Task 1 complete
    Steps:
      1. Run: python3 -c "
# Just verify import works and no syntax errors
from src.ui.tooltip import TooltipPopup
print('TooltipPopup import: PASS')
"
      2. Assert: exit code 0, no import errors
    Expected Result: Module loads cleanly
    Failure Indicators: SyntaxError, ImportError
    Evidence: .sisyphus/evidence/task-4-import.txt
  ```

  **Commit**: YES (groups with Task 3)
  - Message: `feat(ui): render precise multi-span grammar highlights`
  - Files: `src/ui/tooltip.py`
  - Pre-commit: `pytest tests/test_highlight.py`

- [x] 5. Update and extend test suite for multi-part grammar highlighting

  **What to do**:
  Two test files need updates:

  **(A) `tests/test_grammar.py` — New tests for capturing group extraction**:
  - Add test: `test_grammar_hit_matched_parts_populated_for_capturing_groups` — Use a sentence that triggers rule 164 (`(なり).*?(なり)`) and verify `matched_parts` is a non-empty tuple of `(int, int)` pairs where each pair's text slice is a valid substring
  - Add test: `test_grammar_hit_matched_parts_empty_for_simple_rules` — Use `食べてから寝る` (rule 762, no capturing groups) and verify `matched_parts == ()`
  - Add test: `test_grammar_hit_matched_parts_spans_are_absolute_positions` — Verify each `(start, end)` in `matched_parts` satisfies `0 <= start < end <= len(text)` and `text[start:end]` is non-empty
  - Update `test_grammar_hit_fields` to also assert `isinstance(h.matched_parts, tuple)`

  **(B) `tests/test_highlight.py` — New tests for multi-span rendering and hover**:
  - Update `_make_grammar()` helper to accept optional `matched_parts` parameter with default `()`
  - Add test: `test_get_highlight_at_position_grammar_parts_only` — Multi-part grammar hit; positions on keyword parts return `GrammarHit`, filler position returns `None`
  - Add test: `test_get_highlight_at_position_grammar_fallback_full_range` — Grammar hit with empty `matched_parts`; all positions in `[start, end)` return hit (backward compat)
  - Add test: `test_apply_to_document_multi_part_grammar_partial_highlight` — Verify that for a multi-part grammar hit, only the keyword part characters get grammar color+bold, while filler characters remain unformatted
  - Add test: `test_vocab_not_suppressed_in_grammar_filler_gap` — Vocab hit within filler gap of multi-part grammar is NOT suppressed by `_is_fully_covered()`
  - Add test: `test_vocab_suppressed_within_grammar_part` — Vocab hit fully inside a keyword part IS still suppressed

  **Must NOT do**:
  - Do NOT modify any production source files in this task — tests only
  - Do NOT remove or modify existing tests — only add new ones and update `_make_grammar` helper
  - Do NOT create new test files — add to existing `test_grammar.py` and `test_highlight.py`

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Multiple test functions across two files, requires understanding of QTextDocument API, grammar matching, and the new `matched_parts` semantics
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 3 (sequential — depends on all prior tasks)
  - **Blocks**: F1-F4
  - **Blocked By**: Tasks 1, 2, 3, 4 (all production changes must be complete)

  **References**:

  **Pattern References**:
  - `tests/test_grammar.py:23-34` — `test_grammar_hit_fields()` — Add `isinstance(h.matched_parts, tuple)` assertion. Shows pattern for field validation tests.
  - `tests/test_grammar.py:37-43` — `test_grammar_hit_word_field_populated()` — Pattern for testing a specific rule's fields. Follow same style for capturing group tests.
  - `tests/test_highlight.py:40-49` — `_make_grammar()` helper. Needs `matched_parts=()` parameter added with default.
  - `tests/test_highlight.py:83-92` — `test_get_highlight_at_position_returns_grammar_over_vocab` — Pattern for position-based hit detection tests.
  - `tests/test_highlight.py:233-250` — `test_apply_to_document_grammar_suppresses_vocab` — Pattern for QTextCursor-based color verification.
  - `tests/test_highlight.py:253-276` — `test_apply_to_document_non_overlapping_both_present` — Shows how to verify colors at specific cursor positions using `charFormat().foreground().color().name()`.

  **API/Type References**:
  - `src/models.py:29-38` — `GrammarHit` with `matched_parts` field. Constructor signature for test helpers.
  - `PySide6.QtGui.QTextCursor` — `setPosition(N+1)` then `charFormat()` returns format of character at position N.

  **WHY Each Reference Matters**:
  - `_make_grammar()` helper is used by ALL highlight tests — updating it once ensures all new tests can use `matched_parts`
  - Existing test patterns show exact assertion style (QColor comparison, isinstance checks) to follow
  - QTextCursor position semantics (N+1 trick) must be followed exactly for color verification tests

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: All new and existing tests pass
    Tool: Bash
    Preconditions: All tasks 1-4 complete, test files updated
    Steps:
      1. Run: pytest tests/test_grammar.py tests/test_highlight.py -v
      2. Assert: 0 failures, all tests discovered and pass
      3. Count: at least 5 new tests added (verify with pytest output)
    Expected Result: All tests pass — both new multi-part tests and existing backward-compat tests
    Failure Indicators: Any test failure, missing test discovery
    Evidence: .sisyphus/evidence/task-5-all-tests.txt

  Scenario: Full test suite passes (no regressions anywhere)
    Tool: Bash
    Preconditions: All tasks 1-4 complete, test files updated
    Steps:
      1. Run: pytest tests/ -v
      2. Assert: 0 failures across entire suite
    Expected Result: No regressions in any module
    Failure Indicators: Any failure outside grammar/highlight tests
    Evidence: .sisyphus/evidence/task-5-full-suite.txt

  Scenario: Linting and type checking pass
    Tool: Bash
    Preconditions: All tasks 1-5 complete
    Steps:
      1. Run: ruff check . && ruff format --check .
      2. Run: mypy src/
      3. Assert: both commands exit 0
    Expected Result: Clean lint and type checks
    Failure Indicators: Ruff errors, mypy type errors
    Evidence: .sisyphus/evidence/task-5-lint-types.txt
  ```

  **Commit**: YES
  - Message: `test: comprehensive tests for multi-part grammar highlighting`
  - Files: `tests/test_grammar.py`, `tests/test_highlight.py`
  - Pre-commit: `pytest tests/`

---

## Final Verification Wave (MANDATORY — after ALL implementation tasks)

> 4 review agents run in PARALLEL. ALL must APPROVE. Rejection → fix → re-run.

- [x] F1. **Plan Compliance Audit** — `oracle`
  Read the plan end-to-end. For each "Must Have": verify implementation exists (read file, run command). For each "Must NOT Have": search codebase for forbidden patterns — reject with file:line if found. Check evidence files exist in `.sisyphus/evidence/`. Compare deliverables against plan.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [x] F2. **Code Quality Review** — `unspecified-high`
  Run `ruff check . && ruff format --check .` + `mypy src/` + `pytest tests/`. Review all changed files for: `type: ignore`, empty catches, `print()` in prod, commented-out code, unused imports. Check AI slop: excessive comments, over-abstraction, generic variable names.
  Output: `Lint [PASS/FAIL] | Types [PASS/FAIL] | Tests [N pass/N fail] | Files [N clean/N issues] | VERDICT`

- [x] F3. **Real Manual QA** — `unspecified-high`
  Start from clean state. Execute EVERY QA scenario from EVERY task — follow exact steps, capture evidence. Test cross-task integration (grammar with capturing groups vs without). Test edge cases: empty text, no grammar hits, overlapping hits. Save to `.sisyphus/evidence/final-qa/`.
  Output: `Scenarios [N/N pass] | Integration [N/N] | Edge Cases [N tested] | VERDICT`

- [x] F4. **Scope Fidelity Check** — `deep`
  For each task: read "What to do", read actual diff (`git log/diff`). Verify 1:1 — everything in spec was built (no missing), nothing beyond spec was built (no creep). Check "Must NOT do" compliance. Detect cross-task contamination: Task N touching Task M's files. Flag unaccounted changes.
  Output: `Tasks [N/N compliant] | Contamination [CLEAN/N issues] | Unaccounted [CLEAN/N files] | VERDICT`

---

## Commit Strategy

| After Task | Commit Message | Files | Pre-commit Check |
|-----------|---------------|-------|-----------------|
| 1 + 2 | `feat(analysis): extract capturing group spans in GrammarMatcher` | `src/models.py`, `src/analysis/grammar.py` | `pytest tests/test_grammar.py` |
| 3 + 4 | `feat(ui): render precise multi-span grammar highlights` | `src/ui/highlight.py`, `src/ui/tooltip.py` | `pytest tests/test_highlight.py` |
| 5 | `test: comprehensive tests for multi-part grammar highlighting` | `tests/test_grammar.py`, `tests/test_highlight.py` | `pytest tests/` |

---

## Success Criteria

### Verification Commands
```bash
pytest tests/ -v              # Expected: all tests pass, 0 failures
ruff check . && ruff format --check .  # Expected: clean
mypy src/                     # Expected: clean, no new errors
```

### Final Checklist
- [ ] All "Must Have" requirements implemented
- [ ] All "Must NOT Have" guardrails respected
- [ ] All existing tests pass (backward compatibility)
- [ ] New tests cover multi-part highlighting, fallback, hover detection, vocab suppression
- [ ] Grammar rules with capturing groups produce per-part highlight spans
- [ ] Grammar rules without capturing groups still work as before
