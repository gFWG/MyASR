# Learnings — vocabulary-csv-migration

## 2026-03-11 Session ses_322eaefc6ffevPScOWx3LrQ1Sp — Initial Survey

### CSV Format
- File: `data/vocabulary.csv` — 8293 rows + header
- Columns: `id,pronBase,lemma,definition,level`
- Sample: `1001,アア,嗚呼,'Ah! Oh! Alas!',N1`
- Level strings: 'N1'-'N5' → convert to int via `int(row['level'][1:])` → 1-5
- 48 entries have empty definition (omit in UI, no placeholder)

### Current jlpt_vocab.py
- `JLPTVocabLookup` loads JSON `{lemma: level_int}`
- `lookup(lemma: str) -> int | None`
- `find_beyond_level(tokens, user_level, text) -> list[VocabHit]`
- Uses `token.lemma` for lookup
- Fugashi outputs `私-代名詞` style lemmas → strip after `-` before lookup

### Duplicate Strategy
- Multiple CSV rows with same lemma → keep easiest level (highest N-number)
- O(1) dict lookup preserved via `dict[str, VocabEntry]`

### VocabEntry (new dataclass)
- `@dataclass(frozen=True, slots=True)`
- Fields: `vocab_id: int, pronunciation: str, lemma: str, definition: str, level: int`

### VocabHit Additions (Task 2)
- Add to existing: `vocab_id: int = 0, pronunciation: str = "", definition: str = ""`

### HighlightVocab Additions (Task 2)
- Add to existing: `vocab_id: int = 0, pronunciation: str = "", definition: str = ""`

### DB Schema Additions (Task 3)
- ADD columns: `vocab_id INTEGER NOT NULL DEFAULT 0`
- ADD columns: `pronunciation TEXT NOT NULL DEFAULT ''`
- ADD columns: `definition TEXT NOT NULL DEFAULT ''`
- Migration via ALTER TABLE with try/except for existing columns

### Repository Updates (Task 3)
- INSERT must include new 3 columns
- SELECT must return and map new 3 columns

### Test Files
- tests/test_jlpt_vocab.py — main test for CSV loader
- tests/test_db_repository.py — must handle new columns
- tests/test_db_schema.py — migration tests
- tests/test_analysis_pipeline.py — pipeline integration

### Pipeline Path (Task 5)
- Change `JLPTVocabLookup('data/jlpt_vocab.json')` → `JLPTVocabLookup('data/vocabulary.csv')`

### Toolchain
- ruff check . && ruff format --check .
- mypy src/
- pytest tests/

## 2026-03-11 Session — T1: jlpt_vocab.py CSV migration

### Implementation completed

#### VocabEntry dataclass
- `@dataclass(frozen=True, slots=True)` in `src/analysis/jlpt_vocab.py`
- Fields: `vocab_id: int, pronunciation: str, lemma: str, definition: str, level: int`

#### JLPTVocabLookup changes
- Internal `_vocab: dict[str, VocabEntry]` (replaces `dict[str, int]`)
- `.csv` extension → `_load_csv()` via `csv.DictReader`; else → `_load_json()` (backward compat)
- Dedup: keep easiest level (highest int); overwrite only if `new_level > existing.level`
- New `lookup_entry(lemma) -> VocabEntry | None`
- `find_beyond_level`: `clean_lemma = token.lemma.split('-')[0]` before lookup
- VocabHit populated with `vocab_id, pronunciation, definition` from entry

#### VocabHit (models.py)
- Added 3 fields with defaults: `vocab_id: int = 0`, `pronunciation: str = ""`, `definition: str = ""`

#### Test gotchas
- `映画` is N5 in CSV (not N4 as originally expected) → changed parametrize test to use `驚く→N4`
- `と` is N1 in CSV (particle/conjunction!) → duplicate-position test used `ん` as non-vocab separator
- `間` appears twice: N3 (id=7754) and N4 (id=7973); dedup keeps N4(4) — higher int wins

### Results
- ruff: ✓ clean
- mypy: ✓ 39 files no issues
- pytest tests/test_jlpt_vocab.py: 17 passed
- pytest tests/ (full suite): 350 passed, 14 skipped, 1 xfailed

## 2026-03-11 — T2b: HighlightVocab new fields

### Changes made
- `src/db/models.py` `HighlightVocab`: added 3 fields AFTER `tooltip_shown`:
  - `vocab_id: int = 0`
  - `pronunciation: str = ""`
  - `definition: str = ""`
- Fields have defaults → all existing construction sites remain valid without changes
- `VocabHit` already had these fields (added in T1); no changes needed there

### Tests added (tests/test_db_repository.py)
- `test_highlight_vocab_new_fields_default_values`: verifies defaults are 0/""/""
- `test_highlight_vocab_new_fields_explicit_values`: verifies explicit assignment works

### Results
- pytest tests/test_db_repository.py: 40 passed
- ruff check + format: ✓ clean
- mypy src/: ✓ 39 files no issues

## 2026-03-11 — T3: DB schema + repository migration

### Changes made

#### src/db/schema.py
- Added 3 columns to `highlight_vocab` in `SCHEMA_SQL`:
  - `vocab_id INTEGER NOT NULL DEFAULT 0`
  - `pronunciation TEXT NOT NULL DEFAULT ''`
  - `definition TEXT NOT NULL DEFAULT ''`
- Added ALTER TABLE migrations in `init_db()` AFTER `conn.executescript(SCHEMA_SQL)`:
  - Each ALTER wrapped in `try/except sqlite3.OperationalError` (column already exists)
  - `conn.commit()` called after each successful ALTER

#### src/db/repository.py `insert_sentence`
- INSERT now 10 params: `(sentence_id, surface, lemma, pos, jlpt_level, is_beyond_level, tooltip_shown, vocab_id, pronunciation, definition)`
- Uses `int(v.vocab_id)` to ensure integer type

#### src/db/repository.py `get_sentence_with_highlights`
- SELECT now includes `vocab_id, pronunciation, definition`
- `HighlightVocab` constructor: `vocab_id=int(vrow[8])`, `pronunciation=str(vrow[9])`, `definition=str(vrow[10])`

### Tests added

#### tests/test_db_schema.py
- `test_init_db_schema_columns`: added assertions for `vocab_id`, `pronunciation`, `definition` in vocab_cols
- `test_init_db_migrates_old_database`: creates old schema without new cols, calls init_db, verifies cols present after migration

#### tests/test_db_repository.py
- `test_highlight_vocab_new_fields_roundtrip`: inserts HighlightVocab with vocab_id=99, pronunciation="ねこ", definition="cat"; verifies round-trip via get_sentence_with_highlights

### Results
- pytest tests/test_db_schema.py tests/test_db_repository.py: 50 passed
- pytest tests/ (full suite): 371 passed, 14 skipped, 1 xfailed
- ruff check + format: ✓ clean
- mypy src/: ✓ 39 files no issues

### UI Update for Vocabulary Sentence Detail
- Handled conditionally adding `pronunciation` (with `[]` formatting) and `definition` (with `—` separator) to `src/ui/sentence_detail.py`.
- Ensured secondary colors like `#777777` and smaller font-sizes `12px` align with the Microsoft Design System and existing styles.
- Added tests in `tests/test_sentence_detail.py` that utilize `QLabel` extraction to assert the correct presence or absence of the newly added text fields.
\n- Added optional pronunciation and definition fields to tooltip UI.\n- Updated tooltip tests to cover empty vs non-empty states for new fields.

## export_records update (2026-03-11)

- JSON path: SELECT now fetches `surface, lemma, jlpt_level, pos, vocab_id, pronunciation, definition` (7 cols) from `highlight_vocab`. Dict keys match field names.
- CSV path: SELECT now fetches `lemma, vocab_id, pronunciation, definition` (4 cols). New CSV columns appended: `vocab_ids` (semicolon-joined), `vocab_pronunciations`, `vocab_definitions` after existing `vocab_count, grammar_count, vocab_lemmas, grammar_rules`.
- `make_vocab` fixture in tests extended with `vocab_id`, `pronunciation`, `definition` optional params (all default to 0/"").
- New test `test_export_records_json_vocab_pronunciation_definition` verifies round-trip of all three new fields via JSON export.
- `test_export_records_csv_with_highlights` updated to assert new header columns and verify actual cell values in data row.
- All 378 tests pass, mypy clean, ruff clean.

## 2026-03-11 — T6: Delete jlpt_vocab.json + Integration Test

### jlpt_vocab.json removal
- `data/jlpt_vocab.json` deleted via `rm` — contained only 35 legacy entries
- One lingering reference found: `src/analysis/AGENTS.md` line 26
  - Updated: "stored in `data/jlpt_vocab.json`" → "loaded from `data/vocabulary.csv` via `JLPTVocabLookup`"
- Zero references remain in `src/` or `tests/` (grep confirmed)

### Integration test: tests/test_integration_csv_pipeline.py
- 11 tests covering the full CSV→lookup→DB→export pipeline
- Key assertions:
  - `JLPTVocabLookup('data/vocabulary.csv')` loads ≥8000 entries (deduped from 8293 CSV rows)
  - `概念` → pronunciation='ガイネン', vocab_id=1652, definition contains 'concept'/'notion'
  - `食べる` → pronunciation='タベル', level=5
  - `find_beyond_level` with user_level=5 finds 概念 (N1) with correct start/end positions
  - N5 word NOT returned for user_level=3
  - DB round-trip: HighlightVocab with vocab_id/pronunciation/definition preserved through insert→select
  - Multiple vocab hits per sentence round-trip correctly
  - JSON export preserves pronunciation/definition
  - Missing file raises FileNotFoundError
  - Missing sentence_id returns None from get_sentence_with_highlights

### Results
- pytest tests/test_integration_csv_pipeline.py: 11 passed (0.36s)
- pytest tests/ (full suite): 389 passed, 14 skipped, 1 xfailed
- ruff check + format --check: ✓ clean
- mypy src/: ✓ 39 files no issues
