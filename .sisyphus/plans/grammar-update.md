# Grammar Rules Update — grammar.json Full System Integration

## TL;DR

> **Quick Summary**: Replace the old 14-rule `grammar_rules.json` with the new 831-rule `grammar.json`, propagating schema changes (remove `confidence_type`, add `word` field, string→int level parsing) through all 19 affected files: data models, DB schema/migration, grammar matcher, pipeline wiring, UI display, and all 8 test files.
> 
> **Deliverables**:
> - Updated `GrammarMatcher` loading 831 rules from `data/grammar.json`
> - `GrammarHit` and `HighlightGrammar` models with `word` field, no `confidence_type`
> - DB schema migration (drop `confidence_type`, add `word`)
> - Tooltip + SentenceDetail showing `word` for richer learning display
> - N5 grammar color support across all UI layers
> - Fix N5 filtering bug (`>=` → `>`) so N5 users see N5 grammar
> - Fix 3 malformed regex patterns in grammar.json
> - All 8 test files updated, full test suite green
> - Old `grammar_rules.json` deleted
> 
> **Estimated Effort**: Medium
> **Parallel Execution**: YES — 4 waves
> **Critical Path**: Task 1 → Task 2 → Tasks 3-6 (parallel) → Tasks 7-8 (parallel) → Final Verification

---

## Context

### Original Request
User uploaded a complete grammar rules file (`data/grammar.json`) with 831 JLPT grammar rules (fields: id, re, word, description, level). Requested a plan to update all relevant code, with performance target <10ms per sentence and allowance for new libraries if cross-platform compatible.

### Interview Summary
**Key Discussions**:
- `confidence_type` field: User decided to REMOVE entirely (old field not in new data)
- `word` field: User decided to ADD to GrammarHit + HighlightGrammar + DB + tooltip for learning features
- Regex library: User decided to KEEP Python `re` (benchmark: 0.37ms for 831 rules, 27× under target)
- N5 filtering: User decided to CHANGE `>=` to `>` so N5 users see N5 grammar
- Old file: User decided to DELETE `grammar_rules.json`
- Data quality: User decided to FIX malformed patterns directly in grammar.json
- Test strategy: Tests-after (rewrite all affected test files)

**Research Findings**:
- Performance benchmark: 831 compiled `re.Pattern` with `finditer` on 150-char sentence = 0.37ms (27× under 10ms target)
- Regex complexity: 474 pure literals, 357 with metacharacters, ZERO lookahead/lookbehind/backreferences — all RE2-compatible
- Level distribution: N1=253, N2=197, N3=181, N4=123, N5=77
- Data quality issues: ID 101 (full-width `）`), IDs 38/53 (trailing `）)`) — compilation errors
- 19 files affected total (11 source + 8 test), not the initially-scoped 12

### Metis Review
**Identified Gaps** (addressed):
- N5 filtering bug: `>=` means N5 rules never fire — changed to `>`
- 8 test files (not 2) need updating — all factory helpers use `confidence_type`
- SCHEMA_SQL DDL must be updated for fresh databases (not just ALTER migration)
- `pattern` DB column should store `word` for SentenceDetail display
- `rule_id` should be `str(rule["id"])` for internal consistency
- `PRAGMA user_version` for versioned migration instead of fragile try/except

---

## Work Objectives

### Core Objective
Migrate the grammar matching system from the old 14-rule `grammar_rules.json` to the new 831-rule `grammar.json`, updating every layer (data → models → DB → matcher → pipeline → UI → tests) while preserving all existing functionality and adding `word` field for enhanced learning features.

### Concrete Deliverables
- `data/grammar.json` with 3 malformed patterns fixed
- `src/analysis/grammar.py` rewritten for new JSON schema
- `src/db/models.py` updated dataclasses (GrammarHit + HighlightGrammar)
- `src/db/schema.py` updated DDL + versioned migration
- `src/db/repository.py` updated SQL queries
- `src/pipeline/analysis_worker.py` updated mapping
- `src/ui/tooltip.py` showing `word` + description, N5 color
- `src/ui/sentence_detail.py` showing `word`, N5 badge
- `src/ui/highlight.py` N5 color
- `src/config.py` N5 color defaults
- `src/analysis/pipeline.py` path update
- All 8 test files updated
- `data/grammar_rules.json` deleted

### Definition of Done
- [ ] `ruff check . && ruff format --check .` exits 0
- [ ] `mypy src/` exits 0
- [ ] `pytest tests/` all green
- [ ] `grep -r confidence_type src/ tests/` returns 0 results
- [ ] All 831 patterns compile without error
- [ ] Grammar matching returns hits with `word` field populated
- [ ] DB schema has `word` column, no `confidence_type` column
- [ ] Performance: <10ms per sentence (measured <0.4ms)

### Must Have
- All 831 grammar rules loaded and matchable
- `word` field available in GrammarHit, HighlightGrammar, DB, and UI display
- `confidence_type` fully removed from codebase (zero grep results)
- N5 grammar visible to N5 users (filter fix `>=` → `>`)
- N5 colors in all UI layers
- DB migration for existing databases
- Fresh DB schema correct (no create-then-drop cycle)
- All tests passing

### Must NOT Have (Guardrails)
- **NO external regex library** — Python `re` is sufficient (0.37ms benchmark)
- **NO literal-string optimization** for the 474 pure-literal patterns — unnecessary complexity
- **NO streaming/async regex matching** — batch mode is project convention
- **NO grammar path in AppConfig** — hardcoded path is fine for single-file config
- **NO changes to vocab analysis** (`jlpt_vocab.py`, `tokenizer.py`)
- **NO changes to audio/VAD/ASR pipeline**
- **NO new UI widgets or layout changes** — only text content + N5 color additions
- **NO full migration framework** (no Alembic-style system) — just `PRAGMA user_version`
- **NO multi-language support** — Japanese only per project convention
- **NO `type: ignore` or `as any`** — per project anti-patterns

---

## Verification Strategy (MANDATORY)

> **ZERO HUMAN INTERVENTION** — ALL verification is agent-executed. No exceptions.

### Test Decision
- **Infrastructure exists**: YES (pytest, 29 test files)
- **Automated tests**: Tests-after (rewrite broken tests + add new ones)
- **Framework**: pytest
- **Pattern**: Follow existing `tests/test_grammar.py` structure, use `conftest.py` fixtures

### QA Policy
Every task MUST include agent-executed QA scenarios.
Evidence saved to `.sisyphus/evidence/task-{N}-{scenario-slug}.{ext}`.

- **Data validation**: Use Bash (python3 -c) — load JSON, compile patterns, verify fields
- **DB schema**: Use Bash (python3 -c) — init_db, PRAGMA table_info, assert columns
- **Grammar matching**: Use Bash (python3 -c) — import GrammarMatcher, run match, verify output
- **Codebase grep**: Use Bash (grep -r) — verify no stale references survive

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Start Immediately — data fix + model foundation):
├── Task 1: Fix malformed patterns in grammar.json [quick]
├── Task 2: Update GrammarHit + HighlightGrammar models [quick]
└── Task 3: Add N5 colors to config.py [quick]

Wave 2 (After Wave 1 — core implementation, MAX PARALLEL):
├── Task 4: Rewrite GrammarMatcher for new schema (depends: 2) [deep]
├── Task 5: DB schema migration + repository (depends: 2) [unspecified-high]
├── Task 6: Update analysis_worker mapping (depends: 2, 5) [quick]
└── Task 7: Update pipeline.py path (depends: 4) [quick]

Wave 3 (After Wave 2 — UI + cleanup):
├── Task 8: Update tooltip.py display (depends: 2) [quick]
├── Task 9: Update sentence_detail.py + highlight.py N5 colors (depends: 2, 3) [quick]
└── Task 10: Delete grammar_rules.json (depends: 4, 7) [quick]

Wave 4 (After Wave 3 — tests):
├── Task 11: Rewrite test_grammar.py (depends: 4) [unspecified-high]
├── Task 12: Update 6 test files with factory helpers (depends: 2, 5) [unspecified-high]
└── Task 13: Run full test suite + lint + mypy (depends: 11, 12) [quick]

Wave FINAL (After ALL tasks — independent review, 4 parallel):
├── Task F1: Plan compliance audit (oracle)
├── Task F2: Code quality review (unspecified-high)
├── Task F3: Real manual QA (unspecified-high)
└── Task F4: Scope fidelity check (deep)

Critical Path: Task 1 → Task 2 → Task 4 → Task 7 → Task 11 → Task 13 → F1-F4
Parallel Speedup: ~55% faster than sequential
Max Concurrent: 4 (Waves 2 & 3)
```

### Dependency Matrix

| Task | Depends On | Blocks | Wave |
|------|-----------|--------|------|
| 1 | — | 4 | 1 |
| 2 | — | 4, 5, 6, 8, 9, 11, 12 | 1 |
| 3 | — | 9 | 1 |
| 4 | 1, 2 | 7, 10, 11 | 2 |
| 5 | 2 | 6, 12 | 2 |
| 6 | 2, 5 | 12 | 2 |
| 7 | 4 | 10 | 2 |
| 8 | 2 | 12 | 3 |
| 9 | 2, 3 | 12 | 3 |
| 10 | 4, 7 | — | 3 |
| 11 | 4 | 13 | 4 |
| 12 | 2, 5, 6, 8, 9 | 13 | 4 |
| 13 | 11, 12 | F1-F4 | 4 |

### Agent Dispatch Summary

- **Wave 1**: 3 tasks — T1 `quick`, T2 `quick`, T3 `quick`
- **Wave 2**: 4 tasks — T4 `deep`, T5 `unspecified-high`, T6 `quick`, T7 `quick`
- **Wave 3**: 3 tasks — T8 `quick`, T9 `quick`, T10 `quick`
- **Wave 4**: 3 tasks — T11 `unspecified-high`, T12 `unspecified-high`, T13 `quick`
- **FINAL**: 4 tasks — F1 `oracle`, F2 `unspecified-high`, F3 `unspecified-high`, F4 `deep`

---

## TODOs

- [ ] 1. Fix malformed regex patterns in grammar.json

  **What to do**:
  - Fix ID 101: Replace full-width `）` with ASCII `)` in the `re` field
  - Fix ID 38: Remove trailing `）)` (full-width + ASCII parens) from `re` field
  - Fix ID 53: Remove trailing `）)` from `re` field
  - After fixes, verify ALL 831 patterns compile with `re.compile()`

  **Must NOT do**:
  - Do NOT change any other fields (word, description, level, id)
  - Do NOT restructure the JSON file
  - Do NOT add/remove rules

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Simple text fixes in a JSON file, minimal logic
  - **Skills**: []
    - No special skills needed for JSON editing

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 2, 3)
  - **Blocks**: Task 4 (GrammarMatcher needs valid patterns)
  - **Blocked By**: None (can start immediately)

  **References**:

  **Pattern References**:
  - `data/grammar.json` — The file to fix. Search for IDs 38, 53, 101.

  **WHY Each Reference Matters**:
  - `data/grammar.json`: Contains the 3 malformed patterns. ID 101 has `）` (U+FF09) instead of `)` (U+0029). IDs 38 and 53 have trailing `）)` that should be removed. Use the `re` field of each rule.

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: All 831 patterns compile successfully
    Tool: Bash (python3 -c)
    Preconditions: grammar.json has been edited
    Steps:
      1. Run: python3 -c "import json, re; rules=json.load(open('data/grammar.json', encoding='utf-8')); errors=[]; [errors.append(f'ID {r[\"id\"]}: {e}') if not (lambda p: (re.compile(p), True)[-1])(r['re']) else None for r in rules]; print(f'{len(rules)} patterns compiled, {len(errors)} errors')" (wrapped in try/except for compile failures)
      2. More precisely: python3 -c "
         import json, re
         rules = json.load(open('data/grammar.json', encoding='utf-8'))
         errors = []
         for r in rules:
             try:
                 re.compile(r['re'])
             except re.error as e:
                 errors.append(f'ID {r[\"id\"]}: {e}')
         print(f'{len(rules)} rules, {len(errors)} errors')
         assert len(errors) == 0, f'Failed: {errors}'
         print('ALL PATTERNS COMPILE OK')
         "
    Expected Result: "831 rules, 0 errors" followed by "ALL PATTERNS COMPILE OK"
    Failure Indicators: Any "errors" > 0, or assertion error
    Evidence: .sisyphus/evidence/task-1-compile-all-patterns.txt

  Scenario: Specific IDs 38, 53, 101 are fixed
    Tool: Bash (python3 -c)
    Preconditions: grammar.json has been edited
    Steps:
      1. Run: python3 -c "
         import json, re
         rules = {r['id']: r for r in json.load(open('data/grammar.json', encoding='utf-8'))}
         for rid in [38, 53, 101]:
             pat = rules[rid]['re']
             assert '）' not in pat, f'ID {rid} still has full-width paren: {pat}'
             re.compile(pat)
             print(f'ID {rid}: OK — {pat}')
         print('ALL FIXED IDS VERIFIED')
         "
    Expected Result: Each ID prints "OK" with its pattern, then "ALL FIXED IDS VERIFIED"
    Failure Indicators: AssertionError about full-width parens, or re.error
    Evidence: .sisyphus/evidence/task-1-fixed-ids-verified.txt
  ```

  **Commit**: YES (commit 1)
  - Message: `fix(data): fix malformed regex patterns in grammar.json`
  - Files: `data/grammar.json`
  - Pre-commit: `python3 -c "import json,re; [re.compile(r['re']) for r in json.load(open('data/grammar.json', encoding='utf-8'))]"`

- [ ] 2. Update GrammarHit + HighlightGrammar dataclasses

  **What to do**:
  - In `src/db/models.py`, modify `GrammarHit` frozen dataclass:
    - REMOVE field: `confidence_type: str`
    - ADD field: `word: str` (the display form from grammar.json, e.g., "ものを")
    - Keep all other fields: rule_id, matched_text, jlpt_level, description, start_pos, end_pos
  - In `src/db/models.py`, modify `HighlightGrammar` frozen dataclass:
    - REMOVE field: `confidence_type: str`
    - ADD field: `word: str | None` (nullable because old DB records won't have it)
    - Keep all other fields: id, sentence_id, rule_id, pattern, jlpt_level, description, is_beyond_level, tooltip_shown

  **Must NOT do**:
  - Do NOT change `AnalysisResult`, `VocabHit`, `HighlightVocab`, or any other model
  - Do NOT change field types of existing fields
  - Do NOT add `__post_init__` or validation logic

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Two dataclass field additions/removals in one file
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 3)
  - **Blocks**: Tasks 4, 5, 6, 8, 9, 11, 12 (all downstream consumers)
  - **Blocked By**: None (can start immediately)

  **References**:

  **Pattern References**:
  - `src/db/models.py:GrammarHit` — Current dataclass with `confidence_type: str` field. Follow the `@dataclass(frozen=True, slots=True)` pattern.
  - `src/db/models.py:HighlightGrammar` — Current dataclass with `confidence_type: str` field.

  **API/Type References**:
  - `src/db/models.py:VocabHit` — Sibling dataclass showing the slot-frozen pattern to follow

  **WHY Each Reference Matters**:
  - `GrammarHit`: The pipeline DTO — every consumer reads its fields. Adding `word` here makes it available to tooltip, analysis_worker, etc.
  - `HighlightGrammar`: The DB record DTO — `word: str | None` is nullable because existing DB rows won't have this value.

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: GrammarHit has word, no confidence_type
    Tool: Bash (python3 -c)
    Preconditions: models.py has been edited
    Steps:
      1. Run: python3 -c "
         from src.db.models import GrammarHit
         import dataclasses
         fields = {f.name for f in dataclasses.fields(GrammarHit)}
         assert 'word' in fields, f'word missing from GrammarHit: {fields}'
         assert 'confidence_type' not in fields, f'confidence_type still in GrammarHit: {fields}'
         # Verify construction works
         hit = GrammarHit(rule_id='1', matched_text='ながら', jlpt_level=3, word='ながら', description='while', start_pos=0, end_pos=3)
         assert hit.word == 'ながら'
         print(f'GrammarHit fields: {fields}')
         print('GrammarHit OK')
         "
    Expected Result: "GrammarHit OK" with fields showing word present, confidence_type absent
    Failure Indicators: ImportError, AssertionError, TypeError on construction
    Evidence: .sisyphus/evidence/task-2-grammarhit-fields.txt

  Scenario: HighlightGrammar has word, no confidence_type
    Tool: Bash (python3 -c)
    Preconditions: models.py has been edited
    Steps:
      1. Run: python3 -c "
         from src.db.models import HighlightGrammar
         import dataclasses
         fields = {f.name: f.type for f in dataclasses.fields(HighlightGrammar)}
         assert 'word' in fields, f'word missing: {fields}'
         assert 'confidence_type' not in fields, f'confidence_type still present: {fields}'
         # Verify nullable word works
         hg = HighlightGrammar(id=1, sentence_id=1, rule_id='1', pattern='ながら', jlpt_level=3, word=None, description='while', is_beyond_level=True, tooltip_shown=False)
         assert hg.word is None
         print(f'HighlightGrammar fields: {list(fields.keys())}')
         print('HighlightGrammar OK')
         "
    Expected Result: "HighlightGrammar OK"
    Failure Indicators: AssertionError, TypeError
    Evidence: .sisyphus/evidence/task-2-highlightgrammar-fields.txt
  ```

  **Commit**: YES (commit 2)
  - Message: `refactor(models): update grammar models — drop confidence_type, add word`
  - Files: `src/db/models.py`
  - Pre-commit: `ruff check src/db/models.py`

- [ ] 3. Add N5 grammar colors to config

  **What to do**:
  - In `src/config.py`, add N5 color entries to `DEFAULT_JLPT_COLORS` dict:
    - Add `"n5_vocab": "#..."` (pick a color distinct from N1-N4, suggest a warm/neutral tone like brown or olive)
    - Add `"n5_grammar": "#..."` (matching grammar variant)
  - Follow the existing pattern: n1_vocab/n1_grammar, n2_vocab/n2_grammar, etc.

  **Must NOT do**:
  - Do NOT change existing N1-N4 colors
  - Do NOT change AppConfig fields or defaults
  - Do NOT modify any other config settings

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Adding 2 color entries to a dict literal
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2)
  - **Blocks**: Task 9 (UI needs N5 colors)
  - **Blocked By**: None (can start immediately)

  **References**:

  **Pattern References**:
  - `src/config.py:DEFAULT_JLPT_COLORS` — Existing dict with n1_vocab, n1_grammar through n4_vocab, n4_grammar entries. Each is a hex color string.

  **WHY Each Reference Matters**:
  - Follow the exact naming pattern (n5_vocab, n5_grammar) and hex color format (#RRGGBB). The UI layers look up colors by these exact key names.

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: N5 colors exist in defaults
    Tool: Bash (python3 -c)
    Preconditions: config.py has been edited
    Steps:
      1. Run: python3 -c "
         from src.config import DEFAULT_JLPT_COLORS
         assert 'n5_vocab' in DEFAULT_JLPT_COLORS, 'n5_vocab missing'
         assert 'n5_grammar' in DEFAULT_JLPT_COLORS, 'n5_grammar missing'
         for key in ['n5_vocab', 'n5_grammar']:
             val = DEFAULT_JLPT_COLORS[key]
             assert val.startswith('#') and len(val) == 7, f'{key} bad format: {val}'
         print(f'N5 colors: vocab={DEFAULT_JLPT_COLORS[\"n5_vocab\"]}, grammar={DEFAULT_JLPT_COLORS[\"n5_grammar\"]}')
         print('N5 COLORS OK')
         "
    Expected Result: "N5 COLORS OK" with two valid hex colors
    Failure Indicators: KeyError, AssertionError
    Evidence: .sisyphus/evidence/task-3-n5-colors.txt

  Scenario: All JLPT levels (1-5) have both vocab and grammar colors
    Tool: Bash (python3 -c)
    Steps:
      1. Run: python3 -c "
         from src.config import DEFAULT_JLPT_COLORS
         for level in range(1, 6):
             for kind in ['vocab', 'grammar']:
                 key = f'n{level}_{kind}'
                 assert key in DEFAULT_JLPT_COLORS, f'Missing: {key}'
         print('All 10 JLPT color keys present (N1-N5 × vocab/grammar)')
         "
    Expected Result: "All 10 JLPT color keys present"
    Failure Indicators: AssertionError for missing key
    Evidence: .sisyphus/evidence/task-3-all-jlpt-colors.txt
  ```

  **Commit**: Groups with commit 5 (UI changes)

- [ ] 4. Rewrite GrammarMatcher for new grammar.json schema

  **What to do**:
  - Rewrite `_CompiledRule` dataclass to match new JSON fields:
    - `rule_id: str` ← `str(rule["id"])` (int→str conversion)
    - `pattern: re.Pattern[str]` ← `re.compile(rule["re"])`
    - `jlpt_level: int` ← `int(rule["level"][1:])` (parse "N1"→1, "N2"→2, etc.)
    - `word: str` ← `rule["word"]`
    - `description: str` ← `rule["description"]`
    - REMOVE `confidence_type` field
  - Update `GrammarMatcher.__init__()`:
    - Load from `rules_path` parameter (JSON with new schema)
    - Add validation: `level` must parse to int in {1,2,3,4,5}
    - Pre-compile all patterns (keep existing pattern)
    - Log warning for patterns that fail to compile (don't crash, skip them)
  - Update `GrammarMatcher.match()`:
    - **FIX N5 BUG**: Change `if rule.jlpt_level >= user_level` to `if rule.jlpt_level > user_level`
    - Populate `word` field in GrammarHit: `word=rule.word`
    - REMOVE `confidence_type` from GrammarHit construction
  - Update `pipeline.py`:
    - Change path from `"data/grammar_rules.json"` to `"data/grammar.json"`

  **Must NOT do**:
  - Do NOT add external regex libraries
  - Do NOT optimize literal patterns with `str.__contains__`
  - Do NOT change the public API signature of `GrammarMatcher.match(text, user_level)`
  - Do NOT add grammar path to AppConfig

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Core logic rewrite with schema translation, validation, and bug fix. Must be precise.
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 5, 6 in Wave 2, though 6 depends on 5)
  - **Parallel Group**: Wave 2
  - **Blocks**: Tasks 7, 10, 11
  - **Blocked By**: Tasks 1, 2

  **References**:

  **Pattern References**:
  - `src/analysis/grammar.py` — Full file. Current `_CompiledRule` dataclass (line ~15), `__init__` JSON loading (line ~30), `match()` linear scan with finditer (line ~55). Rewrite all three, preserve overall structure.

  **API/Type References**:
  - `src/db/models.py:GrammarHit` — The output DTO. After Task 2, it has: rule_id, matched_text, jlpt_level, word, description, start_pos, end_pos.
  - `data/grammar.json` — Input schema: `{id: int, re: str, word: str, description: str, level: str}`

  **External References**:
  - Python `re.compile()` docs for error handling on bad patterns

  **WHY Each Reference Matters**:
  - `grammar.py`: This IS the file being rewritten. Understand current structure to preserve the architectural pattern while swapping internals.
  - `GrammarHit`: The contract this function must produce. Every field must be populated correctly.
  - `grammar.json`: The input contract. Field names and types are different from old format — careful mapping required.

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: GrammarMatcher loads all 831 rules
    Tool: Bash (python3 -c)
    Preconditions: grammar.py rewritten, grammar.json fixed (Task 1)
    Steps:
      1. Run: python3 -c "
         from src.analysis.grammar import GrammarMatcher
         gm = GrammarMatcher('data/grammar.json')
         # Access internal rules count
         rule_count = len(gm._rules)
         assert rule_count == 831, f'Expected 831 rules, got {rule_count}'
         print(f'Loaded {rule_count} rules')
         print('LOAD OK')
         "
    Expected Result: "Loaded 831 rules" + "LOAD OK"
    Failure Indicators: ImportError, FileNotFoundError, assertion failure
    Evidence: .sisyphus/evidence/task-4-load-rules.txt

  Scenario: Grammar matching returns hits with word field
    Tool: Bash (python3 -c)
    Preconditions: GrammarMatcher loaded
    Steps:
      1. Run: python3 -c "
         from src.analysis.grammar import GrammarMatcher
         gm = GrammarMatcher('data/grammar.json')
         hits = gm.match('音楽を聴きながら勉強した', 5)
         assert len(hits) > 0, 'No hits found'
         for h in hits:
             assert h.word, f'Hit {h.rule_id} has empty word'
             assert h.matched_text, f'Hit {h.rule_id} has empty matched_text'
             assert 1 <= h.jlpt_level <= 5, f'Bad level: {h.jlpt_level}'
             assert h.start_pos >= 0 and h.end_pos > h.start_pos
             assert not hasattr(h, 'confidence_type'), 'confidence_type still exists!'
             print(f'  rule_id={h.rule_id}, word={h.word}, match={h.matched_text}, level=N{h.jlpt_level}, pos={h.start_pos}:{h.end_pos}')
         print(f'{len(hits)} hits — ALL HAVE WORD FIELD')
         "
    Expected Result: Multiple hits printed with word field populated, "ALL HAVE WORD FIELD"
    Failure Indicators: AssertionError, AttributeError
    Evidence: .sisyphus/evidence/task-4-match-with-word.txt

  Scenario: N5 filtering fix — N5 rules fire for user_level=5
    Tool: Bash (python3 -c)
    Preconditions: Filter changed from >= to >
    Steps:
      1. Run: python3 -c "
         from src.analysis.grammar import GrammarMatcher
         gm = GrammarMatcher('data/grammar.json')
         # 'です' is N5 grammar
         hits_l5 = gm.match('これは本です', 5)
         n5_hits = [h for h in hits_l5 if h.jlpt_level == 5]
         assert len(n5_hits) > 0, f'N5 rules did not fire for user_level=5. All hits: {[(h.rule_id, h.jlpt_level) for h in hits_l5]}'
         print(f'N5 hits for user_level=5: {len(n5_hits)}')
         # N5 should NOT fire for user_level=4
         hits_l4 = gm.match('これは本です', 4)
         n5_hits_l4 = [h for h in hits_l4 if h.jlpt_level == 5]
         assert len(n5_hits_l4) == 0, f'N5 rules should not fire for user_level=4 but got {len(n5_hits_l4)}'
         print('N5 correctly excluded for user_level=4')
         print('N5 FILTER FIX VERIFIED')
         "
    Expected Result: N5 hits > 0 for level 5, 0 for level 4, "N5 FILTER FIX VERIFIED"
    Failure Indicators: AssertionError
    Evidence: .sisyphus/evidence/task-4-n5-filter.txt

  Scenario: Performance under 10ms
    Tool: Bash (python3 -c)
    Preconditions: GrammarMatcher loaded with 831 rules
    Steps:
      1. Run: python3 -c "
         import time
         from src.analysis.grammar import GrammarMatcher
         gm = GrammarMatcher('data/grammar.json')
         text = '昨日友達と映画を見に行きました。とても面白かったので、また見たいと思います。'
         # Warmup
         gm.match(text, 5)
         # Benchmark
         times = []
         for _ in range(100):
             t0 = time.perf_counter()
             gm.match(text, 5)
             times.append((time.perf_counter() - t0) * 1000)
         avg = sum(times) / len(times)
         print(f'Avg: {avg:.3f}ms, Min: {min(times):.3f}ms, Max: {max(times):.3f}ms')
         assert avg < 10, f'Too slow: {avg:.3f}ms'
         print('PERFORMANCE OK (<10ms)')
         "
    Expected Result: Avg well under 10ms (expect <1ms), "PERFORMANCE OK"
    Failure Indicators: avg >= 10ms
    Evidence: .sisyphus/evidence/task-4-performance.txt
  ```

  **Commit**: YES (commit 3)
  - Message: `feat(analysis): rewrite GrammarMatcher for 831-rule grammar.json`
  - Files: `src/analysis/grammar.py`, `src/analysis/pipeline.py`
  - Pre-commit: `python3 -c "from src.analysis.grammar import GrammarMatcher; gm=GrammarMatcher('data/grammar.json'); print(f'{len(gm._rules)} rules loaded')"`

- [ ] 5. DB schema migration + repository update

  **What to do**:
  - In `src/db/schema.py`:
    - Update `SCHEMA_SQL` DDL for `highlight_grammar` table: REMOVE `confidence_type TEXT NOT NULL`, ADD `word TEXT`
    - Add `PRAGMA user_version` based migration:
      - Version 0→1: `ALTER TABLE highlight_grammar DROP COLUMN confidence_type` + `ALTER TABLE highlight_grammar ADD COLUMN word TEXT`
      - Wrap in `BEGIN EXCLUSIVE` / `COMMIT` transaction
      - Update `PRAGMA user_version = 1` after successful migration
    - Keep existing migration try/except pattern as fallback for edge cases
  - In `src/db/repository.py`:
    - Update `INSERT INTO highlight_grammar` — remove `confidence_type` column, add `word` column
    - Update `SELECT` queries that read `highlight_grammar` — remove `confidence_type`, add `word`
    - Update `HighlightGrammar` construction from row data — remove `confidence_type`, add `word`

  **Must NOT do**:
  - Do NOT install Alembic or build a full migration framework
  - Do NOT change `sentences` or `highlight_vocab` tables
  - Do NOT change the `LearningRepository` constructor signature
  - Do NOT drop the entire table and recreate (would lose user data)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: DB schema migration requires careful SQL, transaction safety, and query updates across multiple methods
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Task 4 in Wave 2)
  - **Parallel Group**: Wave 2
  - **Blocks**: Tasks 6, 12
  - **Blocked By**: Task 2 (needs updated HighlightGrammar model)

  **References**:

  **Pattern References**:
  - `src/db/schema.py` — Full file. Current `SCHEMA_SQL` DDL (line ~10), `init_db()` function (line ~40), existing migration pattern with try/except ALTER (line ~65-76).
  - `src/db/repository.py` — `insert_sentence()` method (find the INSERT INTO highlight_grammar), SELECT queries for grammar records, HighlightGrammar row construction.

  **API/Type References**:
  - `src/db/models.py:HighlightGrammar` — After Task 2: fields are id, sentence_id, rule_id, pattern, jlpt_level, word (str|None), description, is_beyond_level, tooltip_shown

  **WHY Each Reference Matters**:
  - `schema.py`: The DDL must match the new model exactly. The migration must handle existing DBs with confidence_type data gracefully.
  - `repository.py`: Every SQL statement touching highlight_grammar must be updated to match the new schema. Column order in INSERT/SELECT must match.
  - `HighlightGrammar`: The target model — SQL results must map to these exact fields.

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Fresh DB has correct schema (no confidence_type, has word)
    Tool: Bash (python3 -c)
    Preconditions: schema.py updated
    Steps:
      1. Run: python3 -c "
         from src.db.schema import init_db
         conn = init_db(':memory:')
         cols = {r[1]: r[2] for r in conn.execute('PRAGMA table_info(highlight_grammar)').fetchall()}
         assert 'word' in cols, f'word column missing. Columns: {list(cols.keys())}'
         assert 'confidence_type' not in cols, f'confidence_type still present. Columns: {list(cols.keys())}'
         print(f'Columns: {list(cols.keys())}')
         print('FRESH SCHEMA OK')
         conn.close()
         "
    Expected Result: Columns list includes 'word', excludes 'confidence_type', "FRESH SCHEMA OK"
    Failure Indicators: AssertionError
    Evidence: .sisyphus/evidence/task-5-fresh-schema.txt

  Scenario: Migration works on existing DB with confidence_type data
    Tool: Bash (python3 -c)
    Preconditions: schema.py has migration logic
    Steps:
      1. Run: python3 -c "
         import sqlite3
         # Simulate old schema
         conn = sqlite3.connect(':memory:')
         conn.execute('''CREATE TABLE IF NOT EXISTS sentences (
             id INTEGER PRIMARY KEY, text TEXT, created_at TEXT)''')
         conn.execute('''CREATE TABLE IF NOT EXISTS highlight_grammar (
             id INTEGER PRIMARY KEY, sentence_id INTEGER,
             rule_id TEXT NOT NULL, pattern TEXT NOT NULL,
             jlpt_level INTEGER, confidence_type TEXT NOT NULL,
             description TEXT, is_beyond_level INTEGER NOT NULL DEFAULT 0,
             tooltip_shown INTEGER NOT NULL DEFAULT 0,
             FOREIGN KEY (sentence_id) REFERENCES sentences(id))''')
         # Insert old-format data
         conn.execute('''INSERT INTO sentences (id, text, created_at)
             VALUES (1, 'test', '2024-01-01')''')
         conn.execute('''INSERT INTO highlight_grammar
             (sentence_id, rule_id, pattern, jlpt_level, confidence_type, description, is_beyond_level, tooltip_shown)
             VALUES (1, 'N3_nagara', 'N3_nagara', 3, 'high', 'while doing', 1, 0)''')
         conn.commit()
         # Now run migration
         from src.db.schema import init_db
         init_db(conn)
         # Verify migration
         cols = {r[1] for r in conn.execute('PRAGMA table_info(highlight_grammar)').fetchall()}
         assert 'word' in cols, f'word not added: {cols}'
         assert 'confidence_type' not in cols, f'confidence_type not dropped: {cols}'
         # Verify old data survived (minus confidence_type)
         rows = conn.execute('SELECT rule_id, pattern, description FROM highlight_grammar').fetchall()
         assert len(rows) == 1
         assert rows[0][0] == 'N3_nagara'
         print('MIGRATION OK — old data preserved')
         conn.close()
         "
    Expected Result: "MIGRATION OK — old data preserved"
    Failure Indicators: sqlite3.OperationalError, AssertionError
    Evidence: .sisyphus/evidence/task-5-migration.txt
  ```

  **Commit**: YES (commit 4)
  - Message: `feat(db): schema migration — drop confidence_type, add word column`
  - Files: `src/db/schema.py`, `src/db/repository.py`
  - Pre-commit: `python3 -c "from src.db.schema import init_db; c=init_db(':memory:'); print('DB OK')"`

- [ ] 6. Update analysis_worker GrammarHit→HighlightGrammar mapping

  **What to do**:
  - In `src/pipeline/analysis_worker.py`, update the code that converts `GrammarHit` to `HighlightGrammar`:
    - REMOVE `confidence_type=hit.confidence_type`
    - ADD `word=hit.word`
    - Change `pattern=hit.rule_id` to `pattern=hit.word` (store display form, not internal ID)
    - Keep all other field mappings unchanged

  **Must NOT do**:
  - Do NOT change the worker's signal/slot mechanism
  - Do NOT change how `AnalysisResult` is passed around
  - Do NOT modify the vocab hit mapping

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: ~4 lines changed in one mapping block
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (depends on Tasks 2 + 5)
  - **Parallel Group**: Wave 2 (after 5 completes)
  - **Blocks**: Task 12 (test updates)
  - **Blocked By**: Tasks 2, 5

  **References**:

  **Pattern References**:
  - `src/pipeline/analysis_worker.py` lines ~117-129 — The GrammarHit→HighlightGrammar mapping block. Currently maps: rule_id→rule_id, rule_id→pattern (duplicated), jlpt_level→jlpt_level, confidence_type→confidence_type, description→description.

  **API/Type References**:
  - `src/db/models.py:GrammarHit` — After Task 2: has word field
  - `src/db/models.py:HighlightGrammar` — After Task 2: has word field, no confidence_type

  **WHY Each Reference Matters**:
  - `analysis_worker.py`: This is the bridge between pipeline DTOs and DB records. Must map every field correctly.

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Worker mapping compiles and has correct fields
    Tool: Bash (python3 -c)
    Preconditions: analysis_worker.py updated
    Steps:
      1. Run: python3 -c "
         import ast, inspect
         from src.pipeline import analysis_worker
         source = inspect.getsource(analysis_worker)
         assert 'confidence_type' not in source, 'confidence_type still referenced in analysis_worker'
         assert 'word=hit.word' in source or 'word = hit.word' in source, 'word mapping missing'
         print('analysis_worker mapping OK')
         "
    Expected Result: "analysis_worker mapping OK"
    Failure Indicators: AssertionError
    Evidence: .sisyphus/evidence/task-6-worker-mapping.txt
  ```

  **Commit**: Groups with commit 4 (DB changes)

- [ ] 7. Update pipeline.py grammar file path

  **What to do**:
  - In `src/analysis/pipeline.py` line ~30, change:
    - `GrammarMatcher("data/grammar_rules.json")` → `GrammarMatcher("data/grammar.json")`

  **Must NOT do**:
  - Do NOT add the path to AppConfig
  - Do NOT change any other pipeline logic

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Single string change in one line
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (depends on Task 4)
  - **Parallel Group**: Wave 2 (after 4 completes)
  - **Blocks**: Task 10 (safe to delete old file)
  - **Blocked By**: Task 4

  **References**:

  **Pattern References**:
  - `src/analysis/pipeline.py:30` — `GrammarMatcher("data/grammar_rules.json")`

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Pipeline uses grammar.json path
    Tool: Bash (grep)
    Steps:
      1. Run: grep -n "grammar_rules" src/analysis/pipeline.py
      2. Run: grep -n "grammar.json" src/analysis/pipeline.py
    Expected Result: grep 1 returns nothing (exit 1). grep 2 returns the line with "data/grammar.json"
    Failure Indicators: "grammar_rules" still found in pipeline.py
    Evidence: .sisyphus/evidence/task-7-path-update.txt
  ```

  **Commit**: Groups with commit 3 (GrammarMatcher rewrite)

- [ ] 8. Update tooltip.py grammar display

  **What to do**:
  - In `src/ui/tooltip.py`, method `show_for_grammar()`:
    - Change the description display from `f"{hit.confidence_type}: {description}"` to show the `word` field prominently as the grammar point label, with `description` as the explanation
    - The `word` field (e.g., "ながら", "ために") should be the main display text, and `description` (English meaning) should be secondary
    - REMOVE any reference to `confidence_type`
  - Add N5 color to `_JLPT_GRAMMAR_COLORS` dict (level 5 → color matching `n5_grammar` from config)

  **Must NOT do**:
  - Do NOT change tooltip positioning, animation, or show/hide logic
  - Do NOT change vocab tooltip behavior
  - Do NOT redesign the tooltip layout

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Text display change + color dict entry in one file
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Tasks 9, 10)
  - **Blocks**: Task 12 (test updates for tooltip)
  - **Blocked By**: Task 2 (needs updated GrammarHit with word field)

  **References**:

  **Pattern References**:
  - `src/ui/tooltip.py:show_for_grammar()` lines ~148-187 — Current display logic. Shows N{level} badge, matched_text as word, `f"{hit.confidence_type}: {description}"` as description. `_JLPT_GRAMMAR_COLORS` dict maps level int → color string.

  **WHY Each Reference Matters**:
  - This is where `confidence_type` appears in UI display. Must be removed and replaced with `word`-based display.
  - `_JLPT_GRAMMAR_COLORS` only has levels 1-4. N5 must be added.

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: No confidence_type in tooltip source
    Tool: Bash (grep)
    Steps:
      1. Run: grep -n "confidence_type" src/ui/tooltip.py
    Expected Result: No matches (exit code 1)
    Failure Indicators: Any match found
    Evidence: .sisyphus/evidence/task-8-tooltip-no-confidence.txt

  Scenario: N5 color in tooltip
    Tool: Bash (python3 -c)
    Steps:
      1. Run: python3 -c "
         # Import the color dict (may need to check the actual variable name)
         import ast
         with open('src/ui/tooltip.py') as f:
             source = f.read()
         assert '5:' in source or '5 :' in source, 'N5 color key missing from grammar colors dict'
         print('N5 color entry found in tooltip')
         "
    Expected Result: "N5 color entry found in tooltip"
    Evidence: .sisyphus/evidence/task-8-tooltip-n5-color.txt
  ```

  **Commit**: Groups with commit 5 (UI changes)

- [ ] 9. Update sentence_detail.py + highlight.py for N5

  **What to do**:
  - In `src/ui/sentence_detail.py`:
    - `_build_grammar_group()`: The `gh.pattern` field now contains the `word` value (set by analysis_worker in Task 6). Verify the display reads naturally.
    - `_make_jlpt_badge()`: Add N5 to `_JLPT_COLORS` dict so N5 grammar gets a colored badge
  - In `src/ui/highlight.py`:
    - Add N5 to the `JLPT_COLORS` / grammar color mapping (if it has a level→color dict)
    - Ensure level 5 gets a valid color instead of falling through to default/error

  **Must NOT do**:
  - Do NOT change the sentence detail dialog layout or widget structure
  - Do NOT change highlight rendering logic beyond color addition
  - Do NOT add new UI elements

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Adding N5 color entries to existing dicts in 2 files
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Tasks 8, 10)
  - **Blocks**: Task 12 (test updates)
  - **Blocked By**: Tasks 2, 3

  **References**:

  **Pattern References**:
  - `src/ui/sentence_detail.py:_build_grammar_group()` lines ~201-229 — Renders each HighlightGrammar with JLPT badge, pattern label, description
  - `src/ui/sentence_detail.py:_make_jlpt_badge()` — Has `_JLPT_COLORS` dict for levels 1-4 only
  - `src/ui/highlight.py` lines ~70-137 — Grammar span rendering. Check for level→color mapping.

  **WHY Each Reference Matters**:
  - `sentence_detail.py`: The `_JLPT_COLORS` dict needs N5. Without it, N5 badges will either error or use wrong color.
  - `highlight.py`: Grammar span coloring must handle level 5.

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: N5 color in sentence detail and highlight
    Tool: Bash (grep)
    Steps:
      1. Run: grep -c "5" src/ui/sentence_detail.py | head -1  # Check N5 in JLPT_COLORS
      2. More precisely: python3 -c "
         for f in ['src/ui/sentence_detail.py', 'src/ui/highlight.py']:
             with open(f) as fh:
                 content = fh.read()
             assert 'confidence_type' not in content, f'{f} still has confidence_type'
             print(f'{f}: confidence_type removed')
         print('UI FILES CLEAN')
         "
    Expected Result: "UI FILES CLEAN"
    Evidence: .sisyphus/evidence/task-9-ui-n5-colors.txt
  ```

  **Commit**: Groups with commit 5 (UI changes)

- [ ] 10. Delete old grammar_rules.json

  **What to do**:
  - Delete `data/grammar_rules.json` from the repository
  - Verify no remaining references to `grammar_rules.json` in the codebase

  **Must NOT do**:
  - Do NOT delete `data/grammar.json` (the new file!)
  - Do NOT delete any other data files

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Single file deletion + verification grep
  - **Skills**: [`git-master`]
    - `git-master`: Needed for `git rm` to properly stage deletion

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Tasks 8, 9)
  - **Blocks**: None
  - **Blocked By**: Tasks 4, 7 (nothing references the old file anymore)

  **References**:

  **Pattern References**:
  - `data/grammar_rules.json` — The file to delete
  - `tests/test_grammar.py` — Previously referenced this path. Must be updated first (but test rewrite in Task 11 handles this)

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Old file deleted, no references remain
    Tool: Bash
    Steps:
      1. Run: test ! -f data/grammar_rules.json && echo "FILE DELETED" || echo "FILE STILL EXISTS"
      2. Run: grep -r "grammar_rules" src/ tests/ && echo "STALE REFS FOUND" || echo "NO STALE REFS"
    Expected Result: "FILE DELETED" and "NO STALE REFS"
    Failure Indicators: "FILE STILL EXISTS" or "STALE REFS FOUND"
    Evidence: .sisyphus/evidence/task-10-old-file-deleted.txt
  ```

  **Commit**: YES (commit 7)
  - Message: `chore: delete obsolete grammar_rules.json`
  - Files: `data/grammar_rules.json` (deletion)
  - Pre-commit: `grep -r grammar_rules src/ tests/` exits with code 1 (no matches)

- [ ] 11. Rewrite test_grammar.py for new schema

  **What to do**:
  - Completely rewrite `tests/test_grammar.py` to test against `data/grammar.json`:
    - Update `RULES_PATH` to `"data/grammar.json"`
    - Update rule count assertion to 831
    - Replace all old rule_id references ('N3_nagara', 'N3_tame_ni', 'N2_ni_totte') with new integer-based IDs from grammar.json
    - Test matching with known grammar patterns from the new dataset
    - Remove ALL `confidence_type` assertions
    - ADD `word` field assertions (verify hits have correct word)
    - Test N5 filter fix: user_level=5 returns N5 hits, user_level=4 does not
    - Test level parsing: verify "N1"→1, "N5"→5 conversion
    - Keep edge case tests: empty text, non-Japanese text, FileNotFoundError
    - Test pattern compilation validation (malformed pattern is skipped with warning)
    - Test position accuracy: `text[hit.start_pos:hit.end_pos] == hit.matched_text`

  **Must NOT do**:
  - Do NOT import from or test grammar_rules.json (deleted)
  - Do NOT assert confidence_type in any test
  - Do NOT change test infrastructure (conftest.py, fixtures)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Full test file rewrite with multiple test cases, requires understanding of new schema
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Task 12)
  - **Parallel Group**: Wave 4
  - **Blocks**: Task 13 (full suite run)
  - **Blocked By**: Task 4 (needs working GrammarMatcher)

  **References**:

  **Pattern References**:
  - `tests/test_grammar.py` — Current test file (117 lines, 12+ tests). Structure to follow but content must change entirely.
  - `data/grammar.json` — Source of truth for expected rule IDs, word values, levels

  **API/Type References**:
  - `src/analysis/grammar.py:GrammarMatcher` — The class under test. After Task 4: loads grammar.json, match() returns GrammarHit with word field, filter uses `>` not `>=`.
  - `src/db/models.py:GrammarHit` — Fields to assert: rule_id(str), matched_text, jlpt_level(int), word(str), description(str), start_pos(int), end_pos(int)

  **Test References**:
  - `tests/test_grammar.py` — Current test structure: uses `RULES_PATH` constant, `@pytest.fixture` for matcher, `test_*` functions

  **WHY Each Reference Matters**:
  - `test_grammar.py`: Understand current test patterns to follow (fixture style, assertion patterns) while replacing content.
  - `grammar.json`: Need actual rule IDs and expected matches for test assertions.

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: All grammar tests pass
    Tool: Bash (pytest)
    Preconditions: test_grammar.py rewritten
    Steps:
      1. Run: pytest tests/test_grammar.py -v
    Expected Result: All tests pass, 0 failures
    Failure Indicators: Any FAILED test
    Evidence: .sisyphus/evidence/task-11-grammar-tests.txt

  Scenario: No confidence_type in grammar tests
    Tool: Bash (grep)
    Steps:
      1. Run: grep -c "confidence_type" tests/test_grammar.py
    Expected Result: 0 matches (exit code 1)
    Evidence: .sisyphus/evidence/task-11-no-confidence-type.txt
  ```

  **Commit**: Groups with commit 6 (test updates)

- [ ] 12. Update 6 remaining test files with factory helpers

  **What to do**:
  - Update ALL test files that construct `GrammarHit` or `HighlightGrammar` objects:
    - `tests/test_highlight.py`: `_make_grammar()` helper — remove `confidence_type`, add `word`
    - `tests/test_db_repository.py`: `make_grammar()` helper — remove `confidence_type`, add `word`
    - `tests/test_analysis_worker.py`: `make_grammar_hit()` helper — remove `confidence_type`, add `word`
    - `tests/test_db_schema.py`: Assert `word` in columns, NOT assert `confidence_type`
    - `tests/test_overlay.py`: Inline `GrammarHit(...)` construction — remove `confidence_type`, add `word`
    - `tests/test_tooltip.py`: `_make_grammar_hit()` helper — remove `confidence_type`, add `word`; remove assertion on confidence_type display
  - Use `ast_grep_search` first to find ALL occurrences of `GrammarHit(` and `HighlightGrammar(` across tests/

  **Must NOT do**:
  - Do NOT change test logic beyond field updates
  - Do NOT modify conftest.py
  - Do NOT add new tests (that's Task 11's job for grammar-specific tests)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: 6 files with factory helpers that all need consistent updates. Must find every occurrence.
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Task 11)
  - **Parallel Group**: Wave 4
  - **Blocks**: Task 13 (full suite run)
  - **Blocked By**: Tasks 2, 5, 6, 8, 9 (all source changes must be done)

  **References**:

  **Pattern References**:
  - `tests/test_highlight.py` — `_make_grammar()` function that creates HighlightGrammar with confidence_type
  - `tests/test_db_repository.py` — `make_grammar()` function
  - `tests/test_analysis_worker.py` — `make_grammar_hit()` function
  - `tests/test_db_schema.py` — Column assertions for highlight_grammar table
  - `tests/test_overlay.py` — Inline GrammarHit construction
  - `tests/test_tooltip.py` — `_make_grammar_hit()` function + confidence_type display assertion

  **WHY Each Reference Matters**:
  - Each factory helper constructs test objects matching the model dataclass. After model changes in Task 2, every construction site must add `word=` and remove `confidence_type=`. Missing even one causes TypeError at test time.

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: No confidence_type in any test file
    Tool: Bash (grep)
    Steps:
      1. Run: grep -r "confidence_type" tests/
    Expected Result: 0 matches (exit code 1)
    Failure Indicators: Any match found
    Evidence: .sisyphus/evidence/task-12-no-confidence-in-tests.txt

  Scenario: All updated test files import/construct correctly
    Tool: Bash (python3 -c)
    Steps:
      1. Run: python3 -c "
         import importlib, sys
         test_files = [
             'tests.test_highlight',
             'tests.test_db_repository',
             'tests.test_analysis_worker',
             'tests.test_db_schema',
             'tests.test_overlay',
             'tests.test_tooltip',
         ]
         for mod in test_files:
             try:
                 importlib.import_module(mod)
                 print(f'{mod}: IMPORT OK')
             except Exception as e:
                 print(f'{mod}: IMPORT FAILED — {e}')
                 sys.exit(1)
         print('ALL 6 TEST FILES IMPORT OK')
         "
    Expected Result: "ALL 6 TEST FILES IMPORT OK"
    Evidence: .sisyphus/evidence/task-12-test-imports.txt
  ```

  **Commit**: Groups with commit 6 (test updates)

- [ ] 13. Run full test suite + lint + type check

  **What to do**:
  - Run the complete verification suite:
    1. `ruff check .` — linting
    2. `ruff format --check .` — formatting
    3. `mypy src/` — type checking
    4. `pytest tests/ -v` — full test suite
  - Fix any failures found
  - Run `grep -r confidence_type src/ tests/` — must return 0 results
  - Verify `data/grammar_rules.json` does not exist

  **Must NOT do**:
  - Do NOT suppress warnings with `# noqa` unless they are false positives
  - Do NOT skip failing tests
  - Do NOT add `type: ignore` comments

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Running verification commands, fixing minor issues
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (must be after all other tasks)
  - **Parallel Group**: Sequential (after Tasks 11, 12)
  - **Blocks**: Final Verification Wave
  - **Blocked By**: Tasks 11, 12

  **References**:

  **Pattern References**:
  - `pyproject.toml` — Ruff, mypy, pytest configuration

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Full verification passes
    Tool: Bash
    Steps:
      1. Run: ruff check . && echo "LINT OK" || echo "LINT FAIL"
      2. Run: ruff format --check . && echo "FORMAT OK" || echo "FORMAT FAIL"
      3. Run: mypy src/ && echo "TYPES OK" || echo "TYPES FAIL"
      4. Run: pytest tests/ -v && echo "TESTS OK" || echo "TESTS FAIL"
      5. Run: grep -r confidence_type src/ tests/ && echo "STALE REFS" || echo "CLEAN"
      6. Run: test ! -f data/grammar_rules.json && echo "OLD FILE GONE" || echo "OLD FILE EXISTS"
    Expected Result: All 6 checks pass: LINT OK, FORMAT OK, TYPES OK, TESTS OK, CLEAN, OLD FILE GONE
    Failure Indicators: Any FAIL or STALE REFS or OLD FILE EXISTS
    Evidence: .sisyphus/evidence/task-13-full-verification.txt
  ```

  **Commit**: NO (verification only — any fixes get their own descriptive commit)

---

## Final Verification Wave (MANDATORY — after ALL implementation tasks)

> 4 review agents run in PARALLEL. ALL must APPROVE. Rejection → fix → re-run.

- [ ] F1. **Plan Compliance Audit** — `oracle`
  Read the plan end-to-end. For each "Must Have": verify implementation exists (read file, run command). For each "Must NOT Have": search codebase for forbidden patterns — reject with file:line if found. Check evidence files exist in `.sisyphus/evidence/`. Compare deliverables against plan.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [ ] F2. **Code Quality Review** — `unspecified-high`
  Run `ruff check . && ruff format --check .` + `mypy src/` + `pytest tests/`. Review all changed files for: `as any`/`type: ignore`, empty catches, console.log in prod, commented-out code, unused imports. Check AI slop: excessive comments, over-abstraction, generic names.
  Output: `Lint [PASS/FAIL] | Types [PASS/FAIL] | Tests [N pass/N fail] | Files [N clean/N issues] | VERDICT`

- [ ] F3. **Real Manual QA** — `unspecified-high`
  Start from clean state. Verify: (1) all 831 patterns compile, (2) grammar matching returns hits with `word` populated, (3) N5 rules fire for user_level=5, (4) DB migration works on existing DB with confidence_type data, (5) fresh DB has correct schema, (6) `grep -r confidence_type src/ tests/` returns 0 results, (7) performance <10ms.
  Output: `Scenarios [N/N pass] | VERDICT`

- [ ] F4. **Scope Fidelity Check** — `deep`
  For each task: read "What to do", read actual diff (git log/diff). Verify 1:1 — everything in spec was built, nothing beyond spec was built. Check "Must NOT do" compliance. Detect cross-task contamination. Flag unaccounted changes.
  Output: `Tasks [N/N compliant] | Contamination [CLEAN/N issues] | Unaccounted [CLEAN/N files] | VERDICT`

---

## Commit Strategy

| # | Message | Key Files | Pre-commit Check |
|---|---------|-----------|-----------------|
| 1 | `fix(data): fix malformed regex patterns in grammar.json` | `data/grammar.json` | `python3 -c "import json,re; [re.compile(r['re']) for r in json.load(open('data/grammar.json'))]"` |
| 2 | `refactor(models): update grammar models — drop confidence_type, add word` | `src/db/models.py` | `ruff check src/db/models.py` |
| 3 | `feat(analysis): rewrite GrammarMatcher for 831-rule grammar.json` | `src/analysis/grammar.py`, `src/analysis/pipeline.py` | `python3 -c "from src.analysis.grammar import GrammarMatcher"` |
| 4 | `feat(db): schema migration — drop confidence_type, add word column` | `src/db/schema.py`, `src/db/repository.py`, `src/pipeline/analysis_worker.py` | `python3 -c "from src.db.schema import init_db; import sqlite3; c=init_db(':memory:')"` |
| 5 | `feat(ui): update tooltip + sentence detail with word field, add N5 colors` | `src/ui/tooltip.py`, `src/ui/sentence_detail.py`, `src/ui/highlight.py`, `src/config.py` | `ruff check src/ui/ src/config.py` |
| 6 | `test: rewrite grammar tests for new 831-rule schema` | `tests/test_grammar.py`, 6 other test files | `pytest tests/` |
| 7 | `chore: delete obsolete grammar_rules.json` | `data/grammar_rules.json` | `test ! -f data/grammar_rules.json` |

---

## Success Criteria

### Verification Commands
```bash
# All patterns compile
python3 -c "import json,re; rules=json.load(open('data/grammar.json')); [re.compile(r['re']) for r in rules]; print(f'{len(rules)} OK')"
# Expected: 831 OK

# Grammar matching works with word field
python3 -c "from src.analysis.grammar import GrammarMatcher; gm=GrammarMatcher('data/grammar.json'); hits=gm.match('音楽を聴きながら勉強した', 5); print(f'{len(hits)} hits'); [print(f'  {h.rule_id}: {h.word} ({h.matched_text})') for h in hits]"
# Expected: >0 hits, each with word populated

# N5 filtering works
python3 -c "from src.analysis.grammar import GrammarMatcher; gm=GrammarMatcher('data/grammar.json'); hits=gm.match('これは本です', 5); n5=[h for h in hits if h.jlpt_level==5]; print(f'N5 hits: {len(n5)}')"
# Expected: N5 hits: >0

# DB schema correct
python3 -c "from src.db.schema import init_db; c=init_db(':memory:'); cols={r[1] for r in c.execute('PRAGMA table_info(highlight_grammar)').fetchall()}; assert 'word' in cols; assert 'confidence_type' not in cols; print('Schema OK')"
# Expected: Schema OK

# Performance
python3 -c "import time,json,re; rules=json.load(open('data/grammar.json')); pats=[re.compile(r['re']) for r in rules]; text='昨日友達と映画を見に行きました。とても面白かったので、また見たいと思います。'; t0=time.perf_counter(); [list(p.finditer(text)) for p in pats]; ms=(time.perf_counter()-t0)*1000; print(f'{ms:.2f}ms'); assert ms<10"
# Expected: <1ms, assert passes

# No stale references
grep -r confidence_type src/ tests/
# Expected: 0 results (exit code 1)

# Full suite
ruff check . && ruff format --check . && mypy src/ && pytest tests/
# Expected: all pass
```

### Final Checklist
- [ ] All "Must Have" present
- [ ] All "Must NOT Have" absent
- [ ] All 831 rules load and match
- [ ] `word` field flows from JSON → GrammarHit → HighlightGrammar → DB → UI
- [ ] N5 grammar visible to N5 users
- [ ] `confidence_type` fully purged
- [ ] All tests pass
- [ ] Performance <10ms
