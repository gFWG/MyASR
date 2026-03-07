# Post-MVP Detailed Plan — MyASR Japanese Learning Overlay

## Scope

Four features from milestones.md Post-MVP table, plus a prerequisite (System Tray) and an enhancement (Overlay Resize). Incorporates three user-requested adjustments:

1. **Vocab/grammar deduplication & implicit review on re-encounter**
2. **Overlay resizing with adaptive text layout**
3. **Selective highlighting on review cards**

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Settings Panel | Separate `QDialog` | Non-modal, doesn't interfere with overlay |
| Learning Panel | Separate `QWidget` window | Needs table + detail view, too complex for overlay |
| Review Algorithm | SM-2 (SuperMemo-2) | Classic, well-understood, no external deps |
| Review Granularity | Vocab/grammar item-level | One review item per unique lemma (vocab) or rule_id (grammar) |
| Panel Navigation | `QSystemTrayIcon` + context menu | Overlay is frameless, no menu bar available |
| Overlay Resize | Drag edges/corners + size grip | Standard desktop pattern |
| Re-encounter Handling | Implicit "Good" review | Same item in new sentence reinforces memory without user action |

---

## Feature 0 — System Tray Icon

**Priority**: Prerequisite — all panels need an entry point.
**Effort**: Small
**Depends On**: M4

### Design

`QSystemTrayIcon` with right-click context menu:
- **Settings** → opens SettingsDialog
- **Learning History** → opens LearningPanel
- **Review** (with due-count badge) → opens ReviewPanel
- ─── separator ───
- **Show/Hide Overlay** → toggles OverlayWindow visibility
- **Quit** → clean shutdown

### Signals

- `settings_requested` → show SettingsDialog
- `history_requested` → show LearningPanel
- `review_requested` → show ReviewPanel
- `toggle_overlay` → show/hide OverlayWindow
- `quit_requested` → QApplication.quit()

### Integration

- Instantiate in `main.py` after QApplication
- Tray keeps app process alive when overlay is hidden
- Due-count badge: poll `ReviewRepository.get_queue_count()` on a 60s QTimer

### Files

| Action | File |
|--------|------|
| NEW | `src/ui/tray.py` — `SystemTrayManager(QObject)` |
| MODIFY | `src/main.py` — instantiate tray, wire signals |
| NEW | `tests/test_tray.py` |

---

## Feature 1 — Settings Panel

**Priority**: P1
**Effort**: Medium
**Depends On**: M4 + Feature 0

### New Config Fields

```python
# Added to AppConfig in src/config.py
overlay_opacity: float = 0.78          # 0.0–1.0, maps to QWidget opacity
overlay_width: int = 800               # persisted from resize
overlay_height: int = 120              # persisted from resize
overlay_font_size_jp: int = 16
overlay_font_size_cn: int = 14
enable_vocab_highlight: bool = True
enable_grammar_highlight: bool = True
audio_device_id: int | None = None     # None = system default
```

All new fields have defaults, so `load_config()` remains backward-compatible with existing `data/config.json`.

### Live-Reload Mechanism

1. SettingsDialog saves config via `save_config()`.
2. SettingsDialog emits `config_changed(AppConfig)` signal.
3. Connected slots on OverlayWindow and PipelineWorker react:
   - **OverlayWindow.on_config_changed**: update opacity, font sizes, highlight toggles, re-render current sentence.
   - **PipelineWorker.on_config_changed**: update user_level on PreprocessingPipeline, update OllamaClient config (mode, templates, url, model, timeout). Thread-safe via `QMetaObject.invokeMethod` with `Qt.QueuedConnection`.

### Dialog Layout

```
┌─ Settings ──────────────────────────────────┐
│ [General] [Appearance] [Model] [Templates]  │  ← QTabWidget
│                                             │
│  General Tab:                               │
│    JLPT Level:     [▼ N3 ]                  │
│    LLM Mode:       [▼ Translation ]         │
│                                             │
│  Appearance Tab:                            │
│    Opacity:        [====●====] 0.78         │
│    JP Font Size:   [▲ 16 ▼]                │
│    CN Font Size:   [▲ 14 ▼]                │
│    ☑ Vocab Highlighting                     │
│    ☑ Grammar Highlighting                   │
│                                             │
│  Model Tab:                                 │
│    Ollama URL:     [http://localhost:11434]  │
│    Model:          [qwen3.5:4b           ]  │
│    Timeout (sec):  [▲ 30.0 ▼]              │
│    [Test Connection]  ✅ Connected           │
│                                             │
│  Templates Tab:                             │
│    Translation Prompt:                      │
│    ┌────────────────────────────────────┐   │
│    │ {japanese_text} placeholder hint   │   │
│    └────────────────────────────────────┘   │
│    Explanation Prompt:                      │
│    ┌────────────────────────────────────┐   │
│    │ ...                                │   │
│    └────────────────────────────────────┘   │
│                                             │
│              [ Cancel ]  [ Save ]           │
└─────────────────────────────────────────────┘
```

### Files

| Action | File |
|--------|------|
| MODIFY | `src/config.py` — new fields with defaults |
| NEW | `src/ui/settings.py` — `SettingsDialog(QDialog)` |
| MODIFY | `src/ui/overlay.py` — `on_config_changed()` slot |
| MODIFY | `src/pipeline.py` — `on_config_changed()` slot (thread-safe) |
| MODIFY | `src/main.py` — wire config_changed signal |
| NEW | `tests/test_settings.py` |

---

## Feature 1.5 — Overlay Resize & Adaptive Text Layout

**Priority**: P1 (enhancement within Settings scope)
**Effort**: Small–Medium
**Depends On**: M4 + Feature 1 (for config persistence)

### Current State (Problem)

- Fixed `resize(800, 120)` — no user resize capability.
- Text is left-aligned by default (QTextBrowser).
- No multi-line handling beyond QTextBrowser's built-in word wrap.
- Long sentences just scroll or overflow.

### Design

#### Resize Support

1. Add `QSizeGrip` in bottom-right corner of overlay.
2. Remove the fixed `resize(800, 120)` — use `setMinimumSize(400, 80)` and `setMaximumSize(screen_width, 400)`.
3. Override `resizeEvent()` to:
   - Store new size to AppConfig and call `save_config()` (debounced — 500ms QTimer to avoid spam).
   - Re-center text browsers within new dimensions.
4. On startup, read `overlay_width` / `overlay_height` from config, apply as initial size.
5. Re-position to bottom-center after resize using `_center_on_screen()` updated for new dimensions.
6. Keep drag-to-move working alongside edge-resize.

#### Adaptive Text Layout

The overlay text must be: **centered overall in the window, but left-aligned within the text block, with multi-line wrapping**.

Modify `HighlightRenderer.build_rich_text()` HTML output to use a centered container with left-aligned inline-block:

```html
<div style="text-align: center; width: 100%;">
  <span style="display: inline-block; text-align: left; max-width: 95%;">
    <span style="color: #C8E6C9; font-weight: bold;">食べる</span>のが好きです。
    <!-- ... highlighted spans ... -->
  </span>
</div>
```

This gives:
- **Centered block** within the QTextBrowser viewport.
- **Left-aligned text** within the block itself (natural reading direction).
- **Multi-line wrapping** when text exceeds the viewport width.

Also apply same pattern to the translation line (`_cn_browser`).

#### Dynamic Font Sizing (stretch goal)

If text is too long for the overlay at the configured font size, we could shrink the font. But this adds complexity — defer to a later iteration. The multi-line wrap is sufficient for now.

### Files

| Action | File |
|--------|------|
| MODIFY | `src/ui/overlay.py` — resize support, QSizeGrip, resizeEvent, config persistence |
| MODIFY | `src/ui/highlight.py` — HTML layout with centered container |
| MODIFY | `src/config.py` — overlay_width/height fields (already in Feature 1) |
| Extend | `tests/test_overlay.py`, `tests/test_highlight.py` |

---

## Feature 2 — Learning Panel (History)

**Priority**: P1
**Effort**: Medium
**Depends On**: M4 + DB + Feature 0

### Repository Extensions

```python
# New methods on LearningRepository (src/db/repository.py)

def get_sentences_filtered(
    self,
    limit: int = 50,
    offset: int = 0,
    sort_by: Literal["created_at", "japanese_text"] = "created_at",
    sort_order: Literal["asc", "desc"] = "desc",
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[SentenceRecord]: ...

def get_sentence_count(
    self,
    query: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> int: ...

def get_sentence_with_highlights(
    self,
    sentence_id: int,
) -> tuple[SentenceRecord, list[HighlightVocab], list[HighlightGrammar]]: ...
```

### Panel Layout

```
┌─ Learning History ──────────────────────────────────────────┐
│ Search: [________________] From: [2024-01-01] To: [today]   │
│ [🔍 Search]                                                 │
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Time       │ Japanese           │ Translation  │ Vocab  │ │
│ │────────────┼────────────────────┼──────────────┼────────│ │
│ │ 14:32:01   │ 今日は天気がいい   │ 今天天气很好 │ 3      │ │
│ │ 14:31:45   │ お腹が空いた       │ 肚子饿了     │ 2      │ │
│ │ ...        │ ...                │ ...          │ ...    │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ ◄ Previous  Page 1 of 12  Next ►                            │
│                                                             │
│ [Export...]  [Delete by Date Range...]                       │
└─────────────────────────────────────────────────────────────┘
```

Click a row → Detail view (QDialog or panel split):

```
┌─ Sentence Detail ─────────────────────────────────────┐
│                                                       │
│  今日は天気がいいですね                                │  ← highlighted HTML
│  Translation: 今天天气真好啊                           │
│  Explanation: (if available)                          │
│                                                       │
│  Vocab:                                               │
│    N4  天気 (てんき) — noun                            │
│    N3  いい — adjective          [+ Add to Review]    │
│                                                       │
│  Grammar:                                             │
│    N4  〜がいい — pattern         [+ Add to Review]    │
│                                                       │
│  Recorded: 2024-03-07 14:32:01                        │
│                                                       │
│                              [ Close ]                │
└───────────────────────────────────────────────────────┘
```

### Files

| Action | File |
|--------|------|
| MODIFY | `src/db/repository.py` — filtered queries, count, highlight joins |
| NEW | `src/ui/learning_panel.py` — `LearningPanel(QWidget)`, `SentenceDetailDialog(QDialog)` |
| MODIFY | `src/main.py` — wire tray → panel |
| NEW | `tests/test_learning_panel.py` |

---

## Feature 3 — CSV/JSON Export (with filters)

**Priority**: P1
**Effort**: Small
**Depends On**: DB

### Current State

`LearningRepository.export_records(format)` already exports ALL records. Needs:
- Date range filter
- Optional highlight inclusion
- File save dialog in UI

### Extended Signature

```python
def export_records(
    self,
    format: Literal["json", "csv"] = "json",
    date_from: str | None = None,
    date_to: str | None = None,
    include_highlights: bool = False,
) -> str: ...
```

When `include_highlights=True`:
- **JSON**: Each record gains `"vocab_highlights": [...]` and `"grammar_highlights": [...]` nested arrays.
- **CSV**: Additional columns: `vocab_count`, `grammar_count`, `vocab_lemmas` (semicolon-delimited), `grammar_rules` (semicolon-delimited).

### UI Integration

Export triggered from:
1. **Learning Panel** "Export" button → opens filter dialog → `QFileDialog.getSaveFileName`.
2. **Tray menu** "Quick Export" → exports all to user-chosen file (no filter dialog).

### Files

| Action | File |
|--------|------|
| MODIFY | `src/db/repository.py` — filtered export with highlights |
| MODIFY | `src/ui/learning_panel.py` — export dialog |
| MODIFY | `src/ui/tray.py` — "Quick Export" menu action |
| Extend | `tests/test_db_repository.py` |

---

## Feature 4 — Review System (SM-2)

**Priority**: P2
**Effort**: Large
**Depends On**: DB + Features 0, 2

This is the most complex feature. Broken into 5 sub-features.

### 4A — Item-Level Deduplication Model

#### The Problem

Currently, every sentence INSERT creates fresh `highlight_vocab` and `highlight_grammar` rows. The same word 食べる appearing in 10 sentences creates 10 independent `highlight_vocab` rows with no linkage.

The review system needs **one review item per unique vocab lemma** (or grammar rule_id). When the same item is encountered again in a new sentence, it should count as an implicit "Good" review.

#### Design: `review_items` Table

```sql
CREATE TABLE review_items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    item_type   TEXT    NOT NULL CHECK (item_type IN ('vocab', 'grammar')),
    item_key    TEXT    NOT NULL,   -- lemma (vocab) or rule_id (grammar)
    display     TEXT    NOT NULL,   -- surface form or pattern text for display
    jlpt_level  INTEGER,
    first_sentence_id  INTEGER NOT NULL REFERENCES sentence_records(id),
    interval_days      REAL    NOT NULL DEFAULT 0,
    ease_factor        REAL    NOT NULL DEFAULT 2.5,
    repetitions        INTEGER NOT NULL DEFAULT 0,
    next_review        TEXT    NOT NULL,
    last_review        TEXT,
    last_grade         INTEGER,
    total_encounters   INTEGER NOT NULL DEFAULT 1,
    created_at         TEXT    NOT NULL,
    UNIQUE (item_type, item_key)
);
CREATE INDEX idx_review_next ON review_items(next_review);
```

Key decisions:
- `item_key` = `lemma` for vocab, `rule_id` for grammar → enables dedup.
- `UNIQUE(item_type, item_key)` → prevents duplicate review items.
- `first_sentence_id` → links to the first sentence where item was encountered (for review card context).
- `total_encounters` → incremented on each re-encounter, useful for stats.
- `display` → the surface form or matched_text, so the review card can show the word even without joining to highlights.

#### Encounter Flow

```
New sentence arrives in PipelineWorker._process_segment()
  └─ After insert_sentence() returns highlight IDs
       └─ For each vocab hit where is_beyond_level=True:
            ├─ SELECT FROM review_items WHERE item_type='vocab' AND item_key=lemma
            ├─ NOT FOUND → INSERT new review_item (next_review=now, first_sentence_id=current)
            └─ FOUND → implicit_review(item_id, grade=GOOD)
                        UPDATE total_encounters += 1
       └─ Same for grammar hits
```

**`implicit_review()`** applies SM-2 with grade=GOOD, exactly as if the user pressed "Good" in the review UI. This means:
- Re-encountered items get their interval extended.
- Items encountered frequently will have long intervals (effectively "mastered").
- Items encountered once and never again stay at short intervals (keep coming up for review).

### 4B — SM-2 Algorithm

Pure function, no side effects, no DB dependency.

```python
# src/review/sm2.py

def calculate_sm2(
    repetitions: int,
    ease_factor: float,
    interval_days: float,
    grade: int,  # 0=Again, 1=Hard, 2=Good, 3=Easy
) -> tuple[int, float, float]:
    """Calculate next SM-2 state.

    Returns:
        (new_repetitions, new_ease_factor, new_interval_days)
    """
```

**SM-2 Rules**:
- **grade < 2 (Again/Hard)**: reset repetitions=0, interval=1 day (review tomorrow), ease -= 0.2 (clamp ≥ 1.3)
- **grade == 2 (Good)**: if rep=0 → interval=1; if rep=1 → interval=6; else → interval *= ease. ease += 0.0. rep += 1
- **grade == 3 (Easy)**: same interval logic as Good, but ease += 0.15. rep += 1
- Ease never drops below 1.3.

**`next_review`** = now + `new_interval_days` (stored as ISO datetime string).

### 4C — Review Repository

```python
# src/db/review_repository.py

class ReviewRepository:
    def __init__(self, conn: sqlite3.Connection) -> None: ...

    def add_item(
        self, item_type: Literal["vocab", "grammar"],
        item_key: str, display: str, jlpt_level: int | None,
        sentence_id: int,
    ) -> int | None:
        """Add review item. Returns id, or None if already exists."""

    def implicit_review(self, item_type: str, item_key: str) -> None:
        """Apply SM-2 with grade=GOOD for re-encountered items.
        Also increments total_encounters."""

    def get_due_items(self, limit: int = 20) -> list[ReviewItem]: ...

    def get_queue_count(self) -> int: ...

    def update_after_review(self, item_id: int, grade: int) -> None:
        """Apply SM-2, update interval/ease/next_review/repetitions."""

    def get_item_with_context(
        self, item_id: int,
    ) -> tuple[ReviewItem, SentenceRecord, HighlightVocab | HighlightGrammar]:
        """Get review item + source sentence + original highlight for card display."""

    def get_stats(self) -> dict[str, int | float]:
        """Return total_items, due_today, avg_ease, items_per_level."""

    def increment_encounters(self, item_type: str, item_key: str) -> None:
        """Bump total_encounters for an existing item."""
```

### 4D — Auto-Enrollment & Implicit Review

Modify `PipelineWorker` to hook into the review system after each sentence:

```python
# In PipelineWorker._process_segment(), after insert_sentence():

for i, hit in enumerate(result.analysis.vocab_hits):
    if hit.jlpt_level > self._config.user_jlpt_level:  # beyond user level
        existing = self._review_repo.add_item(
            item_type="vocab", item_key=hit.lemma,
            display=hit.surface, jlpt_level=hit.jlpt_level,
            sentence_id=sentence_id,
        )
        if existing is None:
            # Item already existed → implicit "Good" review
            self._review_repo.implicit_review("vocab", hit.lemma)

# Same pattern for grammar_hits using hit.rule_id as item_key
```

Manual enrollment from Learning Panel detail view also calls `review_repo.add_item()`.

### 4E — Review UI with Selective Highlighting

#### Selective Highlighting

New method in `HighlightRenderer`:

```python
def build_review_text(
    self,
    japanese_text: str,
    analysis: AnalysisResult,
    target: VocabHit | GrammarHit,
) -> str:
    """Build HTML with ONLY the target item highlighted.

    All other vocab/grammar in the sentence rendered as plain text.
    The target item gets its JLPT-colored highlight.
    """
```

This reuses the same span-building logic from `build_rich_text`, but filters the hit list to only include the one matching `target` (matched by start_pos/end_pos or by lemma/rule_id).

#### Card Layout

```
┌─ Review ──────────────────────────────────────────┐
│                                                   │
│  Due: 5 remaining          [■■■□□□□□□□] 50%       │
│                                                   │
│  ┌─ Card ───────────────────────────────────────┐ │
│  │                                               │ │
│  │  N3                                           │ │  ← JLPT badge
│  │                                               │ │
│  │  概念  (がいねん)                              │ │  ← item display
│  │  noun                                         │ │  ← POS
│  │                                               │ │
│  │  ─── Source Sentence ───                      │ │
│  │  この概念は難しいですね                        │ │  ← ONLY 概念 highlighted
│  │                                               │ │
│  │  ─── [Click to reveal] ───                    │ │  ← card back (hidden)
│  │                                               │ │
│  │  Translation: 这个概念很难呢                   │ │
│  │  Explanation: ...                             │ │
│  │                                               │ │
│  └───────────────────────────────────────────────┘ │
│                                                   │
│  [ Again ]  [ Hard ]  [ Good ]  [ Easy ]          │
│    (1)       (2)       (3)       (4)              │
│                                                   │
│  Session: 3 reviewed, avg ease 2.4                │
└───────────────────────────────────────────────────┘
```

#### Card States

1. **Front**: JLPT badge + item display + source sentence (item highlighted) + "Click to reveal"
2. **Back** (after Space/click): Reveals translation + explanation below the sentence
3. **Graded** (after 1/2/3/4): Applies SM-2, loads next due item. If none → Summary.

#### Summary Screen

After all due items reviewed:
```
All caught up!

Session stats:
  Reviewed: 5 items
  Again: 1 | Hard: 0 | Good: 3 | Easy: 1
  Next review: in 6 hours

[Close]
```

#### Grammar Review Card Variant

For grammar items, the card front shows:
- JLPT badge
- Pattern text (e.g., `〜ている`)
- Confidence type (e.g., "auxiliary")
- Source sentence with only this grammar pattern highlighted

Card back reveals full description + translation.

#### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| Space | Reveal back |
| 1 | Again |
| 2 | Hard |
| 3 | Good |
| 4 | Easy |
| Esc | Close panel |

### Files (All of Feature 4)

| Action | File |
|--------|------|
| MODIFY | `src/db/schema.py` — `review_items` table |
| MODIFY | `src/db/models.py` — `ReviewItem`, `ReviewGrade` |
| NEW | `src/db/review_repository.py` |
| NEW | `src/review/__init__.py` |
| NEW | `src/review/sm2.py` |
| MODIFY | `src/ui/highlight.py` — `build_review_text()` |
| NEW | `src/ui/review_panel.py` — `ReviewPanel(QWidget)` |
| MODIFY | `src/pipeline.py` — auto-enrollment + implicit review hook |
| MODIFY | `src/main.py` — wire tray → ReviewPanel, pass ReviewRepository |
| MODIFY | `src/ui/learning_panel.py` — "Add to Review" buttons in detail view |
| NEW | `tests/test_sm2.py` |
| NEW | `tests/test_review_repository.py` |
| NEW | `tests/test_review_panel.py` |

---

## Implementation Order

```
Feature 0 (System Tray)
    │
    ├──► Feature 1 (Settings) + Feature 1.5 (Overlay Resize)
    │         └──► Can be developed together — resize persists to config
    │
    ├──► Feature 3 (Export)
    │         └──► Smallest feature, extends existing repo method
    │
    ├──► Feature 2 (Learning Panel)
    │         └──► Depends on repo extensions
    │
    └──► Feature 4 (Review System)
              4A (DB + dedup model)
                └──► 4B (SM-2 algorithm)
                      └──► 4C (Review Repository)
                            └──► 4D (Auto-enrollment + implicit review)
                                  └──► 4E (Review UI + selective highlighting)
```

Features 1/1.5, 2, and 3 can be developed in parallel after Feature 0.
Feature 4 is sequential internally but can start 4A/4B in parallel with Features 1–3.

---

## Full File Change Matrix

### New Files (15)

| File | Feature | Purpose |
|------|---------|---------|
| `src/ui/tray.py` | F0 | System tray icon + context menu |
| `src/ui/settings.py` | F1 | Settings dialog with tabs |
| `src/ui/learning_panel.py` | F2 | History table + detail view + export dialog |
| `src/review/__init__.py` | F4 | Package init |
| `src/review/sm2.py` | F4B | SM-2 pure algorithm |
| `src/db/review_repository.py` | F4C | Review item CRUD + SM-2 application |
| `src/ui/review_panel.py` | F4E | Flashcard review UI |
| `tests/test_tray.py` | F0 | Tray signal tests |
| `tests/test_settings.py` | F1 | Config round-trip + dialog tests |
| `tests/test_learning_panel.py` | F2 | Filtered query + pagination tests |
| `tests/test_sm2.py` | F4B | SM-2 parametrized algorithm tests |
| `tests/test_review_repository.py` | F4C | Review CRUD + dedup + implicit review tests |
| `tests/test_review_panel.py` | F4E | Card state transition + keyboard tests |
| `tests/test_overlay_resize.py` | F1.5 | Resize persistence + text layout tests |
| `tests/test_export_filtered.py` | F3 | Filtered export + highlights inclusion tests |

### Modified Files (9)

| File | Features | Changes |
|------|----------|---------|
| `src/config.py` | F1, F1.5 | New fields: opacity, font sizes, dimensions, highlight toggles, audio_device_id |
| `src/db/schema.py` | F4A | `review_items` table + indexes |
| `src/db/models.py` | F4A | `ReviewItem` dataclass, `ReviewGrade` IntEnum |
| `src/db/repository.py` | F2, F3 | Filtered queries, count, highlight joins, filtered export |
| `src/ui/overlay.py` | F1, F1.5 | `on_config_changed()` slot, resize support (QSizeGrip, resizeEvent, min/max, debounced config save) |
| `src/ui/highlight.py` | F1.5, F4E | Centered text layout HTML, `build_review_text()` for selective highlighting |
| `src/pipeline.py` | F1, F4D | `on_config_changed()` slot (thread-safe), auto-enrollment + implicit review hook |
| `src/main.py` | F0, F1, F2, F4 | Tray instantiation, signal wiring, panel lifecycle, ReviewRepository init |
| `src/exceptions.py` | F4 | Optional: `ReviewError` subclass |
