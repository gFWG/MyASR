# Issues — m4-ui-overlay

## [2026-03-06] Known Pre-existing Issues (NOT to fix in M4)
- src/analysis/complexity.py: AppConfig missing complexity_* attributes — not our module
- tests/test_tokenizer.py: fugashi.Tagger not found — pre-existing
- tests/test_complexity.py: constructor param error — pre-existing

## [2026-03-06] Important Gotchas
- Position fields on VocabHit/GrammarHit are runtime-only; do NOT persist to DB
- Task 2b preferred approach: pass text= to find_beyond_level(), use text.find() with search_start
- Task 3: repository.insert_sentence() must return tuple[int, list[int], list[int]] not bare int
- All Qt tests need QT_QPA_PLATFORM=offscreen
