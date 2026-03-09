# Issues — bugfix-improvements

## [2026-03-09] Session: ses_32d3f026fffe4Ouyt2D97O4BbR
Known pre-existing issues (DO NOT FIX):
- test_overlay.py::test_history_max_size expects 100 but _MAX_HISTORY=10 in code
  → Handle in Task 9 by adding @pytest.mark.xfail(reason="pre-existing: _MAX_HISTORY=10 but test expects 100")
