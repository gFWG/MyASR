# Learnings — fugashi-compound-conjugation

## [2026-03-16] Session start

### Codebase Patterns
- Package: `src` (imports as `from src.xxx import ...`)
- Python 3.12, pytest with `pythonpath = ["."]`
- Ruff linting (line-length=99, double quotes), mypy strict
- Token dataclass in `src/models.py` — currently has surface, lemma, pos fields
- FugashiTokenizer in `src/analysis/tokenizer.py` — uses UnidicFeatures26
- PreprocessingPipeline in `src/analysis/pipeline.py`
- JLPTVocabLookup in `src/analysis/jlpt_vocab.py`
- LSP shows existing errors in tokenizer.py: "Tagger" not a known attribute of fugashi (pre-existing, not our issue)

### Key Architecture
- Pipeline flow: tokenize → (will add: merge_prefix_compounds) → find_all_vocab → grammar match
- VocabHit has: surface, lemma, pos, jlpt_level, start_pos, end_pos
- AnalysisResult has: tokens, vocab_hits, grammar_hits
- Token: currently (surface, lemma, pos) — adding pos2, cType, cForm with defaults

### Critical Decisions (from plan)
- Surface concatenation (NOT lemma) for compound lookup
- pos == "接頭辞" triggers compound detection (NOT hardcoded お/ご chars)
- MAX_COMPOUND_TOKENS = 6
- Chain: ONLY 助動詞 and surface in {"て","で"} for continuation
- NO 動詞/非自立可能 or 形容詞/非自立可能 in chain (grammar layer handles)
- VocabHit.lemma stays as base form (e.g., 続ける) — only surface and end_pos modified
- Compound-wins exclusively: suppress standalone component matches

## Task 2: UniDic field extraction (2026-03-16)

- `word.feature.pos2`, `word.feature.cType`, `word.feature.cForm` all may be `None` — use `or ""` shorthand
- `食べる` → `cType="下一段-バ行"`, `cForm="終止形-一般"` — UniDic distinguishes verb class and inflection form
- `させる` auxiliary gets `cType="下一段-サ行"` — causative auxiliary is separately typed
- `pos2` for 動詞一般 is `"一般"`, for 助動詞 it may be `"*"` (asterisk = undefined)
- Prefix `お` in `お世辞` correctly gets `pos1="接頭辞"` with unidic-lite
- Pre-existing LSP errors: `"Tagger" is not a known attribute of module "fugashi"` — type stubs issue, not real

## Task 3: TDD RED Phase (2026-03-16)

### Test file pattern
- `tests/test_compound_merging.py` — 13 tests, 12 fail, 1 passes (regression guard)
- `@pytest.fixture(scope="module")` for `pipeline` fixture matches `test_analysis_pipeline.py`
- ご飯 (AC3 regression guard) already passes in RED — ご飯 is a single fugashi token

### Current pipeline behavior (pre-implementation)
- `pipeline.process("お世辞を言う").vocab_hits` surfaces = `['お', '世辞', '言う']`
- `世辞` VocabHit IS returned standalone (needs suppression after compound merging)
- `pipeline.process("お世辞").tokens` = `[Token('お','接頭辞'), Token('世辞','名詞')]`
- `お` has an independent VocabHit (needs investigation — it shouldn't be meaningful alone)

### Ruff style
- Section-divider comments `# ---...---` accepted by ruff without issue
- f-strings in assertions (error messages) — fine

## F4 Scope Fidelity Check (2026-03-16)

### Scope Audit Result: APPROVED

**Commit messages match plan exactly** (6 commits, correct convention):
1. feat(models): add pos2, cType, cForm fields to Token with defaults
2. feat(tokenizer): extract pos2, cType, cForm from UniDic features
3. test(compound): add failing tests for prefix-compound merging (TDD RED)
4. feat(analysis): implement prefix-compound merging with greedy longest-match
5. test(chain): add failing tests for conjugation chain extension (TDD RED)
6. feat(chain): implement conjugation chain extension (TDD GREEN)

**Changed files**: All expected + one acceptable addition:
- `src/models.py` ✅
- `src/analysis/tokenizer.py` ✅
- `src/analysis/jlpt_vocab.py` ✅
- `src/analysis/pipeline.py` ✅
- `tests/test_compound_merging.py` (new) ✅
- `tests/test_chain_extension.py` (new) ✅
- `tests/test_tokenizer.py` — 2 tests added for new Token fields (Task 2 coverage) — MINOR SCOPE ADDITION but clearly related
- `.sisyphus/evidence/` files ✅

**Forbidden files**: grammar.py, highlight.py, tooltip.py — ALL EMPTY DIFFS ✅

**Algorithm constraints all verified**:
1. Compound trigger uses `pos == "接頭辞"` (POS-based, not character matching) ✅
2. Chain continuation: ONLY `助動詞` OR surface in `{"て","で"}` ✅
3. Chain NEVER creates new VocabHits — only replaces existing via `hits[-1] = VocabHit(...)` ✅
4. VocabHit.lemma never modified — all replacements use `lemma=hit.lemma` ✅
5. 動詞/非自立可能 excluded — chain only continues through `助動詞` pos, so any `動詞` stops it ✅
6. No hardcoded お/ご in compound detection ✅
7. No 接続助詞 in chain logic ✅
8. Compound lookup uses surface concatenation (`surface in vocab`), not lemma ✅
9. TDD RED commits contain only test files (no implementation smuggled) ✅
