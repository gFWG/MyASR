# Decisions — vocabulary-csv-migration

## 2026-03-11 Session ses_322eaefc6ffevPScOWx3LrQ1Sp

### T0: Create vocabulary.csv
- NOT needed — data/vocabulary.csv already exists with 8293 rows
- T0 checkboxes can be marked complete immediately

### Duplicate Lemma Resolution
- Keep easiest level (highest N-number integer) when multiple CSV rows share same lemma
- Deterministic ordering: sort by level descending to overwrite with easiest

### Dash-stripping
- Fugashi produces 私-代名詞 style lemmas
- Strip after '-' BEFORE CSV lookup: `lemma.split('-')[0]`

### Empty Definition Handling
- 48 entries have empty definition field
- In UI: omit definition display entirely (no placeholder text)

### VocabEntry Storage Structure
- Use `dict[str, VocabEntry]` keyed by lemma for O(1) lookup
- Old `dict[str, int]` becomes `dict[str, VocabEntry]`

### backward compatibility
- `lookup(lemma: str) -> int | None` must still exist (returns entry.level)
- New method: `lookup_entry(lemma: str) -> VocabEntry | None` returns full entry

### CSV path hardcoded
- Path stays as `'data/vocabulary.csv'` matching project convention
