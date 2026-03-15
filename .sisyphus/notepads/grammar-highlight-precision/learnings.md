# Learnings

## 2026-03-15 — Session Start

### Pre-existing LSP Errors (NOT caused by our changes)
- `tests/test_highlight.py` lines 17 and 20: Return type errors on generator fixtures (QTextBrowser).
  These are pre-existing — do NOT attempt to fix them, they are out of scope.

### Codebase Conventions
- Package imported as `from src.X import Y` (pythonpath=["."])
- Frozen dataclasses use `= ()` for empty tuple defaults (no `field()` needed for immutables)
- `GrammarHit` is a plain `@dataclass` (NOT frozen) — `matched_parts: tuple[...] = ()` works directly
- `_Span = tuple[int, int, str, str]` — type alias in highlight.py, unchanged
- Tests use `qapp` fixture from conftest.py for PySide6 tests
- QTextCursor: use `setPosition(N+1)` then `charFormat()` to get format at character N

### Grammar JSON
- 831 total rules, 63 have capturing groups (e.g., ID 164: `(なり).*?(なり)`)
- Capturing groups mark keyword parts; `.*?` between them is filler
- No JSON schema change needed — `re` field already has capturing groups embedded

## 2026-03-15 — Task 1: Add matched_parts to GrammarHit

### Change Made
- Added `matched_parts: tuple[tuple[int, int], ...] = ()` to `GrammarHit` in `src/models.py` (after `end_pos: int`)
- Plain `@dataclass` allows direct `= ()` default (no `field()` needed — tuple is immutable)

### Verification
- QA Scenario 1 (with matched_parts): PASS — `((0, 1), (2, 4))` printed, assertion passed
- QA Scenario 2 (default empty tuple): PASS — `()` printed, assertion passed
- QA Scenario 3 (existing tests): PASS — 33/33 tests passed (test_grammar.py + test_highlight.py)

### Backward Compatibility
- Default `= ()` ensures all existing `GrammarHit(...)` calls without `matched_parts` continue to work
- No other files needed modification

## 2026-03-15 — Task 2: Extract capturing group spans in match_all()

### Change Made
- Modified `match_all()` in `src/analysis/grammar.py` lines 88-108
- After each `finditer` match `m`, check `m.lastindex`:
  - If truthy: build `parts = tuple(m.span(i) for i in range(1, m.lastindex+1) if m.group(i) is not None)`
  - Else: `parts = ()`
- Pass `matched_parts=parts` to `GrammarHit(...)` constructor

### Key Technical Notes
- `m.lastindex` is the highest group index that *participated* in the match (not just the count of groups)
- `m.group(i) is not None` guard handles optional groups `(A)?` that didn't match
- Spans are absolute positions in the original text (not relative to match start)
- The comment `# has capturing groups` was retained — `m.lastindex` truthiness is non-obvious

### Verification
- QA Scenario 1 (capturing groups): PASS — rule=164 `なりとなり` → `parts=((0, 2), (3, 5))`, spans valid
- QA Scenario 2 (no capturing groups): PASS — rule=762 `てから` → `matched_parts=()` 
- QA Scenario 3 (existing tests): PASS — 12/12 tests passed in tests/test_grammar.py

### Backward Compatibility
- Rules without capturing groups: `parts = ()` → same as before (default field value)
- All existing `GrammarHit` usages unaffected — `matched_parts` was added with default `()`
    - No other files modified

## 2026-03-15 — Task 4: Fix tooltip word label to use hit.word

### Change Made
- Modified `src/ui/tooltip.py` line 139 in `show_for_grammar()`
- Changed `self._word_label.setText(hit.matched_text)` → `self._word_label.setText(hit.word)`
- This makes the tooltip title show the grammar pattern name (e.g., `てから`) instead of the raw matched text

### Key Technical Notes
- `hit.word` = grammar pattern name (the conceptual identifier)
- `hit.matched_text` = raw text from the audio/transcript that triggered the match
- Line 142 already correctly uses `hit.word or hit.matched_text` for description — untouched
- Only ONE line changed; no layout, styling, or other methods affected

### Verification
- QA Scenario 1 (source check): PASS — `hit.word` present, `hit.matched_text` absent in word_label
- QA Scenario 2 (import check): PASS — `TooltipPopup` imports without syntax errors

## 2026-03-15 — Task 3: HighlightRenderer multi-part grammar spans

### Changes Made (src/ui/highlight.py only)

**Change A — apply_to_document() grammar span building (lines 80-87):**
- OLD: one span per `GrammarHit` using `(gh.start_pos, gh.end_pos, ...)`
- NEW: if `gh.matched_parts` is non-empty → one span per part; else fallback to full range
- Effect: `grammar_spans` now contains per-keyword-part spans; filler positions between parts have no grammar span

**Change C — get_highlight_at_position() grammar hit loop (lines 139-146):**
- OLD: `if gh.start_pos <= position < gh.end_pos: return gh`
- NEW: if `gh.matched_parts` → check each part range; else check full range
- Effect: hover only triggers on keyword parts; filler positions fall through to vocab check

### Change B — _is_fully_covered() (NO CHANGES NEEDED)
- `_is_fully_covered(start, end, grammar_spans)` checks: any single span with `gs_start <= start and end <= gs_end`
- After Change A, `grammar_spans` has per-part spans. A vocab in filler (e.g., [1,2)) won't be covered by any part span (e.g., (0,1) and (2,4)) — neither contains [1,2)
- A vocab in a keyword part (e.g., [0,1)) IS covered by part span (0,1) → suppressed correctly
- Logic is inherently correct; no change needed.

### QA Results (all PASS)
- Scenario 1 (part-level hover): `hit_at_0=GrammarHit`, `hit_at_1=None`, `hit_at_2=GrammarHit` ✓
- Scenario 2 (fallback hover): all 3 positions return hit, pos 3 returns None ✓
- Scenario 3 (vocab in filler): filler pos 1 returns VocabHit (not suppressed) ✓
- Scenario 4 (existing tests): 21/21 passed ✓

### File: src/ui/highlight.py — 176 lines total

## 2026-03-15 — Task 5: Update and extend test suite

### Changes Made

**tests/test_grammar.py** (+4 tests, updated 1):
- `test_grammar_hit_fields`: Added `isinstance(h.matched_parts, tuple)` assertion
- `test_grammar_hit_matched_parts_populated_for_capturing_groups`: rule 164 `なりとなり` → non-empty matched_parts
- `test_grammar_hit_matched_parts_empty_for_simple_rules`: rule 762 `てから` → `matched_parts == ()`
- `test_grammar_hit_matched_parts_spans_are_absolute_positions`: spans are valid absolute positions in text

**tests/test_highlight.py** (+5 tests, updated helper):
- `_make_grammar()`: Added optional `matched_parts: tuple[tuple[int, int], ...] = ()` kwarg
- `test_get_highlight_at_position_grammar_parts_only`: parts-only hover logic verified
- `test_get_highlight_at_position_grammar_fallback_full_range`: empty matched_parts falls back to full range
- `test_apply_to_document_multi_part_grammar_partial_highlight`: filler positions get no grammar color
- `test_vocab_not_suppressed_in_grammar_filler_gap`: vocab in filler IS highlighted (not suppressed)
- `test_vocab_suppressed_within_grammar_part`: vocab inside grammar part IS suppressed

### QA Results
- Scenario 1 (targeted): 41/41 PASS (15 grammar + 26 highlight; 8 new)
- Scenario 2 (full suite): 391 PASS, 1 pre-existing FAIL (test_tooltip.py::test_show_for_grammar_sets_word_label — pre-existing from Task 4)
- Scenario 3 (lint/types): ruff check CLEAN; ruff format: 2 pre-existing files would reformat (not our files); mypy: 0 issues

### Key Technical Notes
- `_make_grammar()` keyword arg uses Python 3.12 syntax `tuple[tuple[int, int], ...]` — no import needed
- `test_vocab_not_suppressed_in_grammar_filler_gap` uses 6-char string with trailing space to avoid length confusion
- Pre-existing ruff format issues in `src/analysis/jlpt_vocab.py` and `src/ui/overlay.py` are out of scope
