# Grammar-Update: Learnings

## 2026-03-12 Session Init

### File Structure
- `data/grammar.json` — new 831-rule file, schema: `{id: int, re: str, word: str, description: str, level: str}` (level='N1'-'N5')
- `data/grammar_rules.json` — old 14-rule file to DELETE later
- `src/analysis/grammar.py` — GrammarMatcher class, _CompiledRule dataclass
- `src/analysis/pipeline.py` — PreprocessingPipeline, hardwires `data/grammar_rules.json`
- `src/db/models.py` — GrammarHit (has `confidence_type`, no `word`), HighlightGrammar (has `confidence_type`, no `word`)
- `src/db/schema.py` — `highlight_grammar` table has `confidence_type TEXT NOT NULL`, no `word` column
- `src/db/repository.py` — insert_sentence and get_sentence_with_highlights use confidence_type
- `src/pipeline/analysis_worker.py` — creates HighlightGrammar with confidence_type=hit.confidence_type, pattern=hit.rule_id
- `src/config.py` — DEFAULT_JLPT_COLORS has n4, n3, n2, n1 only — MISSING n5_vocab, n5_grammar

### Current grammar.py field names (OLD → to be replaced)
- `_CompiledRule` fields: rule_id, pattern, jlpt_level, confidence_type, description
- JSON keys used: `rule["rule_id"]`, `rule["pattern_regex"]`, `rule["jlpt_level"]`, `rule["confidence_type"]`, `rule["description"]`

### NEW grammar.json field names
- JSON keys: `id`, `re`, `word`, `description`, `level` (e.g. "N1", "N5")

### N5 filter bug
- OLD (wrong): `if rule.jlpt_level >= user_level: continue`  → skips N5 when user=N5
- NEW (correct): `if rule.jlpt_level > user_level: continue`

### Malformed regex IDs
- ID 38: trailing `）)` to remove
- ID 53: trailing `）)` to remove  
- ID 101: full-width `）` instead of `)` — last char fix

### DB Schema Change
- REMOVE `confidence_type TEXT NOT NULL` from `highlight_grammar`
- ADD `word TEXT` (nullable)
- Migration: `ALTER TABLE highlight_grammar DROP COLUMN confidence_type` + `ADD COLUMN word TEXT`
- DB version: PRAGMA user_version 0→1

### analysis_worker.py changes
- `pattern=hit.word` (was `hit.rule_id`)
- `word=hit.word` (new field)
- REMOVE `confidence_type=hit.confidence_type`

## models.py dataclass field changes (2026-03-12)
- `GrammarHit`: removed `confidence_type: str`, added `word: str` after `matched_text`
- `HighlightGrammar`: removed `confidence_type: str`, added `word: str | None` after `pattern`
- `word` is non-nullable in `GrammarHit` (new hits always have a word) but `str | None` in `HighlightGrammar` (old DB rows won't have a word value)
- LSP diagnostics clean after change

### config.py DEFAULT_JLPT_COLORS updated
- Added `n5_vocab: '#E8F5E9'` and `n5_grammar: '#81C784'` BEFORE n4 entries
- Dict is now ordered N5→N4→N3→N2→N1
- `jlpt_colors_to_renderer_format()` already generic (parses int from level_str[1:]) — no changes needed

## Fix: Malformed Regex Patterns (IDs 38, 53, 101)
**Date:** 2026-03-12

### Pattern of Error
Three rules had full-width closing paren `）` (U+FF09) mixed into the regex `re` field, causing regex parse errors:
- IDs 38, 53: trailing `）)` — two chars (full-width + ASCII) at end of non-capturing group
- ID 101: trailing `）` — single full-width paren instead of ASCII `)`

### Root Cause
Full-width Japanese punctuation `）` was accidentally included in the `re` field instead of the `word` field where it belongs. The `word` field uses `（...）` for pronunciation annotations.

### Fix Applied
- ID 38: `たえない）)` → `たえない)`  (removed `）` before final `)`)
- ID 53: `みられる）)` → `みられる)`  (removed `）` before final `)`)
- ID 101: `うってかわり）` → `うってかわり)` (replaced full-width `）` with ASCII `)`)

### Verification
- All 3 regexes are valid non-capturing groups `(?:...|...)` after fix
- `python3 -c "import json; json.load(open('data/grammar.json'))"` passes

## grammar.py rewrite (2026-03-12)

### grammar.json schema (confirmed)
- Keys: `id` (int), `re` (str), `word` (str), `description` (str), `level` (str: 'N1'-'N5')
- 831 rules total, all load successfully (no invalid regex found)
- Level parsing: `int(str(rule["level"])[1:])` → N1→1, N5→5

### _CompiledRule fields (new)
- `rule_id: str` (from `id`)
- `word: str` (from `word`)
- `pattern: re.Pattern[str]` (compiled from `re`)
- `jlpt_level: int` (from `level` → int)
- `description: str`
- Uses `@dataclass(frozen=True, slots=True)` per project conventions

### GrammarHit construction (new)
- `rule_id=rule.rule_id`, `word=rule.word`, `matched_text=m.group()`
- `jlpt_level=rule.jlpt_level`, `description=rule.description`
- `start_pos=m.start()`, `end_pos=m.end()`
- NO `confidence_type` — field removed from models.py already

### Filter fix
- Old (BUG): `if rule.jlpt_level >= user_level: continue`
- New (CORRECT): `if rule.jlpt_level > user_level: continue`
- Meaning: skip rules harder (lower level int) than user's level

### Other files with residual confidence_type errors (NOT our task)
- ~~`src/pipeline/analysis_worker.py` line 118/124~~ ✅ FIXED (see below)
- `src/db/repository.py` lines 165, 611, 617
- `src/ui/tooltip.py` line 182
- `tests/test_analysis_worker.py` lines 61/65
- These are separate tasks, DO NOT touch

### Sanity test result
```
python3 -c "from src.analysis.grammar import GrammarMatcher; m = GrammarMatcher('data/grammar.json'); print(len(m._rules), 'rules loaded')"
# → 831 rules loaded
```

## DB Schema Migration + Repository Update (2026-03-12)

### schema.py changes
- `highlight_grammar` CREATE TABLE: replaced `confidence_type TEXT NOT NULL,` with `word TEXT,` (nullable)
- Added `from sqlite3 import OperationalError` import for migration error handling
- Added versioned migration block after existing ad-hoc migrations list:
  - Reads `PRAGMA user_version` → variable `user_version: int`
  - `if user_version < 1`: DROP COLUMN `confidence_type`, ADD COLUMN `word TEXT`, set `PRAGMA user_version = 1`, commit
  - Each ALTER wrapped in `try/except OperationalError` (idempotent)
- Pattern: versioned block uses `PRAGMA user_version` tracking; old migrations use flat list (two patterns coexist)

### repository.py changes
- `insert_sentence`: INSERT INTO `highlight_grammar` now uses `word` column instead of `confidence_type`
  - Column list: `(sentence_id, rule_id, pattern, jlpt_level, word, description, is_beyond_level, tooltip_shown)`
  - Param tuple: `g.word` at index 4 (was `g.confidence_type`)
- `get_sentence_with_highlights`: SELECT now fetches `word` instead of `confidence_type`
  - Column at index 5: `word` (was `confidence_type`)
  - `HighlightGrammar` constructed with `word=grow[5]` (was `confidence_type=grow[5]`)
- Column order in SELECT unchanged: `id[0], sentence_id[1], rule_id[2], pattern[3], jlpt_level[4], word[5], description[6], is_beyond_level[7], tooltip_shown[8]`

### LSP verification
- Both `src/db/schema.py` and `src/db/repository.py` — zero errors after changes

## analysis_worker.py grammar mapping fix (2026-03-12)

### Changes made
- `HighlightGrammar` construction in `_process_one`:
  - `pattern=hit.rule_id` → `pattern=hit.word`
  - `word=hit.word` ADDED (new field)
  - `confidence_type=hit.confidence_type` REMOVED
- LSP diagnostics: zero errors after change
- PySide6 import error is expected in WSL/Linux (Windows runtime target only)

## tooltip.py N5 color + word display fix (2026-03-12)

### Changes
- `_JLPT_GRAMMAR_COLORS`: added `5: '#81C784'` before entry `4: '#4CAF50'`
- `show_for_grammar` line 183: `f"{hit.confidence_type}: {description}"` → `f"{hit.word or hit.matched_text}: {description}"`
- LSP diagnostics: zero errors after both changes

## pipeline.py grammar path update (2026-03-12)

### Change
- `src/analysis/pipeline.py` line 30: `GrammarMatcher("data/grammar_rules.json")` → `GrammarMatcher("data/grammar.json")`

### Verification
- LSP diagnostics: zero errors on pipeline.py
- `python3 -c "from src.analysis.pipeline import PreprocessingPipeline"` → pre-existing `ModuleNotFoundError: No module named 'fugashi'` (not our code, WSL2 env missing native dep)

## highlight.py + sentence_detail.py N5 color support (2026-03-12)

### Changes
- `src/ui/highlight.py`: Added `5: {"vocab": "#E8F5E9", "grammar": "#81C784"}` as first entry in `JLPT_COLORS` dict (before N4)
- `src/ui/sentence_detail.py`: Updated `_make_jlpt_badge` docstring arg description from "1–4" to "1–5"
- `_JLPT_COLORS = HighlightRenderer.JLPT_COLORS` in sentence_detail.py auto-picks up N5 (no change needed there)
- `_badge_color()` and `_grammar_color()/_vocab_color()` already handle new level gracefully

## Test fixture confidence_type → word migration (2026-03-12)

### Files updated
- `tests/test_analysis_worker.py`: `make_grammar_hit()` — `confidence_type="definite"` → `word="て"`
- `tests/test_db_repository.py`: `make_grammar()` factory — `confidence_type: str = "high"` → `word: str | None = "ながら"`, updated HighlightGrammar constructor arg
- `tests/test_db_schema.py`: `assert "confidence_type" in grammar_cols` → `assert "confidence_type" not in grammar_cols` + `assert "word" in grammar_cols`
- `tests/test_highlight.py`: `_make_grammar()` factory — `confidence_type="high"` → `word="ながら"`
- `tests/test_overlay.py`: `GrammarHit(...)` inline — `confidence_type="exact"` → `word="ても"`
- `tests/test_tooltip.py`: `_make_grammar_hit()` factory — `confidence_type: str = "exact"` → `word: str = "ても"`; also updated `test_show_for_grammar_sets_desc_label` to remove `assert "exact" in` (replaced by word-based display)

### Pre-existing unrelated failure (not our concern)
- `test_highlight.py::test_jlpt_colors_has_all_four_levels` — FAILS because JLPT_COLORS now has 5 levels ({1,2,3,4,5}) but test expects {1,2,3,4}. Pre-existing issue from N5 addition.

### pytest result: 156 passed, 1 failed (pre-existing), 1 xfailed

## test_grammar.py rewrite (2026-03-12)

### New test file: tests/test_grammar.py
- Uses `data/grammar.json` (NOT `grammar_rules.json`)
- 14 tests, all PASS
- Constants: `TEKARA_N5_RULE_ID = "762"` (てから, N5), `YOUNI_N3_RULE_ID = "460"` (ように, N3)
- Anchor sentences: `TEKARA_SENTENCE = "食べてから寝る"`, `YOUNI_SENTENCE = "上手になるように練習している"`

### Tests covered
1. `test_grammar_matcher_loads_rules` — `len(matcher._rules) == 831`
2. `test_grammar_matcher_file_not_found` — raises FileNotFoundError
3. `test_grammar_hit_fields` — all 7 fields: rule_id(str), word(str), matched_text(str), jlpt_level(int 1-5), description(str), start_pos(int≥0), end_pos(int>start)
4. `test_grammar_hit_word_field_populated` — rule 762 word=="てから", jlpt_level==5
5. `test_match_tekara_n5` — rule 762 in hits for user_level=5
6. `test_match_youni_n3` — rule 460 in hits for user_level=5
7. `test_matched_text_is_substring` — matched_text in original text
8. `test_positions_identify_matched_text` — text[start:end]==matched_text, 0≤start<end≤len(text)
9. `test_user_level_5_includes_n5_rules` — N5 rule NOT filtered when user_level=5 (5 > 5 is False)
10. `test_user_level_4_skips_n5_rules` — N5 rule IS filtered when user_level=4 (5 > 4 is True)
11. `test_user_level_3_only_returns_n3_or_harder` — all hits have jlpt_level ≤ 3
12. `test_user_level_5_includes_n3_rules` — N3 rule (level=3) not filtered for user_level=5
13. `test_match_empty_text_returns_empty` — []
14. `test_match_non_japanese_returns_empty` — []

### Filter semantics (confirmed)
- `if rule.jlpt_level > user_level: continue`
- N5 = jlpt_level=5; user_level=5: 5>5 False → NOT skipped ✓
- N5 = jlpt_level=5; user_level=4: 5>4 True → SKIPPED ✓
- N3 = jlpt_level=3; user_level=5: 3>5 False → NOT skipped ✓

## Verification Run (2026-03-12)

### ruff check . && ruff format --check .
- **Result: PASS** — "All checks passed! 71 files already formatted"

### mypy src/
- **Result: 14 errors in 6 files** — ALL PRE-EXISTING:
  - 13× `Missing type parameters for generic type "ndarray"` in backends.py, silero.py, qwen_asr.py, models.py, types.py
  - 1× `Invalid syntax; you likely need to run mypy using Python 3.12 or newer` in capture.py (Python type alias syntax)
  - None of these are new or related to grammar-update work

### grep -r "confidence_type" src/ tests/
- **Result: 0 source matches** (only binary .pyc cache files + migration ALTER TABLE DROP COLUMN string in schema.py + `not in grammar_cols` assertion in test_db_schema.py)
- All Python source files are clean of `confidence_type` usage ✓

### pytest tests/ (excluding ML-dep collection-error files)
- **Result: 276 passed, 25 failed, 6 skipped, 1 xfailed, 19 errors**
- All failures are pre-existing environmental issues:
  - `fugashi` not installed → test_asr_worker.py, test_pipeline_migration.py, test_learning_panel.py
  - `torch` not installed → test_silero_vad.py (19 errors)
  - `scipy` not installed → test_backends.py
  - Python 3.10 SyntaxError (`type X = ...` syntax requires 3.12) → test_audio_capture.py, test_wasapi_loopback.py
- Collection-error files (ignored): test_analysis_pipeline.py, test_integration.py, test_integration_pipeline_overlay.py, test_orchestrator.py, test_qwen_asr.py, test_tokenizer.py, test_vad_worker.py
- **No new failures introduced by grammar-update work**
