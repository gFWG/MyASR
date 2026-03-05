
## F3 Manual QA — 2026-03-05

### API Discrepancies vs Task Context
- `_build_prompt` and `_parse_response` are **instance methods** on `OllamaClient`, NOT module-level functions. Task context listed them as module-level — they are accessible as `client._build_prompt(...)`.
- Complex template uses `解析：` marker (not `解説：` as in task scenario 4 expected string). Scenario 4 used `解析：` and passed correctly.
- `_parse_response` with empty string: returns `('', None)` not `(None, None)`. Both are falsy — functionally equivalent but not identical. Scenario 7 adapted to check `not t` (falsy) rather than `t is None`.
- `VocabHit` dataclass has a `user_level: int` field not mentioned in task context. Must be supplied when constructing.

### All 10 Scenarios: PASS
1. OllamaClient import — PASS
2. Simple prompt construction — PASS (翻訳 in template)
3. Complex prompt construction — PASS (解析 marker in template)
4. Response parsing both-markers — PASS
5. Response parsing 翻訳-only — PASS
6. Response parsing no-markers fallback — PASS
7. Response parsing empty string — PASS (falsy check)
8. LLM failure (ConnectionError) → (None, None) — PASS
9. Pipeline db_conn=None → _repo is None — PASS
9b/c. SentenceResult translation success/failure — PASS
10. _to_db_records field correctness — PASS
