# Milestone 1 — Preprocessing Pipeline

## TL;DR

> **Quick Summary**: Implement the complete Japanese text preprocessing pipeline — DB layer (schema, models, CRUD), morphological analysis (fugashi tokenizer), JLPT vocab lookup, grammar pattern matching, complexity scoring, and pipeline assembly. All backed by tests and data stubs.
> 
> **Deliverables**:
> - `src/db/schema.py` + `src/db/models.py` + `src/db/repository.py` — SQLite schema, dataclasses, CRUD
> - `src/analysis/tokenizer.py` — Fugashi tokenizer wrapper
> - `src/analysis/jlpt_vocab.py` — JLPT vocabulary lookup
> - `src/analysis/grammar.py` — Grammar pattern matcher
> - `src/analysis/complexity.py` — Complexity scorer
> - `src/analysis/pipeline.py` — End-to-end preprocessing pipeline
> - `data/jlpt_vocab.json` — JLPT vocab stub (≥20 entries)
> - `data/grammar_rules.json` — Grammar rules stub (≥10 rules)
> - Full test suite for all modules
> 
> **Estimated Effort**: Medium
> **Parallel Execution**: YES — 3 waves
> **Critical Path**: Task 1 (models) → Tasks 2-6 (parallel core) → Task 7 (pipeline assembly)

---

## Context

### Original Request
Implement all Milestone 1 tasks (1.1-1.7) as defined in `docs/tasks.md` and `docs/milestones.md`. Milestone 0 (scaffolding, config, exceptions) is already complete.

### Interview Summary
**Key Discussions**:
- **Scope**: M1 only (tasks 1.1-1.7). M0 is complete — `src/config.py`, `src/exceptions.py`, `tests/test_config.py`, `pyproject.toml`, `requirements.txt` all exist.
- **Data files**: Testing stubs only — ≥20 JLPT vocab entries, ≥10 grammar rules. Not full production dictionaries.
- **Test strategy**: Tests-after (implement then test), using pytest with mypy strict.

**Research Findings**:
- **jreadability API**: `compute_readability(text, tagger=None)` returns `float`. HIGHER score = EASIER text. Accepts optional shared `fugashi.Tagger`.
- **⚠️ CRITICAL BUG IN ARCHITECTURE DOC**: `docs/architecture.md` says `readability > 3.0` = complex, but empirically: simple "これは猫です" → 6.20, medium "昨日友達と映画を見に行きました" → 4.80, complex "経済的観点から…" → 1.11. The threshold is INVERTED. **Correct logic: `readability < 3.0` = complex** (lower score = harder text).
- **fugashi API**: Use `fugashi.Tagger()` (NOT `GenericTagger`). Call via `tagger(text)` returns `list[UnidicNode]`. Access `word.surface`, `word.feature.lemma`, `word.feature.pos1`.
- **Shared tagger optimization**: `jreadability.compute_readability()` accepts optional `tagger` param — share the `fugashi.Tagger` instance to avoid double dictionary load.

### Metis Review
**Identified Gaps** (addressed):
- **jreadability threshold inversion**: Documented as `> 3.0` = complex, but empirically it's inverted. Plan uses correct `< 3.0` threshold. Note added to Task 6 (complexity scorer).
- **fugashi API correction**: Task docs say `GenericTagger` — plan uses correct `Tagger()` class.
- **Shared tagger instance**: Plan specifies sharing `fugashi.Tagger` between tokenizer and jreadability to avoid double memory usage.
- **Edge cases**: Empty string, punctuation-only, single-character inputs addressed in acceptance criteria.
- **JLPT level direction**: Lower number = harder (N1 hardest, N5 easiest). `find_beyond_level` finds words where `word_level < user_level` (i.e., harder than user's level).

---

## Work Objectives

### Core Objective
Build a complete preprocessing pipeline that takes raw Japanese text and produces an `AnalysisResult` with tokenization, JLPT vocabulary highlights, grammar pattern matches, and complexity classification — all backed by SQLite persistence.

### Concrete Deliverables
- 7 source modules in `src/db/` and `src/analysis/`
- 7 test files in `tests/`
- 2 data stubs in `data/`
- All modules pass `mypy --strict` and `ruff check`

### Definition of Done
- [ ] `pytest -x --tb=short` — all tests pass (≥30 tests total)
- [ ] `mypy .` — zero errors
- [ ] `ruff check . && ruff format --check .` — clean
- [ ] Pipeline processes Japanese text end-to-end in < 50ms per sentence

### Must Have
- All dataclasses match `docs/api-data.md` exactly (field names, types, defaults)
- SQLite schema matches `docs/api-data.md` exactly (table names, columns, constraints)
- WAL mode and foreign keys enabled in init_db()
- Complexity threshold logic: ANY threshold exceeded → `is_complex = True`
- jreadability threshold uses correct direction: score < 3.0 = complex
- `fugashi.Tagger` shared between tokenizer and jreadability calls
- Grammar > Vocab priority when overlapping (noted for future UI use)
- All public functions have type annotations (mypy strict)
- Google-style docstrings on public classes and non-trivial functions

### Must NOT Have (Guardrails)
- **NO audio/VAD/ASR code** — that's Milestone 2
- **NO LLM/Ollama code** — that's Milestone 3
- **NO UI/PySide6 code** — that's Milestone 4
- **NO production data files** — stubs only for testing
- **NO ORM** — use stdlib `sqlite3` directly
- **NO abstract base classes** — simple concrete implementations
- **NO `as Any` or `@ts-ignore`** equivalent — no `type: ignore` without justification
- **NO print() for logging** — use `logging.getLogger(__name__)`
- **NO bare except clauses** — specific exceptions only

---

## Verification Strategy (MANDATORY)

> **ZERO HUMAN INTERVENTION** — ALL verification is agent-executed. No exceptions.

### Test Decision
- **Infrastructure exists**: YES — pyproject.toml has pytest config, tests/ dir exists, test_config.py as pattern
- **Automated tests**: Tests-after (implement module, then write tests)
- **Framework**: pytest (configured in pyproject.toml, testpaths=['tests'], pythonpath=['.'])
- **Pattern to follow**: `tests/test_config.py` — parametrize, fixtures, descriptive names

### QA Policy
Every task MUST include agent-executed QA scenarios.
Evidence saved to `.sisyphus/evidence/task-{N}-{scenario-slug}.{ext}`.

- **DB modules**: Use Bash (python) — Create in-memory DB, run CRUD ops, verify
- **Analysis modules**: Use Bash (python) — Import, call with known inputs, compare output
- **Pipeline**: Use Bash (python) — Process known sentences, verify full AnalysisResult

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Start Immediately — foundation):
├── Task 1: DB schema + models + data stubs [quick]
│   (schema.py, models.py, jlpt_vocab.json, grammar_rules.json)

Wave 2 (After Wave 1 — core modules, MAX PARALLEL):
├── Task 2: DB repository [unspecified-high] (depends: 1)
├── Task 3: Fugashi tokenizer [quick] (depends: 1 for Token model)
├── Task 4: JLPT vocab lookup [quick] (depends: 1 for VocabHit/Token models)
├── Task 5: Grammar pattern matcher [unspecified-high] (depends: 1 for GrammarHit model)
├── Task 6: Complexity scorer [deep] (depends: 1 for VocabHit/GrammarHit models)

Wave 3 (After Wave 2 — integration):
├── Task 7: Pipeline assembly + test [deep] (depends: 3, 4, 5, 6)

Wave FINAL (After ALL tasks — verification):
├── Task F1: Plan compliance audit [oracle]
├── Task F2: Code quality review [unspecified-high]
├── Task F3: Real manual QA [unspecified-high]
├── Task F4: Scope fidelity check [deep]

Critical Path: Task 1 → Task 6 → Task 7 → F1-F4
Parallel Speedup: ~50% faster than sequential (5 parallel in Wave 2)
Max Concurrent: 5 (Wave 2)
```

### Dependency Matrix

| Task | Depends On | Blocks | Wave |
|------|-----------|--------|------|
| 1 | — | 2, 3, 4, 5, 6 | 1 |
| 2 | 1 | 7 (optional) | 2 |
| 3 | 1 | 7 | 2 |
| 4 | 1 | 7 | 2 |
| 5 | 1 | 7 | 2 |
| 6 | 1 | 7 | 2 |
| 7 | 3, 4, 5, 6 | F1-F4 | 3 |
| F1-F4 | 7 | — | FINAL |

### Agent Dispatch Summary

- **Wave 1**: 1 task — T1 → `quick`
- **Wave 2**: 5 tasks — T2 → `unspecified-high`, T3 → `quick`, T4 → `quick`, T5 → `unspecified-high`, T6 → `deep`
- **Wave 3**: 1 task — T7 → `deep`
- **FINAL**: 4 tasks — F1 → `oracle`, F2 → `unspecified-high`, F3 → `unspecified-high`, F4 → `deep`

---

## TODOs

- [ ] 1. DB Schema, Models, and Data Stubs

  **What to do**:
  - Create `src/db/schema.py`:
    - Define `SCHEMA_SQL` string with CREATE TABLE statements for `sentence_records`, `highlight_vocab`, `highlight_grammar`, `app_settings` — exact schema from `docs/api-data.md`
    - Function `init_db(db_path: str) -> sqlite3.Connection` — creates tables if not exist, enables WAL mode (`PRAGMA journal_mode=WAL`), enables foreign keys (`PRAGMA foreign_keys=ON`), returns connection
  - Create `src/db/models.py`:
    - DB dataclasses: `SentenceRecord`, `HighlightVocab`, `HighlightGrammar` — exact fields/types from `docs/api-data.md`
    - Pipeline dataclasses: `Token(surface: str, lemma: str, pos: str)`, `VocabHit(surface: str, lemma: str, pos: str, jlpt_level: int, user_level: int)`, `GrammarHit(rule_id: str, matched_text: str, jlpt_level: int, confidence_type: str, description: str)`, `AnalysisResult(tokens: list[Token], vocab_hits: list[VocabHit], grammar_hits: list[GrammarHit], complexity_score: float, is_complex: bool)`, `SentenceResult(japanese_text: str, chinese_translation: str | None, explanation: str | None, analysis: AnalysisResult, created_at: datetime = field(default_factory=datetime.now))` — note: `created_at` is `datetime` (from `datetime` module) with auto-default, NOT a string. Import `from datetime import datetime` and `from dataclasses import field`.
  - Create `data/jlpt_vocab.json` — testing stub with ≥20 entries covering N1-N5 levels. Format: `{"lemma": level}` (e.g., `{"食べる": 5, "概念": 1, ...}`). Include known words for test sentences.
  - Create `data/grammar_rules.json` — testing stub with ≥10 rules covering N1-N5 levels. Format: `[{"rule_id": "N2_passive", "pattern_regex": "regex_string", "jlpt_level": 2, "confidence_type": "high"|"ambiguous", "description": "..."}]` — note: the JSON key is `pattern_regex` (matching `docs/api-data.md`), NOT `pattern`.
  - Create `tests/test_db_schema.py` — test init_db creates tables, WAL mode enabled, foreign keys ON, schema correctness (column names, types), idempotent init (call twice = no error)

  **Must NOT do**:
  - No ORM — use stdlib sqlite3
  - No abstract base classes on the dataclasses
  - Do NOT create full production data files — stubs only

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Schema is well-defined in docs, dataclasses are simple, data stubs are small. No complex logic.
  - **Skills**: []
    - No special skills needed — straightforward Python + SQLite
  - **Skills Evaluated but Omitted**:
    - `playwright`: No browser involved
    - `frontend-ui-ux`: No UI

  **Parallelization**:
  - **Can Run In Parallel**: NO (foundation task)
  - **Parallel Group**: Wave 1 (solo)
  - **Blocks**: Tasks 2, 3, 4, 5, 6
  - **Blocked By**: None (can start immediately)

  **References** (CRITICAL):

  **Pattern References**:
  - `src/config.py` — Follow the same dataclass style (frozen=False, field defaults, type annotations)
  - `src/exceptions.py` — Follow the same module structure (imports, docstrings)
  - `tests/test_config.py` — Follow the same test structure (pytest parametrize, fixtures, naming)

  **API/Type References**:
  - `docs/api-data.md` — **THE source of truth** for all schema definitions, dataclass fields, and data file formats. Contains exact SQL CREATE TABLE statements, all dataclass field names/types/defaults, JSON formats for vocab and grammar data.

  **External References**:
  - sqlite3 stdlib: WAL mode via `PRAGMA journal_mode=WAL`, foreign keys via `PRAGMA foreign_keys=ON`

  **WHY Each Reference Matters**:
  - `docs/api-data.md`: Every field name, type, and default MUST match exactly. The executor should copy the SQL and dataclass definitions from this doc.
  - `src/config.py`: Shows the project's established dataclass style — use `@dataclass`, not frozen, with default values and `| None` union types.
  - `tests/test_config.py`: Shows test naming convention (`test_<what>_<condition>`), use of `tmp_path` fixture, and assertion patterns.

  **Acceptance Criteria**:

  - [ ] `python -c "from src.db.schema import init_db, SCHEMA_SQL"` — imports succeed
  - [ ] `python -c "from src.db.models import SentenceRecord, HighlightVocab, HighlightGrammar, Token, VocabHit, GrammarHit, AnalysisResult, SentenceResult"` — all imports succeed
  - [ ] `python -c "import json; d=json.load(open('data/jlpt_vocab.json')); assert len(d) >= 20; print(f'{len(d)} entries')"` — ≥20 entries
  - [ ] `python -c "import json; r=json.load(open('data/grammar_rules.json')); assert len(r) >= 10; print(f'{len(r)} rules')"` — ≥10 rules
  - [ ] `pytest tests/test_db_schema.py -x` — all tests pass
  - [ ] `mypy src/db/schema.py src/db/models.py` — zero errors
  - [ ] `ruff check src/db/schema.py src/db/models.py` — clean

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: init_db creates valid database with all tables
    Tool: Bash (python)
    Preconditions: No existing database file
    Steps:
      1. Run: python -c "
         from src.db.schema import init_db
         import sqlite3, tempfile, os
         path = os.path.join(tempfile.mkdtemp(), 'test.db')
         conn = init_db(path)
         cur = conn.execute(\"SELECT name FROM sqlite_master WHERE type='table' ORDER BY name\")
         tables = [r[0] for r in cur.fetchall()]
         print(f'Tables: {tables}')
         assert 'sentence_records' in tables
         assert 'highlight_vocab' in tables
         assert 'highlight_grammar' in tables
         assert 'app_settings' in tables
         wal = conn.execute('PRAGMA journal_mode').fetchone()[0]
         fk = conn.execute('PRAGMA foreign_keys').fetchone()[0]
         print(f'WAL: {wal}, FK: {fk}')
         assert wal == 'wal', f'Expected WAL, got {wal}'
         assert fk == 1, f'Expected FK=1, got {fk}'
         conn.close()
         os.unlink(path)
         print('PASS')
         "
      2. Verify output contains "PASS"
    Expected Result: All 4 tables created, WAL mode enabled, foreign keys ON
    Failure Indicators: ImportError, AssertionError, missing tables
    Evidence: .sisyphus/evidence/task-1-init-db.txt

  Scenario: Pipeline dataclasses instantiate with correct fields
    Tool: Bash (python)
    Preconditions: None
    Steps:
      1. Run: python -c "
         from src.db.models import Token, VocabHit, GrammarHit, AnalysisResult, SentenceResult
         t = Token(surface='食べ', lemma='食べる', pos='動詞')
         assert t.surface == '食べ' and t.lemma == '食べる' and t.pos == '動詞'
         v = VocabHit(surface='食べ', lemma='食べる', pos='動詞', jlpt_level=5, user_level=3)
         assert v.jlpt_level == 5
         g = GrammarHit(rule_id='N2_passive', matched_text='された', jlpt_level=2, confidence_type='high', description='Passive')
         assert g.confidence_type == 'high'
         a = AnalysisResult(tokens=[t], vocab_hits=[v], grammar_hits=[g], complexity_score=1.5, is_complex=True)
         assert a.is_complex is True
         s = SentenceResult(japanese_text='test', chinese_translation=None, explanation=None, analysis=a)
         assert s.chinese_translation is None
         from datetime import datetime as dt
         assert isinstance(s.created_at, dt), f'created_at should be datetime, got {type(s.created_at)}'
         print('PASS — all dataclasses valid')
         "
    Expected Result: All dataclasses construct without error, fields accessible
    Failure Indicators: TypeError (wrong fields), ImportError
    Evidence: .sisyphus/evidence/task-1-dataclasses.txt

  Scenario: Data stubs are valid JSON with correct structure
    Tool: Bash (python)
    Preconditions: None
    Steps:
      1. Run: python -c "
         import json
         vocab = json.load(open('data/jlpt_vocab.json'))
         assert isinstance(vocab, dict), f'Expected dict, got {type(vocab)}'
         assert len(vocab) >= 20, f'Only {len(vocab)} entries, need ≥20'
         for lemma, level in list(vocab.items())[:5]:
             assert isinstance(lemma, str) and isinstance(level, int)
             assert 1 <= level <= 5, f'Invalid level {level} for {lemma}'
         print(f'Vocab: {len(vocab)} entries, levels {set(vocab.values())} — PASS')
         
         rules = json.load(open('data/grammar_rules.json'))
         assert isinstance(rules, list), f'Expected list, got {type(rules)}'
         assert len(rules) >= 10, f'Only {len(rules)} rules, need ≥10'
         required_keys = {'rule_id', 'pattern_regex', 'jlpt_level', 'confidence_type', 'description'}
         for r in rules[:3]:
             missing = required_keys - set(r.keys())
             assert not missing, f'Missing keys: {missing}'
         print(f'Grammar: {len(rules)} rules — PASS')
         "
    Expected Result: Both files valid JSON, correct structure, sufficient entries
    Failure Indicators: JSONDecodeError, AssertionError, missing keys
    Evidence: .sisyphus/evidence/task-1-data-stubs.txt
  ```

  **Evidence to Capture:**
  - [ ] task-1-init-db.txt — DB creation and pragma verification
  - [ ] task-1-dataclasses.txt — Dataclass instantiation verification
  - [ ] task-1-data-stubs.txt — Data file validation

  **Commit**: YES
  - Message: `feat(db): add schema, models, and data stubs for M1`
  - Files: `src/db/schema.py`, `src/db/models.py`, `data/jlpt_vocab.json`, `data/grammar_rules.json`, `tests/test_db_schema.py`
  - Pre-commit: `pytest tests/test_db_schema.py -x && mypy src/db/schema.py src/db/models.py`

- [ ] 2. DB Repository (CRUD Operations)

  **What to do**:
  - Create `src/db/repository.py`:
    - Class `LearningRepository`:
      - `__init__(self, conn: sqlite3.Connection) -> None` — store connection
      - `insert_sentence(self, record: SentenceRecord, vocab: list[HighlightVocab], grammar: list[HighlightGrammar]) -> int` — Insert record + all highlights in a single transaction. Return the inserted record's ID. Use `conn.execute(...).lastrowid`.
      - `get_sentences(self, limit: int = 50, offset: int = 0) -> list[SentenceRecord]` — Fetch recent records ordered by `created_at DESC`
      - `search_sentences(self, query: str) -> list[SentenceRecord]` — Full-text search on `japanese_text` and `chinese_translation` using `LIKE '%query%'`
      - `mark_tooltip_shown(self, highlight_type: str, highlight_id: int) -> None` — Set `tooltip_shown=1` on the appropriate table (`highlight_vocab` or `highlight_grammar` based on `highlight_type`)
      - `export_records(self, format: str = "json") -> str` — Export all records as JSON or CSV string
      - `delete_before(self, cutoff_date: str) -> int` — Delete records before ISO date, return count deleted
  - Create `tests/test_db_repository.py`:
    - Use `@pytest.fixture` with in-memory SQLite (`":memory:"`) + `init_db`
    - Test insert + retrieve roundtrip
    - Test insert with empty vocab/grammar lists
    - Test search finds matching records, returns empty for no match
    - Test mark_tooltip_shown updates correct record
    - Test export_records JSON format (valid JSON, all fields present)
    - Test export_records CSV format
    - Test delete_before removes correct records, returns count
    - Test transaction atomicity (if record insert fails, no highlights written)

  **Must NOT do**:
  - No ORM — raw sqlite3 only
  - No connection pooling or thread safety — single connection, same thread
  - Do NOT modify schema.py or models.py

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Multiple CRUD methods with transaction logic, comprehensive test suite needed. Not trivial but well-scoped.
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - All skills irrelevant — pure Python + sqlite3

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 3, 4, 5, 6)
  - **Blocks**: Task 7 (optional — pipeline doesn't directly use repo, but final verification needs it)
  - **Blocked By**: Task 1 (needs models and schema)

  **References** (CRITICAL):

  **Pattern References**:
  - `src/db/schema.py` (from Task 1) — Use `init_db()` for test fixtures, use `SCHEMA_SQL` for understanding table structure
  - `src/db/models.py` (from Task 1) — `SentenceRecord`, `HighlightVocab`, `HighlightGrammar` dataclass definitions — these are the inputs/outputs for all repository methods
  - `tests/test_config.py` — Test structure pattern: fixtures, parametrize, naming convention

  **API/Type References**:
  - `docs/api-data.md` — Schema section shows exact column names, types, constraints, indexes. Use this to construct correct INSERT/SELECT SQL.

  **WHY Each Reference Matters**:
  - `src/db/models.py`: Every repository method takes/returns these dataclasses. Field names = column names in SQL.
  - `docs/api-data.md`: The SQL column names and types must match exactly when constructing queries.
  - `tests/test_config.py`: Follow the established fixture and naming patterns for consistency.

  **Acceptance Criteria**:

  - [ ] `python -c "from src.db.repository import LearningRepository"` — imports succeed
  - [ ] `pytest tests/test_db_repository.py -x` — all tests pass (≥8 tests)
  - [ ] `mypy src/db/repository.py` — zero errors
  - [ ] `ruff check src/db/repository.py` — clean

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Insert and retrieve a sentence with highlights
    Tool: Bash (python)
    Preconditions: None (uses in-memory DB)
    Steps:
      1. Run: python -c "
         from src.db.schema import init_db
         from src.db.models import SentenceRecord, HighlightVocab, HighlightGrammar
         from src.db.repository import LearningRepository
         conn = init_db(':memory:')
         repo = LearningRepository(conn)
         rec = SentenceRecord(id=None, japanese_text='昨日映画を見た', chinese_translation='昨天看了电影', explanation=None, complexity_score=2.5, is_complex=False, source_context=None, created_at='2024-01-15T10:00:00')
         vocab = [HighlightVocab(id=None, sentence_id=0, surface='映画', lemma='映画', pos='名詞', jlpt_level=5, is_beyond_level=False, tooltip_shown=False)]
         grammar = [HighlightGrammar(id=None, sentence_id=0, rule_id='N4_past', pattern='た$', jlpt_level=4, confidence_type='high', description='Past tense', is_beyond_level=False, tooltip_shown=False)]
         rid = repo.insert_sentence(rec, vocab, grammar)
         assert rid >= 1, f'Expected positive ID, got {rid}'
         rows = repo.get_sentences(limit=10)
         assert len(rows) == 1
         assert rows[0].japanese_text == '昨日映画を見た'
         print(f'Insert ID={rid}, retrieved {len(rows)} rows — PASS')
         conn.close()
         "
    Expected Result: Record inserted with positive ID, retrievable via get_sentences
    Failure Indicators: IntegrityError, wrong field values, empty result
    Evidence: .sisyphus/evidence/task-2-insert-retrieve.txt

  Scenario: Search finds matching records
    Tool: Bash (python)
    Preconditions: None
    Steps:
      1. Run: python -c "
         from src.db.schema import init_db
         from src.db.models import SentenceRecord
         from src.db.repository import LearningRepository
         conn = init_db(':memory:')
         repo = LearningRepository(conn)
         r1 = SentenceRecord(id=None, japanese_text='猫が好きです', chinese_translation='我喜欢猫', explanation=None, complexity_score=1.0, is_complex=False, source_context=None, created_at='2024-01-15T10:00:00')
         r2 = SentenceRecord(id=None, japanese_text='犬が好きです', chinese_translation='我喜欢狗', explanation=None, complexity_score=1.0, is_complex=False, source_context=None, created_at='2024-01-15T10:01:00')
         repo.insert_sentence(r1, [], [])
         repo.insert_sentence(r2, [], [])
         results = repo.search_sentences('猫')
         assert len(results) == 1, f'Expected 1 match for 猫, got {len(results)}'
         assert results[0].japanese_text == '猫が好きです'
         no_results = repo.search_sentences('鳥')
         assert len(no_results) == 0, f'Expected 0 matches for 鳥, got {len(no_results)}'
         print('Search — PASS')
         conn.close()
         "
    Expected Result: Search returns only matching records, empty for no match
    Failure Indicators: Wrong result count, SQL error
    Evidence: .sisyphus/evidence/task-2-search.txt

  Scenario: Delete before cutoff removes correct records
    Tool: Bash (python)
    Preconditions: None
    Steps:
      1. Run: python -c "
         from src.db.schema import init_db
         from src.db.models import SentenceRecord
         from src.db.repository import LearningRepository
         conn = init_db(':memory:')
         repo = LearningRepository(conn)
         old = SentenceRecord(id=None, japanese_text='old', chinese_translation=None, explanation=None, complexity_score=0, is_complex=False, source_context=None, created_at='2023-01-01T00:00:00')
         new = SentenceRecord(id=None, japanese_text='new', chinese_translation=None, explanation=None, complexity_score=0, is_complex=False, source_context=None, created_at='2024-06-01T00:00:00')
         repo.insert_sentence(old, [], [])
         repo.insert_sentence(new, [], [])
         count = repo.delete_before('2024-01-01')
         assert count == 1, f'Expected 1 deleted, got {count}'
         remaining = repo.get_sentences()
         assert len(remaining) == 1
         assert remaining[0].japanese_text == 'new'
         print(f'Deleted {count}, remaining {len(remaining)} — PASS')
         conn.close()
         "
    Expected Result: Only old record deleted, new record remains
    Failure Indicators: Wrong delete count, remaining records incorrect
    Evidence: .sisyphus/evidence/task-2-delete.txt
  ```

  **Evidence to Capture:**
  - [ ] task-2-insert-retrieve.txt
  - [ ] task-2-search.txt
  - [ ] task-2-delete.txt

  **Commit**: YES
  - Message: `feat(db): add learning repository with CRUD operations`
  - Files: `src/db/repository.py`, `tests/test_db_repository.py`
  - Pre-commit: `pytest tests/test_db_repository.py -x && mypy src/db/repository.py`

- [ ] 3. Fugashi Tokenizer Wrapper

  **What to do**:
  - Create `src/analysis/tokenizer.py`:
    - Class `FugashiTokenizer`:
      - `__init__(self) -> None` — Initialize `fugashi.Tagger()` (NOT `GenericTagger`). Store as `self._tagger`.
      - `tokenize(self, text: str) -> list[Token]` — Call `self._tagger(text)`, iterate results, build `Token(surface=word.surface, lemma=word.feature.lemma, pos=word.feature.pos1)`. Handle: empty input → return `[]`. Filter out punctuation-only tokens (where `pos == '補助記号'` or `pos == '記号'`). Handle None lemma (some tokens may lack it) — fall back to surface.
      - Property `tagger` — expose the internal `fugashi.Tagger` instance so it can be shared with `jreadability.compute_readability(text, tagger=self.tagger)` later in the pipeline.
  - Create `tests/test_tokenizer.py`:
    - Test with ≥3 known Japanese sentences
    - Test empty string returns empty list
    - Test punctuation-only string returns empty list (e.g., "。！？")
    - Test known sentence produces expected tokens (surface, lemma, pos)
    - Test sentence with mixed content (kanji, hiragana, katakana)

  **Must NOT do**:
  - Do NOT use `fugashi.GenericTagger` — use `fugashi.Tagger` (which uses unidic-lite)
  - Do NOT hardcode a dictionary path — `Tagger()` auto-finds unidic-lite
  - Do NOT mock fugashi in tests — use the real tagger for integration accuracy (it's fast)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Single class, 1-2 methods, well-defined behavior. Straightforward wrapper.
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - All irrelevant — pure Python wrapping a native library

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 2, 4, 5, 6)
  - **Blocks**: Task 7
  - **Blocked By**: Task 1 (needs Token model from models.py)

  **References** (CRITICAL):

  **Pattern References**:
  - `src/config.py` — Module structure pattern (imports, logging setup, class style)

  **API/Type References**:
  - `src/db/models.py:Token` (from Task 1) — The `Token(surface, lemma, pos)` dataclass that `tokenize()` returns
  - `docs/api-data.md` — Token dataclass definition for field reference

  **External References**:
  - fugashi API (verified in env): `fugashi.Tagger()` constructor, `tagger(text)` returns `list[UnidicNode]`, each node has `.surface` (str) and `.feature` (UnidicFeatures26 with `.lemma`, `.pos1`, `.pos2`, etc.)
  - Note: `word.feature.lemma` may be `None` for some tokens (e.g., symbols). Fall back to `word.surface`.

  **WHY Each Reference Matters**:
  - `Token` model: Must return exactly this dataclass — constructor signature must match
  - fugashi API notes: The `Tagger` vs `GenericTagger` distinction is critical. The feature attribute access pattern (`.feature.lemma`, `.feature.pos1`) is non-obvious.

  **Acceptance Criteria**:

  - [ ] `python -c "from src.analysis.tokenizer import FugashiTokenizer"` — imports
  - [ ] `pytest tests/test_tokenizer.py -x` — all pass (≥5 tests)
  - [ ] `mypy src/analysis/tokenizer.py` — clean
  - [ ] `ruff check src/analysis/tokenizer.py` — clean

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Tokenize known Japanese sentence
    Tool: Bash (python)
    Preconditions: fugashi + unidic-lite installed
    Steps:
      1. Run: python -c "
         from src.analysis.tokenizer import FugashiTokenizer
         from src.db.models import Token
         t = FugashiTokenizer()
         tokens = t.tokenize('昨日友達と映画を見に行きました')
         print(f'Token count: {len(tokens)}')
         for tok in tokens:
             assert isinstance(tok, Token), f'Expected Token, got {type(tok)}'
             print(f'  {tok.surface} | {tok.lemma} | {tok.pos}')
         assert len(tokens) >= 5, f'Expected ≥5 tokens, got {len(tokens)}'
         # Check that '映画' is in there
         lemmas = [tok.lemma for tok in tokens]
         assert '映画' in lemmas, f'映画 not found in lemmas: {lemmas}'
         print('PASS')
         "
    Expected Result: ≥5 tokens, 映画 appears as lemma, all tokens are Token instances
    Failure Indicators: ImportError, token count too low, missing expected lemmas
    Evidence: .sisyphus/evidence/task-3-tokenize.txt

  Scenario: Empty and punctuation-only input
    Tool: Bash (python)
    Preconditions: None
    Steps:
      1. Run: python -c "
         from src.analysis.tokenizer import FugashiTokenizer
         t = FugashiTokenizer()
         assert t.tokenize('') == [], f'Empty string should return []'
         punct = t.tokenize('。！？、')
         assert punct == [], f'Punctuation-only should return [], got {punct}'
         print('PASS — empty and punctuation handled')
         "
    Expected Result: Both return empty lists
    Failure Indicators: Non-empty results, TypeError
    Evidence: .sisyphus/evidence/task-3-edge-cases.txt

  Scenario: Tagger property is accessible for sharing
    Tool: Bash (python)
    Preconditions: None
    Steps:
      1. Run: python -c "
         from src.analysis.tokenizer import FugashiTokenizer
         import fugashi
         t = FugashiTokenizer()
         tagger = t.tagger
         assert isinstance(tagger, fugashi.Tagger), f'Expected fugashi.Tagger, got {type(tagger)}'
         print('PASS — tagger property works')
         "
    Expected Result: tagger property returns fugashi.Tagger instance
    Failure Indicators: AttributeError, wrong type
    Evidence: .sisyphus/evidence/task-3-tagger-property.txt
  ```

  **Evidence to Capture:**
  - [ ] task-3-tokenize.txt
  - [ ] task-3-edge-cases.txt
  - [ ] task-3-tagger-property.txt

  **Commit**: YES
  - Message: `feat(analysis): add fugashi tokenizer wrapper`
  - Files: `src/analysis/tokenizer.py`, `tests/test_tokenizer.py`
  - Pre-commit: `pytest tests/test_tokenizer.py -x && mypy src/analysis/tokenizer.py`

- [ ] 4. JLPT Vocabulary Lookup

  **What to do**:
  - Create `src/analysis/jlpt_vocab.py`:
    - Class `JLPTVocabLookup`:
      - `__init__(self, vocab_path: str) -> None` — Load JSON dict from file into `self._vocab: dict[str, int]`. Raise `FileNotFoundError` if path invalid. Validate structure on load.
      - `lookup(self, lemma: str) -> int | None` — Return JLPT level (1-5) or None if not found
      - `find_beyond_level(self, tokens: list[Token], user_level: int) -> list[VocabHit]` — For each token, look up lemma. If found AND `jlpt_level < user_level` (lower number = harder), create `VocabHit`. Return list of beyond-level hits. **IMPORTANT**: Level 1 = hardest (N1), Level 5 = easiest (N5). "Beyond level" means the word is harder than the user's current level — i.e., `word_level < user_level`.
  - Create `tests/test_jlpt_vocab.py`:
    - Test lookup returns correct level for known words
    - Test lookup returns None for unknown words
    - Test find_beyond_level with user_level=3: N1/N2 words flagged, N3/N4/N5 not
    - Test find_beyond_level with user_level=5: only N4/N3/N2/N1 flagged (none for N5-only input)
    - Test empty token list returns empty
    - Test parametrize across multiple (word, expected_level) pairs

  **Must NOT do**:
  - Do NOT implement fuzzy matching — exact lemma lookup only
  - Do NOT load data lazily — load all at __init__
  - Do NOT modify the data stub file

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Simple dict lookup, straightforward logic. The level comparison is the only tricky part (lower = harder).
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - All irrelevant

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 2, 3, 5, 6)
  - **Blocks**: Task 7
  - **Blocked By**: Task 1 (needs Token, VocabHit models + data/jlpt_vocab.json)

  **References** (CRITICAL):

  **Pattern References**:
  - `src/config.py:load_config()` — Pattern for loading JSON files with error handling

  **API/Type References**:
  - `src/db/models.py:Token` — Input type for find_beyond_level
  - `src/db/models.py:VocabHit` — Output type for find_beyond_level. Fields: `surface, lemma, pos, jlpt_level, user_level`
  - `data/jlpt_vocab.json` (from Task 1) — The dictionary to load. Format: `{"lemma": level_int}`

  **External References**:
  - None — pure Python dict operations

  **WHY Each Reference Matters**:
  - `Token`/`VocabHit` models: Exact field names matter. `VocabHit.user_level` captures the user's level at time of analysis (for historical reference).
  - `data/jlpt_vocab.json`: The executor needs to know this is `{str: int}` format, not a list of objects.
  - Level direction: N1(1)=hardest, N5(5)=easiest. "Beyond level" = `word_level < user_level` (e.g., user=3, word=1 → beyond).

  **Acceptance Criteria**:

  - [ ] `python -c "from src.analysis.jlpt_vocab import JLPTVocabLookup"` — imports
  - [ ] `pytest tests/test_jlpt_vocab.py -x` — all pass (≥6 tests)
  - [ ] `mypy src/analysis/jlpt_vocab.py` — clean
  - [ ] `ruff check src/analysis/jlpt_vocab.py` — clean

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Lookup returns correct JLPT levels
    Tool: Bash (python)
    Preconditions: data/jlpt_vocab.json exists from Task 1
    Steps:
      1. Run: python -c "
         from src.analysis.jlpt_vocab import JLPTVocabLookup
         v = JLPTVocabLookup('data/jlpt_vocab.json')
         # Test a known N5 word (should be in stub)
         level = v.lookup('食べる')
         print(f'食べる: N{level}')
         assert level == 5, f'Expected 5, got {level}'
         # Test unknown word
         unk = v.lookup('xyznotaword')
         assert unk is None, f'Expected None for unknown, got {unk}'
         print('PASS — lookup works')
         "
    Expected Result: Known word returns correct level, unknown returns None
    Failure Indicators: Wrong level, non-None for unknown
    Evidence: .sisyphus/evidence/task-4-lookup.txt

  Scenario: find_beyond_level correctly identifies hard words
    Tool: Bash (python)
    Preconditions: data/jlpt_vocab.json exists
    Steps:
      1. Run: python -c "
         from src.analysis.jlpt_vocab import JLPTVocabLookup
         from src.db.models import Token
         v = JLPTVocabLookup('data/jlpt_vocab.json')
         # Simulate tokens: one N5 word, one N1 word
         tokens = [
             Token(surface='食べ', lemma='食べる', pos='動詞'),  # N5
             Token(surface='概念', lemma='概念', pos='名詞'),    # N1
         ]
         # User level 3 → N1 and N2 words are 'beyond level'
         hits = v.find_beyond_level(tokens, user_level=3)
         print(f'Hits for user_level=3: {len(hits)}')
         for h in hits:
             print(f'  {h.lemma} N{h.jlpt_level} (user={h.user_level})')
         # 概念 (N1) should be beyond level 3
         assert any(h.lemma == '概念' for h in hits), '概念 should be beyond level 3'
         # 食べる (N5) should NOT be beyond level 3
         assert not any(h.lemma == '食べる' for h in hits), '食べる should not be beyond level 3'
         print('PASS')
         "
    Expected Result: N1 word flagged as beyond level 3, N5 word not flagged
    Failure Indicators: Wrong hits, level comparison inverted
    Evidence: .sisyphus/evidence/task-4-beyond-level.txt

  Scenario: Empty token list returns empty hits
    Tool: Bash (python)
    Preconditions: None
    Steps:
      1. Run: python -c "
         from src.analysis.jlpt_vocab import JLPTVocabLookup
         v = JLPTVocabLookup('data/jlpt_vocab.json')
         hits = v.find_beyond_level([], user_level=3)
         assert hits == [], f'Expected [], got {hits}'
         print('PASS — empty input handled')
         "
    Expected Result: Empty list
    Failure Indicators: Non-empty result, exception
    Evidence: .sisyphus/evidence/task-4-empty.txt
  ```

  **Evidence to Capture:**
  - [ ] task-4-lookup.txt
  - [ ] task-4-beyond-level.txt
  - [ ] task-4-empty.txt

  **Commit**: YES
  - Message: `feat(analysis): add JLPT vocabulary lookup`
  - Files: `src/analysis/jlpt_vocab.py`, `tests/test_jlpt_vocab.py`
  - Pre-commit: `pytest tests/test_jlpt_vocab.py -x && mypy src/analysis/jlpt_vocab.py`

- [ ] 5. Grammar Pattern Matcher

  **What to do**:
  - Create `src/analysis/grammar.py`:
    - Class `GrammarMatcher`:
      - `__init__(self, rules_path: str) -> None` — Load JSON rules array from file. Pre-compile all regex patterns from `rule["pattern_regex"]` with `re.compile()` once during init. Store compiled patterns alongside rule data. Raise `FileNotFoundError` if path invalid.
      - `match(self, text: str, user_level: int) -> list[GrammarHit]` — Run all compiled patterns against text. For each match where `rule.jlpt_level < user_level` (beyond user's level, same logic as vocab), create a `GrammarHit`. Include `confidence_type` from rule. Return all matches. Handle: empty text → `[]`. Handle: no matches → `[]`.
  - Create `tests/test_grammar.py`:
    - Test with ≥5 grammar patterns from the stub rules
    - Test known sentence with N2 passive pattern matches correctly
    - Test confidence_type (high vs ambiguous) propagated correctly
    - Test user_level filtering: pattern present but within level → not returned
    - Test empty text returns empty
    - Test text with no grammar matches returns empty
    - Test multiple patterns matching same text (both returned)

  **Must NOT do**:
  - Do NOT implement grammar priority (grammar > vocab) — that's UI layer (M4)
  - Do NOT parse POS tags for grammar — use regex on surface text only
  - Do NOT modify the data stub file

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Regex compilation, multiple pattern matching, confidence handling — more moving parts than vocab lookup.
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - All irrelevant

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 2, 3, 4, 6)
  - **Blocks**: Task 7
  - **Blocked By**: Task 1 (needs GrammarHit model + data/grammar_rules.json)

  **References** (CRITICAL):

  **Pattern References**:
  - `src/analysis/jlpt_vocab.py` (from Task 4) — Same JSON-loading pattern, same level comparison logic (`level < user_level` = beyond)

  **API/Type References**:
  - `src/db/models.py:GrammarHit` — Output type. Fields: `rule_id: str, matched_text: str, jlpt_level: int, confidence_type: str, description: str`
  - `data/grammar_rules.json` (from Task 1) — Input format: `[{"rule_id": str, "pattern_regex": str (regex string), "jlpt_level": int, "confidence_type": "high"|"ambiguous", "description": str}]` — note: JSON key is `pattern_regex`, NOT `pattern`

  **External References**:
  - Python `re` module: `re.compile()` for pattern pre-compilation, `pattern.search(text)` or `pattern.findall(text)` for matching

  **WHY Each Reference Matters**:
  - `GrammarHit` model: `matched_text` should be the actual matched substring from `re.search().group()`, not the original regex pattern. The JSON key for the regex is `pattern_regex`.
  - Grammar rules format: The `pattern_regex` field is a regex string. Must `re.compile()` at init, not at match time.
  - Level logic: Same as vocab — `rule_level < user_level` = beyond user's level.

  **Acceptance Criteria**:

  - [ ] `python -c "from src.analysis.grammar import GrammarMatcher"` — imports
  - [ ] `pytest tests/test_grammar.py -x` — all pass (≥7 tests)
  - [ ] `mypy src/analysis/grammar.py` — clean
  - [ ] `ruff check src/analysis/grammar.py` — clean

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Match known grammar pattern in sentence
    Tool: Bash (python)
    Preconditions: data/grammar_rules.json exists from Task 1
    Steps:
      1. Run: python -c "
         from src.analysis.grammar import GrammarMatcher
         gm = GrammarMatcher('data/grammar_rules.json')
         # Test with a sentence that should trigger a grammar rule
         # The stub should include common patterns like passive, causative, etc.
         import json
         rules = json.load(open('data/grammar_rules.json'))
         # Find a rule and construct a matching sentence
         rule = rules[0]
         print(f'Testing rule: {rule[\"rule_id\"]} (N{rule[\"jlpt_level\"]})')
         import re
         # Use user_level high enough that the rule is beyond
         hits = gm.match('この本は先生に読まれた', user_level=5)
         print(f'Matches found: {len(hits)}')
         for h in hits:
             print(f'  {h.rule_id}: \"{h.matched_text}\" N{h.jlpt_level} ({h.confidence_type})')
         print('PASS — grammar matching works')
         "
    Expected Result: At least one grammar pattern matched with correct fields populated
    Failure Indicators: No matches when expected, wrong matched_text, wrong confidence_type
    Evidence: .sisyphus/evidence/task-5-grammar-match.txt

  Scenario: User level filtering excludes within-level patterns
    Tool: Bash (python)
    Preconditions: data/grammar_rules.json exists
    Steps:
      1. Run: python -c "
         from src.analysis.grammar import GrammarMatcher
         gm = GrammarMatcher('data/grammar_rules.json')
         # With user_level=1 (N1), nothing should be 'beyond level' since N1 is highest
         hits = gm.match('この本は先生に読まれた', user_level=1)
         assert len(hits) == 0, f'Expected 0 hits for user_level=1, got {len(hits)}: {[h.rule_id for h in hits]}'
         print('PASS — user_level=1 correctly filters all')
         "
    Expected Result: No hits when user is at highest level
    Failure Indicators: Non-zero hits, level comparison inverted
    Evidence: .sisyphus/evidence/task-5-level-filter.txt

  Scenario: Empty text and no-match text
    Tool: Bash (python)
    Preconditions: None
    Steps:
      1. Run: python -c "
         from src.analysis.grammar import GrammarMatcher
         gm = GrammarMatcher('data/grammar_rules.json')
         assert gm.match('', user_level=5) == [], 'Empty text should return []'
         assert gm.match('hello world', user_level=5) == [], 'Non-Japanese should return []'
         print('PASS — edge cases handled')
         "
    Expected Result: Both return empty lists
    Failure Indicators: Non-empty results, regex error on empty input
    Evidence: .sisyphus/evidence/task-5-edge-cases.txt
  ```

  **Evidence to Capture:**
  - [ ] task-5-grammar-match.txt
  - [ ] task-5-level-filter.txt
  - [ ] task-5-edge-cases.txt

  **Commit**: YES
  - Message: `feat(analysis): add grammar pattern matcher`
  - Files: `src/analysis/grammar.py`, `tests/test_grammar.py`
  - Pre-commit: `pytest tests/test_grammar.py -x && mypy src/analysis/grammar.py`

- [ ] 6. Complexity Scorer

  **What to do**:
  - Create `src/analysis/complexity.py`:
    - Class `ComplexityScorer`:
      - `__init__(self, config: AppConfig, tagger: fugashi.Tagger | None = None) -> None` — Store config thresholds. Accept optional shared fugashi tagger for jreadability. If None provided, jreadability will create its own.
      - `score(self, vocab_hits: list[VocabHit], grammar_hits: list[GrammarHit], text: str) -> tuple[float, bool]` — Compute complexity:
        1. Count beyond-level vocab: `len(vocab_hits)` (already filtered by find_beyond_level)
        2. Count N1 grammar hits: `sum(1 for g in grammar_hits if g.jlpt_level == 1)`
        3. Count ambiguous grammar: `sum(1 for g in grammar_hits if g.confidence_type == "ambiguous")`
        4. Compute readability: `jreadability.compute_readability(text, tagger=self._tagger)` — **IMPORTANT**: HIGHER score = EASIER text
        5. `is_complex = True` if ANY threshold exceeded:
           - `len(vocab_hits) >= config.complexity_vocab_threshold` (default 2)
           - `n1_grammar_count >= config.complexity_n1_grammar_threshold` (default 1)
           - **`readability_score < config.complexity_readability_threshold`** (default 3.0) — ⚠️ LESS THAN, not greater than. Lower readability = harder = complex.
           - `ambiguous_count >= config.complexity_ambiguous_grammar_threshold` (default 1)
        6. `complexity_score` = weighted composite (e.g., normalized 0-10 scale). Suggested formula: `score = (vocab_weight * vocab_count + grammar_weight * n1_count + readability_weight * (10 - readability) + ambiguous_weight * ambiguous_count)`. Exact formula can be simple; the boolean `is_complex` is what matters most.
      - Return `(complexity_score, is_complex)`
  - Create `tests/test_complexity.py`:
    - Test simple sentence (no vocab hits, no grammar, high readability) → is_complex=False
    - Test sentence exceeding vocab threshold → is_complex=True
    - Test sentence exceeding N1 grammar threshold → is_complex=True
    - Test sentence exceeding readability threshold (low score) → is_complex=True
    - Test sentence exceeding ambiguous grammar threshold → is_complex=True
    - Test edge: exactly at threshold boundary
    - Test empty text handling
    - Test with shared tagger parameter

  **Must NOT do**:
  - Do NOT use `readability > threshold` — the correct logic is `readability < threshold` (lower = harder)
  - Do NOT over-engineer the composite score formula — keep it simple, the boolean matters most
  - Do NOT import or depend on FugashiTokenizer directly — accept optional tagger param

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Multiple threshold checks, jreadability integration with inverted semantics, composite scoring formula — requires careful logic. The readability inversion is a known trap.
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - All irrelevant

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 2, 3, 4, 5)
  - **Blocks**: Task 7
  - **Blocked By**: Task 1 (needs VocabHit, GrammarHit models + AppConfig)

  **References** (CRITICAL):

  **Pattern References**:
  - `src/config.py:AppConfig` — Contains all threshold defaults: `complexity_vocab_threshold=2`, `complexity_n1_grammar_threshold=1`, `complexity_readability_threshold=3.0`, `complexity_ambiguous_grammar_threshold=1`

  **API/Type References**:
  - `src/db/models.py:VocabHit` — Input type. Has `jlpt_level` field.
  - `src/db/models.py:GrammarHit` — Input type. Has `jlpt_level` and `confidence_type` fields.
  - `src/config.py:AppConfig` — Threshold fields used for comparison.
  - `docs/architecture.md` — Complexity threshold table (BUT note the readability direction is wrong in the doc).

  **External References**:
  - `jreadability.compute_readability(text: str, tagger: Optional[fugashi.Tagger] = None) -> float` — Returns readability score. HIGHER = EASIER (verified: simple "これは猫です" → 6.20, complex "経済的観点から…" → 1.11).

  **WHY Each Reference Matters**:
  - `AppConfig` thresholds: The scorer MUST use these configurable thresholds, not hardcoded values.
  - jreadability: The **inverted semantics** are the biggest risk. LOWER score = HARDER text. The threshold check is `score < threshold` (not `>`).
  - `docs/architecture.md`: Reference for threshold logic, but the readability direction in the doc is WRONG. Use empirical evidence.

  **Acceptance Criteria**:

  - [ ] `python -c "from src.analysis.complexity import ComplexityScorer"` — imports
  - [ ] `pytest tests/test_complexity.py -x` — all pass (≥8 tests)
  - [ ] `mypy src/analysis/complexity.py` — clean
  - [ ] `ruff check src/analysis/complexity.py` — clean

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Simple sentence classified as not complex
    Tool: Bash (python)
    Preconditions: None
    Steps:
      1. Run: python -c "
         from src.analysis.complexity import ComplexityScorer
         from src.config import AppConfig
         scorer = ComplexityScorer(AppConfig())
         # No vocab hits, no grammar hits, simple text (high readability score)
         score, is_complex = scorer.score([], [], 'これは猫です')
         print(f'Score: {score:.2f}, is_complex: {is_complex}')
         assert is_complex is False, f'Simple sentence should not be complex'
         print('PASS — simple sentence correctly classified')
         "
    Expected Result: is_complex=False for simple sentence with no hits
    Failure Indicators: is_complex=True (false positive)
    Evidence: .sisyphus/evidence/task-6-simple.txt

  Scenario: Complex sentence with beyond-level vocab flagged
    Tool: Bash (python)
    Preconditions: None
    Steps:
      1. Run: python -c "
         from src.analysis.complexity import ComplexityScorer
         from src.db.models import VocabHit
         from src.config import AppConfig
         scorer = ComplexityScorer(AppConfig())
         # 2 beyond-level vocab hits (meets threshold of 2)
         vocab = [
             VocabHit(surface='概念', lemma='概念', pos='名詞', jlpt_level=1, user_level=3),
             VocabHit(surface='抽象', lemma='抽象', pos='名詞', jlpt_level=1, user_level=3),
         ]
         score, is_complex = scorer.score(vocab, [], '概念と抽象について考える')
         print(f'Score: {score:.2f}, is_complex: {is_complex}')
         assert is_complex is True, f'Should be complex with {len(vocab)} beyond-level vocab'
         print('PASS — vocab threshold triggers complexity')
         "
    Expected Result: is_complex=True when vocab hits meet threshold
    Failure Indicators: is_complex=False (missed threshold)
    Evidence: .sisyphus/evidence/task-6-vocab-complex.txt

  Scenario: Readability threshold uses correct direction (lower = harder)
    Tool: Bash (python)
    Preconditions: None
    Steps:
      1. Run: python -c "
         from src.analysis.complexity import ComplexityScorer
         from src.config import AppConfig
         import jreadability
         scorer = ComplexityScorer(AppConfig())
         # This complex sentence should have readability < 3.0
         hard_text = '経済的観点から見ると、この政策は持続可能性に欠けると言わざるを得ない'
         raw_score = jreadability.compute_readability(hard_text)
         print(f'Raw readability: {raw_score:.2f} (threshold: 3.0)')
         assert raw_score < 3.0, f'Expected low readability for hard text, got {raw_score}'
         score, is_complex = scorer.score([], [], hard_text)
         print(f'Complexity score: {score:.2f}, is_complex: {is_complex}')
         assert is_complex is True, f'Hard text with low readability should be complex'
         # Easy text should NOT trigger readability threshold
         easy_text = 'これは猫です'
         raw_easy = jreadability.compute_readability(easy_text)
         print(f'Easy readability: {raw_easy:.2f}')
         _, easy_complex = scorer.score([], [], easy_text)
         assert easy_complex is False, f'Easy text should not be complex'
         print('PASS — readability direction correct')
         "
    Expected Result: Hard text (low readability) → complex=True. Easy text (high readability) → complex=False.
    Failure Indicators: Direction inverted (hard=False, easy=True)
    Evidence: .sisyphus/evidence/task-6-readability.txt
  ```

  **Evidence to Capture:**
  - [ ] task-6-simple.txt
  - [ ] task-6-vocab-complex.txt
  - [ ] task-6-readability.txt

  **Commit**: YES
  - Message: `feat(analysis): add complexity scorer`
  - Files: `src/analysis/complexity.py`, `tests/test_complexity.py`
  - Pre-commit: `pytest tests/test_complexity.py -x && mypy src/analysis/complexity.py`

- [ ] 7. Preprocessing Pipeline Assembly

  **What to do**:
  - Create `src/analysis/pipeline.py`:
    - Class `PreprocessingPipeline`:
      - `__init__(self, config: AppConfig) -> None` — Initialize all components in correct order:
        1. `self._tokenizer = FugashiTokenizer()` — creates the fugashi.Tagger
        2. `self._vocab_lookup = JLPTVocabLookup(vocab_path)` — path derived from config or default `"data/jlpt_vocab.json"`
        3. `self._grammar_matcher = GrammarMatcher(rules_path)` — path derived from config or default `"data/grammar_rules.json"`
        4. `self._scorer = ComplexityScorer(config, tagger=self._tokenizer.tagger)` — **SHARE the fugashi tagger** from the tokenizer so jreadability doesn't create its own
      - `process(self, text: str) -> AnalysisResult` — Run the full pipeline:
        1. `tokens = self._tokenizer.tokenize(text)`
        2. `vocab_hits = self._vocab_lookup.find_beyond_level(tokens, config.user_jlpt_level)`
        3. `grammar_hits = self._grammar_matcher.match(text, config.user_jlpt_level)`
        4. `complexity_score, is_complex = self._scorer.score(vocab_hits, grammar_hits, text)`
        5. Return `AnalysisResult(tokens=tokens, vocab_hits=vocab_hits, grammar_hits=grammar_hits, complexity_score=complexity_score, is_complex=is_complex)`
      - Add timing: log elapsed time per call at DEBUG level using `logging.getLogger(__name__)` and `time.perf_counter()`
  - Create `tests/test_analysis_pipeline.py`:
    - Test end-to-end with ≥3 known Japanese sentences
    - Test simple sentence produces AnalysisResult with is_complex=False
    - Test complex sentence (with hard vocab + grammar) produces is_complex=True
    - Test empty string returns AnalysisResult with empty lists and is_complex=False
    - Test all fields populated correctly (tokens list, vocab_hits, grammar_hits, scores)
    - Test tagger is shared (verify `pipeline._scorer._tagger is pipeline._tokenizer.tagger`)
    - Optional: benchmark test — 10 iterations in < 500ms (50ms average)

  **Must NOT do**:
  - Do NOT create a second fugashi.Tagger — share from tokenizer
  - Do NOT catch exceptions in process() — let them propagate (caller handles)
  - Do NOT add LLM/audio/UI code — this is preprocessing only
  - Do NOT hardcode data file paths — derive from config or use sensible defaults

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Integration task wiring 4 components together. Must verify tagger sharing, correct data flow, latency target. Needs careful assembly.
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - All irrelevant

  **Parallelization**:
  - **Can Run In Parallel**: NO (depends on all Wave 2 tasks)
  - **Parallel Group**: Wave 3 (solo)
  - **Blocks**: F1-F4
  - **Blocked By**: Tasks 3, 4, 5, 6

  **References** (CRITICAL):

  **Pattern References**:
  - `src/analysis/tokenizer.py` (from Task 3) — `FugashiTokenizer.tokenize()` returns `list[Token]`, `.tagger` property for sharing
  - `src/analysis/jlpt_vocab.py` (from Task 4) — `JLPTVocabLookup.find_beyond_level(tokens, user_level)` returns `list[VocabHit]`
  - `src/analysis/grammar.py` (from Task 5) — `GrammarMatcher.match(text, user_level)` returns `list[GrammarHit]`
  - `src/analysis/complexity.py` (from Task 6) — `ComplexityScorer(config, tagger=)`, `.score(vocab_hits, grammar_hits, text)` returns `(float, bool)`

  **API/Type References**:
  - `src/db/models.py:AnalysisResult` — Output type. Fields: `tokens, vocab_hits, grammar_hits, complexity_score, is_complex`
  - `src/config.py:AppConfig` — `user_jlpt_level` (for vocab/grammar filtering), all complexity thresholds

  **External References**:
  - Python `time.perf_counter()` for latency measurement
  - Python `logging` for debug timing output

  **WHY Each Reference Matters**:
  - All 4 analysis modules: The pipeline is a pure orchestration layer. It must call each module's API correctly. The executor needs to know exact method signatures and return types.
  - `AppConfig.user_jlpt_level`: Passed to both `find_beyond_level` and `match` for level filtering.
  - Tagger sharing: `ComplexityScorer.__init__` accepts `tagger` param. Must pass `self._tokenizer.tagger` to avoid double dictionary load (~100MB RAM savings).

  **Acceptance Criteria**:

  - [ ] `python -c "from src.analysis.pipeline import PreprocessingPipeline"` — imports
  - [ ] `pytest tests/test_analysis_pipeline.py -x` — all pass (≥6 tests)
  - [ ] `mypy src/analysis/pipeline.py` — clean
  - [ ] `ruff check src/analysis/pipeline.py` — clean
  - [ ] Full validation: `ruff check . && ruff format --check . && mypy . && pytest -x --tb=short` — all pass

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: End-to-end pipeline produces correct AnalysisResult
    Tool: Bash (python)
    Preconditions: All analysis modules and data stubs exist
    Steps:
      1. Run: python -c "
         from src.analysis.pipeline import PreprocessingPipeline
         from src.db.models import AnalysisResult, Token, VocabHit, GrammarHit
         from src.config import AppConfig
         p = PreprocessingPipeline(AppConfig())
         result = p.process('昨日友達と映画を見に行きました')
         assert isinstance(result, AnalysisResult), f'Expected AnalysisResult, got {type(result)}'
         assert len(result.tokens) > 0, 'Should have tokens'
         assert all(isinstance(t, Token) for t in result.tokens), 'All tokens should be Token'
         assert isinstance(result.vocab_hits, list), 'vocab_hits should be list'
         assert isinstance(result.grammar_hits, list), 'grammar_hits should be list'
         assert isinstance(result.complexity_score, float), 'score should be float'
         assert isinstance(result.is_complex, bool), 'is_complex should be bool'
         print(f'Tokens: {len(result.tokens)}, Vocab hits: {len(result.vocab_hits)}, Grammar hits: {len(result.grammar_hits)}')
         print(f'Score: {result.complexity_score:.2f}, Complex: {result.is_complex}')
         print('PASS — end-to-end pipeline works')
         "
    Expected Result: Valid AnalysisResult with populated fields
    Failure Indicators: ImportError, wrong types, empty tokens
    Evidence: .sisyphus/evidence/task-7-e2e.txt

  Scenario: Tagger is shared between tokenizer and complexity scorer
    Tool: Bash (python)
    Preconditions: Pipeline initialized
    Steps:
      1. Run: python -c "
         from src.analysis.pipeline import PreprocessingPipeline
         from src.config import AppConfig
         p = PreprocessingPipeline(AppConfig())
         tagger_from_tokenizer = p._tokenizer.tagger
         tagger_from_scorer = p._scorer._tagger
         assert tagger_from_scorer is tagger_from_tokenizer, 'Tagger should be shared (same object), not duplicated'
         print(f'Tokenizer tagger id: {id(tagger_from_tokenizer)}')
         print(f'Scorer tagger id: {id(tagger_from_scorer)}')
         print('PASS — tagger shared correctly')
         "
    Expected Result: Same tagger object (identity check passes)
    Failure Indicators: Different objects (separate taggers loaded)
    Evidence: .sisyphus/evidence/task-7-tagger-shared.txt

  Scenario: Pipeline latency under 50ms average
    Tool: Bash (python)
    Preconditions: Pipeline initialized
    Steps:
      1. Run: python -c "
         import time
         from src.analysis.pipeline import PreprocessingPipeline
         from src.config import AppConfig
         p = PreprocessingPipeline(AppConfig())
         # Warm up
         p.process('テスト')
         # Benchmark
         sentences = ['昨日友達と映画を見に行きました', 'これは猫です', '経済的観点から見ると問題がある']
         total = 0
         runs = 30
         for i in range(runs):
             text = sentences[i % len(sentences)]
             start = time.perf_counter()
             p.process(text)
             elapsed = time.perf_counter() - start
             total += elapsed
         avg_ms = (total / runs) * 1000
         print(f'Average latency: {avg_ms:.1f}ms over {runs} runs')
         assert avg_ms < 50, f'Too slow: {avg_ms:.1f}ms > 50ms target'
         print('PASS — latency within target')
         "
    Expected Result: Average < 50ms per sentence
    Failure Indicators: Latency exceeds 50ms
    Evidence: .sisyphus/evidence/task-7-latency.txt

  Scenario: Empty string produces valid empty result
    Tool: Bash (python)
    Preconditions: Pipeline initialized
    Steps:
      1. Run: python -c "
         from src.analysis.pipeline import PreprocessingPipeline
         from src.config import AppConfig
         p = PreprocessingPipeline(AppConfig())
         result = p.process('')
         assert result.tokens == [], f'Expected no tokens, got {result.tokens}'
         assert result.vocab_hits == [], f'Expected no vocab hits'
         assert result.grammar_hits == [], f'Expected no grammar hits'
         assert result.is_complex is False, f'Empty text should not be complex'
         print('PASS — empty input handled')
         "
    Expected Result: Empty lists, is_complex=False
    Failure Indicators: Non-empty results, exception on empty input
    Evidence: .sisyphus/evidence/task-7-empty.txt
  ```

  **Evidence to Capture:**
  - [ ] task-7-e2e.txt
  - [ ] task-7-tagger-shared.txt
  - [ ] task-7-latency.txt
  - [ ] task-7-empty.txt

  **Commit**: YES
  - Message: `feat(analysis): assemble preprocessing pipeline`
  - Files: `src/analysis/pipeline.py`, `tests/test_analysis_pipeline.py`
  - Pre-commit: `ruff check . && ruff format --check . && mypy . && pytest -x --tb=short`

---

## Final Verification Wave (MANDATORY — after ALL implementation tasks)

> 4 review agents run in PARALLEL. ALL must APPROVE. Rejection → fix → re-run.

- [ ] F1. **Plan Compliance Audit** — `oracle`
  Read the plan end-to-end. For each "Must Have": verify implementation exists (read file, run command). For each "Must NOT Have": search codebase for forbidden patterns — reject with file:line if found. Check evidence files exist in `.sisyphus/evidence/`. Compare deliverables against plan.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [ ] F2. **Code Quality Review** — `unspecified-high`
  Run `ruff check . && ruff format --check . && mypy . && pytest -x --tb=short`. Review all changed files for: `type: ignore` without comment, empty catches, print() in production code, commented-out code, unused imports. Check AI slop: excessive comments, over-abstraction, generic variable names (data/result/item/temp used without clarity).
  Output: `Lint [PASS/FAIL] | Types [PASS/FAIL] | Tests [N pass/N fail] | Files [N clean/N issues] | VERDICT`

- [ ] F3. **Real Manual QA** — `unspecified-high`
  Start from clean state. Execute EVERY QA scenario from EVERY task — follow exact steps, capture evidence. Test cross-task integration: process a sentence through the full pipeline and verify all fields populated. Test edge cases: empty string, punctuation-only, unknown words, no grammar matches. Save to `.sisyphus/evidence/final-qa/`.
  Output: `Scenarios [N/N pass] | Integration [N/N] | Edge Cases [N tested] | VERDICT`

- [ ] F4. **Scope Fidelity Check** — `deep`
  For each task: read "What to do", read actual diff (git log/diff). Verify 1:1 — everything in spec was built, nothing beyond spec was built. Check "Must NOT do" compliance. Detect cross-task contamination: Task N touching Task M's files. Flag unaccounted changes.
  Output: `Tasks [N/N compliant] | Contamination [CLEAN/N issues] | Unaccounted [CLEAN/N files] | VERDICT`

---

## Commit Strategy

- **Task 1**: `feat(db): add schema, models, and data stubs for M1` — schema.py, models.py, jlpt_vocab.json, grammar_rules.json
- **Task 2**: `feat(db): add learning repository with CRUD operations` — repository.py, test_db_repository.py
- **Task 3**: `feat(analysis): add fugashi tokenizer wrapper` — tokenizer.py, test_tokenizer.py
- **Task 4**: `feat(analysis): add JLPT vocabulary lookup` — jlpt_vocab.py, test_jlpt_vocab.py
- **Task 5**: `feat(analysis): add grammar pattern matcher` — grammar.py, test_grammar.py
- **Task 6**: `feat(analysis): add complexity scorer` — complexity.py, test_complexity.py
- **Task 7**: `feat(analysis): assemble preprocessing pipeline` — pipeline.py, test_analysis_pipeline.py
- **Final**: `chore: M1 milestone verification and cleanup` (if any fixes needed)

---

## Success Criteria

### Verification Commands
```bash
# Full validation suite
ruff check . && ruff format --check . && mypy . && pytest -x --tb=short

# Pipeline latency check
python -c "
import time
from src.analysis.pipeline import PreprocessingPipeline
from src.config import AppConfig
p = PreprocessingPipeline(AppConfig())
start = time.perf_counter()
for _ in range(10):
    p.process('昨日友達と映画を見に行きました')
elapsed = (time.perf_counter() - start) / 10
print(f'Average latency: {elapsed*1000:.1f}ms')
assert elapsed < 0.05, f'Too slow: {elapsed*1000:.1f}ms > 50ms'
"
```

### Final Checklist
- [ ] All "Must Have" present
- [ ] All "Must NOT Have" absent
- [ ] All tests pass (≥30 tests)
- [ ] mypy clean
- [ ] ruff clean
- [ ] Pipeline latency < 50ms per sentence
- [ ] Data stubs contain sufficient entries for tests
