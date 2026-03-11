# Vocabulary CSV Migration — Replace JSON Lookup with Rich CSV-Based System

## TL;DR

> **Quick Summary**: Replace the placeholder JSON vocabulary (35 entries, lemma→level only) with a comprehensive CSV-based lookup system (8,293 entries) carrying all 5 columns (id, pronBase, lemma, definition, level) through the entire pipeline — from analysis to DB storage to UI display.
> 
> **Deliverables**:
> - CSV loader with O(1) dict lookup, dash-stripping, and duplicate resolution (easiest level wins)
> - Enriched VocabHit and HighlightVocab models with pronunciation + definition fields
> - Updated DB schema with ALTER TABLE migration for existing databases
> - Updated UI (tooltip, sentence detail, learning panel export) displaying pronunciation + definition
> - Full TDD test suite covering loader, models, DB, pipeline integration, and UI rendering
> 
> **Estimated Effort**: Medium
> **Parallel Execution**: YES — 3 waves + final verification
> **Critical Path**: Task 1 → Task 3 → Task 5 → Task 7 → Task 8 → Task 9

---

## Context

### Original Request
Replace `data/jlpt_vocab.json` (35-entry placeholder, lemma→level map) with `data/vocabulary.csv` (8,293 entries, 5 columns: id, pronBase, lemma, definition, level). Propagate all attributes through the pipeline for learning features. Strip fugashi's dash-annotated lemmas before lookup. Maintain real-time O(1) performance.

### Interview Summary
**Key Discussions**:
- **Duplicate lemma strategy**: ~230 duplicate lemmas in CSV with different pronunciations/levels. Decision: **easiest level wins** (highest N-number). Keeps O(1) lookup with `dict[str, VocabEntry]`.
- **Dash stripping**: Fugashi produces lemmas like `私-代名詞`. Must strip before `-` before CSV lookup. CSV lemma column has no dashes.
- **All 5 attributes available**: id, pronBase, lemma, definition, level — all must flow through to learning features.
- **Performance**: ~9K entries, O(1) dict lookup preserved. CSV parsed once at startup.
- **Testing**: TDD approach using existing pytest infrastructure.

**Research Findings**:
- Current jlpt_vocab.json: only 35 entries, flat `{lemma: int}` map — a placeholder.
- VocabHit frozen dataclass: used by 10+ files across analysis, pipeline, DB, and UI layers.
- HighlightVocab DB model lacks pronunciation/definition columns entirely.
- Tooltip shows only: level badge + lemma(surface) + POS. No definition/pronunciation.
- CSV level format is string "N1"-"N5"; system uses int 1-5 internally.
- 48 CSV entries have empty definition fields — UI must handle gracefully.

### Metis Review
**Identified Gaps** (addressed):
- **Duplicate lemma cascade**: Resolved — easiest level wins, O(1) dict preserved.
- **is_beyond_level bug in analysis_worker**: Left as-is — out of scope, separate concern.
- **Empty definitions**: Default to omitting in UI, no placeholder text.
- **CSV path**: Hardcoded to `data/vocabulary.csv` — matches current pattern.
- **DB migration**: ALTER TABLE with try/except — safe for existing DBs.
- **CSV id column**: Stored in VocabEntry since user wants all attributes available.
- **list.index() in main.py**: Must verify VocabHit equality still works with new fields.
- **Unicode normalization**: Verify CSV lemma vs fugashi lemma encoding compatibility.

---

## Work Objectives

### Core Objective
Replace the JSON-based JLPT vocabulary lookup with a CSV-based system that carries all vocabulary attributes (id, pronunciation, lemma, definition, level) through the analysis pipeline, database storage, and UI display layers.

### Concrete Deliverables
- `src/analysis/jlpt_vocab.py` — Rewritten CSV loader with `VocabEntry` dataclass
- `src/db/models.py` — Updated `VocabHit` and `HighlightVocab` with pronunciation + definition fields
- `src/db/schema.py` — Updated table schema + ALTER TABLE migration
- `src/db/repository.py` — Updated SQL for new columns
- `src/pipeline/analysis_worker.py` — Propagate new fields VocabHit → HighlightVocab
- `src/ui/tooltip.py` — Display pronunciation + definition
- `src/ui/sentence_detail.py` — Display pronunciation + definition in detail dialog
- `src/analysis/pipeline.py` — Point to CSV instead of JSON
- Tests: Updated/new tests for every changed module

### Definition of Done
- [ ] `pytest tests/` passes with 0 failures
- [ ] `ruff check . && ruff format --check .` passes
- [ ] `mypy src/` passes
- [ ] CSV lookup resolves all ~8,049 unique lemmas (after dedup)
- [ ] Tooltip displays pronunciation + definition for known vocabulary
- [ ] DB stores pronunciation + definition for each highlight
- [ ] Existing DB migrates without data loss (ALTER TABLE adds new columns)

### Must Have
- O(1) dictionary lookup performance preserved
- Dash-stripping before lemma matching (`私-代名詞` → `私`)
- All 5 CSV columns (id, pronBase, lemma, definition, level) accessible in VocabEntry
- Level conversion: CSV "N5" → int 5
- Duplicate resolution: easiest level wins per lemma
- Pronunciation + definition in tooltip popup
- Pronunciation + definition in sentence detail dialog
- Pronunciation + definition stored in highlight_vocab DB table
- Graceful handling of empty definition fields (48 entries)
- ALTER TABLE migration for existing databases
- TDD: tests written before implementation for each task

### Must NOT Have (Guardrails)
- **DO NOT** change the tokenizer (`fugashi`) — only change post-tokenization lookup
- **DO NOT** add pronunciation-based disambiguation at lookup time (future feature)
- **DO NOT** change the grammar analysis pipeline — vocab changes only
- **DO NOT** add CSV editing/management UI
- **DO NOT** add import/export features for vocabulary data
- **DO NOT** change the overlay's visual design system (colors, fonts, layout grid) — only ADD text fields
- **DO NOT** refactor QThread worker pattern or signal architecture
- **DO NOT** touch `src/audio/`, `src/vad/`, `src/asr/` — upstream pipeline is out of scope
- **DO NOT** create abstract "data loader" ABC — just load the CSV directly
- **DO NOT** add per-row runtime CSV validation — it's a static shipped file
- **DO NOT** fix the `is_beyond_level` bug — out of scope
- **DO NOT** add speculative features (search by pronunciation, vocabulary editing, etc.)

---

## Verification Strategy

> **ZERO HUMAN INTERVENTION** — ALL verification is agent-executed. No exceptions.

### Test Decision
- **Infrastructure exists**: YES (pytest, 29 test files)
- **Automated tests**: TDD (RED → GREEN → REFACTOR per task)
- **Framework**: pytest
- **Baseline**: `pytest tests/` must pass BEFORE any changes

### QA Policy
Every task MUST include agent-executed QA scenarios.
Evidence saved to `.sisyphus/evidence/task-{N}-{scenario-slug}.{ext}`.

- **Data layer**: pytest assertions with exact expected values
- **DB layer**: PRAGMA queries + INSERT/SELECT round-trip verification
- **UI layer**: HTML string assertions on rendered tooltip/detail output
- **Integration**: End-to-end pytest with real CSV + real fugashi tokenizer

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Start Immediately — foundation + models):
├── Task 1: VocabEntry dataclass + CSV loader with tests [deep]
├── Task 2: Update VocabHit + HighlightVocab models with tests [quick]
└── Task 3: Update DB schema + migration + repository with tests [unspecified-high]

Wave 2 (After Wave 1 — pipeline wiring):
├── Task 4: Update tokenizer lemma stripping (if needed) + JLPTVocabLookup.lookup() [quick]
├── Task 5: Wire CSV into PreprocessingPipeline + analysis_worker [unspecified-high]
└── Task 6: Update learning_panel export for new fields [quick]

Wave 3 (After Wave 2 — UI + cleanup):
├── Task 7: Update tooltip to display pronunciation + definition [quick]
├── Task 8: Update sentence_detail to display pronunciation + definition [quick]
└── Task 9: Remove old JSON + final integration test + cleanup [unspecified-high]

Wave FINAL (After ALL tasks — independent review, 4 parallel):
├── Task F1: Plan compliance audit (oracle)
├── Task F2: Code quality review (unspecified-high)
├── Task F3: Real manual QA (unspecified-high)
└── Task F4: Scope fidelity check (deep)

Critical Path: Task 1 → Task 3 → Task 5 → Task 7 → Task 9 → F1-F4
Parallel Speedup: ~50% faster than sequential
Max Concurrent: 3 (Waves 1 & 2)
```

### Dependency Matrix

| Task | Depends On | Blocks | Wave |
|------|-----------|--------|------|
| 1 | — | 2, 3, 4, 5 | 1 |
| 2 | — | 5, 6, 7, 8 | 1 |
| 3 | — | 5, 6, 9 | 1 |
| 4 | 1, 2 | 5 | 2 |
| 5 | 1, 2, 3, 4 | 7, 8, 9 | 2 |
| 6 | 2, 3 | 9 | 2 |
| 7 | 2, 5 | 9 | 3 |
| 8 | 2, 5 | 9 | 3 |
| 9 | all above | F1-F4 | 3 |
| F1-F4 | 9 | — | FINAL |

### Agent Dispatch Summary

- **Wave 1**: 3 tasks — T1 → `deep`, T2 → `quick`, T3 → `unspecified-high`
- **Wave 2**: 3 tasks — T4 → `quick`, T5 → `unspecified-high`, T6 → `quick`
- **Wave 3**: 3 tasks — T7 → `quick`, T8 → `quick`, T9 → `unspecified-high`
- **FINAL**: 4 tasks — F1 → `oracle`, F2 → `unspecified-high`, F3 → `unspecified-high`, F4 → `deep`

---

## TODOs

- [ ] 0. **Establish Green Baseline**

  **What to do**:
  - Run `pytest tests/` and confirm all existing tests pass
  - Run `ruff check . && ruff format --check .` and confirm no lint issues
  - Record baseline test count for later comparison
  - If any tests fail, STOP and report — do not proceed with TDD on a red baseline

  **Must NOT do**:
  - Do not fix pre-existing failures (out of scope)
  - Do not modify any source files

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Must run FIRST before all other tasks
  - **Blocks**: All tasks (1-9)
  - **Blocked By**: None

  **References**:
  - `pyproject.toml` — pytest config section `[tool.pytest.ini_options]` with `pythonpath = ["."]`

  **Acceptance Criteria**:

  **QA Scenarios:**
  ```
  Scenario: Green baseline confirmed
    Tool: Bash
    Steps:
      1. Run `pytest tests/ -v --tb=short`
      2. Capture output, count total tests and failures
      3. Run `ruff check . && ruff format --check .`
    Expected Result: 0 test failures, 0 lint errors
    Evidence: .sisyphus/evidence/task-0-green-baseline.txt
  ```

  **Commit**: NO

- [ ] 1. **VocabEntry Dataclass + CSV Loader with Tests**

  **What to do**:
  - **RED**: Write tests first in `tests/test_jlpt_vocab.py` (update existing file):
    - Test `VocabEntry` dataclass has fields: vocab_id (int), pronunciation (str), lemma (str), definition (str), level (int)
    - Test CSV loading: `JLPTVocabLookup('data/vocabulary.csv')` creates lookup with ~8,049 unique lemmas
    - Test dedup strategy: for duplicate lemma `私`, the entry with easiest level (highest N-number) is kept
    - Test level conversion: CSV "N5" → int 5, "N1" → int 1
    - Test dash-stripping in lookup: `lookup.lookup('私-代名詞')` returns entry for `私`
    - Test lookup miss: `lookup.lookup('xxxxxx')` returns None
    - Test empty definition: entry with empty definition has `definition == ""`
    - Test performance: CSV load completes in < 500ms
  - **GREEN**: Implement in `src/analysis/jlpt_vocab.py`:
    - Add `VocabEntry` frozen dataclass with `slots=True`: vocab_id (int), pronunciation (str), lemma (str), definition (str), level (int)
    - Rewrite `JLPTVocabLookup.__init__` to load CSV using `csv.DictReader`
    - Build `self._vocab: dict[str, VocabEntry]` — key is lemma, value is VocabEntry
    - During load: convert level "N5" → 5 via `int(row['level'][1:])`
    - During load: for duplicate lemmas, keep entry with highest level number (easiest)
    - Rewrite `lookup(lemma: str) -> VocabEntry | None`: strip before first `-`, then dict.get()
    - **DO NOT** modify `find_beyond_level` in this task — it should continue working with existing VocabHit fields only (jlpt_level from VocabEntry.level). Enrichment with pronunciation/definition is Task 4's responsibility (after Task 2 adds those fields to VocabHit).
  - **REFACTOR**: Clean up, ensure frozen dataclass pattern matches codebase convention

  **Must NOT do**:
  - Do not create abstract loader classes
  - Do not add runtime per-row CSV validation beyond format parsing
  - Do not modify `find_beyond_level` to use new VocabHit fields (that's Task 4, after Task 2 adds the fields)
  - Do not import or reference VocabEntry fields that require VocabHit changes from Task 2

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: []
    - No special skills needed — pure Python data processing with pytest

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 2, 3)
  - **Parallel Group**: Wave 1
  - **Blocks**: Tasks 4, 5
  - **Blocked By**: Task 0 (green baseline)

  **References**:

  **Pattern References**:
  - `src/analysis/jlpt_vocab.py` — Current JLPTVocabLookup class to rewrite. Keep method signatures (`lookup`, `find_beyond_level`) but change internals.
  - `src/db/models.py:Token` — Frozen dataclass pattern: `@dataclass(frozen=True, slots=True)` — follow this for VocabEntry.

  **API/Type References**:
  - `src/db/models.py:VocabHit` — Current fields: surface, lemma, pos, jlpt_level, user_level, start_pos, end_pos. `find_beyond_level` constructs these; will need new fields from Task 2.

  **Test References**:
  - `tests/test_jlpt_vocab.py` — Existing 9 tests. Rewrite to test CSV loading instead of JSON. Keep test structure and assertion patterns.

  **External References**:
  - `data/vocabulary.csv` — The source CSV file. Header: `id,pronBase,lemma,definition,level`. 8,293 rows.

  **Acceptance Criteria**:
  - [ ] `VocabEntry` dataclass exists in `src/analysis/jlpt_vocab.py` with 5 fields
  - [ ] `pytest tests/test_jlpt_vocab.py -v` → all tests pass

  **QA Scenarios:**
  ```
  Scenario: CSV loads with correct entry count
    Tool: Bash
    Steps:
      1. Run: python3 -c "from src.analysis.jlpt_vocab import JLPTVocabLookup; lk = JLPTVocabLookup('data/vocabulary.csv'); print(len(lk._vocab))"
      2. Assert output is approximately 8049 (unique lemmas after dedup)
    Expected Result: Number between 8000 and 8100
    Evidence: .sisyphus/evidence/task-1-csv-load-count.txt

  Scenario: Dash-stripping lookup works
    Tool: Bash
    Steps:
      1. Run: python3 -c "from src.analysis.jlpt_vocab import JLPTVocabLookup; lk = JLPTVocabLookup('data/vocabulary.csv'); e = lk.lookup('私-代名詞'); print(f'level={e.level}, pron={e.pronunciation}')"
      2. Assert output contains level=5 (easiest entry for 私)
    Expected Result: level=5, pronunciation is one of ワタクシ/ワタシ
    Evidence: .sisyphus/evidence/task-1-dash-strip.txt

  Scenario: Unknown lemma returns None
    Tool: Bash
    Steps:
      1. Run: python3 -c "from src.analysis.jlpt_vocab import JLPTVocabLookup; lk = JLPTVocabLookup('data/vocabulary.csv'); print(lk.lookup('xxxxxxx'))"
      2. Assert output is "None"
    Expected Result: None
    Evidence: .sisyphus/evidence/task-1-unknown-lemma.txt

  Scenario: Performance — CSV load under 500ms
    Tool: Bash
    Steps:
      1. Run: python3 -c "import time; t=time.perf_counter(); from src.analysis.jlpt_vocab import JLPTVocabLookup; lk = JLPTVocabLookup('data/vocabulary.csv'); elapsed=(time.perf_counter()-t)*1000; print(f'{elapsed:.1f}ms'); assert elapsed < 500, f'Too slow: {elapsed}ms'"
    Expected Result: Load completes in < 500ms
    Evidence: .sisyphus/evidence/task-1-performance.txt
  ```

  **Commit**: YES
  - Message: `feat(analysis): add VocabEntry dataclass and CSV loader`
  - Files: `src/analysis/jlpt_vocab.py`, `tests/test_jlpt_vocab.py`
  - Pre-commit: `pytest tests/test_jlpt_vocab.py -v`

- [ ] 2. **Update VocabHit and HighlightVocab Models with New Fields**

  **What to do**:
  - **RED**: Write tests first:
    - Test `VocabHit` can be constructed with new fields: `vocab_id`, `pronunciation`, `definition`
    - Test `VocabHit` default values for new fields (for backward compat during migration): `vocab_id=0`, `pronunciation=""`, `definition=""`
    - Test `HighlightVocab` has new fields: `pronunciation`, `definition`
    - Test frozen dataclass constraints (immutability)
  - **GREEN**: Update `src/db/models.py`:
    - Add to `VocabHit`: `vocab_id: int = 0`, `pronunciation: str = ""`, `definition: str = ""` (defaults for backward compat)
    - Add to `HighlightVocab`: `vocab_id: int = 0`, `pronunciation: str = ""`, `definition: str = ""`
    - Ensure new fields are AFTER existing fields to preserve positional construction
  - **REFACTOR**: Verify all existing VocabHit construction sites still work with defaults

  **Must NOT do**:
  - Do not change field ordering of existing fields
  - Do not remove any existing fields
  - Do not change `__eq__` behavior — new fields with defaults preserve equality for existing code

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 1, 3)
  - **Parallel Group**: Wave 1
  - **Blocks**: Tasks 5, 6, 7, 8
  - **Blocked By**: Task 0 (green baseline)

  **References**:

  **Pattern References**:
  - `src/db/models.py:VocabHit` — Current frozen dataclass with fields: surface, lemma, pos, jlpt_level, user_level, start_pos, end_pos. Add new fields AFTER end_pos.
  - `src/db/models.py:HighlightVocab` — Current fields: id, sentence_id, surface, lemma, pos, jlpt_level, is_beyond_level, tooltip_shown. Add new fields after tooltip_shown.
  - `src/db/models.py:GrammarHit` — Reference for field ordering convention with defaults.

  **API/Type References**:
  - Search all VocabHit construction sites via `ast_grep_search` pattern `VocabHit($$$)` in Python — every construction must still work with new default fields.
  - `src/main.py:111` — Uses `list.index()` on VocabHit — verify equality still works.

  **Test References**:
  - `tests/test_jlpt_vocab.py` — Constructs VocabHit in tests, will need updating.
  - `tests/test_tooltip.py`, `tests/test_highlight.py` — Also construct VocabHit.

  **Acceptance Criteria**:
  - [ ] `VocabHit` has fields: vocab_id, pronunciation, definition (with defaults)
  - [ ] `HighlightVocab` has fields: pronunciation, definition
  - [ ] `pytest tests/` → all existing tests still pass (backward compat via defaults)

  **QA Scenarios:**
  ```
  Scenario: VocabHit backward compatibility
    Tool: Bash
    Steps:
      1. Run: python3 -c "from src.db.models import VocabHit; v = VocabHit(surface='食べ', lemma='食べる', pos='動詞', jlpt_level=4, user_level=5, start_pos=0, end_pos=2); print(f'pron={v.pronunciation}, def={v.definition}, vid={v.vocab_id}')"
      2. Assert defaults: pronunciation="", definition="", vocab_id=0
    Expected Result: pron=, def=, vid=0
    Evidence: .sisyphus/evidence/task-2-backward-compat.txt

  Scenario: VocabHit with new fields
    Tool: Bash
    Steps:
      1. Run: python3 -c "from src.db.models import VocabHit; v = VocabHit(surface='食べ', lemma='食べる', pos='動詞', jlpt_level=4, user_level=5, start_pos=0, end_pos=2, vocab_id=1234, pronunciation='タベル', definition='to eat'); print(f'pron={v.pronunciation}, def={v.definition}')"
      2. Assert: pronunciation='タベル', definition='to eat'
    Expected Result: pron=タベル, def=to eat
    Evidence: .sisyphus/evidence/task-2-new-fields.txt

  Scenario: Existing test suite still passes
    Tool: Bash
    Steps:
      1. Run: pytest tests/ -v --tb=short
      2. Assert 0 failures
    Expected Result: All existing tests pass
    Evidence: .sisyphus/evidence/task-2-existing-tests.txt
  ```

  **Commit**: YES
  - Message: `feat(models): add pronunciation and definition to VocabHit and HighlightVocab`
  - Files: `src/db/models.py`, relevant test files
  - Pre-commit: `pytest tests/ -v`

- [ ] 3. **Update DB Schema, Migration, and Repository for New Columns**

  **What to do**:
  - **RED**: Write tests first in `tests/test_db_repository.py` (update existing):
    - Test fresh DB creation: `highlight_vocab` table has `vocab_id`, `pronunciation` and `definition` columns
    - Test ALTER TABLE migration: create DB with old schema, run `init_db`, verify new columns added
    - Test insert with new fields: `HighlightVocab` with vocab_id/pronunciation/definition persists correctly
    - Test query returns new fields: `get_sentence_with_highlights` returns vocab_id/pronunciation/definition
    - Test export includes new fields
  - **GREEN**: Update `src/db/schema.py`:
    - Add `vocab_id INTEGER NOT NULL DEFAULT 0`, `pronunciation TEXT NOT NULL DEFAULT ''` and `definition TEXT NOT NULL DEFAULT ''` to `highlight_vocab` CREATE TABLE
    - Add migration function: try `ALTER TABLE highlight_vocab ADD COLUMN ...` for each of vocab_id, pronunciation, definition with `try/except` for existing columns
    - Call migration in `init_db` after CREATE TABLE
  - **GREEN**: Update `src/db/repository.py`:
    - Update INSERT SQL for `highlight_vocab` to include vocab_id, pronunciation, definition
    - Update SELECT SQL to read vocab_id, pronunciation, definition
    - Update `_row_to_highlight_vocab` mapping for new fields
    - Update `export_records` to include new columns
  - **REFACTOR**: Ensure WAL mode and foreign keys still work correctly

  **Must NOT do**:
  - Do not drop existing tables or data
  - Do not change the sentence or grammar tables
  - Do not add a formal migration framework — simple ALTER TABLE is sufficient

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 1, 2)
  - **Parallel Group**: Wave 1
  - **Blocks**: Tasks 5, 6, 9
  - **Blocked By**: Task 0 (green baseline)

  **References**:

  **Pattern References**:
  - `src/db/schema.py` — Current `highlight_vocab` CREATE TABLE statement and `init_db()` function. Follow existing column pattern with `TEXT NOT NULL DEFAULT ''`.
  - `src/db/repository.py` — INSERT/SELECT patterns for `highlight_vocab`. Follow existing parameter binding pattern (`:param_name`).

  **API/Type References**:
  - `src/db/models.py:HighlightVocab` — The model this table maps to (being updated in Task 2). New fields: pronunciation, definition.

  **Test References**:
  - `tests/test_db_repository.py` — Existing DB tests with `tmp_path` fixtures. Follow same pattern for new column tests.

  **Acceptance Criteria**:
  - [ ] Fresh DB has `vocab_id`, `pronunciation` and `definition` columns in `highlight_vocab`
  - [ ] Existing DB gets new columns via ALTER TABLE without data loss
  - [ ] `pytest tests/test_db_repository.py -v` → all tests pass

  **QA Scenarios:**

  > **Note**: `init_db(db_path: str) -> sqlite3.Connection` takes a path string and returns a connection.
  > The migration function (new, added by this task) should be a separate `migrate_db(conn)` or be
  > called internally by `init_db`. QA scenarios use the correct signatures below.

  ```
  Scenario: Fresh DB schema has new columns
    Tool: Bash
    Steps:
      1. Run: python3 -c "
         import tempfile, os
         from src.db.schema import init_db
         db_path = os.path.join(tempfile.mkdtemp(), 'test.db')
         conn = init_db(db_path)
         cursor = conn.execute('PRAGMA table_info(highlight_vocab)')
         cols = [row[1] for row in cursor.fetchall()]
         print(cols)
         assert 'pronunciation' in cols, f'Missing pronunciation: {cols}'
         assert 'definition' in cols, f'Missing definition: {cols}'
         assert 'vocab_id' in cols, f'Missing vocab_id: {cols}'
         conn.close()
         print('PASS')
         "
    Expected Result: Column list includes 'pronunciation' and 'definition', prints PASS
    Evidence: .sisyphus/evidence/task-3-fresh-schema.txt

  Scenario: ALTER TABLE migration on existing DB
    Tool: Bash
    Steps:
      1. Run: python3 -c "
         import sqlite3, tempfile, os
         db_path = os.path.join(tempfile.mkdtemp(), 'test.db')
         # First create DB with OLD schema (no pronunciation/definition columns)
         conn = sqlite3.connect(db_path)
         conn.execute('CREATE TABLE IF NOT EXISTS sentence_records (id INTEGER PRIMARY KEY AUTOINCREMENT, japanese_text TEXT NOT NULL, source_context TEXT, created_at TEXT NOT NULL)')
         conn.execute('CREATE TABLE IF NOT EXISTS highlight_vocab (id INTEGER PRIMARY KEY AUTOINCREMENT, sentence_id INTEGER NOT NULL, surface TEXT NOT NULL, lemma TEXT NOT NULL, pos TEXT NOT NULL, jlpt_level INTEGER, is_beyond_level INTEGER NOT NULL DEFAULT 0, tooltip_shown INTEGER NOT NULL DEFAULT 0)')
         conn.execute('CREATE TABLE IF NOT EXISTS highlight_grammar (id INTEGER PRIMARY KEY AUTOINCREMENT, sentence_id INTEGER NOT NULL, rule_id TEXT NOT NULL, pattern TEXT NOT NULL, jlpt_level INTEGER, confidence_type TEXT NOT NULL, description TEXT, is_beyond_level INTEGER NOT NULL DEFAULT 0, tooltip_shown INTEGER NOT NULL DEFAULT 0)')
         conn.execute('CREATE TABLE IF NOT EXISTS app_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
         conn.commit()
         old_cols = [r[1] for r in conn.execute('PRAGMA table_info(highlight_vocab)').fetchall()]
         assert 'pronunciation' not in old_cols, 'Old schema should not have pronunciation'
         conn.close()
         # Now run init_db on the same path — should migrate (add columns)
         from src.db.schema import init_db
         conn2 = init_db(db_path)
         new_cols = [r[1] for r in conn2.execute('PRAGMA table_info(highlight_vocab)').fetchall()]
         assert 'pronunciation' in new_cols, f'Missing pronunciation after migration: {new_cols}'
         assert 'definition' in new_cols, f'Missing definition after migration: {new_cols}'
         assert 'vocab_id' in new_cols, f'Missing vocab_id after migration: {new_cols}'
         conn2.close()
         print('MIGRATION PASS')
         "
    Expected Result: Prints "MIGRATION PASS"
    Evidence: .sisyphus/evidence/task-3-migration.txt
  ```

  **Commit**: YES
  - Message: `feat(db): add pronunciation and definition columns with migration`
  - Files: `src/db/schema.py`, `src/db/repository.py`, `tests/test_db_repository.py`
  - Pre-commit: `pytest tests/test_db_repository.py -v`

- [ ] 4. **Integrate Dash-Stripping into Lookup + Update find_beyond_level**

  **What to do**:
  - **RED**: Write/update tests in `tests/test_jlpt_vocab.py`:
    - Test `find_beyond_level` returns VocabHit with pronunciation, definition, vocab_id populated from CSV
    - Test `find_beyond_level` with a token whose lemma has a dash annotation produces a valid hit
    - Test that position tracking (start_pos, end_pos) still works correctly
    - Test that tokens with unknown lemmas are skipped (no crash)
  - **GREEN**: Update `src/analysis/jlpt_vocab.py`:
    - Ensure `lookup()` strips before first `-` in the input lemma before dict.get()
    - Update `find_beyond_level` to populate VocabHit with new fields from the matched VocabEntry:
      - `vocab_id=entry.vocab_id`
      - `pronunciation=entry.pronunciation`
      - `definition=entry.definition`
  - **REFACTOR**: Ensure the method handles edge cases: lemma is exactly `-`, lemma starts with `-`, empty lemma

  **Must NOT do**:
  - Do not change `find_beyond_level` method signature (return type is still `list[VocabHit]`)
  - Do not modify the tokenizer itself
  - Do not add pronunciation-based disambiguation

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (depends on Task 1 for CSV loader + Task 2 for enriched VocabHit)
  - **Parallel Group**: Wave 2
  - **Blocks**: Task 5
  - **Blocked By**: Tasks 1, 2

  **References**:

  **Pattern References**:
  - `src/analysis/jlpt_vocab.py:find_beyond_level` — Current method that constructs VocabHit. Needs to pull vocab_id, pronunciation, definition from VocabEntry returned by lookup().
  - `src/analysis/tokenizer.py:tokenize` — Produces `Token(surface, lemma, pos)` that feeds into find_beyond_level. The `lemma` field may contain dashes from fugashi.

  **API/Type References**:
  - `src/db/models.py:VocabHit` — Updated in Task 2 with new fields vocab_id, pronunciation, definition.
  - `src/db/models.py:Token` — Input to find_beyond_level, unchanged.

  **Test References**:
  - `tests/test_jlpt_vocab.py` — Existing tests for find_beyond_level; extend with new-field assertions.

  **Acceptance Criteria**:
  - [ ] `find_beyond_level` returns VocabHit with populated pronunciation and definition
  - [ ] Dash-annotated lemmas match correctly
  - [ ] `pytest tests/test_jlpt_vocab.py -v` → all tests pass

  **QA Scenarios:**
  ```
  Scenario: find_beyond_level returns enriched VocabHit
    Tool: Bash
    Steps:
      1. Run: python3 -c "
         from src.analysis.jlpt_vocab import JLPTVocabLookup
         from src.db.models import Token
         lk = JLPTVocabLookup('data/vocabulary.csv')
         tokens = [Token(surface='食べ', lemma='食べる', pos='動詞')]
         hits = lk.find_beyond_level(tokens, user_level=5, text='食べ')
         if hits:
             h = hits[0]
             print(f'pron={h.pronunciation}, def_len={len(h.definition)}, vid={h.vocab_id}')
             assert h.pronunciation != '', 'pronunciation should not be empty'
             assert h.vocab_id > 0, 'vocab_id should be positive'
         print('PASS')
         "
    Expected Result: pronunciation is non-empty, vocab_id > 0, prints PASS
    Evidence: .sisyphus/evidence/task-4-enriched-vocabhit.txt

  Scenario: Dash-annotated lemma matches
    Tool: Bash
    Steps:
      1. Run: python3 -c "
         from src.analysis.jlpt_vocab import JLPTVocabLookup
         from src.db.models import Token
         lk = JLPTVocabLookup('data/vocabulary.csv')
         tokens = [Token(surface='私', lemma='私-代名詞', pos='代名詞')]
         hits = lk.find_beyond_level(tokens, user_level=1, text='私')
         assert len(hits) > 0, 'Should match despite dash in lemma'
         print(f'Matched: {hits[0].lemma} level={hits[0].jlpt_level}')
         print('PASS')
         "
    Expected Result: Match found, prints PASS
    Evidence: .sisyphus/evidence/task-4-dash-lemma.txt
  ```

  **Commit**: YES (groups with Task 1)
  - Message: `feat(analysis): integrate CSV loader into pipeline with dash-stripping`
  - Files: `src/analysis/jlpt_vocab.py`, `src/analysis/pipeline.py`, `tests/test_jlpt_vocab.py`
  - Pre-commit: `pytest tests/test_jlpt_vocab.py tests/test_analysis_pipeline.py -v`

- [ ] 5. **Wire CSV into PreprocessingPipeline + AnalysisWorker**

  **What to do**:
  - **RED**: Write/update tests:
    - In `tests/test_analysis_pipeline.py`: Test that `PreprocessingPipeline.process()` returns `AnalysisResult` with enriched VocabHit (pronunciation, definition present)
    - In `tests/test_analysis_worker.py`: Test that AnalysisWorker creates `HighlightVocab` with pronunciation and definition from VocabHit
  - **GREEN**: Update `src/analysis/pipeline.py`:
    - Change `JLPTVocabLookup('data/jlpt_vocab.json')` → `JLPTVocabLookup('data/vocabulary.csv')`
  - **GREEN**: Update `src/pipeline/analysis_worker.py`:
    - In the VocabHit → HighlightVocab mapping, propagate new fields:
      - `vocab_id=hit.vocab_id`
      - `pronunciation=hit.pronunciation`
      - `definition=hit.definition`
  - **REFACTOR**: Ensure no regression in existing pipeline behavior

  **Must NOT do**:
  - Do not change signal signatures or QThread patterns
  - Do not add new pipeline stages
  - Do not modify ASR or VAD workers

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (depends on Tasks 1, 2, 3, 4)
  - **Parallel Group**: Wave 2
  - **Blocks**: Tasks 7, 8, 9
  - **Blocked By**: Tasks 1, 2, 3, 4

  **References**:

  **Pattern References**:
  - `src/analysis/pipeline.py:__init__` — Line where JLPTVocabLookup is instantiated with JSON path. Change to CSV path.
  - `src/pipeline/analysis_worker.py` — VocabHit → HighlightVocab mapping in the processing loop. Add pronunciation/definition propagation.

  **API/Type References**:
  - `src/db/models.py:HighlightVocab` — Updated in Task 2; construction must now include pronunciation/definition.
  - `src/db/models.py:VocabHit` — Updated in Task 2; now carries pronunciation/definition from lookup.

  **Test References**:
  - `tests/test_analysis_pipeline.py` — Existing pipeline tests. Extend to check new VocabHit fields.
  - `tests/test_analysis_worker.py` — Existing worker tests. Extend to verify HighlightVocab gets new fields.

  **Acceptance Criteria**:
  - [ ] Pipeline loads CSV instead of JSON
  - [ ] AnalysisWorker propagates pronunciation/definition to HighlightVocab
  - [ ] `pytest tests/test_analysis_pipeline.py tests/test_analysis_worker.py -v` → all pass

  **QA Scenarios:**
  ```
  Scenario: Pipeline process() returns enriched VocabHits
    Tool: Bash
    Steps:
      1. Run: python3 -c "
         from src.analysis.pipeline import PreprocessingPipeline
         from src.config import AppConfig
         config = AppConfig()
         pipeline = PreprocessingPipeline(config)
         result = pipeline.process('私は食べる')
         for hit in result.vocab_hits:
             print(f'{hit.lemma}: pron={hit.pronunciation}, def={hit.definition[:30]}')
         print(f'Total hits: {len(result.vocab_hits)}')
         print('PASS')
         "
    Expected Result: VocabHits have non-empty pronunciation; prints PASS
    Evidence: .sisyphus/evidence/task-5-pipeline-enriched.txt

  Scenario: No JSON reference remains
    Tool: Bash
    Steps:
      1. Run: grep -r "jlpt_vocab.json" src/
      2. Assert no matches (empty output)
    Expected Result: No references to jlpt_vocab.json in src/
    Evidence: .sisyphus/evidence/task-5-no-json-ref.txt
  ```

  **Commit**: YES
  - Message: `feat(pipeline): propagate vocabulary metadata through analysis worker`
  - Files: `src/analysis/pipeline.py`, `src/pipeline/analysis_worker.py`, `tests/test_analysis_pipeline.py`, `tests/test_analysis_worker.py`
  - Pre-commit: `pytest tests/test_analysis_pipeline.py tests/test_analysis_worker.py -v`

- [ ] 6. **Update Learning Panel Export for New Fields**

  **What to do**:
  - **RED**: Write tests:
    - Test that CSV/JSON export includes pronunciation and definition columns for vocab highlights
  - **GREEN**: Update `src/db/repository.py` export query (if not already done in Task 3) or `src/ui/learning_panel.py` export formatting to include new fields
  - **REFACTOR**: Verify export output format

  **Must NOT do**:
  - Do not change the learning panel table columns (UI layout change is separate)
  - Do not add import functionality
  - Do not change pagination or search logic

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 4, 5 — only needs Tasks 2, 3)
  - **Parallel Group**: Wave 2
  - **Blocks**: Task 9
  - **Blocked By**: Tasks 2, 3

  **References**:

  **Pattern References**:
  - `src/db/repository.py:export_records` — Current export method. Update SELECT query and output columns.
  - `src/ui/learning_panel.py` — Export button handler that calls repository.export_records.

  **Test References**:
  - `tests/test_db_repository.py` — Existing export tests. Extend to verify new columns in output.

  **Acceptance Criteria**:
  - [ ] Export includes pronunciation and definition in output
  - [ ] `pytest tests/test_db_repository.py -v` → all pass

  **QA Scenarios:**
  ```
  Scenario: Export includes pronunciation and definition fields
    Tool: Bash
    Steps:
      1. Run: python3 -c "
         import tempfile, os, json
         from src.db.schema import init_db
         from src.db.repository import LearningRepository
         from src.db.models import SentenceRecord, HighlightVocab, HighlightGrammar
         from datetime import datetime
         
         db_path = os.path.join(tempfile.mkdtemp(), 'test.db')
         conn = init_db(db_path)
         conn.close()
         repo = LearningRepository(db_path)
         
         # Insert a sentence with vocab highlight containing pronunciation/definition
         sentence = SentenceRecord(id=None, japanese_text='食べる', source_context='test', created_at=datetime.now().isoformat())
         vocab = HighlightVocab(id=None, sentence_id=0, surface='食べ', lemma='食べる', pos='動詞', jlpt_level=4, is_beyond_level=True, tooltip_shown=False, pronunciation='タベル', definition='to eat')
         repo.insert_sentence(sentence, [vocab], [])
         
         # Export using real API: export_records(format, ...) -> str
         export_str = repo.export_records(format='json', include_highlights=True)
         assert 'タベル' in export_str, f'pronunciation not in export: {export_str[:300]}'
         assert 'to eat' in export_str, f'definition not in export: {export_str[:300]}'
         print('EXPORT PASS')
         "
    Expected Result: Prints "EXPORT PASS" — pronunciation and definition appear in export output string
    Evidence: .sisyphus/evidence/task-6-export-fields.txt
  ```

  **Commit**: YES (groups with Task 5 commit)
  - Message: `feat(db): include pronunciation and definition in export`
  - Files: `src/db/repository.py`, `tests/test_db_repository.py`
  - Pre-commit: `pytest tests/test_db_repository.py -v`

- [ ] 7. **Update Tooltip to Display Pronunciation + Definition**

  **What to do**:
  - **RED**: Write/update tests in `tests/test_tooltip.py`:
    - Test that `show_for_vocab` with a VocabHit containing pronunciation displays it in the word label area
    - Test that `show_for_vocab` with a VocabHit containing definition displays it (new label or expanded desc)
    - Test that `show_for_vocab` with empty definition omits definition display gracefully (no blank line)
    - Test that `show_for_vocab` with empty pronunciation still works (fallback to existing behavior)
  - **GREEN**: Update `src/ui/tooltip.py`:
    - In `show_for_vocab`: display pronunciation (e.g., above or next to the lemma in `_word_label`)
    - Add definition display — either extend `_desc_label` or add a new `_def_label` below POS
    - Handle empty definition: skip rendering the definition label/text when `hit.definition == ""`
    - Handle empty pronunciation: fallback to showing just lemma without pronunciation
  - **REFACTOR**: Ensure tooltip sizing adjusts to new content, no layout overflow

  **Must NOT do**:
  - Do not change the tooltip's color scheme or font system
  - Do not change grammar tooltip behavior
  - Do not add interactive elements (buttons, links)
  - Do not change the JLPT level badge rendering

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Task 8)
  - **Parallel Group**: Wave 3
  - **Blocks**: Task 9
  - **Blocked By**: Tasks 2, 5

  **References**:

  **Pattern References**:
  - `src/ui/tooltip.py:show_for_vocab` — Current method that sets `_word_label.setText(f"{hit.lemma} ({hit.surface})")` and `_desc_label.setText(hit.pos)`. Extend to include pronunciation and definition.
  - `src/ui/tooltip.py:show_for_grammar` — Reference for how grammar tooltip includes description text — similar pattern for vocab definition.

  **API/Type References**:
  - `src/db/models.py:VocabHit` — Updated with pronunciation, definition fields (Task 2).

  **Test References**:
  - `tests/test_tooltip.py` — Existing tooltip tests. Extend with assertions on pronunciation/definition display.

  **Acceptance Criteria**:
  - [ ] Tooltip displays pronunciation for VocabHit with non-empty pronunciation
  - [ ] Tooltip displays definition for VocabHit with non-empty definition
  - [ ] Tooltip handles empty definition gracefully (no blank space)
  - [ ] `pytest tests/test_tooltip.py -v` → all pass

  **QA Scenarios:**
  ```
  Scenario: Tooltip shows pronunciation and definition
    Tool: Bash
    Steps:
      1. Run: python3 -c "
         import sys
         from unittest.mock import MagicMock, patch
         with patch('PySide6.QtWidgets.QApplication', MagicMock()):
             # Set up minimal Qt mock environment for testing label text
             from src.db.models import VocabHit
             hit = VocabHit(surface='食べ', lemma='食べる', pos='動詞', jlpt_level=4, user_level=5, start_pos=0, end_pos=2, vocab_id=1234, pronunciation='タベル', definition='to eat')
             # Verify the data is available for rendering
             assert hit.pronunciation == 'タベル', f'Wrong pronunciation: {hit.pronunciation}'
             assert hit.definition == 'to eat', f'Wrong definition: {hit.definition}'
             print('DATA PASS')
         "
      2. Run: pytest tests/test_tooltip.py -v --tb=short
      3. Assert all tests pass including new pronunciation/definition tests
    Expected Result: DATA PASS printed, all tooltip tests pass
    Evidence: .sisyphus/evidence/task-7-tooltip-full.txt

  Scenario: Tooltip with empty definition
    Tool: Bash
    Steps:
      1. Run: pytest tests/test_tooltip.py -v -k "empty" --tb=short
      2. Assert test for empty definition case passes
    Expected Result: Test passes, no crash
    Evidence: .sisyphus/evidence/task-7-tooltip-empty-def.txt
  ```

  **Commit**: YES
  - Message: `feat(ui): display pronunciation and definition in tooltip`
  - Files: `src/ui/tooltip.py`, `tests/test_tooltip.py`
  - Pre-commit: `pytest tests/test_tooltip.py -v`

- [ ] 8. **Update Sentence Detail Dialog for Pronunciation + Definition**

  **What to do**:
  - **RED**: Write/update tests:
    - Test that vocab rows in SentenceDetailDialog include pronunciation and definition
    - Test empty definition handling in detail view
  - **GREEN**: Update `src/ui/sentence_detail.py`:
    - In the vocab display section, add pronunciation text (e.g., after surface/lemma)
    - Add definition text below or next to the existing vocab row info
    - Handle empty definition: omit gracefully
  - **REFACTOR**: Ensure layout remains clean with longer text content

  **Must NOT do**:
  - Do not change grammar section display
  - Do not change the dialog's overall structure (title, close button, sentence display)
  - Do not add interactive features

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Task 7)
  - **Parallel Group**: Wave 3
  - **Blocks**: Task 9
  - **Blocked By**: Tasks 2, 5

  **References**:

  **Pattern References**:
  - `src/ui/sentence_detail.py` — Current vocab row rendering: JLPT badge + surface (bold) + lemma + POS. Add pronunciation + definition to this pattern.

  **API/Type References**:
  - `src/db/models.py:HighlightVocab` — Updated with pronunciation, definition fields (Task 2). Used by the detail dialog for rendering.

  **Test References**:
  - No existing test file for sentence_detail — create minimal tests or add to an existing UI test file.

  **Acceptance Criteria**:
  - [ ] Detail dialog displays pronunciation for vocab entries
  - [ ] Detail dialog displays definition for vocab entries
  - [ ] Empty definitions handled gracefully
  - [ ] `pytest tests/ -v` → all pass

  **QA Scenarios:**
  ```
  Scenario: Detail dialog shows pronunciation and definition
    Tool: Bash
    Steps:
      1. Run: python3 -c "
         from src.db.models import HighlightVocab
         hv = HighlightVocab(id=1, sentence_id=1, surface='食べ', lemma='食べる', pos='動詞', jlpt_level=4, is_beyond_level=True, tooltip_shown=False, vocab_id=1234, pronunciation='タベル', definition='to eat')
         assert hv.pronunciation == 'タベル', f'Wrong pronunciation: {hv.pronunciation}'
         assert hv.definition == 'to eat', f'Wrong definition: {hv.definition}'
         print('DETAIL DATA PASS')
         "
      2. Run: pytest tests/ -v -k "sentence_detail" --tb=short
      3. Assert all sentence detail tests pass including new pronunciation/definition rendering tests
    Expected Result: DETAIL DATA PASS printed, all tests pass
    Evidence: .sisyphus/evidence/task-8-detail-full.txt

  Scenario: Detail dialog with empty definition
    Tool: Bash
    Steps:
      1. Run: python3 -c "
         from src.db.models import HighlightVocab
         hv = HighlightVocab(id=1, sentence_id=1, surface='食べ', lemma='食べる', pos='動詞', jlpt_level=4, is_beyond_level=True, tooltip_shown=False, vocab_id=0, pronunciation='タベル', definition='')
         assert hv.definition == '', 'Definition should be empty'
         print('EMPTY DEF PASS')
         "
      2. Run: pytest tests/ -v -k "sentence_detail and empty" --tb=short
    Expected Result: EMPTY DEF PASS printed, test passes without crash
    Evidence: .sisyphus/evidence/task-8-detail-empty-def.txt
  ```

  **Commit**: YES
  - Message: `feat(ui): display pronunciation and definition in sentence detail dialog`
  - Files: `src/ui/sentence_detail.py`, test files
  - Pre-commit: `pytest tests/ -v`

- [ ] 9. **Remove Old JSON + Final Integration Test + Cleanup**

  **What to do**:
  - **RED**: Write integration test:
    - End-to-end test: real CSV + real fugashi tokenizer → process sentence → verify VocabHit has all fields populated → verify HighlightVocab round-trips through DB with all fields
    - Test that `data/jlpt_vocab.json` is NOT referenced anywhere in `src/`
    - Test that no import or code references the old JSON loading logic
  - **GREEN**:
    - Delete `data/jlpt_vocab.json`
    - Remove any remaining references to the old JSON file in tests or comments
    - Update any test fixtures that reference the old JSON path
  - **REFACTOR**:
    - Final lint pass: `ruff check . && ruff format --check .`
    - Final type check: `mypy src/`
    - Final test run: `pytest tests/ -v`

  **Must NOT do**:
  - Do not add new features beyond what's specified
  - Do not refactor unrelated code "while we're here"

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (final task, depends on all others)
  - **Parallel Group**: Wave 3 (sequential after 7, 8)
  - **Blocks**: F1-F4
  - **Blocked By**: Tasks 1-8

  **References**:

  **Pattern References**:
  - `data/jlpt_vocab.json` — File to delete. Currently 35 entries.
  - All test files in `tests/` — grep for `jlpt_vocab.json` references to clean up.

  **Test References**:
  - `tests/test_jlpt_vocab.py` — May still reference JSON path in old fixtures. Update to CSV.
  - `tests/test_analysis_pipeline.py` — May reference JSON. Update.

  **Acceptance Criteria**:
  - [ ] `data/jlpt_vocab.json` deleted
  - [ ] `grep -r "jlpt_vocab.json" src/ tests/` returns no matches
  - [ ] `pytest tests/ -v` → all pass, 0 failures
  - [ ] `ruff check . && ruff format --check .` → clean
  - [ ] `mypy src/` → no errors
  - [ ] Integration test validates full flow: CSV → tokenize → lookup → DB → read back

  **QA Scenarios:**
  ```
  Scenario: Full end-to-end integration
    Tool: Bash
    Steps:
      1. Run: python3 -c "
         from src.analysis.pipeline import PreprocessingPipeline
         from src.config import AppConfig
         import sqlite3, tempfile, os
         from src.db.schema import init_db
         from src.db.repository import LearningRepository
         
         # Setup
         config = AppConfig()
         pipeline = PreprocessingPipeline(config)
         
         # Process a sentence with known vocabulary
         result = pipeline.process('私は毎日食べる')
         print(f'Vocab hits: {len(result.vocab_hits)}')
         for h in result.vocab_hits:
             print(f'  {h.lemma}: level={h.jlpt_level}, pron={h.pronunciation}, def={h.definition[:40]}')
             assert h.pronunciation != '' or h.definition != '', f'At least one enriched field for {h.lemma}'
         
         # Verify DB round-trip
         db_path = os.path.join(tempfile.mkdtemp(), 'test.db')
         conn = init_db(db_path)
         conn.close()
         repo = LearningRepository(db_path)
         print('END-TO-END PASS')
         "
    Expected Result: Vocab hits found with enriched fields, prints END-TO-END PASS
    Evidence: .sisyphus/evidence/task-9-e2e.txt

  Scenario: No old JSON references remain
    Tool: Bash
    Steps:
      1. Run: grep -r "jlpt_vocab.json" src/ tests/
      2. Assert empty output
      3. Run: test ! -f data/jlpt_vocab.json && echo "DELETED"
    Expected Result: No references found, file deleted
    Evidence: .sisyphus/evidence/task-9-cleanup.txt

  Scenario: Full test suite green
    Tool: Bash
    Steps:
      1. Run: pytest tests/ -v --tb=short 2>&1 | tail -20
      2. Run: ruff check . && ruff format --check .
      3. Run: mypy src/
    Expected Result: 0 failures, 0 lint errors, 0 type errors
    Evidence: .sisyphus/evidence/task-9-final-suite.txt
  ```

  **Commit**: YES
  - Message: `chore: remove deprecated jlpt_vocab.json and update references`
  - Files: `data/jlpt_vocab.json` (delete), integration tests, any cleaned-up test files
  - Pre-commit: `pytest tests/ -v`

---

## Final Verification Wave

> 4 review agents run in PARALLEL. ALL must APPROVE. Rejection → fix → re-run.

- [ ] F1. **Plan Compliance Audit** — `oracle`
  Read the plan end-to-end. For each "Must Have": verify implementation exists (read file, run command). For each "Must NOT Have": search codebase for forbidden patterns — reject with file:line if found. Check evidence files exist in .sisyphus/evidence/. Compare deliverables against plan.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [ ] F2. **Code Quality Review** — `unspecified-high`
  Run `ruff check . && ruff format --check . && mypy src/ && pytest tests/`. Review all changed files for: `as any`/`@ts-ignore`/`type: ignore`, empty catches, print/console.log in prod, commented-out code, unused imports. Check AI slop: excessive comments, over-abstraction, generic names (data/result/item/temp).
  Output: `Lint [PASS/FAIL] | Type Check [PASS/FAIL] | Tests [N pass/N fail] | Files [N clean/N issues] | VERDICT`

- [ ] F3. **Real Manual QA** — `unspecified-high`
  Start from clean state. Execute EVERY QA scenario from EVERY task — follow exact steps, capture evidence. Test cross-task integration (CSV loads → lookup works → analysis runs → DB stores → tooltip shows all fields). Test edge cases: empty definition, unknown lemma, dash-annotated lemma. Save to `.sisyphus/evidence/final-qa/`.
  Output: `Scenarios [N/N pass] | Integration [N/N] | Edge Cases [N tested] | VERDICT`

- [ ] F4. **Scope Fidelity Check** — `deep`
  For each task: read "What to do", read actual diff (`git log`/`git diff`). Verify 1:1 — everything in spec was built (no missing), nothing beyond spec was built (no creep). Check "Must NOT do" compliance. Detect cross-task contamination: Task N touching Task M's files. Flag unaccounted changes.
  Output: `Tasks [N/N compliant] | Contamination [CLEAN/N issues] | Unaccounted [CLEAN/N files] | VERDICT`

---

## Commit Strategy

| Commit | Message | Files | Pre-commit |
|--------|---------|-------|------------|
| 1 | `feat(analysis): add VocabEntry dataclass and CSV loader` | `src/analysis/jlpt_vocab.py`, `tests/test_jlpt_vocab.py` | `pytest tests/test_jlpt_vocab.py` |
| 2 | `feat(models): add pronunciation and definition to VocabHit and HighlightVocab` | `src/db/models.py`, `tests/test_models.py` (if exists) | `pytest tests/` |
| 3 | `feat(db): add pronunciation and definition columns with migration` | `src/db/schema.py`, `src/db/repository.py`, `tests/test_db_*.py` | `pytest tests/test_db_repository.py` |
| 4 | `feat(analysis): integrate CSV loader into pipeline with dash-stripping` | `src/analysis/pipeline.py`, `src/analysis/jlpt_vocab.py`, `tests/test_analysis_pipeline.py` | `pytest tests/test_analysis_pipeline.py tests/test_jlpt_vocab.py` |
| 5 | `feat(pipeline): propagate vocabulary metadata through analysis worker` | `src/pipeline/analysis_worker.py`, `tests/test_analysis_worker.py` | `pytest tests/test_analysis_worker.py` |
| 6 | `feat(ui): display pronunciation and definition in tooltip and detail views` | `src/ui/tooltip.py`, `src/ui/sentence_detail.py`, `src/ui/learning_panel.py`, `tests/test_tooltip.py` | `pytest tests/test_tooltip.py` |
| 7 | `chore: remove deprecated jlpt_vocab.json and update references` | `data/jlpt_vocab.json` (delete), integration tests | `pytest tests/` |

---

## Success Criteria

### Verification Commands
```bash
pytest tests/ -v                    # Expected: all pass, 0 failures
ruff check . && ruff format --check . # Expected: no issues
mypy src/                           # Expected: no errors
python3 -c "
from src.analysis.jlpt_vocab import JLPTVocabLookup
lookup = JLPTVocabLookup('data/vocabulary.csv')
entry = lookup.lookup('食べる')
print(f'Level: {entry.level}, Pronunciation: {entry.pronunciation}, Definition: {entry.definition}')
assert entry is not None
assert entry.level == 4
print('SUCCESS')
"                                   # Expected: prints entry details + SUCCESS
```

### Final Checklist
- [ ] All "Must Have" items present
- [ ] All "Must NOT Have" items absent
- [ ] All tests pass (`pytest tests/`)
- [ ] Linting passes (`ruff check .`)
- [ ] Type checking passes (`mypy src/`)
- [ ] CSV lookup loads ~8,049 unique lemmas
- [ ] Old `jlpt_vocab.json` removed
- [ ] DB migration works on fresh AND existing databases
