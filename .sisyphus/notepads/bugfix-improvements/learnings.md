# Learnings — bugfix-improvements

## [2026-03-09] Session: ses_32d3f026fffe4Ouyt2D97O4BbR
Plan initialized. Key conventions to follow:
- Working directory: /home/yuheng/MyASR-bugfix-improvements (worktree)
- All files are in `src/` (flat structure: src/audio, src/vad, src/asr, etc.)
- Tests mirror src/ in `tests/`
- Run tests: `pytest -x --tb=short`
- Lint: `ruff check . && ruff format --check .`
- Type check: `mypy .`
- Evidence dir: `.sisyphus/evidence/`
- Source of truth for plan: `.sisyphus/plans/bugfix-improvements.md`
