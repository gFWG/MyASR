# Grammar Overlap Resolution

## TL;DR

> **Quick Summary**: Add a greedy overlap resolution algorithm to `GrammarMatcher.match_all()` so overlapping grammar hits are reduced to the most relevant non-overlapping set, using a Longest → Earliest → JLPT tiebreaker cascade. Also add a minimum match length filter (≥2 chars) to suppress single-kana noise.
>
> **Deliverables**:
> - `_resolve_overlaps()` private method in `src/analysis/grammar.py`
> - `_MIN_MATCH_LEN = 2` module constant in `src/analysis/grammar.py`
> - Updated `match_all()` with resolution + updated docstring
> - `tests/test_grammar_resolution.py` — TDD unit + integration tests
>
> **Estimated Effort**: Short
> **Parallel Execution**: YES — 2 waves
> **Critical Path**: Task 1 (validate assumptions) → Task 2 (write tests) → Task 3 (implement) → Task 4 (regression + QA)

---

## Context

### Original Request
Analyze and fix grammar matching overlap issues in `src/analysis/grammar.py` where multiple grammar rules can match overlapping text spans, producing noisy results.

### Interview Summary
**Key Discussions**:
- **Strategy**: Longest match → Earliest start → Lowest JLPT level (harder wins) tiebreaker cascade
- **Strictness**: Strict non-overlapping — if two spans overlap by even 1 char, only the winner survives
- **Single-kana filtering**: Add minimum match length filter (≥2 chars) to suppress 71 single/double-char noise rules
- **Layer**: Resolution happens in `grammar.py` (analysis layer), not UI layer
- **Testing**: TDD — write failing tests first, then implement to pass them

**Research Findings**:
- 831 grammar rules (N1=253, N2=197, N3=181, N4=123, N5=77)
- 71 single/double-char regex rules are the major noise source (`に`, `と`, `な`, `も`, `し`, `い`, `が`, `か`, `の`, `は`, `で`, `を`)
- `ことにする` → 7 hits without resolution; should resolve to 1
- `ようにしている` → 10 hits without resolution; should resolve to ≤3
- Performance overhead: <1ms for typical ASR segments (<100 chars)
- Existing test coverage: zero tests for grammar-vs-grammar overlaps
- `highlight.py` grammar-vs-vocab suppression is unaffected (uses full containment, not overlap)

### Metis Review
**Identified Gaps** (addressed):
- **`matched_parts` contract**: Resolution uses `start_pos`/`end_pos` only; `matched_parts` is a rendering detail, preserved unchanged on winning hits
- **Min-length measurement**: Uses `end_pos - start_pos` (span width), not `len(matched_text)`
- **Zero-length matches**: Must be pre-filtered before resolution (regex `finditer()` can produce them)
- **Adjacent spans**: `[0,3)` and `[3,5)` are NOT overlapping — strict inequality `start_a < end_b AND start_b < end_a`
- **Vocab re-surfacing**: When a short grammar hit is eliminated, vocab hits it previously suppressed may re-appear — this is desired behavior
- **Assumption validation**: Must verify no legitimate grammar rule only matches 1 char before hardcoding min-length=2
- **Deterministic sort**: Single sort key `(-(end-start), start, jlpt)` guarantees stability

---

## Work Objectives

### Core Objective
Add overlap resolution to `GrammarMatcher.match_all()` so it returns a clean, non-overlapping set of grammar hits prioritized by length, position, and JLPT difficulty.

### Concrete Deliverables
- `_MIN_MATCH_LEN: int = 2` constant in `src/analysis/grammar.py`
- `_resolve_overlaps(self, hits: list[GrammarHit]) -> list[GrammarHit]` private method
- Modified `match_all()` calling `_resolve_overlaps()` before return, with updated docstring
- `tests/test_grammar_resolution.py` with unit tests (synthetic hits) + integration tests (real grammar.json)

### Definition of Done
- [ ] `pytest tests/test_grammar_resolution.py` — all tests PASS
- [ ] `pytest tests/test_grammar.py` — all existing tests PASS (zero regression)
- [ ] `ruff check src/analysis/grammar.py tests/test_grammar_resolution.py` — clean
- [ ] `mypy src/analysis/grammar.py` — clean
- [ ] `ことにする` resolves to exactly 1 hit
- [ ] `ようにしている` resolves to ≤3 non-overlapping hits

### Must Have
- Greedy interval selection with sort key `(-(end-start), start, jlpt_level)`
- Min-length filter using `end_pos - start_pos >= _MIN_MATCH_LEN`
- Zero-length match guard
- Results sorted by `start_pos` ascending after resolution
- `matched_parts` preserved unchanged on winning hits
- TDD test file with ≥12 parametrized test cases

### Must NOT Have (Guardrails)
- **DO NOT** modify `src/ui/highlight.py` — grammar-vs-vocab suppression stays as-is
- **DO NOT** modify `src/models.py` — no changes to `GrammarHit` or `AnalysisResult`
- **DO NOT** modify `src/analysis/pipeline.py` — no changes to pipeline orchestration
- **DO NOT** modify `data/grammar.json` — no changes to the rule data file
- **DO NOT** add `min_length` to `AppConfig` or any configuration — hardcode `_MIN_MATCH_LEN = 2`
- **DO NOT** add a `match_resolved()` public method — resolution happens inside `match_all()`
- **DO NOT** use `matched_parts` in overlap detection logic — use `start_pos`/`end_pos` only
- **DO NOT** add over-abstraction (no Interval Tree, no Aho-Corasick — greedy is sufficient for N<100)
- **DO NOT** resolve grammar-vs-vocab overlaps — that is handled in `highlight.py` and is out of scope

---

## Verification Strategy

> **ZERO HUMAN INTERVENTION** — ALL verification is agent-executed. No exceptions.

### Test Decision
- **Infrastructure exists**: YES — pytest configured in `pyproject.toml` with `pythonpath = ["."]`
- **Automated tests**: TDD — write failing tests first, then implement
- **Framework**: pytest (already in use)

### QA Policy
Every task MUST include agent-executed QA scenarios.
Evidence saved to `.sisyphus/evidence/task-{N}-{scenario-slug}.{ext}`.

- **Algorithm**: Use Bash (python -c) — construct synthetic hits, call `_resolve_overlaps()`, assert results
- **Integration**: Use Bash (python -c) — call `GrammarMatcher.match_all()` with real sentences, assert hit counts
- **Regression**: Use Bash (pytest) — run existing test suite, assert zero failures

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Start Immediately — validation + TDD tests):
├── Task 1: Validate assumptions about short rules in grammar.json [quick]
└── Task 2: Write TDD test file (tests/test_grammar_resolution.py) [deep]
    (Task 2 depends on Task 1's findings for min-length threshold)

Wave 2 (After Wave 1 — implementation + regression):
├── Task 3: Implement _resolve_overlaps() and modify match_all() [deep]
└── Task 4: Run regression suite + integration QA [unspecified-high]
    (Task 4 depends on Task 3)

Wave FINAL (After ALL tasks — independent review, 4 parallel):
├── Task F1: Plan compliance audit (oracle)
├── Task F2: Code quality review (unspecified-high)
├── Task F3: Real manual QA (unspecified-high)
└── Task F4: Scope fidelity check (deep)

Critical Path: Task 1 → Task 2 → Task 3 → Task 4 → F1-F4
Parallel Speedup: Wave 1 has partial parallelism (Task 1 is quick, feeds Task 2)
Max Concurrent: 4 (Final wave)
```

### Dependency Matrix

| Task | Depends On | Blocks | Wave |
|------|-----------|--------|------|
| 1 | — | 2, 3 | 1 |
| 2 | 1 | 3 | 1 |
| 3 | 1, 2 | 4 | 2 |
| 4 | 3 | F1-F4 | 2 |
| F1-F4 | 4 | — | FINAL |

### Agent Dispatch Summary

- **Wave 1**: 2 tasks — T1 → `quick`, T2 → `deep`
- **Wave 2**: 2 tasks — T3 → `deep`, T4 → `unspecified-high`
- **FINAL**: 4 tasks — F1 → `oracle`, F2 → `unspecified-high`, F3 → `unspecified-high`, F4 → `deep`

---

## TODOs

- [ ] 1. Validate Assumptions About Short Grammar Rules

  **What to do**:
  - Query `data/grammar.json` to find ALL rules where the regex can only ever match ≤1 character
  - Specifically check: are there any N1/N2 grammar rules whose regex matches exactly 1 character that would represent a legitimate grammar point (not particle noise)?
  - Count how many rules have regexes that CAN match 1-char strings (test by running each regex against single Japanese characters)
  - If any legitimate single-char N1/N2 rule is found, report it — this would require adjusting `_MIN_MATCH_LEN` or adding an exception list
  - Record findings as a comment at the top of the test file (Task 2) and as evidence

  **Must NOT do**:
  - Do NOT modify `data/grammar.json`
  - Do NOT modify any source code
  - Do NOT add exception lists preemptively — only flag if a legitimate rule is found

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Single-file data analysis, no code changes, quick scripted check
  - **Skills**: []
    - No specialized skills needed — just Python scripting against a JSON file

  **Parallelization**:
  - **Can Run In Parallel**: NO (Task 2 depends on this)
  - **Parallel Group**: Wave 1, sequential before Task 2
  - **Blocks**: Task 2, Task 3
  - **Blocked By**: None (can start immediately)

  **References**:

  **Pattern References**:
  - `data/grammar.json` — Full rule set (831 rules). Each rule has `id`, `re`, `word`, `description`, `level`. Check the `re` field for patterns that can match ≤1 char.

  **API/Type References**:
  - Python `re` module — use `re.fullmatch(pattern, char)` to test if a pattern can match single characters

  **WHY Each Reference Matters**:
  - `data/grammar.json` is the source of truth for all grammar rules. We need to verify assumption A2 (no legitimate grammar rule matches only 1 char) before hardcoding `_MIN_MATCH_LEN = 2`.

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Identify all rules that can match single characters
    Tool: Bash (python -c)
    Preconditions: data/grammar.json exists with 831 rules
    Steps:
      1. Load all 831 rules from data/grammar.json
      2. For each rule, test its regex against all common single Japanese characters:
         hiragana あ-ん (46), katakana ア-ン (46), common particles (は,が,を,に,で,と,も,の,か,へ,や,よ,ね,わ)
      3. Collect rules where any single-char test produces a match
      4. Group results by JLPT level and print summary
      5. Assert: report count and list of matching rules
    Expected Result: A list of rules that match single chars, grouped by level.
      All such rules should be N4/N5 particles. Zero N1/N2/N3 rules matching only single chars.
    Failure Indicators: Any N1/N2 rule matching only 1 char → _MIN_MATCH_LEN=2 needs reconsideration
    Evidence: .sisyphus/evidence/task-1-short-rule-analysis.txt
  ```

  **Evidence to Capture:**
  - [ ] `.sisyphus/evidence/task-1-short-rule-analysis.txt` — Full output of the analysis script

  **Commit**: NO (analysis only, no code changes)

- [ ] 2. Write TDD Tests for Overlap Resolution (RED phase)

  **What to do**:
  - Create `tests/test_grammar_resolution.py` with comprehensive tests for `_resolve_overlaps()` behavior
  - **Unit tests** (synthetic `GrammarHit` objects — no file I/O, no `GrammarMatcher`):
    - Empty hit list → returns empty list
    - Single hit → returns that hit unchanged
    - Two non-overlapping hits → both preserved
    - Two overlapping hits, different lengths → longer wins
    - Two overlapping hits, same length, different start → earlier start wins
    - Two hits with identical span → lower `jlpt_level` wins
    - Adjacent-but-touching spans `[0,3)` + `[3,5)` → both preserved (NOT overlapping)
    - Three mutually overlapping spans → greedy selects optimal non-overlapping set
    - Hit with `end_pos - start_pos < 2` → filtered by min-length
    - Hit with `start_pos == end_pos` (zero-length) → filtered
    - Hit with `matched_parts` → preserved unchanged on winning hit
    - Multiple occurrences of same `rule_id` (non-overlapping) → all preserved
    - Hit at `start_pos == 0` → handled correctly
    - Results returned sorted by `start_pos` ascending
  - **Integration tests** (real `GrammarMatcher` with `data/grammar.json`):
    - `ことにする` → exactly 1 hit (the full-phrase match)
    - `食べてから飲んでから寝る` → both `てから` occurrences preserved
    - `わけではない` → exactly 1 hit (the full-phrase match)
    - Empty string → empty list
  - Use `pytest.mark.parametrize` for the unit test matrix
  - Use `@pytest.fixture` for the real `GrammarMatcher` instance
  - Import `GrammarHit` from `src.models` for synthetic construction
  - Test the resolution indirectly via `match_all()` since `_resolve_overlaps` is private
  - All tests MUST FAIL at this point (implementation doesn't exist yet)

  **Must NOT do**:
  - Do NOT implement `_resolve_overlaps()` — that is Task 3
  - Do NOT modify any existing test files
  - Do NOT modify `src/analysis/grammar.py`
  - Do NOT add tests for vocab overlap resolution (out of scope)

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Requires careful test design covering 14+ edge cases, TDD discipline, understanding of the algorithm contract
  - **Skills**: []
    - No specialized skills needed — standard pytest patterns

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 1, after Task 1
  - **Blocks**: Task 3
  - **Blocked By**: Task 1 (min-length threshold validation)

  **References**:

  **Pattern References**:
  - `tests/test_grammar.py` — Existing grammar tests. Follow the same fixture patterns, import style, and assertion patterns. Note the `pipeline` fixture that loads real `data/grammar.json`.
  - `tests/conftest.py` — Shared fixtures. Check if there's a grammar matcher fixture to reuse.

  **API/Type References**:
  - `src/models.py:30-38` — `GrammarHit` dataclass fields. Use these exact fields when constructing synthetic test hits: `rule_id`, `matched_text`, `word`, `jlpt_level`, `description`, `start_pos`, `end_pos`, `matched_parts`.
  - `src/analysis/grammar.py:74-108` — `match_all()` method signature and return type. This is what integration tests call.

  **Test References**:
  - `tests/test_grammar.py` — See how existing tests construct fixtures, use real `data/grammar.json`, and assert on `GrammarHit` fields.
  - `tests/test_highlight.py` — See grammar-vs-vocab priority tests for assertion patterns on position-based hits.

  **WHY Each Reference Matters**:
  - `tests/test_grammar.py` provides the canonical test pattern to follow (fixture style, import conventions)
  - `src/models.py:GrammarHit` defines the exact constructor signature needed for synthetic hits
  - `src/analysis/grammar.py:match_all()` is the public API the integration tests will call

  **Acceptance Criteria**:

  **TDD (RED phase):**
  - [ ] `tests/test_grammar_resolution.py` created with ≥14 parametrized unit test cases
  - [ ] `tests/test_grammar_resolution.py` created with ≥4 integration test cases
  - [ ] `pytest tests/test_grammar_resolution.py` → ALL FAIL (expected — no implementation yet)
  - [ ] `pytest tests/test_grammar.py` → ALL PASS (no regression from just adding a test file)

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: All new tests fail (RED phase confirmation)
    Tool: Bash (pytest)
    Preconditions: tests/test_grammar_resolution.py exists, _resolve_overlaps() NOT yet implemented
    Steps:
      1. Run: pytest tests/test_grammar_resolution.py -v 2>&1
      2. Count FAILED tests in output
      3. Assert: all test cases report FAILED or ERROR (none pass accidentally)
    Expected Result: 0 passed, ≥14 failed or errors
    Failure Indicators: Any test PASSES → test is not actually testing resolution behavior
    Evidence: .sisyphus/evidence/task-2-red-phase.txt

  Scenario: Existing tests unaffected
    Tool: Bash (pytest)
    Preconditions: tests/test_grammar.py exists unchanged
    Steps:
      1. Run: pytest tests/test_grammar.py -v 2>&1
      2. Assert: all existing tests pass
    Expected Result: All tests PASS, 0 failures
    Failure Indicators: Any FAILURE → the new test file has import side-effects
    Evidence: .sisyphus/evidence/task-2-existing-tests.txt
  ```

  **Evidence to Capture:**
  - [ ] `.sisyphus/evidence/task-2-red-phase.txt` — pytest output showing all new tests FAIL
  - [ ] `.sisyphus/evidence/task-2-existing-tests.txt` — pytest output showing all existing tests PASS

  **Commit**: YES
  - Message: `test(grammar): add TDD tests for overlap resolution (RED)`
  - Files: `tests/test_grammar_resolution.py`
  - Pre-commit: `pytest tests/test_grammar.py -v` (existing tests still pass)

- [ ] 3. Implement `_resolve_overlaps()` and Modify `match_all()` (GREEN phase)

  **What to do**:
  - Add module-level constant to `src/analysis/grammar.py`:
    ```python
    _MIN_MATCH_LEN: int = 2
    ```
    Place it after the `logger = logging.getLogger(__name__)` line, before the `_CompiledRule` class.
  - Add private method `_resolve_overlaps` to `GrammarMatcher`:
    ```python
    def _resolve_overlaps(self, hits: list[GrammarHit]) -> list[GrammarHit]:
    ```
    Algorithm:
    1. Filter out zero-length matches (`hit.end_pos <= hit.start_pos`)
    2. Filter out hits shorter than `_MIN_MATCH_LEN` (`hit.end_pos - hit.start_pos < _MIN_MATCH_LEN`)
    3. Sort remaining hits by `key=lambda h: (-(h.end_pos - h.start_pos), h.start_pos, h.jlpt_level)`
       (longest first, then earliest start, then hardest JLPT)
    4. Greedy interval selection: iterate sorted hits, keep hit if it doesn't overlap any already-selected hit
       Overlap condition: `selected.start_pos < candidate.end_pos and candidate.start_pos < selected.end_pos`
    5. Re-sort selected hits by `start_pos` ascending before returning
  - Modify `match_all()`:
    - After the `for rule in self._rules:` loop collects all raw hits, add:
      ```python
      return self._resolve_overlaps(hits)
      ```
    - Update the docstring to document:
      - Min-length filtering (hits shorter than `_MIN_MATCH_LEN` chars are discarded)
      - Overlap resolution (greedy: longest → earliest → hardest JLPT wins)
      - Return order (sorted by `start_pos` ascending)
  - Run ALL tests to confirm GREEN phase

  **Must NOT do**:
  - Do NOT modify `src/ui/highlight.py`
  - Do NOT modify `src/models.py`
  - Do NOT modify `src/analysis/pipeline.py`
  - Do NOT modify `data/grammar.json`
  - Do NOT add `min_length` to `AppConfig`
  - Do NOT add a public `match_resolved()` method
  - Do NOT use `matched_parts` in overlap detection
  - Do NOT use Interval Tree or Aho-Corasick — simple greedy loop is sufficient
  - Do NOT add excessive comments — the algorithm is self-documenting with good variable names

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Algorithm implementation requiring careful correctness, TDD GREEN phase discipline, understanding of edge cases
  - **Skills**: []
    - No specialized skills needed — standard Python algorithm implementation

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 2, sequential
  - **Blocks**: Task 4
  - **Blocked By**: Task 1 (min-length validation), Task 2 (tests must exist first)

  **References**:

  **Pattern References**:
  - `src/analysis/grammar.py:14-31` — `_CompiledRule` frozen dataclass pattern. Follow the same style for constants and method documentation (Google-style docstrings).
  - `src/analysis/grammar.py:74-108` — Current `match_all()` implementation. The resolution call goes between the loop (line 107) and the return. Currently returns `hits` directly; change to `return self._resolve_overlaps(hits)`.
  - `src/analysis/grammar.py:51` — `self._rules: list[_CompiledRule]` — shows naming convention for private members.

  **API/Type References**:
  - `src/models.py:30-38` — `GrammarHit` fields used in the algorithm: `start_pos`, `end_pos`, `jlpt_level`. These are the ONLY fields the algorithm reads. All other fields pass through unchanged.

  **External References**:
  - Greedy Interval Scheduling algorithm: sort by priority metric, iterate keeping non-overlapping. Standard algorithm — no external library needed.

  **WHY Each Reference Matters**:
  - `grammar.py:74-108` is the exact code being modified — the executor must understand the current structure to insert the resolution call correctly
  - `grammar.py:14-31` shows the project's style for frozen dataclasses and type annotations
  - `models.py:GrammarHit` defines the fields the algorithm operates on

  **Acceptance Criteria**:

  **TDD (GREEN phase):**
  - [ ] `pytest tests/test_grammar_resolution.py -v` → ALL PASS
  - [ ] `pytest tests/test_grammar.py -v` → ALL PASS (zero regression)
  - [ ] `ruff check src/analysis/grammar.py` → clean
  - [ ] `mypy src/analysis/grammar.py` → clean

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: All new resolution tests pass (GREEN phase)
    Tool: Bash (pytest)
    Preconditions: _resolve_overlaps() implemented in grammar.py
    Steps:
      1. Run: pytest tests/test_grammar_resolution.py -v 2>&1
      2. Count PASSED vs FAILED
      3. Assert: all tests PASS, 0 failures
    Expected Result: ≥14 passed, 0 failed
    Failure Indicators: Any FAILURE → algorithm has a bug in that edge case
    Evidence: .sisyphus/evidence/task-3-green-phase.txt

  Scenario: Existing grammar tests still pass (regression)
    Tool: Bash (pytest)
    Preconditions: match_all() modified to call _resolve_overlaps()
    Steps:
      1. Run: pytest tests/test_grammar.py -v 2>&1
      2. Assert: all existing tests pass
    Expected Result: All existing tests PASS
    Failure Indicators: Any FAILURE → resolution changed match_all() behavior in a breaking way
    Evidence: .sisyphus/evidence/task-3-regression.txt

  Scenario: ことにする resolves to 1 hit (integration)
    Tool: Bash (python -c)
    Preconditions: grammar.py with _resolve_overlaps(), data/grammar.json exists
    Steps:
      1. Run:
         python -c "
         from src.analysis.grammar import GrammarMatcher
         gm = GrammarMatcher('data/grammar.json')
         hits = gm.match_all('ことにする')
         print(f'Hits: {len(hits)}')
         for h in hits: print(f'  {h.word} [{h.start_pos},{h.end_pos}) jlpt=N{h.jlpt_level}')
         assert len(hits) == 1, f'Expected 1, got {len(hits)}'
         print('PASS')
         "
      2. Assert: output shows exactly 1 hit and "PASS"
    Expected Result: 1 hit covering the full phrase ことにする
    Failure Indicators: More than 1 hit → resolution not filtering correctly; 0 hits → min-length or resolution too aggressive
    Evidence: .sisyphus/evidence/task-3-koto-ni-suru.txt

  Scenario: Non-overlapping duplicate patterns preserved
    Tool: Bash (python -c)
    Preconditions: grammar.py with _resolve_overlaps(), data/grammar.json exists
    Steps:
      1. Run:
         python -c "
         from src.analysis.grammar import GrammarMatcher
         gm = GrammarMatcher('data/grammar.json')
         hits = gm.match_all('食べてから飲んでから寝る')
         tekara = [h for h in hits if 'てから' in h.matched_text]
         print(f'てから hits: {len(tekara)}')
         for h in tekara: print(f'  [{h.start_pos},{h.end_pos}) {h.matched_text}')
         assert len(tekara) == 2, f'Expected 2 てから, got {len(tekara)}'
         print('PASS')
         "
      2. Assert: output shows exactly 2 てから hits at different positions and "PASS"
    Expected Result: 2 non-overlapping てから matches preserved
    Failure Indicators: 1 hit → algorithm incorrectly deduplicating by rule_id; 0 hits → min-length filtering too aggressively
    Evidence: .sisyphus/evidence/task-3-tekara-double.txt

  Scenario: Lint and type-check pass
    Tool: Bash (ruff + mypy)
    Preconditions: grammar.py modified
    Steps:
      1. Run: ruff check src/analysis/grammar.py 2>&1
      2. Run: mypy src/analysis/grammar.py 2>&1
      3. Assert: both return exit code 0
    Expected Result: No lint errors, no type errors
    Failure Indicators: Any error → fix before committing
    Evidence: .sisyphus/evidence/task-3-lint.txt
  ```

  **Evidence to Capture:**
  - [ ] `.sisyphus/evidence/task-3-green-phase.txt`
  - [ ] `.sisyphus/evidence/task-3-regression.txt`
  - [ ] `.sisyphus/evidence/task-3-koto-ni-suru.txt`
  - [ ] `.sisyphus/evidence/task-3-tekara-double.txt`
  - [ ] `.sisyphus/evidence/task-3-lint.txt`

  **Commit**: YES
  - Message: `feat(grammar): add overlap resolution to match_all()`
  - Files: `src/analysis/grammar.py`
  - Pre-commit: `pytest tests/ && ruff check src/analysis/grammar.py && mypy src/analysis/grammar.py`

- [ ] 4. Full Regression Suite + Integration QA

  **What to do**:
  - Run the ENTIRE test suite: `pytest tests/ -v`
  - Run integration QA with multiple real sentences through the full pipeline
  - Verify that `highlight.py` behavior is correct with resolved grammar hits (grammar-vs-vocab suppression still works as expected)
  - Test additional real sentences: `ようにしている`, `わけではない`, `食べなければならない`
  - Verify that the pipeline end-to-end (`PreprocessingPipeline.process()`) returns resolved hits
  - Check for any vocab hits that re-surfaced due to grammar hit elimination (expected and acceptable)

  **Must NOT do**:
  - Do NOT modify any source files — this is a verification-only task
  - Do NOT fix bugs found — report them for the implementing agent to fix in Task 3's session

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Comprehensive verification across multiple modules, requires careful analysis of behavior changes
  - **Skills**: []
    - No specialized skills needed

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 2, after Task 3
  - **Blocks**: F1-F4
  - **Blocked By**: Task 3

  **References**:

  **Pattern References**:
  - `src/analysis/pipeline.py:29-54` — `PreprocessingPipeline.process()` orchestrates tokenize → vocab → grammar. Integration tests should call this, not `GrammarMatcher` directly.
  - `src/ui/highlight.py:80-99` — `apply_to_document()` consumes `AnalysisResult.grammar_hits`. Fewer grammar hits after resolution → fewer highlight spans. Check that grammar-vs-vocab priority still works correctly.

  **API/Type References**:
  - `src/models.py:42-46` — `AnalysisResult` contains `grammar_hits: list[GrammarHit]`. This is what the pipeline returns.
  - `src/models.py:54-91` — `SentenceResult.get_display_analysis()` filters by JLPT level. Verify this still works with resolved hits.

  **WHY Each Reference Matters**:
  - `pipeline.py` is the real entry point for analysis — testing through it catches integration issues
  - `highlight.py` is the primary consumer — even though we don't modify it, we must verify it handles resolved hits correctly

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Full test suite passes
    Tool: Bash (pytest)
    Preconditions: All implementation complete
    Steps:
      1. Run: pytest tests/ -v 2>&1
      2. Assert: 0 failures, 0 errors
    Expected Result: All tests across ALL test files pass
    Failure Indicators: Any failure in any test file → regression detected
    Evidence: .sisyphus/evidence/task-4-full-suite.txt

  Scenario: Pipeline end-to-end with resolved grammar
    Tool: Bash (python -c)
    Preconditions: All implementation complete, data/grammar.json and data/vocabulary.csv exist
    Steps:
      1. Run:
         python -c "
         from src.analysis.pipeline import PreprocessingPipeline
         p = PreprocessingPipeline()
         r = p.process('ことにする')
         print(f'Grammar hits: {len(r.grammar_hits)}')
         for h in r.grammar_hits:
             print(f'  {h.word} [{h.start_pos},{h.end_pos}) N{h.jlpt_level}')
         assert len(r.grammar_hits) == 1
         # Also test non-overlapping preservation
         r2 = p.process('食べてから飲んでから寝る')
         tekara = [h for h in r2.grammar_hits if 'てから' in h.matched_text]
         print(f'てから hits: {len(tekara)}')
         assert len(tekara) == 2
         print('ALL PASS')
         "
      2. Assert: output shows 1 hit for ことにする, 2 hits for てから, and "ALL PASS"
    Expected Result: Pipeline returns resolved, non-overlapping grammar hits
    Failure Indicators: Unexpected hit counts → resolution not working through pipeline
    Evidence: .sisyphus/evidence/task-4-pipeline-e2e.txt

  Scenario: Additional real sentence verification
    Tool: Bash (python -c)
    Preconditions: All implementation complete
    Steps:
      1. Run:
         python -c "
         from src.analysis.grammar import GrammarMatcher
         gm = GrammarMatcher('data/grammar.json')
         # Test multiple real sentences
         tests = [
             ('ようにしている', 3),   # expect ≤3 non-overlapping
             ('わけではない', 1),      # expect 1 (full phrase)
             ('食べなければならない', 1),  # expect 1 (なければならない)
         ]
         for text, max_expected in tests:
             hits = gm.match_all(text)
             # Verify non-overlapping
             for i, a in enumerate(hits):
                 for b in hits[i+1:]:
                     assert not (a.start_pos < b.end_pos and b.start_pos < a.end_pos), \
                         f'Overlap detected: {a.word}[{a.start_pos},{a.end_pos}) vs {b.word}[{b.start_pos},{b.end_pos})'
             print(f'{text}: {len(hits)} hits (max expected: {max_expected}) - non-overlapping verified')
             assert len(hits) <= max_expected, f'{text}: expected ≤{max_expected}, got {len(hits)}'
         print('ALL PASS')
         "
      2. Assert: all sentences produce ≤expected hits, all non-overlapping, "ALL PASS"
    Expected Result: Real sentences produce clean, non-overlapping grammar hit sets
    Failure Indicators: Overlap detected or too many hits → resolution has gaps
    Evidence: .sisyphus/evidence/task-4-real-sentences.txt

  Scenario: No overlapping grammar hits in output (property test)
    Tool: Bash (python -c)
    Preconditions: All implementation complete
    Steps:
      1. Run:
         python -c "
         from src.analysis.grammar import GrammarMatcher
         gm = GrammarMatcher('data/grammar.json')
         sentences = [
             'ことにする', 'ようにしている', 'わけではない',
             '食べなければならない', '食べてから飲んでから寝る',
             '日本語を勉強しなければならないと思います',
             '彼女は毎日運動するようにしている',
         ]
         for s in sentences:
             hits = gm.match_all(s)
             hits_sorted = sorted(hits, key=lambda h: h.start_pos)
             for i in range(len(hits_sorted) - 1):
                 a, b = hits_sorted[i], hits_sorted[i+1]
                 assert a.end_pos <= b.start_pos, \
                     f'OVERLAP in \"{s}\": {a.word}[{a.start_pos},{a.end_pos}) vs {b.word}[{b.start_pos},{b.end_pos})'
             print(f'  {s}: {len(hits)} non-overlapping hits ✓')
         print('ALL PASS — no overlaps detected in any sentence')
         "
      2. Assert: all sentences have strictly non-overlapping hits, "ALL PASS"
    Expected Result: Zero overlapping pairs across all test sentences
    Failure Indicators: Any overlap assertion failure → algorithm bug
    Evidence: .sisyphus/evidence/task-4-no-overlap-property.txt
  ```

  **Evidence to Capture:**
  - [ ] `.sisyphus/evidence/task-4-full-suite.txt`
  - [ ] `.sisyphus/evidence/task-4-pipeline-e2e.txt`
  - [ ] `.sisyphus/evidence/task-4-real-sentences.txt`
  - [ ] `.sisyphus/evidence/task-4-no-overlap-property.txt`

  **Commit**: NO (verification only)

---

## Final Verification Wave (MANDATORY — after ALL implementation tasks)

> 4 review agents run in PARALLEL. ALL must APPROVE. Rejection → fix → re-run.

- [ ] F1. **Plan Compliance Audit** — `oracle`
  Read the plan end-to-end. For each "Must Have": verify implementation exists (read `src/analysis/grammar.py`, find `_resolve_overlaps`, `_MIN_MATCH_LEN`, updated docstring). For each "Must NOT Have": search for modifications to `highlight.py`, `models.py`, `pipeline.py`, `grammar.json`. Check evidence files exist in `.sisyphus/evidence/`. Compare deliverables against plan.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [ ] F2. **Code Quality Review** — `unspecified-high`
  Run `ruff check src/analysis/grammar.py tests/test_grammar_resolution.py && mypy src/analysis/grammar.py && pytest tests/`. Review `grammar.py` for: magic numbers (should use `_MIN_MATCH_LEN`), empty catches, `type: ignore`, commented-out code, unused imports, excessive comments, over-abstraction.
  Output: `Ruff [PASS/FAIL] | Mypy [PASS/FAIL] | Tests [N pass/N fail] | Code Review [CLEAN/N issues] | VERDICT`

- [ ] F3. **Real Manual QA** — `unspecified-high`
  Execute EVERY QA scenario from EVERY task — follow exact steps in `python -c` blocks, capture evidence. Test with real sentences: `ことにする`, `ようにしている`, `わけではない`, `食べなければならない`, `食べてから飲んでから寝る`. Verify non-overlapping output. Save to `.sisyphus/evidence/final-qa/`.
  Output: `Scenarios [N/N pass] | Integration [N/N] | Edge Cases [N tested] | VERDICT`

- [ ] F4. **Scope Fidelity Check** — `deep`
  Run `git diff` on all changed files. Verify ONLY `src/analysis/grammar.py` and `tests/test_grammar_resolution.py` were modified/created. No changes to `highlight.py`, `models.py`, `pipeline.py`, `grammar.json`, `config.py`. Check "Must NOT do" compliance. Flag unaccounted changes.
  Output: `Files Changed [N expected/N actual] | Scope [CLEAN/N violations] | VERDICT`

---

## Commit Strategy

| Order | Message | Files | Pre-commit Check |
|-------|---------|-------|-----------------|
| 1 | `test(grammar): add TDD tests for overlap resolution (RED)` | `tests/test_grammar_resolution.py` | `pytest tests/test_grammar.py` (existing pass, new fail expected) |
| 2 | `feat(grammar): add overlap resolution to match_all()` | `src/analysis/grammar.py` | `pytest tests/ && ruff check src/analysis/grammar.py && mypy src/analysis/grammar.py` |
| 3 (optional) | `chore: lint fixes for grammar resolution` | any | `ruff check . && mypy src/` — skip if commit 2 is clean |

---

## Success Criteria

### Verification Commands
```bash
pytest tests/test_grammar_resolution.py -v  # Expected: all PASS
pytest tests/test_grammar.py -v              # Expected: all PASS (zero regression)
ruff check src/analysis/grammar.py           # Expected: clean
mypy src/analysis/grammar.py                 # Expected: clean
python -c "
from src.analysis.grammar import GrammarMatcher
gm = GrammarMatcher('data/grammar.json')
hits = gm.match_all('ことにする')
print(f'ことにする: {len(hits)} hit(s)')
for h in hits: print(f'  {h.word} [{h.start_pos},{h.end_pos})')
assert len(hits) == 1
"
```

### Final Checklist
- [ ] All "Must Have" present: `_MIN_MATCH_LEN`, `_resolve_overlaps()`, updated docstring, test file
- [ ] All "Must NOT Have" absent: no changes to highlight.py, models.py, pipeline.py, grammar.json
- [ ] All tests pass: existing + new
- [ ] Overlap examples produce expected hit counts
