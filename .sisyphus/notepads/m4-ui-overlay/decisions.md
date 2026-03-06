# Decisions — m4-ui-overlay

## [2026-03-06] Initial Decisions

### Wave 1 Parallelization
- Task 1 (models) must run first, alone
- Tasks 2a and 2b can run in parallel AFTER Task 1
- Task 2c runs after both 2a and 2b complete
- All Wave 1 tasks commit together in a single commit

### Wave 2 Parallelization  
- Tasks 3 (pipeline) and 4 (HighlightRenderer) can run in parallel
- Task 5 (OverlayWindow) runs after BOTH 3 and 4 complete

### Wave 3 Parallelization
- Tasks 6 (TooltipPopup) and 7 (main.py) can run in parallel
- Task 7 only needs src/ui/overlay.py and src/ui/tooltip.py to exist

### Commits
- Wave 1: single commit grouping tasks 1+2a+2b+2c
- Each Wave 2/3 task: individual commits
- Pre-commit hook: `ruff check . && mypy . && pytest -x`
