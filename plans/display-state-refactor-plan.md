# Display State Refactor Plan

## Overview

Refactor the data flow to separate "raw analysis data" from "display filtering logic", ensuring:

1. Rendering and hover detection use the same data source
2. Config changes (JLPT level, enable_*) take effect immediately
3. Historical records respond to config changes

## Current Problems

| Problem | Root Cause |
|---------|------------|
| Tooltip triggers after disabling highlights | Hover detection uses `result.analysis` directly |
| JLPT level change doesn't affect existing sentences | `VocabHit.user_level` baked in at analysis time |
| JLPT level change doesn't affect new sentences | `PreprocessingPipeline._config` not updated |

## Architecture Change

```
Before (Problem):
  Analysis: find_beyond_level(user_level=3) → Only N1/N2 vocab → Baked into SentenceResult
  Config change: user_level=4 → SentenceResult still has N1/N2 → Cannot change

After (Solution):
  Analysis: find_all_vocab() → All vocab with levels → Store complete data
  Display: get_display_hits(user_level=4) → Runtime filter → Immediate response
```

## Implementation Steps

### Phase 1: Data Model Changes

#### 1.1 Modify `VocabHit` (src/db/models.py)

```python
# Before
@dataclass
class VocabHit:
    surface: str
    lemma: str
    pos: str
    jlpt_level: int
    user_level: int  # ← REMOVE
    start_pos: int
    end_pos: int
    vocab_id: int = 0
    pronunciation: str = ""
    definition: str = ""

# After
@dataclass
class VocabHit:
    surface: str
    lemma: str
    pos: str
    jlpt_level: int
    start_pos: int
    end_pos: int
    vocab_id: int = 0
    pronunciation: str = ""
    definition: str = ""
```

#### 1.2 Modify `HighlightVocab` (src/db/models.py)

```python
# Before
@dataclass
class HighlightVocab:
    id: int | None
    sentence_id: int
    surface: str
    lemma: str
    pos: str
    jlpt_level: int | None
    is_beyond_level: bool  # ← REMOVE
    tooltip_shown: bool
    vocab_id: int = 0
    pronunciation: str = ""
    definition: str = ""

# After
@dataclass
class HighlightVocab:
    id: int | None
    sentence_id: int
    surface: str
    lemma: str
    pos: str
    jlpt_level: int | None
    tooltip_shown: bool
    vocab_id: int = 0
    pronunciation: str = ""
    definition: str = ""
```

#### 1.3 Modify `HighlightGrammar` (src/db/models.py)

```python
# Before
@dataclass
class HighlightGrammar:
    id: int | None
    sentence_id: int
    rule_id: str
    pattern: str
    word: str | None
    jlpt_level: int | None
    description: str | None
    is_beyond_level: bool  # ← REMOVE
    tooltip_shown: bool

# After
@dataclass
class HighlightGrammar:
    id: int | None
    sentence_id: int
    rule_id: str
    pattern: str
    word: str | None
    jlpt_level: int | None
    description: str | None
    tooltip_shown: bool
```

#### 1.4 Add `get_display_hits()` to `SentenceResult` (src/db/models.py)

```python
@dataclass
class SentenceResult:
    japanese_text: str
    analysis: AnalysisResult
    created_at: datetime = field(default_factory=datetime.now)
    sentence_id: int | None = None
    highlight_vocab_ids: list[int] | None = None
    highlight_grammar_ids: list[int] | None = None

    def get_display_analysis(
        self,
        user_level: int,
        enable_vocab: bool = True,
        enable_grammar: bool = True,
    ) -> AnalysisResult:
        """Return filtered analysis based on current user config.

        This is the SINGLE SOURCE OF TRUTH for both rendering and hover detection.

        Filter logic:
        - Vocab: show where jlpt_level < user_level (harder than user)
        - Grammar: show where jlpt_level <= user_level (user level and below)

        Args:
            user_level: User's current JLPT level (1-5, where 1=N1 hardest).
            enable_vocab: Whether to include vocab hits.
            enable_grammar: Whether to include grammar hits.

        Returns:
            AnalysisResult with filtered vocab_hits and grammar_hits.
        """
        if self.analysis is None:
            return AnalysisResult(tokens=[], vocab_hits=[], grammar_hits=[])

        vocab_hits = []
        if enable_vocab:
            vocab_hits = [
                h for h in self.analysis.vocab_hits
                if h.jlpt_level < user_level
            ]

        grammar_hits = []
        if enable_grammar:
            grammar_hits = [
                h for h in self.analysis.grammar_hits
                if h.jlpt_level <= user_level
            ]

        return AnalysisResult(
            tokens=self.analysis.tokens,
            vocab_hits=vocab_hits,
            grammar_hits=grammar_hits,
        )
```

---

### Phase 2: Analysis Layer Changes

#### 2.1 Modify `JLPTVocabLookup.find_beyond_level()` → `find_all_vocab()` (src/analysis/jlpt_vocab.py)

```python
def find_all_vocab(
    self, tokens: list[Token], text: str = ""
) -> list[VocabHit]:
    """Find all JLPT vocabulary in tokens.

    Returns ALL vocab matches with their JLPT levels, without filtering by user level.
    Display-time filtering should use SentenceResult.get_display_analysis().

    Args:
        tokens: List of Token objects to check.
        text: Original text for calculating character positions.

    Returns:
        List of VocabHit for all words found in vocabulary.
    """
    hits: list[VocabHit] = []
    search_start = 0
    for token in tokens:
        clean_lemma = token.lemma.split("-")[0]
        entry = self.lookup_entry(clean_lemma)
        if entry is not None:
            if text:
                pos = text.find(token.surface, search_start)
                if pos >= 0:
                    start_pos = pos
                    end_pos = start_pos + len(token.surface)
                    search_start = end_pos
                else:
                    start_pos = 0
                    end_pos = 0
            else:
                start_pos = 0
                end_pos = 0
            hits.append(
                VocabHit(
                    surface=token.surface,
                    lemma=token.lemma,
                    pos=token.pos,
                    jlpt_level=entry.level,
                    start_pos=start_pos,
                    end_pos=end_pos,
                    vocab_id=entry.vocab_id,
                    pronunciation=entry.pronunciation,
                    definition=entry.definition,
                )
            )
    return hits
```

#### 2.2 Modify `GrammarMatcher.match()` → `match_all()` (src/analysis/grammar.py)

```python
def match_all(self, text: str) -> list[GrammarHit]:
    """Find all grammar patterns in text.

    Returns ALL grammar matches with their JLPT levels, without filtering by user level.
    Display-time filtering should use SentenceResult.get_display_analysis().

    Args:
        text: Japanese text to analyze.

    Returns:
        List of GrammarHit for all patterns found.
    """
    if not text:
        return []
    hits: list[GrammarHit] = []
    for rule in self._rules:
        for m in rule.pattern.finditer(text):
            hits.append(
                GrammarHit(
                    rule_id=rule.rule_id,
                    word=rule.word,
                    matched_text=m.group(),
                    jlpt_level=rule.jlpt_level,
                    description=rule.description,
                    start_pos=m.start(),
                    end_pos=m.end(),
                )
            )
    return hits
```

#### 2.3 Modify `PreprocessingPipeline` (src/analysis/pipeline.py)

Remove `_config` entirely since it's no longer needed:

```python
class PreprocessingPipeline:
    """Orchestrates Japanese text analysis: tokenize → vocab → grammar.

    Shares a single fugashi.Tagger via FugashiTokenizer.
    """

    def __init__(self) -> None:
        """Initialize all pipeline components.

        Note: No config needed - analysis returns ALL matches, filtering happens at display time.
        """
        self._tokenizer = FugashiTokenizer()
        self._vocab_lookup = JLPTVocabLookup("data/vocabulary.csv")
        self._grammar_matcher = GrammarMatcher("data/grammar.json")

    def process(self, text: str) -> AnalysisResult:
        """Run the full analysis pipeline on a Japanese text.

        Returns ALL vocab and grammar matches without filtering.
        Display-time filtering is handled by SentenceResult.get_display_analysis().

        Args:
            text: Japanese text to analyse (may be empty).

        Returns:
            AnalysisResult with tokens, vocab_hits, and grammar_hits.
        """
        start = time.perf_counter()

        tokens = self._tokenizer.tokenize(text)
        vocab_hits = self._vocab_lookup.find_all_vocab(tokens, text=text)
        grammar_hits = self._grammar_matcher.match_all(text)

        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.debug("Pipeline processed %d chars in %.1f ms", len(text), elapsed_ms)

        return AnalysisResult(
            tokens=tokens,
            vocab_hits=vocab_hits,
            grammar_hits=grammar_hits,
        )
```

**Changes**:
- Removed `config: AppConfig` parameter from `__init__`
- Removed `self._config` attribute
- Removed import of `AppConfig` (no longer needed)

---

### Phase 3: Pipeline Worker Changes

#### 3.1 Modify `AnalysisWorker._process_one()` (src/pipeline/analysis_worker.py)

```python
def _process_one(self, asr_result: ASRResult, db_repo: LearningRepository) -> None:
    """Process a single ASRResult: analyse, persist, emit.

    Args:
        asr_result: The transcription result to process.
        db_repo: Thread-local repository for DB persistence.
    """

    analysis = self._analysis_pipeline.process(asr_result.text)

    # Build SentenceRecord
    record = SentenceRecord(
        id=None,
        japanese_text=asr_result.text,
        source_context=asr_result.segment_id,
        created_at=datetime.now().isoformat(),
    )

    # Build highlight lists from AnalysisResult
    # Note: Store ALL vocab/grammar hits, filtering happens at display time
    vocab_highlights = [
        HighlightVocab(
            id=None,
            sentence_id=0,  # will be assigned by DB
            surface=hit.surface,
            lemma=hit.lemma,
            pos=hit.pos,
            jlpt_level=hit.jlpt_level,
            tooltip_shown=False,
            vocab_id=hit.vocab_id,
            pronunciation=hit.pronunciation,
            definition=hit.definition,
        )
        for hit in analysis.vocab_hits
    ]

    grammar_highlights = [
        HighlightGrammar(
            id=None,
            sentence_id=0,  # will be assigned by DB
            rule_id=hit.rule_id,
            pattern=hit.word,
            word=hit.word,
            jlpt_level=hit.jlpt_level,
            description=hit.description,
            tooltip_shown=False,
        )
        for hit in analysis.grammar_hits
    ]

    # Persist and get auto-assigned IDs
    sentence_id, vocab_ids, grammar_ids = db_repo.insert_sentence(
        record, vocab_highlights, grammar_highlights
    )

    # Emit SentenceResult
    sentence_result = SentenceResult(
        japanese_text=asr_result.text,
        analysis=analysis,
        created_at=datetime.now(),
        sentence_id=sentence_id,
        highlight_vocab_ids=vocab_ids,
        highlight_grammar_ids=grammar_ids,
    )
    self.sentence_ready.emit(sentence_result)
    logger.debug(
        "Analysis complete for segment %s: sentence_id=%d, vocab=%d, grammar=%d",
        asr_result.segment_id,
        sentence_id,
        len(vocab_ids),
        len(grammar_ids),
    )
```

#### 3.2 Modify `PipelineOrchestrator.__init__()` (src/pipeline/orchestrator.py)

Update the creation of `PreprocessingPipeline` to not pass `AppConfig`:

```python
# Before (lines 78-89)
# ── Analysis worker (ASRResult → SentenceResult with DB persistence) ──
# AppConfig-based construction: PreprocessingPipeline needs AppConfig.
# We pass config dict; analysis pipeline uses user_jlpt_level.
_valid_keys = AppConfig.__dataclass_fields__.keys()
_app_config = AppConfig(**{k: v for k, v in config.items() if k in _valid_keys})
analysis_pipeline = PreprocessingPipeline(_app_config)
self._analysis_worker = AnalysisWorker(
    text_queue=self._text_queue,
    analysis_pipeline=analysis_pipeline,
    db_path=config.get("db_path", ":memory:"),
    config=config,
)

# After
# ── Analysis worker (ASRResult → SentenceResult with DB persistence) ──
# PreprocessingPipeline no longer needs AppConfig - filtering happens at display time.
analysis_pipeline = PreprocessingPipeline()
self._analysis_worker = AnalysisWorker(
    text_queue=self._text_queue,
    analysis_pipeline=analysis_pipeline,
    db_path=config.get("db_path", ":memory:"),
    config=config,
)
```

**Changes**:
- Removed `AppConfig` import and construction
- `PreprocessingPipeline()` now takes no arguments

---

### Phase 4: Display Layer Changes

#### 4.1 Modify `OverlayWindow._render_in_browser()` (src/ui/overlay.py)

```python
def _render_in_browser(self, browser: "QTextBrowser", result: SentenceResult) -> None:
    """Render a SentenceResult into the given browser widget.

    Uses SentenceResult.get_display_analysis() as the single source of truth.

    Args:
        browser: The QTextBrowser to render into.
        result: The sentence result to render.
    """
    doc = browser.document()

    if result.analysis is not None:
        # Use get_display_analysis() - SINGLE SOURCE OF TRUTH
        display_analysis = result.get_display_analysis(
            user_level=self._user_level,
            enable_vocab=self._enable_vocab,
            enable_grammar=self._enable_grammar,
        )
        self._renderer.apply_to_document(
            doc,
            result.japanese_text,
            display_analysis,
            user_level=self._user_level,
        )
    else:
        doc.setPlainText(result.japanese_text)

    # Center align all blocks
    cursor = QTextCursor(doc)
    cursor.select(QTextCursor.SelectionType.Document)
    block_fmt = QTextBlockFormat()
    block_fmt.setAlignment(Qt.AlignmentFlag.AlignCenter)
    cursor.setBlockFormat(block_fmt)
```

#### 4.2 Modify `OverlayWindow._handle_hover_at_viewport_pos()` (src/ui/overlay.py)

```python
def _handle_hover_at_viewport_pos(
    self,
    browser: "QTextBrowser",
    result: "SentenceResult | None",
    viewport_pos: QPoint,
) -> None:
    """Emit highlight_hovered for the highlighted word under the cursor.

    Uses SentenceResult.get_display_analysis() as the single source of truth,
    ensuring consistency with rendering.

    Args:
        browser: The browser widget in whose viewport the hover occurred.
        result: The SentenceResult currently displayed in that browser.
        viewport_pos: Mouse position in viewport-local coordinates.
    """
    if result is None or result.analysis is None:
        self.highlight_left.emit()
        return

    cursor = browser.cursorForPosition(viewport_pos)
    char_pos = cursor.position()

    # Use get_display_analysis() - SAME DATA SOURCE AS RENDERING
    display_analysis = result.get_display_analysis(
        user_level=self._user_level,
        enable_vocab=self._enable_vocab,
        enable_grammar=self._enable_grammar,
    )

    hit: VocabHit | GrammarHit | None = self._renderer.get_highlight_at_position(
        char_pos,
        display_analysis,
    )
    if hit is not None:
        global_pos = browser.viewport().mapToGlobal(viewport_pos)
        self.highlight_hovered.emit(hit, global_pos, result)
    else:
        self.highlight_left.emit()
```

---

#### 4.3 Modify `OverlayWindow.on_config_changed()` (src/ui/overlay.py)

Add re-rendering for preview browser when in BROWSE mode:

```python
def on_config_changed(self, config: AppConfig) -> None:
    """Apply live config changes to the overlay without restarting.

    Args:
        config: Updated application configuration.
    """
    self._config = config
    self.setWindowOpacity(config.overlay_opacity)
    self._user_level = config.user_jlpt_level
    self._enable_vocab = config.enable_vocab_highlight
    self._enable_grammar = config.enable_grammar_highlight

    # Update font on both widget and document for HTML content
    new_font = _make_font(config.overlay_font_size_jp)
    self._jp_browser.setFont(new_font)
    self._jp_browser.document().setDefaultFont(new_font)
    self._preview_browser.setFont(new_font)
    self._preview_browser.document().setDefaultFont(new_font)

    self._renderer.update_colors(jlpt_colors_to_renderer_format(config.jlpt_colors))

    # Resize history capacity
    self._history.resize(config.max_history)

    # Re-render current sentence in main browser
    if self._current_result is not None:
        self._render_result(self._current_result)

    # Re-render latest sentence in preview browser (if in BROWSE mode)
    # This ensures config changes affect both browsers immediately
    if self._preview_browser.isVisible() and self._history.latest is not None:
        self._render_in_browser(self._preview_browser, self._history.latest)

    # Adjust height if no content
    if self._current_result is None:
        QTimer.singleShot(0, self._adjust_height_to_content)

    self._update_arrow_visibility()

    logger.debug(
        "on_config_changed: opacity=%.2f user_level=%d jp_font=%d vocab=%s grammar=%s"
        " max_history=%d",
        config.overlay_opacity,
        config.user_jlpt_level,
        config.overlay_font_size_jp,
        config.enable_vocab_highlight,
        config.enable_grammar_highlight,
        config.max_history,
    )
```

**Key Changes**:
- Added re-render for `_preview_browser` when visible (BROWSE mode)
- Both main and preview browsers now respond to config changes immediately
- This matches the behavior of font changes which already affect both browsers

---

### Phase 5: Database Schema Migration

#### 5.1 Create Migration Script

Create a migration to remove `is_beyond_level` column:

```sql
-- Migration: Remove is_beyond_level column
-- Date: 2026-03-12

-- Step 1: Create new tables without is_beyond_level
CREATE TABLE highlight_vocab_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sentence_id INTEGER NOT NULL,
    surface TEXT NOT NULL,
    lemma TEXT NOT NULL,
    pos TEXT NOT NULL,
    jlpt_level INTEGER,
    tooltip_shown INTEGER NOT NULL DEFAULT 0,
    vocab_id INTEGER DEFAULT 0,
    pronunciation TEXT DEFAULT '',
    definition TEXT DEFAULT '',
    FOREIGN KEY (sentence_id) REFERENCES sentences(id) ON DELETE CASCADE
);

CREATE TABLE highlight_grammar_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sentence_id INTEGER NOT NULL,
    rule_id TEXT NOT NULL,
    pattern TEXT NOT NULL,
    word TEXT,
    jlpt_level INTEGER,
    description TEXT,
    tooltip_shown INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (sentence_id) REFERENCES sentences(id) ON DELETE CASCADE
);

-- Step 2: Copy data (excluding is_beyond_level)
INSERT INTO highlight_vocab_new 
    (id, sentence_id, surface, lemma, pos, jlpt_level, tooltip_shown, vocab_id, pronunciation, definition)
SELECT id, sentence_id, surface, lemma, pos, jlpt_level, tooltip_shown, vocab_id, pronunciation, definition
FROM highlight_vocab;

INSERT INTO highlight_grammar_new 
    (id, sentence_id, rule_id, pattern, word, jlpt_level, description, tooltip_shown)
SELECT id, sentence_id, rule_id, pattern, word, jlpt_level, description, tooltip_shown
FROM highlight_grammar;

-- Step 3: Drop old tables
DROP TABLE highlight_vocab;
DROP TABLE highlight_grammar;

-- Step 4: Rename new tables
ALTER TABLE highlight_vocab_new RENAME TO highlight_vocab;
ALTER TABLE highlight_grammar_new RENAME TO highlight_grammar;

-- Step 5: Recreate indexes
CREATE INDEX IF NOT EXISTS idx_highlight_vocab_sentence_id ON highlight_vocab(sentence_id);
CREATE INDEX IF NOT EXISTS idx_highlight_grammar_sentence_id ON highlight_grammar(sentence_id);
```

#### 5.2 Update `src/db/schema.py`

```python
# Remove is_beyond_level from CREATE TABLE statements

_CREATE_VOCAB_TABLE = """
CREATE TABLE IF NOT EXISTS highlight_vocab (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sentence_id INTEGER NOT NULL,
    surface TEXT NOT NULL,
    lemma TEXT NOT NULL,
    pos TEXT NOT NULL,
    jlpt_level INTEGER,
    tooltip_shown INTEGER NOT NULL DEFAULT 0,
    vocab_id INTEGER DEFAULT 0,
    pronunciation TEXT DEFAULT '',
    definition TEXT DEFAULT '',
    FOREIGN KEY (sentence_id) REFERENCES sentences(id) ON DELETE CASCADE
)
"""

_CREATE_GRAMMAR_TABLE = """
CREATE TABLE IF NOT EXISTS highlight_grammar (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sentence_id INTEGER NOT NULL,
    rule_id TEXT NOT NULL,
    pattern TEXT NOT NULL,
    word TEXT,
    jlpt_level INTEGER,
    description TEXT,
    tooltip_shown INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (sentence_id) REFERENCES sentences(id) ON DELETE CASCADE
)
"""
```

---

### Phase 6: Repository Changes

#### 6.1 Update `LearningRepository.insert_sentence()` (src/db/repository.py)

Remove `is_beyond_level` from INSERT statements:

```python
# In insert_sentence method
cursor.execute(
    """
    INSERT INTO highlight_vocab
        (sentence_id, surface, lemma, pos, jlpt_level,
         tooltip_shown, vocab_id, pronunciation, definition)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
    (
        sentence_id,
        v.surface,
        v.lemma,
        v.pos,
        v.jlpt_level,
        int(v.tooltip_shown),
        v.vocab_id,
        v.pronunciation,
        v.definition,
    ),
)
```

#### 6.2 Update `LearningRepository.get_sentence_detail()` (src/db/repository.py)

Remove `is_beyond_level` from SELECT parsing:

```python
# Update column indices after removing is_beyond_level
# Old: id(0), sentence_id(1), surface(2), lemma(3), pos(4), jlpt_level(5), is_beyond_level(6), ...
# New: id(0), sentence_id(1), surface(2), lemma(3), pos(4), jlpt_level(5), tooltip_shown(6), ...

jlpt_level=vrow[5],
tooltip_shown=bool(vrow[6]),
```

---

### Phase 7: Test Updates

#### 7.1 Files to Update

| File | Changes |
|------|---------|
| `tests/test_highlight.py` | Update fixtures to remove `user_level`, `is_beyond_level` |
| `tests/test_overlay.py` | Update tests for `get_display_analysis()` |
| `tests/test_db_repository.py` | Update DB tests for new schema |
| `tests/test_analysis_pipeline.py` | Update for `find_all_vocab()`, `match_all()` |
| `tests/test_jlpt_vocab.py` | Update for `find_all_vocab()` |
| `tests/test_grammar.py` | Update for `match_all()` |
| `tests/test_analysis_worker.py` | Update for new `VocabHit` structure |
| `tests/test_integration*.py` | Update integration tests |

---

## Migration Strategy

### Clean Migration (Recommended for Dev)

1. Delete existing `data/myasr.db`
2. Apply all code changes
3. Run tests
4. App will create new DB on first run

---

## Verification Checklist

- [ ] `VocabHit` no longer has `user_level`
- [ ] `HighlightVocab/Grammar` no longer has `is_beyond_level`
- [ ] `SentenceResult.get_display_analysis()` returns filtered data
- [ ] `_render_in_browser()` uses `get_display_analysis()`
- [ ] `_handle_hover_at_viewport_pos()` uses `get_display_analysis()`
- [ ] `on_config_changed()` re-renders both main and preview browsers
- [ ] `find_all_vocab()` returns all vocab matches
- [ ] `match_all()` returns all grammar matches
- [ ] `PreprocessingPipeline.__init__()` takes no arguments
- [ ] `PipelineOrchestrator` no longer creates `AppConfig` for `PreprocessingPipeline`
- [ ] DB schema updated
- [ ] Repository INSERT/SELECT updated
- [ ] All tests pass
- [ ] Manual test: toggle highlights → tooltip responds correctly
- [ ] Manual test: change JLPT level → display updates immediately
- [ ] Manual test: in BROWSE mode, config changes affect both browsers

---

## Summary

| Component | Change |
|-----------|--------|
| `VocabHit` | Remove `user_level` |
| `HighlightVocab/Grammar` | Remove `is_beyond_level` |
| `SentenceResult` | Add `get_display_analysis()` |
| `JLPTVocabLookup` | `find_beyond_level()` → `find_all_vocab()` |
| `GrammarMatcher` | `match()` → `match_all()` |
| `PreprocessingPipeline` | Remove `__init__(config)` → `__init__()`, remove `_config` |
| `PipelineOrchestrator` | Remove `AppConfig` construction for `PreprocessingPipeline` |
| `OverlayWindow` | Use `get_display_analysis()` in render and hover; re-render preview on config change |
| DB Schema | Remove `is_beyond_level` column |
| Repository | Update INSERT/SELECT for new schema |