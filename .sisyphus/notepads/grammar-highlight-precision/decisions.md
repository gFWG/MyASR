# Decisions

## 2026-03-15 — Session Start

### matched_parts field
- Type: `tuple[tuple[int, int], ...]` (immutable, hashable)
- Default: `()` (empty = fallback to full range highlighting)
- Placement: After `end_pos` in `GrammarHit` dataclass

### Hover detection
- Multi-part: only keyword parts trigger tooltip; filler text is inert
- Fallback (empty matched_parts): entire range triggers tooltip (backward compat)

### Vocab suppression
- Multi-part: vocab suppressed only if within a keyword part span
- Fallback: vocab suppressed if within full grammar range (unchanged)
- Implementation: `_is_fully_covered()` unchanged — upstream span-building handles it

### Tooltip title
- Old: `hit.matched_text` (full matched string, e.g., "がとてもきれいなら")
- New: `hit.word` (grammar pattern name, e.g., "が...なら")

### Scope guardrails
- NO grammar JSON changes
- NO VocabHit/AnalysisResult/SentenceResult changes
- NO pipeline/signal changes
- NO tooltip redesign
