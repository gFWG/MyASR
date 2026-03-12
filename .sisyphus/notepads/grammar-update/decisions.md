# Grammar-Update: Decisions

## 2026-03-12 Session Init

### Schema decisions
- `HighlightGrammar.confidence_type: str` → REMOVED
- `HighlightGrammar.word: str | None` → ADDED (nullable because old DB rows won't have it)
- `GrammarHit.confidence_type: str` → REMOVED  
- `GrammarHit.word: str` → ADDED (non-nullable for new hits)

### Commit strategy (7 commits total)
1. Task 1 (fix grammar.json regex)
2. Task 2 (models.py)
3. Tasks 4+7 (grammar.py rewrite + pipeline.py path change)
4. Tasks 5+6 (DB schema migration + analysis_worker.py)
5. Tasks 3+8+9 (config N5 colors + ui tooltip + ui highlight)
6. Tasks 11+12 (rewrite test_grammar.py + update 6 test files)
7. Task 10 (delete grammar_rules.json)
