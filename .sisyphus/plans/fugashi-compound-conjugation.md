# Fugashi Compound Merging & Conjugation Chain Extension

## TL;DR

> **Quick Summary**: Leverage Fugashi's UniDic POS data to merge prefix-compound tokens (e.g., お+世辞→お世辞) for correct JLPT lookup, and extend verb conjugation chain highlighting (e.g., 続けさせる highlights fully, not just 続け).
> 
> **Deliverables**:
> - Extended Token model with pos2, cType, cForm fields
> - Prefix-compound merging with greedy longest-match (up to 6 tokens)
 > - Conservative verb/adjective conjugation chain span extension (助動詞 + て/で bridge only)
> - Full TDD test suite (compound + chain tests)
> 
> **Estimated Effort**: Medium
> **Parallel Execution**: YES - 4 waves
> **Critical Path**: Task 1 → Task 2 → Task 4 → Task 6

---

## Context

### Original Request
Improve word matching and display by using Fugashi's data:
1. "お世辞" should be treated as a whole word for lookup, highlight, and tooltip
2. "続けさせる" — "続け" correctly looks up 続ける, but "させる" should also be highlighted as part of the conjugated verb

### Interview Summary
**Key Discussions**:
- Fugashi (unidic-lite) uses Short Unit Word tokenization — splits compounds and conjugation chains
- UnidicFeatures26 provides pos2, cType, cForm fields currently unused
- Vocab CSV has "お世辞" as entry (id=1375, N1); also "世辞" separately (id=2675, N1)
- ~69 お/ご-prefix entries are actually split by Fugashi and need merging
- ~28 are already single tokens (e.g., ご飯) — no action needed
- Some compounds span 3-6 tokens (e.g., お願いします=4 tokens, おまたせしました=6)

**Research Findings**:
- Surface concatenation (NOT lemma) required for compound lookup — Fugashi lemma for お is 御, but CSV key is お世辞
- Chain detection uses conservative POS rules: 助動詞 continuation + て/で surface whitelist only (no pos2-based 接続助詞 matching, no 動詞/非自立可能, no 形容詞/非自立可能)
- Strategy: prefer missing edge cases over false positives — grammar layer handles complex patterns
- UI layer (highlight.py, tooltip.py) needs NO changes — already works with arbitrary start_pos/end_pos spans
- Grammar layer operates on raw text, completely independent — no changes needed

**User Decisions**:
- Tooltip shows base form only (e.g., 続ける)
- Compound wins exclusively (お世辞 suppresses standalone 世辞)
- Pronunciation from CSV only, never Fugashi kana fields
- TDD approach: write failing tests first

### Metis Review
**Identified Gaps** (addressed):
- Compound window must be 6 tokens (not 2) — おまたせしました needs 6
- Surface-concat is ONLY valid lookup key (lemma-concat yields 御世辞 = wrong)
- Index-based while loop required (for-each cannot skip consumed tokens)
- Token backward compatibility: new fields must have defaults
- Chain extension must handle て-form bridges via surface whitelist (て/で only, NOT pos2=接続助詞)
- お願いします is simultaneously compound + chain — greedy longest-match handles this

---

## Work Objectives

### Core Objective
Extend the analysis pipeline to correctly identify and highlight multi-token Japanese words by leveraging Fugashi's POS data for prefix-compound merging and verb conjugation chain detection.

### Concrete Deliverables
- `src/models.py`: Token with pos2, cType, cForm fields (backward compatible)
- `src/analysis/tokenizer.py`: Extract pos2/cType/cForm; compound merging function
- `src/analysis/jlpt_vocab.py`: Index-based iteration + chain extension logic
- `src/analysis/pipeline.py`: Wire compound merge step
- `tests/test_compound_merging.py`: Compound merge test suite
- `tests/test_chain_extension.py`: Chain extension test suite

### Definition of Done
- [ ] `pytest tests/test_compound_merging.py -v` — all pass
- [ ] `pytest tests/test_chain_extension.py -v` — all pass
- [ ] `pytest tests/` — zero regressions
- [ ] `ruff check . && ruff format --check .` — clean
- [ ] `mypy src/` — clean
- [ ] お世辞 recognized as single compound in pipeline output
- [ ] 続けさせる fully highlighted with lemma=続ける

### Must Have
- Greedy longest-match compound merging (up to MAX_COMPOUND_TOKENS=6)
- Surface concatenation for compound lookup (never lemma concat)
- Chain extension for 動詞 and 形容詞 head tokens (conservative: 助動詞 + て/で surface bridge only)
- て/で surface whitelist for chain bridge (NOT pos2=接続助詞 — avoids ば/けど/から/が/のに false positives)
- No 動詞/非自立可能 or 形容詞/非自立可能 in chain continuation (grammar layer handles てしまう, てほしい, etc.)
- Compound-wins-exclusively suppression of individual component matches
- Token backward compatibility (positional construction still works)

### Must NOT Have (Guardrails)
- NO changes to grammar.py, GrammarMatcher, or grammar hits
- NO changes to highlight.py or tooltip.py
- NO Fugashi kana/pronBase as pronunciation source
- NO cForm in chain detection predicate (extract but don't use for chain logic)
- NO hardcoded お/ご prefix characters — 接頭辞 POS tag is the only trigger
- NO Long Unit Word (LUW) detection
- NO conjugation info in tooltip display
- NO non-お/ご prefix special-case handling (不/非/無 etc.)
- NO modification of existing tests (only ADD new test files)

---

## Verification Strategy

> **ZERO HUMAN INTERVENTION** — ALL verification is agent-executed. No exceptions.

### Test Decision
- **Infrastructure exists**: YES (pytest with pythonpath=["."])
- **Automated tests**: TDD (RED-GREEN-REFACTOR)
- **Framework**: pytest
- **TDD flow**: Each implementation task has a preceding test task; tests MUST FAIL before implementation

### QA Policy
Every task includes agent-executed QA scenarios.
Evidence saved to `.sisyphus/evidence/task-{N}-{scenario-slug}.{ext}`.

- **Analysis pipeline**: Use Bash (pytest + python REPL) — run pipeline on test sentences, assert output
- **Token model**: Use Bash (pytest) — construct tokens, verify fields
- **Integration**: Use Bash (pytest) — full pipeline with real Fugashi tokenizer

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Start Immediately — foundation):
├── Task 1: Extend Token model with pos2/cType/cForm [quick]
├── Task 2: Extract new UniDic fields in tokenizer [quick]

Wave 2 (After Wave 1 — compound merging, TDD):
├── Task 3: Write failing compound merge tests [quick]
├── Task 4: Implement compound merge function + wire pipeline [deep]

Wave 3 (After Wave 2 — chain extension, TDD):
├── Task 5: Write failing chain extension tests [quick]
├── Task 6: Implement chain extension in find_all_vocab [deep]

Wave 4 (After ALL — verification):
├── Task F1: Plan compliance audit [oracle]
├── Task F2: Code quality review [unspecified-high]
├── Task F3: Full pipeline QA [unspecified-high]
└── Task F4: Scope fidelity check [deep]

Critical Path: Task 1 → Task 2 → Task 4 → Task 6 → F1-F4
```

### Dependency Matrix

| Task | Depends On | Blocks |
|------|-----------|--------|
| 1 | — | 2, 3, 5 |
| 2 | 1 | 3, 4, 5, 6 |
| 3 | 1, 2 | 4 |
| 4 | 3 | 5, 6 |
| 5 | 4 | 6 |
| 6 | 5 | F1-F4 |
| F1-F4 | 6 | — |

### Agent Dispatch Summary

- **Wave 1**: 2 tasks — T1 `quick`, T2 `quick`
- **Wave 2**: 2 tasks — T3 `quick`, T4 `deep`
- **Wave 3**: 2 tasks — T5 `quick`, T6 `deep`
- **Wave FINAL**: 4 tasks — F1 `oracle`, F2 `unspecified-high`, F3 `unspecified-high`, F4 `deep`

---

## TODOs

> Implementation + Test = ONE Task where noted. EVERY task has QA Scenarios.

- [ ] 1. Extend Token model with pos2, cType, cForm fields

  **What to do**:
  - Add `pos2: str = ""`, `cType: str = ""`, `cForm: str = ""` to the `Token` dataclass in `src/models.py`
  - Fields MUST be keyword-only with default empty strings so existing positional construction `Token("surface", "lemma", "pos")` continues to work
  - Use Python 3.12 dataclass field syntax — add after existing `pos` field with `field(default="")` or keyword-only defaults
  - Write a backward compatibility test immediately: `Token("食べ", "食べる", "動詞")` must still work
  - Verify all existing tests pass unchanged

  **Must NOT do**:
  - Do NOT rename existing `pos` field
  - Do NOT make Token frozen or slotted (it's currently a plain dataclass)
  - Do NOT modify any other model classes (VocabHit, GrammarHit, etc.)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Single file change, adding 3 fields with defaults — trivial modification
  - **Skills**: []
    - No specialized skills needed for a dataclass field addition

  **Parallelization**:
  - **Can Run In Parallel**: NO (foundation for all other tasks)
  - **Parallel Group**: Wave 1 (with Task 2, but Task 2 depends on this)
  - **Blocks**: Tasks 2, 3, 4, 5, 6
  - **Blocked By**: None (can start immediately)

  **References**:

  **Pattern References**:
  - `src/models.py:14-18` — Current Token dataclass definition with surface, lemma, pos fields

  **Test References**:
  - `tests/test_tokenizer.py` — Uses `Token(surface=..., lemma=..., pos=...)` construction — must still work after changes
  - `tests/test_jlpt_vocab.py` — Creates Token objects for vocab lookup tests

  **WHY Each Reference Matters**:
  - `models.py:14-18`: This is the exact class being modified — executor must see current field order and style
  - Test files: Must verify these still pass after adding new fields — backward compatibility proof

  **Acceptance Criteria**:
  - [ ] `Token("食べ", "食べる", "動詞")` constructs without error (backward compat)
  - [ ] `Token("食べ", "食べる", "動詞", pos2="一般", cType="下一段-バ行", cForm="連用形-一般")` constructs correctly
  - [ ] `token.pos2 == ""` when not specified (default)
  - [ ] `pytest tests/test_tokenizer.py tests/test_jlpt_vocab.py` — all pass unchanged
  - [ ] `mypy src/models.py` — no errors

  **QA Scenarios**:

  ```
  Scenario: Token backward compatibility
    Tool: Bash (pytest)
    Preconditions: Token model updated with new fields
    Steps:
      1. Run: pytest tests/test_tokenizer.py tests/test_jlpt_vocab.py -v
      2. Run: python -c "from src.models import Token; t = Token('食べ', '食べる', '動詞'); assert t.pos2 == ''; assert t.cType == ''; assert t.cForm == ''; print('PASS')"
      3. Run: python -c "from src.models import Token; t = Token('食べ', '食べる', '動詞', pos2='一般', cType='下一段-バ行', cForm='連用形-一般'); assert t.pos2 == '一般'; print('PASS')"
    Expected Result: All tests pass, both python commands print PASS
    Failure Indicators: ImportError, TypeError on construction, assertion failure
    Evidence: .sisyphus/evidence/task-1-token-compat.txt

  Scenario: Mypy type check passes
    Tool: Bash (mypy)
    Preconditions: Token model updated
    Steps:
      1. Run: mypy src/models.py
    Expected Result: "Success: no issues found"
    Failure Indicators: Any mypy error about Token fields
    Evidence: .sisyphus/evidence/task-1-mypy.txt
  ```

  **Commit**: YES
  - Message: `feat(models): add pos2, cType, cForm fields to Token with defaults`
  - Files: `src/models.py`
  - Pre-commit: `pytest tests/test_tokenizer.py tests/test_jlpt_vocab.py && mypy src/models.py`

- [ ] 2. Extract pos2, cType, cForm from UniDic features in tokenizer

  **What to do**:
  - In `src/analysis/tokenizer.py`, inside the `tokenize()` method's loop, extract `word.feature.pos2`, `word.feature.cType`, `word.feature.cForm` alongside existing surface/lemma/pos1
  - Handle None/missing values: if `word.feature.pos2` is None, use `""` (same pattern as existing lemma fallback)
  - Pass the new fields to Token constructor: `Token(surface=surface, lemma=lemma, pos=pos, pos2=pos2, cType=ctype, cForm=cform)`
  - Add a test that verifies real Fugashi output populates these fields for known inputs (e.g., "食べる" should give pos2="一般" or similar, cType="下一段-バ行")

  **Must NOT do**:
  - Do NOT extract kana, pron, pronBase, or other UniDic fields (future scope)
  - Do NOT change the POS filter logic (補助記号/記号 exclusion stays the same)
  - Do NOT change the lemma cleaning logic (split("-")[0] stays in jlpt_vocab.py, not here)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Adding 3 field extractions to an existing loop — small, well-defined change
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (depends on Task 1)
  - **Parallel Group**: Wave 1 (sequential after Task 1)
  - **Blocks**: Tasks 3, 4, 5, 6
  - **Blocked By**: Task 1

  **References**:

  **Pattern References**:
  - `src/analysis/tokenizer.py:22-42` — Current tokenize() method showing word.feature.lemma and word.feature.pos1 extraction pattern
  - `src/analysis/tokenizer.py:15-19` — POS filter set and EXCLUDED_POS constant

  **API/Type References**:
  - `src/models.py:14-18` — Token dataclass (after Task 1, will have pos2/cType/cForm fields)

  **External References**:
  - UnidicFeatures26 attribute names: `pos2`, `cType`, `cForm` — accessed via `word.feature.pos2` etc.

  **WHY Each Reference Matters**:
  - `tokenizer.py:22-42`: Shows the exact loop where new extraction must be added — executor must follow the existing None-fallback pattern
  - `tokenizer.py:15-19`: Executor must NOT modify the filter — only add extraction below existing code
  - `models.py`: Token constructor call must include new keyword args

  **Acceptance Criteria**:
  - [ ] `tokenizer.tokenize("食べる")` returns Token with non-empty pos2, cType, cForm
  - [ ] `tokenizer.tokenize("お世辞")` returns tokens where first token has pos="接頭辞"
  - [ ] Tokens with None features get empty string defaults (no AttributeError)
  - [ ] `pytest tests/test_tokenizer.py -v` — all pass (existing + new)
  - [ ] `ruff check src/analysis/tokenizer.py` — clean

  **QA Scenarios**:

  ```
  Scenario: UniDic fields extracted for known verb
    Tool: Bash (python)
    Preconditions: Tokenizer updated to extract pos2/cType/cForm
    Steps:
      1. Run: python -c "
         from src.analysis.tokenizer import FugashiTokenizer
         t = FugashiTokenizer()
         tokens = t.tokenize('食べさせる')
         for tok in tokens:
             print(f'{tok.surface} pos={tok.pos} pos2={tok.pos2} cType={tok.cType} cForm={tok.cForm}')
         assert any(tok.cType != '' for tok in tokens), 'No cType found'
         assert any(tok.pos2 != '' for tok in tokens), 'No pos2 found'
         print('PASS')
         "
    Expected Result: Prints token details with non-empty pos2/cType/cForm, ends with PASS
    Failure Indicators: AttributeError, empty cType/cForm for all tokens, assertion failure
    Evidence: .sisyphus/evidence/task-2-unidic-fields.txt

  Scenario: Prefix token correctly identified
    Tool: Bash (python)
    Preconditions: Tokenizer updated
    Steps:
      1. Run: python -c "
         from src.analysis.tokenizer import FugashiTokenizer
         t = FugashiTokenizer()
         tokens = t.tokenize('お世辞を言う')
         assert tokens[0].surface == 'お'
         assert tokens[0].pos == '接頭辞'
         print('PASS: prefix detected')
         "
    Expected Result: Prints "PASS: prefix detected"
    Failure Indicators: Assertion failure on pos or surface
    Evidence: .sisyphus/evidence/task-2-prefix-detection.txt
  ```

  **Commit**: YES
  - Message: `feat(tokenizer): extract pos2, cType, cForm from UniDic features`
  - Files: `src/analysis/tokenizer.py`, `tests/test_tokenizer.py`
  - Pre-commit: `pytest tests/test_tokenizer.py && ruff check src/analysis/tokenizer.py`

- [ ] 3. Write failing tests for prefix-compound merging (TDD RED phase)

  **What to do**:
  - Create `tests/test_compound_merging.py` with comprehensive test cases
  - Tests use real `FugashiTokenizer` output (not mocked tokens) for behavioral contracts
  - Test cases to include:
    - **AC1**: お世辞 recognized as compound (2-token merge) — VocabHit with surface="お世辞"
    - **AC2**: Compound suppresses standalone component — お世辞 found → no standalone 世辞 hit
    - **AC3**: Non-split compounds unaffected — ご飯 stays single token, single VocabHit
    - **AC8**: Position tracking — text="彼はお世辞を言った", assert hit.start_pos==2, text[start:end]=="お世辞"
    - **AC11**: AnalysisResult.tokens reflects merged token — compound counted as 1 token, not 2
    - **EC3**: Duplicate compounds in same sentence — "お世辞お世辞" finds both occurrences
    - **EC6**: Chained prefixes — ご無沙汰 (if in vocab) or similar 3-token compound
    - **EC1**: お願いします (4-token compound) — greedy longest match
    - Compound Token.pos uses head content word's pos (名詞 for お世辞, not 接頭辞)
  - Use `@pytest.mark.parametrize` for multiple sentence variations
  - Import from `src.analysis.pipeline import PreprocessingPipeline` for integration tests
  - Import from `src.analysis.tokenizer import FugashiTokenizer` for unit tests
  - ALL tests MUST FAIL at this point (no implementation yet)

  **Must NOT do**:
  - Do NOT implement any compound merging logic
  - Do NOT modify existing test files
  - Do NOT mock Fugashi output — use real tokenizer for behavioral contracts
  - Do NOT use `pytest.mark.skip` or `pytest.mark.xfail`

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Writing test file only — no implementation logic, clear structure from acceptance criteria
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (depends on Tasks 1, 2)
  - **Parallel Group**: Wave 2 (with Task 4)
  - **Blocks**: Task 4
  - **Blocked By**: Tasks 1, 2

  **References**:

  **Pattern References**:
  - `tests/test_jlpt_vocab.py` — Existing vocab test patterns, how VocabHit assertions are structured
  - `tests/test_analysis_pipeline.py` — How PreprocessingPipeline is tested end-to-end
  - `tests/test_tokenizer.py` — How FugashiTokenizer tests are structured

  **API/Type References**:
  - `src/models.py:Token` — Token fields to assert on (surface, lemma, pos, pos2)
  - `src/models.py:VocabHit` — VocabHit fields (surface, lemma, start_pos, end_pos, jlpt_level)
  - `src/models.py:AnalysisResult` — Contains tokens, vocab_hits, grammar_hits

  **Data References**:
  - `data/vocabulary.csv` — Has "お世辞" (id=1375, N1), "世辞" (id=2675, N1), "お茶" (various), "お願い" (N4)

  **WHY Each Reference Matters**:
  - `test_jlpt_vocab.py`: Shows assertion patterns for VocabHit (surface, lemma, positions) — copy this style
  - `test_analysis_pipeline.py`: Shows how to run full pipeline and check AnalysisResult — needed for integration tests
  - `vocabulary.csv`: Must know which compounds are actually in the CSV to write valid test expectations

  **Acceptance Criteria**:
  - [ ] `tests/test_compound_merging.py` file exists with 8+ test functions
  - [ ] `pytest tests/test_compound_merging.py --co` — collects all tests without import errors
  - [ ] `pytest tests/test_compound_merging.py` — all tests FAIL (RED phase confirmed)
  - [ ] Tests cover AC1, AC2, AC3, AC8, AC11, EC1, EC3, EC6

  **QA Scenarios**:

  ```
  Scenario: Tests collect and fail correctly (TDD RED)
    Tool: Bash (pytest)
    Preconditions: Test file created, no compound implementation exists
    Steps:
      1. Run: pytest tests/test_compound_merging.py --co -q
      2. Verify output shows 8+ test items collected
      3. Run: pytest tests/test_compound_merging.py -v 2>&1 | tail -5
      4. Verify output shows FAILED (not PASSED, not ERROR)
    Expected Result: All tests collected successfully, all tests FAIL (not error, not skip)
    Failure Indicators: ImportError, collection errors, any test passing prematurely
    Evidence: .sisyphus/evidence/task-3-red-phase.txt

  Scenario: Existing tests unaffected
    Tool: Bash (pytest)
    Preconditions: New test file added
    Steps:
      1. Run: pytest tests/test_tokenizer.py tests/test_jlpt_vocab.py tests/test_analysis_pipeline.py -v
    Expected Result: All existing tests still pass
    Failure Indicators: Any existing test failure
    Evidence: .sisyphus/evidence/task-3-existing-tests.txt
  ```

  **Commit**: YES
  - Message: `test(compound): add failing tests for prefix-compound merging (TDD RED)`
  - Files: `tests/test_compound_merging.py`
  - Pre-commit: `pytest tests/test_compound_merging.py --co && ruff check tests/test_compound_merging.py`

- [ ] 4. Implement prefix-compound merging (TDD GREEN phase)

  **What to do**:
  - Create a `merge_prefix_compounds(tokens: list[Token], text: str, vocab: dict[str, VocabEntry]) -> list[Token]` function
  - Place it in `src/analysis/tokenizer.py` (alongside the tokenizer) or a new `src/analysis/compound.py` — prefer tokenizer.py to avoid new module unless it exceeds ~30 lines
  - **Algorithm — Greedy Longest-Match Surface Concatenation**:
    1. Iterate tokens with index-based `while i < len(tokens)` loop
    2. When `tokens[i].pos == "接頭辞"`, start compound detection:
       a. Try window sizes from `MAX_COMPOUND_TOKENS` (6) down to 2
       b. For each window size `w`, concatenate surfaces: `"".join(t.surface for t in tokens[i:i+w])`
       c. Look up concatenated surface in vocab dict
       d. If found: create merged Token(surface=concat, lemma=concat, pos=tokens[i+1].pos, pos2=tokens[i+1].pos2, ...) using head content word's POS
       e. Append merged token, advance `i += w`, skip consumed tokens
       f. If no window matches: keep original token, advance `i += 1`
    3. Non-prefix tokens pass through unchanged
  - Define `MAX_COMPOUND_TOKENS = 6` as a module constant
  - **Wire into pipeline**: In `src/analysis/pipeline.py`, call `merge_prefix_compounds()` AFTER `tokenize()` and BEFORE `find_all_vocab()`
  - The merge function needs access to the vocab dict — add a public read-only property `vocab_entries` to `JLPTVocabLookup` that returns `self._vocab` (type: `dict[str, VocabEntry]`). Then call `merge_prefix_compounds(tokens, text, self._vocab_lookup.vocab_entries)` in pipeline.py. Do NOT access `_vocab` directly from pipeline.
  - Update `src/analysis/jlpt_vocab.py` `find_all_vocab()` to use index-based `while i < len(tokens)` loop instead of `for token in tokens` — this prepares for Task 6 chain extension too
  - `AnalysisResult.tokens` must contain the post-merge token list (pipeline returns merged tokens)

  **Must NOT do**:
  - Do NOT use lemma concatenation for compound lookup (Fugashi lemma for お is 御)
  - Do NOT hardcode お/ご characters — only check `pos == "接頭辞"` 
  - Do NOT modify grammar.py or grammar matching
  - Do NOT modify highlight.py or tooltip.py
  - Do NOT attempt chain extension yet (Task 6)
  - Do NOT change how vocab positions are calculated (text.find stays)

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Core algorithm implementation with edge cases (greedy match, multi-token window, position tracking) — requires careful reasoning
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (depends on Task 3 tests)
  - **Parallel Group**: Wave 2 (sequential after Task 3)
  - **Blocks**: Tasks 5, 6
  - **Blocked By**: Task 3

  **References**:

  **Pattern References**:
  - `src/analysis/tokenizer.py:22-42` — tokenize() method where merge function will be added or called
  - `src/analysis/pipeline.py:25-46` — process() method showing tokenize→vocab→grammar flow where merge step inserts
  - `src/analysis/jlpt_vocab.py:67-120` — find_all_vocab() current for-loop that needs conversion to while-loop

  **API/Type References**:
  - `src/models.py:Token` — Token dataclass with pos2/cType/cForm (after Tasks 1-2)
  - `src/models.py:VocabHit` — VocabHit fields that find_all_vocab produces
  - `src/analysis/jlpt_vocab.py:JLPTVocabLookup._vocab` — `dict[str, VocabEntry]` used for lookup. Add a public `vocab_entries` property (returning `self._vocab`) so pipeline.py can pass it to the merge function without accessing private attrs.

  **Data References**:
  - `data/vocabulary.csv` — 8293 entries, lookup key is `lemma` column

  **WHY Each Reference Matters**:
  - `tokenizer.py:22-42`: Where merge function lives or is called from — must understand token construction
  - `pipeline.py:25-46`: Must insert merge call between tokenize() and find_all_vocab() — exact insertion point
  - `jlpt_vocab.py:67-120`: The iteration loop being converted — must understand position tracking with search_start
  - `_vocab` dict: Compound lookup uses this same dict — merge function needs access

  **Acceptance Criteria**:
  - [ ] `pytest tests/test_compound_merging.py -v` — ALL tests pass (GREEN phase)
  - [ ] `pytest tests/` — zero regressions
  - [ ] お世辞 merged into single token with correct positions
  - [ ] Standalone 世辞 suppressed when compound お世辞 matched
  - [ ] ご飯 unaffected (not split by Fugashi, no merge needed)
  - [ ] お願いします matched as 4-token compound (greedy longest match)
  - [ ] `ruff check . && mypy src/` — clean

  **QA Scenarios**:

  ```
  Scenario: Compound merging produces correct VocabHit
    Tool: Bash (python)
    Preconditions: Compound merge implemented and wired into pipeline
    Steps:
      1. Run: python -c "
         from src.analysis.pipeline import PreprocessingPipeline
         p = PreprocessingPipeline()
         text = 'お世辞を言った'
         result = p.process(text)
         vocab = result.vocab_hits
         surfaces = [h.surface for h in vocab]
         print(f'Surfaces: {surfaces}')
         oseji = [h for h in vocab if h.surface == 'お世辞']
         assert len(oseji) == 1, f'Expected 1 お世辞 hit, got {len(oseji)}'
         assert text[oseji[0].start_pos:oseji[0].end_pos] == 'お世辞'
         seji_standalone = [h for h in vocab if h.surface == '世辞']
         assert len(seji_standalone) == 0, f'Standalone 世辞 should be suppressed'
         print('PASS')
         "
    Expected Result: Prints surfaces including お世辞, no standalone 世辞, ends with PASS
    Failure Indicators: お世辞 not found, standalone 世辞 present, position mismatch
    Evidence: .sisyphus/evidence/task-4-compound-merge.txt

  Scenario: Non-split compounds unaffected
    Tool: Bash (python)
    Preconditions: Compound merge implemented
    Steps:
      1. Run: python -c "
         from src.analysis.pipeline import PreprocessingPipeline
         p = PreprocessingPipeline()
         result = p.process('ご飯を食べる')
         gohan = [h for h in result.vocab_hits if 'ご飯' in h.surface or '飯' in h.surface]
         print(f'ご飯 hits: {gohan}')
         assert len(gohan) >= 1, 'ご飯 should be found'
         print('PASS')
         "
    Expected Result: ご飯 found as single token (no merge needed), PASS
    Failure Indicators: ご飯 not found or incorrectly processed
    Evidence: .sisyphus/evidence/task-4-nonsplit-compound.txt
  ```

  **Commit**: YES
  - Message: `feat(analysis): implement prefix-compound merging with greedy longest-match`
  - Files: `src/analysis/tokenizer.py`, `src/analysis/jlpt_vocab.py`, `src/analysis/pipeline.py`
  - Pre-commit: `pytest tests/test_compound_merging.py && pytest tests/ && ruff check . && mypy src/`

- [ ] 5. Write failing tests for conjugation chain extension (TDD RED phase)

  **What to do**:
  - Create `tests/test_chain_extension.py` with comprehensive test cases
  - Tests use real `FugashiTokenizer` output (not mocked tokens)
   - Test cases to include:
    - **AC4**: 続けさせる — VocabHit.surface=="続けさせる", lemma=="続ける", end_pos-start_pos==len("続けさせる")
    - **AC5**: 走っています — conservative chain: て is surface bridge, but い(動詞/非自立可能) STOPS the chain. VocabHit.surface=="走って", lemma=="走る". The い+ます portion is NOT part of the chain under conservative rules.
    - **AC6**: 食べる映画 — chain stops at content word 映画, VocabHit for 食べる does NOT extend into 映画
    - **AC7**: Verb not in vocab + 助動詞 → no VocabHit created (chain only extends existing hits)
    - **AC10**: Pipeline latency unchanged — process sentence with chains in <50ms
    - **EC4**: 行かなかった — head verb with pos2=非自立可能, chain still works (なかっ/助動詞 + た/助動詞 both continue)
    - **Conservative boundary test**: 食べてしまう — chain stops after て, しまう(動詞/非自立可能) NOT included. VocabHit.surface=="食べて"
    - **Conservative boundary test**: 食べてほしい — chain stops after て, ほしい(形容詞/非自立可能) NOT included. VocabHit.surface=="食べて"
    - 食べられない — 3-token chain (動詞 + 助動詞 + 助動詞), VocabHit.surface=="食べられない"
    - **False positive prevention**: 食べたんだけど — chain covers 食べたんだ (all 助動詞), stops at けど (助詞 but NOT て/で surface). VocabHit.surface=="食べたんだ"
    - **False positive prevention**: 食べれば — chain covers 食べれ(動詞), stops at ば (助詞/接続助詞 but NOT て/で surface). VocabHit.surface=="食べれ" (or just 食べれば if ば is 助動詞 — verify empirically)
    - Chain with て dead-end: 食べて寝る — て is bridge, but 寝る(動詞/一般) stops chain. VocabHit.surface=="食べて"
  - Use `@pytest.mark.parametrize` for verb conjugation variations
  - ALL tests MUST FAIL at this point

  **Must NOT do**:
  - Do NOT implement chain extension logic
  - Do NOT modify existing test files
  - Do NOT mock Fugashi output
  - Do NOT use pytest.mark.skip or xfail

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Writing test file only — clear structure from acceptance criteria
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (depends on Task 4 completing compound merge)
  - **Parallel Group**: Wave 3 (with Task 6)
  - **Blocks**: Task 6
  - **Blocked By**: Task 4

  **References**:

  **Pattern References**:
  - `tests/test_compound_merging.py` — Sibling test file (from Task 3) — follow same structure and assertion style
  - `tests/test_jlpt_vocab.py` — Existing VocabHit assertion patterns
  - `tests/test_analysis_pipeline.py` — Pipeline integration test patterns

  **API/Type References**:
  - `src/models.py:VocabHit` — Fields: surface, lemma, pos, jlpt_level, start_pos, end_pos
  - `src/models.py:AnalysisResult` — Container for tokens, vocab_hits, grammar_hits

  **Data References**:
  - `data/vocabulary.csv` — CSV format: `id,pronBase,lemma,definition,level`. Lookup key is the `lemma` column. BEFORE writing test assertions, run: `grep -m1 "続ける\|走る\|食べる\|見る\|行く\|読む" data/vocabulary.csv` to confirm which verbs exist in the vocabulary. Only write VocabHit assertions for verbs confirmed present.

  **WHY Each Reference Matters**:
  - `test_compound_merging.py`: Follow same file structure for consistency
  - VocabHit: Must assert on surface (extended), lemma (base form), start_pos/end_pos (extended span)
  - vocabulary.csv: Tests MUST use verbs that ARE in the vocab CSV (lemma column) to get valid VocabHits. Running the grep pre-step is mandatory to avoid false RED from missing vocab entries.

  **Acceptance Criteria**:
  - [ ] `tests/test_chain_extension.py` file exists with 10+ test functions
  - [ ] `pytest tests/test_chain_extension.py --co` — collects all tests without import errors
  - [ ] `pytest tests/test_chain_extension.py` — all tests FAIL (RED phase confirmed)
  - [ ] Tests cover AC4, AC5 (conservative), AC6, AC7, AC10, EC4, plus false-positive prevention tests for けど/ば/しまう/ほしい

  **QA Scenarios**:

  ```
  Scenario: Tests collect and fail correctly (TDD RED)
    Tool: Bash (pytest)
    Preconditions: Test file created, no chain extension exists
    Steps:
      1. Run: pytest tests/test_chain_extension.py --co -q
      2. Verify output shows 8+ test items collected
      3. Run: pytest tests/test_chain_extension.py -v 2>&1 | tail -5
      4. Verify output shows FAILED (not PASSED, not ERROR)
    Expected Result: All tests collected, all FAIL
    Failure Indicators: ImportError, collection errors, premature passes
    Evidence: .sisyphus/evidence/task-5-red-phase.txt

  Scenario: Existing + compound tests unaffected
    Tool: Bash (pytest)
    Preconditions: New chain test file added
    Steps:
      1. Run: pytest tests/ --ignore=tests/test_chain_extension.py -v 2>&1 | tail -3
    Expected Result: All tests pass (including compound tests from Task 4)
    Failure Indicators: Any test failure
    Evidence: .sisyphus/evidence/task-5-existing-tests.txt
  ```

  **Commit**: YES
  - Message: `test(chain): add failing tests for conjugation chain extension (TDD RED)`
  - Files: `tests/test_chain_extension.py`
  - Pre-commit: `pytest tests/test_chain_extension.py --co && ruff check tests/test_chain_extension.py`

- [ ] 6. Implement conjugation chain extension in find_all_vocab (TDD GREEN phase)

  **What to do**:
  - In `src/analysis/jlpt_vocab.py`, after a VocabHit is created for a 動詞 or 形容詞 token, scan forward to extend the hit's span across the conjugation chain
  - **Chain Extension Algorithm (CONSERVATIVE — precision over recall)**:
    1. After creating a VocabHit for token at position `i` where `token.pos in ("動詞", "形容詞")`:
    2. Define `CHAIN_BRIDGE_SURFACES = frozenset({"て", "で"})`
    3. Initialize `chain_end = i + 1`
    4. While `chain_end < len(tokens)` and `tokens[chain_end]` matches chain continuation:
       - `pos == "助動詞"` → continue chain (させる, られる, ない, た, ます, etc.)
       - `surface in CHAIN_BRIDGE_SURFACES` → continue chain (て/で form bridge ONLY)
       - **Anything else → stop chain** (including 動詞/非自立可能 like いる/しまう/みる, and 形容詞/非自立可能 like ほしい — these are left for grammar layer)
    5. If `chain_end > i + 1` (chain found):
       - Extend `VocabHit.surface` to concatenation of all chain token surfaces
       - Extend `VocabHit.end_pos` to cover the last chain token
       - Advance the iteration index past all consumed chain tokens
    6. `VocabHit.lemma` stays as the base form (e.g., 続ける) — NOT modified
  - **Why conservative**: The original rule with pos2=="接続助詞" caught ば/けど/から/が/のに (clause boundaries). With 動詞/非自立可能, it absorbed grammaticalized auxiliaries (しまう/みる/おく) that learners need to see separately. The conservative rule catches ~85-90% of real chains (all pure 助動詞 sequences + て/で bridges) with zero known false positives.
  - **Compound-wins rule**: When chain extends VocabHit, any tokens consumed by the chain that would individually produce VocabHits must be skipped (the index advancement handles this)
  - The while-loop from Task 4 already uses index-based iteration — extend it

  **Must NOT do**:
  - Do NOT create new VocabHits for chain tokens that don't have a head verb match (AC7)
  - Do NOT use cForm in the chain continuation predicate (extract but don't use)
  - Do NOT use pos2 == "接続助詞" for chain continuation — use surface whitelist {"て", "で"} ONLY
  - Do NOT include 動詞/非自立可能 tokens in chain continuation (いる, しまう, みる, おく etc. are left for grammar layer)
  - Do NOT include 形容詞/非自立可能 tokens in chain continuation (ほしい, ない-as-adjective etc. are left for grammar layer)
  - Do NOT modify VocabHit.lemma or VocabHit.pronunciation — only surface and end_pos
  - Do NOT modify grammar.py, highlight.py, or tooltip.py
  - Do NOT extend chains past content words (名詞, standalone 動詞/形容詞 with pos2!="非自立可能")

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Complex POS-based chain detection with multiple continuation rules, edge cases (て-form bridge, 非自立可能), and position tracking
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (depends on Task 5 tests)
  - **Parallel Group**: Wave 3 (sequential after Task 5)
  - **Blocks**: Final verification tasks F1-F4
  - **Blocked By**: Task 5

  **References**:

  **Pattern References**:
  - `src/analysis/jlpt_vocab.py:67-120` — find_all_vocab() method (after Task 4: uses while-loop, has compound support)
  - `src/analysis/jlpt_vocab.py:50-65` — _clean_lemma() and VocabHit creation pattern

  **API/Type References**:
  - `src/models.py:VocabHit` — Fields to modify: surface (str), end_pos (int) — both mutable on plain dataclass
  - `src/models.py:Token` — Fields to check: pos (str), pos2 (str) — chain continuation predicate

  **Test References**:
  - `tests/test_chain_extension.py` — Failing tests from Task 5 that this implementation must make pass

  **External References**:
  - Fugashi empirical data (from research): 続けさせる→[続け/動詞, させる/助動詞], 走っています→[走っ/動詞, て/助詞/接続助詞, い/動詞/非自立可能, ます/助動詞]. Conservative rule: chain stops at て bridge dead-end (い is 動詞/非自立 → excluded).

  **WHY Each Reference Matters**:
  - `jlpt_vocab.py:67-120`: The EXACT method being modified — must understand current iteration pattern and compound merge integration
  - VocabHit: Confirming that surface and end_pos are mutable (plain dataclass) — chain extension mutates these
  - Token: pos and pos2 fields are the chain continuation predicate inputs
  - test_chain_extension.py: These are the acceptance tests — implementation must satisfy them

  **Acceptance Criteria**:
  - [ ] `pytest tests/test_chain_extension.py -v` — ALL tests pass (GREEN phase)
  - [ ] `pytest tests/` — zero regressions (including compound tests)
  - [ ] 続けさせる: VocabHit surface="続けさせる", lemma="続ける", span covers full text
  - [ ] 走っています: conservative chain stops at て (い is 動詞/非自立可能 → excluded). VocabHit.surface=="走って"
  - [ ] 食べる映画: chain stops at 映画
  - [ ] 食べてしまう: chain stops after て — しまう(動詞/非自立) NOT in chain. VocabHit.surface=="食べて"
  - [ ] 食べたんだけど: chain covers 食べたんだ, stops at けど (not て/で surface)
  - [ ] Unmatched verb + 助動詞: no phantom VocabHit created
  - [ ] `ruff check . && mypy src/` — clean
  - [ ] Pipeline latency <50ms for chain-heavy sentences

  **QA Scenarios**:

  ```
  Scenario: Conjugation chain fully highlighted
    Tool: Bash (python)
    Preconditions: Chain extension implemented
    Steps:
      1. Run: python -c "
         from src.analysis.pipeline import PreprocessingPipeline
         p = PreprocessingPipeline()
         text = '続けさせる'
         result = p.process(text)
         vocab = result.vocab_hits
         print(f'Vocab hits: {[(h.surface, h.lemma) for h in vocab]}')
         chain_hit = [h for h in vocab if h.lemma == '続ける']
         assert len(chain_hit) == 1, f'Expected 1 hit for 続ける'
         h = chain_hit[0]
         assert h.surface == '続けさせる', f'Surface should be full chain, got {h.surface}'
         assert text[h.start_pos:h.end_pos] == '続けさせる'
         print('PASS')
         "
    Expected Result: Shows 続けさせる as surface with lemma 続ける, PASS
    Failure Indicators: Surface only shows 続け, position mismatch, missing hit
    Evidence: .sisyphus/evidence/task-6-chain-extension.txt

  Scenario: て-form bridge chain (conservative — stops at 非自立可能 verb)
    Tool: Bash (python)
    Preconditions: Chain extension implemented
    Steps:
      1. Run: python -c "
         from src.analysis.pipeline import PreprocessingPipeline
         p = PreprocessingPipeline()
         text = '走っています'
         result = p.process(text)
         vocab = result.vocab_hits
         run_hit = [h for h in vocab if h.lemma == '走る']
         assert len(run_hit) == 1
         h = run_hit[0]
         assert h.surface == '走って', f'Conservative rule: chain stops at て, got {h.surface}'
         print('PASS')
         "
    Expected Result: 走って as chain surface (conservative: stops before い/動詞/非自立可能), PASS
    Failure Indicators: Chain extends through い+ます (over-extension), or stops at 走っ only
    Evidence: .sisyphus/evidence/task-6-te-form-chain.txt

  Scenario: Chain stops at content word boundary
    Tool: Bash (python)
    Preconditions: Chain extension implemented
    Steps:
      1. Run: python -c "
         from src.analysis.pipeline import PreprocessingPipeline
         p = PreprocessingPipeline()
         text = '食べる映画を見た'
         result = p.process(text)
         eat_hit = [h for h in result.vocab_hits if h.lemma == '食べる']
         assert len(eat_hit) == 1
         assert eat_hit[0].surface == '食べる', f'Should not extend past 食べる, got {eat_hit[0].surface}'
         print('PASS')
         "
    Expected Result: 食べる not extended into 映画, PASS
    Failure Indicators: Surface includes 映画 or later tokens
    Evidence: .sisyphus/evidence/task-6-chain-boundary.txt

  Scenario: Full regression suite passes
    Tool: Bash (pytest)
    Preconditions: All implementation complete
    Steps:
      1. Run: pytest tests/ -v
      2. Run: ruff check . && ruff format --check .
      3. Run: mypy src/
    Expected Result: All tests pass, lint clean, type check clean
    Failure Indicators: Any test failure, lint error, type error
    Evidence: .sisyphus/evidence/task-6-full-regression.txt
  ```

  **Commit**: YES
  - Message: `feat(analysis): implement conjugation chain extension for verb/adjective highlighting`
  - Files: `src/analysis/jlpt_vocab.py`
  - Pre-commit: `pytest tests/test_chain_extension.py && pytest tests/ && ruff check . && mypy src/`

---

## Final Verification Wave (MANDATORY — after ALL implementation tasks)

> 4 review agents run in PARALLEL. ALL must APPROVE. Rejection → fix → re-run.

- [ ] F1. **Plan Compliance Audit** — `oracle`
  Read the plan end-to-end. For each "Must Have": verify implementation exists (read file, run python REPL). For each "Must NOT Have": search codebase for forbidden patterns — reject with file:line if found. Check evidence files exist in .sisyphus/evidence/. Compare deliverables against plan.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [ ] F2. **Code Quality Review** — `unspecified-high`
  Run `ruff check . && ruff format --check . && mypy src/ && pytest tests/`. Review all changed files for: unused imports, empty catches, console.log/print in prod, commented-out code. Check AI slop: excessive comments, over-abstraction, generic names (data/result/item/temp). Verify Token backward compatibility.
  Output: `Lint [PASS/FAIL] | Types [PASS/FAIL] | Tests [N pass/N fail] | Files [N clean/N issues] | VERDICT`

- [ ] F3. **Full Pipeline QA** — `unspecified-high`
  Run the full PreprocessingPipeline on these test sentences and verify output:
  - "お世辞を言う" → compound お世辞 found, no standalone 世辞
  - "続けさせる" → full chain highlighted (助動詞 only), lemma=続ける, surface=続けさせる
  - "走っています" → conservative chain: surface="走って" (stops before い/動詞/非自立可能), lemma=走る
  - "ご飯を食べられない" → ご飯 single token, 食べられない as chain (all 助動詞)
  - "彼はお世辞を言って続けさせた" → compound + chain in same sentence
  - "お願いします" → 4-token compound matched
  - "食べてしまう" → conservative chain: surface="食べて" (stops before しまう/動詞/非自立可能)
  - "食べたんだけど" → chain surface="食べたんだ" (stops at けど — not て/で surface)
  Save all outputs to `.sisyphus/evidence/final-qa/`.
  Output: `Sentences [N/N correct] | Compounds [N/N] | Chains [N/N] | VERDICT`

- [ ] F4. **Scope Fidelity Check** — `deep`
  For each task: read "What to do", read actual diff (git log/diff). Verify 1:1 — everything in spec was built (no missing), nothing beyond spec was built (no creep). Check "Must NOT do" compliance: grammar.py untouched, highlight.py untouched, tooltip.py untouched, no kana/pron usage. Detect cross-task contamination. Flag unaccounted changes.
  Output: `Tasks [N/N compliant] | Contamination [CLEAN/N issues] | Unaccounted [CLEAN/N files] | VERDICT`

---

## Commit Strategy

| Commit | Message | Files | Pre-commit |
|--------|---------|-------|------------|
| 1 | `feat(models): add pos2, cType, cForm fields to Token with defaults` | src/models.py | pytest tests/test_tokenizer.py tests/test_jlpt_vocab.py && mypy src/models.py |
| 2 | `feat(tokenizer): extract pos2, cType, cForm from UniDic features` | src/analysis/tokenizer.py | pytest tests/test_tokenizer.py && ruff check src/analysis/tokenizer.py |
| 3 | `test(compound): add failing tests for prefix-compound merging (TDD RED)` | tests/test_compound_merging.py | pytest tests/test_compound_merging.py --co && ruff check tests/ |
| 4 | `feat(analysis): implement prefix-compound merging with greedy longest-match` | src/analysis/tokenizer.py, jlpt_vocab.py, pipeline.py | pytest tests/ && ruff check . && mypy src/ |
| 5 | `test(chain): add failing tests for conjugation chain extension (TDD RED)` | tests/test_chain_extension.py | pytest tests/test_chain_extension.py --co && ruff check tests/ |
| 6 | `feat(analysis): implement conjugation chain extension for verb/adjective highlighting` | src/analysis/jlpt_vocab.py | pytest tests/ && ruff check . && mypy src/ |

---

## Success Criteria

### Verification Commands
```bash
# All tests pass
pytest tests/ -v                                    # Expected: all pass, 0 failures

# Compound tests specifically
pytest tests/test_compound_merging.py -v            # Expected: 8+ tests, all pass

# Chain tests specifically
pytest tests/test_chain_extension.py -v             # Expected: 10+ tests, all pass

# Lint and type check
ruff check . && ruff format --check .              # Expected: clean
mypy src/                                           # Expected: Success: no issues found

# Quick smoke test
python -c "
from src.analysis.pipeline import PreprocessingPipeline
p = PreprocessingPipeline()
r = p.process('お世辞を言って続けさせた')
for h in r.vocab_hits:
    print(f'{h.surface} (lemma={h.lemma}, level=N{h.jlpt_level}, pos={h.start_pos}-{h.end_pos})')
"
# Expected: お世辞 as compound, 続けさせた as chain with lemma=続ける
```

### Final Checklist
- [ ] All "Must Have" present
- [ ] All "Must NOT Have" absent
- [ ] All tests pass (existing + new)
- [ ] Lint clean, type check clean
- [ ] 6 atomic commits with descriptive messages
