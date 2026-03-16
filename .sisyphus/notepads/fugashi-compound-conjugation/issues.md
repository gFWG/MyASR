# Issues — fugashi-compound-conjugation

## [2026-03-16] Session start

### Pre-existing Issues
- `src/analysis/tokenizer.py` has LSP errors: "Tagger" not a known attribute of fugashi
  - This is a pre-existing type-stub issue, NOT something we introduced
  - Do NOT modify the import approach — it works at runtime via lazy import pattern
