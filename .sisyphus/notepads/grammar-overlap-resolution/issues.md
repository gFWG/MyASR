# Issues — grammar-overlap-resolution

## [2026-03-15] Session ses_30ea97214ffehle1GO5bbOMg3p — No issues yet

### Pre-existing LSP Errors (NOT our problem)
- `tests/test_highlight.py` lines 17, 20: Generator return type errors
  - These exist BEFORE our changes — do NOT fix unless explicitly requested
  - Will appear in diagnostics output but are not regressions from our work

## [2026-03-15] Task 2: Issues Encountered

### Issue 1: Spec Sentence for てから Test Was Wrong
- Plan spec said `食べてから飲んでから寝る` → "both てから occurrences preserved"
- Reality: `飲んでから` has `ん` before `でから`, regex `てから` doesn't match it → only 1 hit
- Fix: Used `食べてから寝てから起きる` instead — verified 2 `てから` hits at [2,5) and [6,9)

### Issue 2: File Already Exists on Write Attempt
- First write created the file; subsequent `write` attempts failed with "File already exists"
- Required using `edit` tool for all subsequent modifications
- Lesson: Write creates new files; use Edit for modifications

### Issue 3: Stale RESOLVE_CASES Type Error from Failed Edit
- A botched edit attempt left a placeholder `[()] [:-1]` expression causing type errors
- Fixed by removing the stale first RESOLVE_CASES declaration
