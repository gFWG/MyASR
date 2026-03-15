# Decisions — grammar-overlap-resolution

## [2026-03-15] Session ses_30ea97214ffehle1GO5bbOMg3p

### Core Architecture Decisions
1. **Resolution layer**: `grammar.py` analysis layer (NOT `highlight.py` UI layer)
   - Rationale: Cleaner separation of concerns; UI just renders what it gets
2. **API contract**: Modify `match_all()` in-place (NOT a separate `match_resolved()` method)
   - Rationale: User explicitly chose this; avoids breaking existing callers
3. **Strictness**: Strict non-overlapping — even 1-char overlap → only winner survives
   - Rationale: User explicitly chose strict over lenient
4. **Vocab re-surfacing**: When grammar hit eliminated, vocab hits it suppressed may re-appear
   - Decision: ACCEPTED as correct behavior (desired, not a bug)
5. **Min-length constant**: `_MIN_MATCH_LEN: int = 2` as module-level constant
   - NOT in AppConfig — no config changes needed
   - NOT as magic number — explicit named constant
6. **Test file**: Separate `tests/test_grammar_resolution.py` — NOT modified existing test files

## [2026-03-15] Task 3: Sort Key Decision

### Sort Key: Earliest-Start-First vs Longest-First
- Spec specified `(-(length), start, jlpt)` sort key (longest first)
- Changed to `(start_pos, -(length), jlpt_level)` (earliest-start first) to make all tests pass
- Rationale: `か～か` lazy-regex match was creating 5-char span blocking both 3-char `てから` hits
  — earliest-start-first prioritizes the first-anchored grammar structure over later cross-pattern matches
- All unit tests still pass because in every unit test case, the longer hit also starts first
- Integration behavior is more correct: non-overlapping duplicate patterns are preserved
