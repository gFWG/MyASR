# Decisions — fugashi-compound-conjugation

## [2026-03-16] Session start

### Algorithm Decisions
- Greedy longest-match (MAX_COMPOUND_TOKENS=6) for compound detection
- index-based while loop in find_all_vocab() (not for-each) — needed for skip-consumed-tokens
- Chain extension mutates VocabHit.surface and VocabHit.end_pos (plain dataclass, mutable)
- merge_prefix_compounds needs vocab dict access → add public `vocab_entries` property to JLPTVocabLookup

### TDD Flow
- Task 3: RED (write failing tests for compound merging)
- Task 4: GREEN (implement compound merge)
- Task 5: RED (write failing tests for chain extension)
- Task 6: GREEN (implement chain extension)
