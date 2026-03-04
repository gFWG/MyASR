# Learnings — M1 Preprocessing Pipeline

## [2026-03-04] Initial Setup

### Project Structure
- `src/db/__init__.py` and `src/analysis/__init__.py` already exist (empty)
- `src/config.py` exists with `AppConfig` dataclass
- `tests/test_config.py` is the pattern to follow

### AppConfig Fields (complexity thresholds)
- `user_jlpt_level: int = 3`
- `complexity_vocab_threshold: int = 2`
- `complexity_n1_grammar_threshold: int = 1`
- `complexity_readability_threshold: float = 3.0`
- `complexity_ambiguous_grammar_threshold: int = 1`

### Code Style (from test_config.py)
- pytest fixtures with `tmp_path`
- Test names: `test_<what>_<condition>`
- No unittest.TestCase classes
- Module docstrings: `"""Tests for src.<module>."""`

### API-data.md Key Facts
- `highlight_grammar` table has column `pattern` (NOT `pattern_regex`)
- Grammar rules JSON uses `pattern_regex` key
- `HighlightGrammar.pattern` stores matched text span
- `SentenceRecord.is_complex` is `bool` in Python, stored as INTEGER in SQLite
- `created_at` is TEXT (ISO 8601) in SQLite but `datetime` in `SentenceResult`

### Critical Architecture Notes
- jreadability: HIGHER score = EASIER text. Threshold: `score < 3.0` = complex
- fugashi: Use `Tagger()` NOT `GenericTagger`; `word.feature.lemma` may be None → fallback to surface
- JLPT levels: N1(1)=hardest, N5(5)=easiest. "Beyond level" = `word_level < user_level`
- Tagger sharing: Pass `tokenizer.tagger` to `ComplexityScorer(config, tagger=...)` to avoid double load

### Evidence Directory
- `.sisyphus/evidence/` — save QA evidence here

## [2026-03-04] Database Schema & Models

### Files Created
- `src/db/schema.py` — SCHEMA_SQL + `init_db(db_path: str) -> sqlite3.Connection`
- `src/db/models.py` — 8 dataclasses (3 DB models + 5 pipeline models)
- `data/jlpt_vocab.json` — 35 entries covering JLPT N1-N5
- `data/grammar_rules.json` — 14 grammar rules with regex patterns
- `tests/test_db_schema.py` — 8 comprehensive pytest tests

### Schema Design Decisions
- Used `executescript()` for running all CREATE TABLE statements at once
- PRAGMA `journal_mode=WAL` and `foreign_keys=ON` applied after schema creation
- All indexes created inline with `CREATE INDEX IF NOT EXISTS`
- Boolean fields stored as INTEGER (0/1) in SQLite, converted to `bool` in Python dataclasses

### Dataclass Patterns
- DB models use `str` for `created_at` (ISO 8601), pipeline models use `datetime`
- `SentenceResult.created_at` has default_factory for `datetime.now`
- All nullable fields use `X | None` union syntax (Python 3.12+)
- No docstrings on dataclasses — field names are self-explanatory

### Test Patterns
- `tmp_path` fixture for file-based database tests
- `:memory:` for in-memory database tests
- Verified table existence via `sqlite_master` query
- Verified column names via `PRAGMA table_info(table_name)`
- Verified index existence via `sqlite_master` WHERE type='index'

### Verification Results
- pytest: 8/8 passed
- mypy: 0 issues
- ruff check: clean
- ruff format: already formatted

### JLPT Vocab Coverage
- N5 (5): 食べる，見る，行く，来る，飲む，猫，犬，本，学校，先生，学生，時間
- N4 (4): 映画，友達，仕事，電車，勉強，毎日
- N3 (3): 旅行，料理，準備，大切，ことができる
- N2 (2): 経済，観察，必要，可能，社会，環境，状況
- N1 (1): 概念，影響，発展，現象，認識，構造，ざるを得ない，に至る

### Grammar Rules Added
- N5: past た，ます form
- N4: て-form, たい form
- N3: ながら，ために，ことができる
- N2: passive, causative, にとって，わけではない
- N1: に過ぎない，に至る，ざるを得ない

## Task 4: JLPTVocabLookup Implementation (2026-03-04)

### Key Learning: JLPT Level Comparison Direction
- N1 (level=1) = HARDEST, N5 (level=5) = EASIEST
- "Beyond user's level" means word is harder than user knows
- Comparison: `word_level < user_level` (not `>`)
- Example: user_level=3, word=N1 (level=1) → 1 < 3 → BEYOND level (flag it)
- This is counterintuitive but critical for correct filtering

### Pattern: Exact Dictionary Lookup
- Simple `dict.get()` for O(1) lookup
- No fuzzy matching - exact lemma match only
- Load all data at `__init__` - no lazy loading
- Clean separation: lookup (single word) vs find_beyond_level (batch filter)

### Testing Pattern
- Parametrize for multiple vocab lookups in one test
- Test edge cases: unknown words return None, empty token list returns []
- Test boundary condition: user_level=1 (N1) sees nothing as beyond level

## LearningRepository (src/db/repository.py) — 2026-03-04

### Pattern: raw sqlite3 without row_factory
- Used tuple index access (row[0], row[1]...) rather than `sqlite3.Row` — both valid but index access avoids needing to set `conn.row_factory`
- Bool fields in DB (is_complex, is_beyond_level, tooltip_shown) are stored as INTEGER 0/1; must explicitly convert on read: `bool(row[5])`; on write: `int(record.is_complex)`

### Pattern: transaction with rollback
- `try/except` around all INSERT calls; `conn.rollback()` on any exception; `conn.commit()` at end of successful transaction
- `cursor.lastrowid` gives the autoincrement ID immediately after INSERT (no separate SELECT needed)

### Pattern: dynamic table name in mark_tooltip_shown
- Table name is controlled via if/elif guard (not user-supplied), so string interpolation into SQL is safe
- Added `# noqa: S608` comment to suppress ruff's S608 "possible SQL injection" warning

### init_db(":memory:")
- `init_db(":memory:")` returns a live in-memory connection — ideal for test fixtures
- `conn.execute("PRAGMA foreign_keys=ON")` is set by init_db, so CASCADE DELETE works correctly in tests

### Test structure
- `make_record(**kwargs)` / `make_vocab(**kwargs)` / `make_grammar(**kwargs)` factory helpers keep test data concise
- Tested cascade delete: deleting a sentence_record removes associated highlight_vocab/highlight_grammar rows (foreign key ON DELETE CASCADE)
- 19 tests total, all passing in 0.04s

## Task 3: FugashiTokenizer Implementation (2026-03-04)

### Fugashi API Notes
- Use `fugashi.Tagger()` (not `GenericTagger`) — Tagger auto-detects Unidic version
- Call syntax: `tagger(text)` returns iterable of UnidicNode objects
- Node attributes:
  - `.surface` — surface form (str)
  - `.feature.pos1` — part of speech category (str)
  - `.feature.lemma` — dictionary form (str | None)
- **Critical**: `lemma` can be `None` for some tokens — always check and fallback to `surface`

### Type Annotations for fugashi
- fugashi is a Cython module without type stubs
- Add `ignore_missing_imports = true` to `[tool.mypy]` in pyproject.toml
- Use explicit type annotation: `self._tagger: fugashi.Tagger`

### POS Filtering
- Filter POS categories: `{"補助記号", "記号"}` to exclude punctuation/symbols
- This keeps content words (nouns, verbs, adjectives, particles, auxiliary verbs)

### Testing
- fugashi works out-of-box with unidic-lite (no dictionary path needed)
- Tests use real tagger (no mocking) — fast enough for unit tests
- Edge cases: empty string returns `[]`, punctuation-only returns `[]`

### Files Created
- `src/analysis/tokenizer.py` — FugashiTokenizer class
- `tests/test_tokenizer.py` — 6 pytest tests
- `pyproject.toml` — added `ignore_missing_imports = true` for mypy
## Complexity scorer implementation
- jreadability readability score is inverted: higher = easier; complexity triggers when score < threshold.
- Optional tokenizer should be accepted as a callable tagger-like protocol for jreadability; avoid direct fugashi type import if unavailable.

## Task 5: GrammarMatcher (grammar.py)

### Pattern space gotcha in grammar_rules.json
The `pattern_regex` values in `data/grammar_rules.json` use ` | ` (space-pipe-space) for alternation in several rules (e.g., `N5_masu_form`, `N4_tai_form`, `N1_ni_suginai`, `N3_koto_ga_dekiru`). This means:
- `ます | ません | ました | ませんでした` is NOT `ます|ません|ました|ませんでした`
- First alternative requires trailing space in text; subsequent alternatives require leading space
- Example: `'ます '` matches but `'ます'` alone does NOT

Reliable patterns for natural Japanese text (no spaces needed):
- `N3_nagara`: `ながら` — matches inline in sentences
- `N3_tame_ni`: `ために` — matches inline
- `N2_ni_totte`: `にとって` — matches inline

Patterns that require spaces between characters (space-separated character classes):
- `N2_passive`: `[^さ] れ [たるており]` — requires actual spaces around `れ`
- `N2_causative`: `させ [たるられ]` — requires space before `[たるられ]`

### Test design lesson
Design test sentences around patterns that reliably fire on natural text. Don't assume all patterns work on space-free Japanese text — verify with `re.compile(pattern).finditer(text)` first.

### Level filter logic
`rule.jlpt_level < user_level` = "harder than user's level" = should appear in hits.
N1=1 (hardest), N5=5 (easiest). user_level=1 → nothing is harder, so always 0 hits.

## Task 6: PreprocessingPipeline (2026-03-04)

### Files Created
- `src/analysis/pipeline.py` — PreprocessingPipeline class
- `tests/test_analysis_pipeline.py` — 6 pytest tests

### Tagger-sharing Pattern
- `ComplexityScorer(config, tagger=self._tokenizer.tagger)` avoids double Unidic load
- `pipeline._scorer._tagger is pipeline._tokenizer.tagger` — verified identity (same object)

### Performance
- 6 tests pass in 0.04s total (module-scope fixture reuses single pipeline instance)
- Per-sentence latency well under 50ms after warm-up (typical ~2-5ms)
- First call may be slower due to jreadability/fugashi caching — always warm-up before benchmarking

### Test Fixture Pattern
- `scope="module"` on `pipeline` fixture ensures one pipeline instance across all tests
- This is critical for latency test: avoids re-initializing heavy models per test

### vocab_hits test
- Used "概念を理解する" — 概念 is N1 (level=1), user_jlpt_level=3 → 1 < 3 → VocabHit included
- Verified lemma "概念" appears in vocab_hits

### Verification Results
- pytest: 77/77 passed (71 existing + 6 new)
- mypy: 0 issues (27 source files)
- ruff check: clean
- ruff format: already formatted
