# QTextCharFormat 迁移方案（简化版）

## 一、问题诊断

### 1.1 当前 Bug 根因

当前 hover 检测链路存在**坐标系统不一致**的问题：

```
MouseMove → cursorForPosition(viewport_pos) → cursor.position()
                                                      ↓
                                             返回 Qt 富文本文档字符偏移
                                             (包含 HTML 标签节点)
                                                      ↓
                                        get_highlight_at_position(char_pos, ...)
                                                      ↓
                                        与 VocabHit/GrammarHit 的 start_pos/end_pos 比较
                                        (这些是原始日文字符串的字符索引)
```

**核心矛盾**：
- `QTextCursor.position()` 返回的是 Qt 富文本文档内部的字符偏移量
- `VocabHit.start_pos/end_pos` 是分词器对**原始日文裸字符串**操作产生的偏移量

HTML 模板中的 `<table>/<tr>/<td>/<span>` 等标签引入了额外的字符计数偏差，导致 hover 检测完全失效。

### 1.2 为什么 QTextCharFormat 能解决

使用 `QTextCharFormat` 方案时：

```python
doc = browser.document()
doc.setPlainText(japanese_text)          # 直接写入裸文本

cursor = QTextCursor(doc)
cursor.setPosition(vh.start_pos)         # start_pos 直接对应 plain text 偏移
cursor.setPosition(vh.end_pos, QTextCursor.MoveMode.KeepAnchor)

fmt = QTextCharFormat()
fmt.setForeground(QColor(color))
cursor.setCharFormat(fmt)
```

此时 `doc.find()` / `cursorForPosition(viewport_pos).position()` 返回的偏移量**与 `start_pos/end_pos` 天然对齐**——因为两者都在同一个 plain text 字符序列上操作。

---

## 二、迁移架构（简化版）

### 2.1 设计决策：完全移除 HTML 路径

经过分析，`build_rich_text()` 的所有使用场景都可以改用 `QTextCharFormat` 方案：

| 使用位置 | 当前实现 | 迁移后 |
|----------|----------|--------|
| [`overlay.py:_render_in_browser()`](src/ui/overlay.py:250) | `build_rich_text()` → `setHtml()` | `apply_to_document()` 直接格式化 |
| [`overlay.py:on_asr_ready()`](src/ui/overlay.py:279) | `_centered_html()` → `setHtml()` | `_set_centered_plain_text()` |
| [`overlay.py:set_status()`](src/ui/overlay.py:337) | `_centered_html()` → `setHtml()` | `_set_centered_plain_text()` |
| [`sentence_detail.py:_build_japanese_section()`](src/ui/sentence_detail.py:133) | `build_rich_text(_EMPTY_ANALYSIS)` | `_set_centered_plain_text()` |

**关键发现**：`sentence_detail.py` 传入的是 `_EMPTY_ANALYSIS`，实际上不会产生任何高亮，只是做了 HTML 转义和居中包装。这完全可以用 `setPlainText()` + `QTextBlockFormat` 替代。

### 2.2 简化后的模块架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        HighlightRenderer                         │
│  (src/ui/highlight.py)                                           │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ apply_to_document() [NEW - 核心方法]                         ││
│  │ → 直接操作 QTextDocument                                     ││
│  │ → 坐标系与 start_pos/end_pos 对齐                            ││
│  │ → 供 overlay 和 sentence_detail 使用                         ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ get_highlight_at_position() [保持不变]                       ││
│  │ → 纯 Python 逻辑，无 Qt 依赖                                  ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
│  ❌ 移除: build_rich_text(), _render_spans(), html 模块导入      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         OverlayWindow                            │
│  (src/ui/overlay.py)                                             │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ _render_in_browser() [MODIFY]                                ││
│  │ → 调用 apply_to_document() + 设置段落居中                     ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
│  ❌ 移除: _centered_html()                                       │
│  ✅ 新增: _set_centered_plain_text() [辅助函数]                  │
└─────────────────────────────────────────────────────────────────┘
```

### 2.3 数据流对比

**Before (HTML 方案)**:
```
japanese_text + analysis → build_rich_text() → HTML string → setHtml()
                                                                    ↓
                                              QTextDocument 解析 HTML
                                                                    ↓
                                              cursor.position() 错位
```

**After (QTextCharFormat 方案)**:
```
japanese_text + analysis → setPlainText() + apply_to_document()
                                              ↓
                                    QTextDocument 直接格式化
                                              ↓
                                    cursor.position() 对齐
```

---

## 三、详细实现方案

### 3.1 `src/ui/highlight.py` 完整重写

```python
"""JLPT vocabulary and grammar highlight renderer using QTextCharFormat.

Renders highlighted Japanese text directly to QTextDocument, ensuring
cursor positions align perfectly with VocabHit/GrammarHit offsets.
"""

import logging
from typing import TypeAlias

from PySide6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor, QTextDocument

from src.db.models import AnalysisResult, GrammarHit, VocabHit

logger = logging.getLogger(__name__)

_TYPE_GRAMMAR = "grammar"
_TYPE_VOCAB = "vocab"

_Span: TypeAlias = tuple[int, int, str, str]


class HighlightRenderer:
    """Renders Japanese text with JLPT-level color highlights using QTextCharFormat.

    Grammar highlights take priority over overlapping vocab highlights.
    Works directly with QTextDocument to ensure position alignment.

    Attributes:
        JLPT_COLORS: Default mapping from JLPT level (1–5) to vocab/grammar hex colors.
    """

    JLPT_COLORS: dict[int, dict[str, str]] = {
        5: {"vocab": "#E8F5E9", "grammar": "#81C784"},
        4: {"vocab": "#C8E6C9", "grammar": "#4CAF50"},
        3: {"vocab": "#BBDEFB", "grammar": "#1976D2"},
        2: {"vocab": "#FFF9C4", "grammar": "#F9A825"},
        1: {"vocab": "#FFCDD2", "grammar": "#D32F2F"},
    }

    def __init__(self, jlpt_colors: dict[int, dict[str, str]] | None = None) -> None:
        self._colors: dict[int, dict[str, str]] = jlpt_colors or dict(self.JLPT_COLORS)

    def update_colors(self, jlpt_colors: dict[int, dict[str, str]]) -> None:
        """Update the JLPT color mapping at runtime.

        Args:
            jlpt_colors: Mapping from JLPT level (1–5) to vocab/grammar hex colors.
        """
        self._colors = jlpt_colors

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def apply_to_document(
        self,
        document: QTextDocument,
        japanese_text: str,
        analysis: AnalysisResult,
        user_level: int,
    ) -> None:
        """Apply JLPT highlights directly to a QTextDocument using QTextCharFormat.

        This method bypasses HTML entirely, ensuring that cursor positions
        align perfectly with VocabHit/GrammarHit start_pos/end_pos values.

        Args:
            document: The QTextDocument to format.
            japanese_text: The raw Japanese string to render.
            analysis: Pipeline analysis result containing vocab and grammar hits.
            user_level: The user's current JLPT level (1–5). Unused but kept for API parity.
        """
        # Set plain text first - this ensures position alignment
        document.setPlainText(japanese_text)

        if not japanese_text:
            return

        # Build spans list
        grammar_spans: list[_Span] = []
        for gh in analysis.grammar_hits:
            color = self._grammar_color(gh.jlpt_level)
            grammar_spans.append((gh.start_pos, gh.end_pos, color, _TYPE_GRAMMAR))

        vocab_spans: list[_Span] = []
        for vh in analysis.vocab_hits:
            if self._is_fully_covered(vh.start_pos, vh.end_pos, grammar_spans):
                logger.debug(
                    "Vocab span [%d,%d] suppressed by grammar coverage",
                    vh.start_pos,
                    vh.end_pos,
                )
                continue
            color = self._vocab_color(vh.jlpt_level)
            vocab_spans.append((vh.start_pos, vh.end_pos, color, _TYPE_VOCAB))

        all_spans = grammar_spans + vocab_spans
        all_spans.sort(key=lambda s: s[0])

        # Apply formatting via QTextCursor
        cursor = QTextCursor(document)

        for start, end, color, _span_type in all_spans:
            cursor.setPosition(start)
            cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)

            fmt = QTextCharFormat()
            fmt.setForeground(QColor(color))
            fmt.setFontWeight(QFont.Weight.Bold)
            cursor.setCharFormat(fmt)

    def get_highlight_at_position(
        self,
        position: int,
        analysis: AnalysisResult,
    ) -> VocabHit | GrammarHit | None:
        """Return the highlight hit at a character position, grammar-first.

        Args:
            position: Zero-based character index into the Japanese text.
            analysis: Pipeline analysis result.

        Returns:
            The first ``GrammarHit`` whose range contains *position*, or the
            first ``VocabHit`` if no grammar hit matches, or ``None``.
        """
        for gh in analysis.grammar_hits:
            if gh.start_pos <= position < gh.end_pos:
                return gh

        for vh in analysis.vocab_hits:
            if vh.start_pos <= position < vh.end_pos:
                return vh

        return None

    # ------------------------------------------------------------------ #
    # Private helpers                                                      #
    # ------------------------------------------------------------------ #

    def _grammar_color(self, jlpt_level: int) -> str:
        """Return the grammar hex color for a JLPT level, defaulting to N4."""
        return self._colors.get(jlpt_level, self._colors.get(4, self.JLPT_COLORS[4]))["grammar"]

    def _vocab_color(self, jlpt_level: int) -> str:
        """Return the vocab hex color for a JLPT level, defaulting to N4."""
        return self._colors.get(jlpt_level, self._colors.get(4, self.JLPT_COLORS[4]))["vocab"]

    @staticmethod
    def _is_fully_covered(
        start: int,
        end: int,
        grammar_spans: list[_Span],
    ) -> bool:
        """Return True if [start, end) is fully contained in any grammar span."""
        for gs_start, gs_end, _color, _type in grammar_spans:
            if gs_start <= start and end <= gs_end:
                return True
        return False
```

**变更摘要**：
- ✅ 新增：`apply_to_document()` 方法
- ✅ 新增：PySide6 导入（`QColor`, `QFont`, `QTextCharFormat`, `QTextCursor`, `QTextDocument`）
- ❌ 移除：`build_rich_text()` 方法
- ❌ 移除：`_render_spans()` 方法
- ❌ 移除：`import html` 模块
- ✅ 保留：`get_highlight_at_position()` 不变
- ✅ 保留：`JLPT_COLORS` 不变

### 3.2 `src/ui/overlay.py` 修改

#### 3.2.1 新增导入

```python
from PySide6.QtGui import (
    # ... 现有导入 ...
    QTextBlockFormat,
    QTextCursor,
)
```

#### 3.2.2 新增辅助函数 `_set_centered_plain_text()`

替代 `_centered_html()`：

```python
def _set_centered_plain_text(
    browser: QTextBrowser, text: str, color: str = "#EEEEEE"
) -> None:
    """Set plain text with center alignment in a QTextBrowser.

    Args:
        browser: The QTextBrowser to update.
        text: The plain text to display.
        color: Foreground color as hex string (default: #EEEEEE).
    """
    doc = browser.document()
    doc.setPlainText(text)

    # Set default text color via stylesheet
    browser.setStyleSheet(f"background: transparent; border: none; color: {color};")

    # Center align all blocks
    cursor = QTextCursor(doc)
    cursor.select(QTextCursor.SelectionType.Document)

    block_fmt = QTextBlockFormat()
    block_fmt.setAlignment(Qt.AlignmentFlag.AlignCenter)
    cursor.setBlockFormat(block_fmt)
```

#### 3.2.3 修改 `_render_in_browser()`

```python
def _render_in_browser(self, browser: QTextBrowser, result: SentenceResult) -> None:
    """Render a SentenceResult into the given browser widget.

    Args:
        browser: The QTextBrowser to render into.
        result: The sentence result to render.
    """
    doc = browser.document()

    if result.analysis is not None:
        filtered_analysis = AnalysisResult(
            tokens=result.analysis.tokens,
            vocab_hits=result.analysis.vocab_hits if self._enable_vocab else [],
            grammar_hits=result.analysis.grammar_hits if self._enable_grammar else [],
        )
        # Use QTextCharFormat API
        self._renderer.apply_to_document(
            doc,
            result.japanese_text,
            filtered_analysis,
            user_level=self._user_level,
        )
    else:
        # No analysis - just show plain text
        doc.setPlainText(result.japanese_text)

    # Center align all blocks
    cursor = QTextCursor(doc)
    cursor.select(QTextCursor.SelectionType.Document)
    block_fmt = QTextBlockFormat()
    block_fmt.setAlignment(Qt.AlignmentFlag.AlignCenter)
    cursor.setBlockFormat(block_fmt)
```

#### 3.2.4 修改 `on_asr_ready()`

```python
def on_asr_ready(self, result: ASRResult) -> None:
    """Show ASR text immediately.

    Args:
        result: ASR output containing Japanese text.
    """
    if self._history.is_browsing:
        _set_centered_plain_text(self._preview_browser, result.text)
    else:
        _set_centered_plain_text(self._jp_browser, result.text)
    QTimer.singleShot(0, self._adjust_height_to_content)
    logger.debug("on_asr_ready: segment_id=%s", result.segment_id)
```

#### 3.2.5 修改 `set_status()`

```python
def set_status(self, text: str) -> None:
    """Display a status message (e.g. 'Initializing...', 'Listening...').

    Args:
        text: Status string to display in the JP browser.
    """
    _set_centered_plain_text(self._jp_browser, text)
    QTimer.singleShot(0, self._adjust_height_to_content)
    logger.debug("set_status: %s", text)
```

#### 3.2.6 移除 `_centered_html()`

该函数不再需要，删除：

```python
# ❌ 删除此函数
def _centered_html(text: str, color: str = "#EEEEEE") -> str:
    ...
```

### 3.3 `src/ui/sentence_detail.py` 修改

#### 3.3.1 修改 `_build_japanese_section()`

```python
def _build_japanese_section(self) -> QTextBrowser:
    from PySide6.QtGui import QTextBlockFormat, QTextCursor
    from PySide6.QtCore import Qt

    browser = QTextBrowser()
    browser.setReadOnly(True)
    browser.setFrameShape(QTextBrowser.Shape.NoFrame)
    browser.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    browser.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    browser.setStyleSheet(f"font-family: {_FONT_FAMILIES}; font-size: 18px;")
    browser.setFixedHeight(60)
    browser.setOpenLinks(False)

    # Set plain text with center alignment
    doc = browser.document()
    doc.setPlainText(self._sentence.japanese_text)

    cursor = QTextCursor(doc)
    cursor.select(QTextCursor.SelectionType.Document)
    block_fmt = QTextBlockFormat()
    block_fmt.setAlignment(Qt.AlignmentFlag.AlignCenter)
    cursor.setBlockFormat(block_fmt)

    return browser
```

#### 3.3.2 移除未使用的导入

```python
# ❌ 移除这些导入（如果不再需要）
from src.ui.highlight import HighlightRenderer
_EMPTY_ANALYSIS = AnalysisResult(tokens=[], vocab_hits=[], grammar_hits=[])
```

### 3.4 测试更新 (`tests/test_highlight.py`)

#### 3.4.1 移除的测试

以下测试验证 `build_rich_text()` 的 HTML 输出，需要移除：

- `test_build_rich_text_empty_text_returns_empty_string`
- `test_build_rich_text_no_hits_returns_escaped_plain_text`
- `test_build_rich_text_html_escapes_special_chars`
- `test_build_rich_text_grammar_suppresses_fully_covered_vocab`
- `test_build_rich_text_non_overlapping_hits_both_colors_present`
- `test_build_rich_text_partial_overlap_vocab_not_suppressed`
- `test_build_rich_text_grammar_exactly_equals_vocab_range_suppresses`
- `test_build_rich_text_grammar_larger_than_vocab_suppresses`
- `test_build_rich_text_output_is_valid_html`
- `test_build_rich_text_contains_span_with_font_weight_bold`
- `test_build_rich_text_plain_text_outside_spans_is_escaped`
- `test_build_rich_text_multiple_vocab_hits_all_colored`
- `test_build_rich_text_contains_centering_table`
- `test_build_rich_text_no_inline_block`
- `test_renderer_accepts_custom_colors`
- `test_update_colors_changes_rendering`
- `test_default_renderer_uses_jlpt_colors`

#### 3.4.2 新增测试

```python
# ------------------------------------------------------------------ #
# apply_to_document — QTextCharFormat API                           #
# ------------------------------------------------------------------


def test_apply_to_document_empty_text(renderer: HighlightRenderer) -> None:
    """Test that empty text results in empty document."""
    from PySide6.QtWidgets import QTextBrowser

    browser = QTextBrowser()
    doc = browser.document()
    analysis = AnalysisResult(tokens=[], vocab_hits=[], grammar_hits=[])

    renderer.apply_to_document(doc, "", analysis, user_level=3)

    assert doc.toPlainText() == ""


def test_apply_to_document_plain_text_no_hits(renderer: HighlightRenderer) -> None:
    """Test that text without hits is set as plain text."""
    from PySide6.QtWidgets import QTextBrowser

    browser = QTextBrowser()
    doc = browser.document()
    analysis = AnalysisResult(tokens=[], vocab_hits=[], grammar_hits=[])

    renderer.apply_to_document(doc, "食べる", analysis, user_level=3)

    assert doc.toPlainText() == "食べる"


def test_apply_to_document_vocab_highlight(renderer: HighlightRenderer) -> None:
    """Test that vocab hits get highlighted with correct color."""
    from PySide6.QtWidgets import QTextBrowser
    from PySide6.QtGui import QColor, QFont, QTextCursor

    browser = QTextBrowser()
    doc = browser.document()
    vocab = [_make_vocab("猫", 0, 1, level=4)]
    analysis = AnalysisResult(tokens=[], vocab_hits=vocab, grammar_hits=[])

    renderer.apply_to_document(doc, "猫", analysis, user_level=4)

    # Verify text content
    assert doc.toPlainText() == "猫"

    # Verify formatting at position 0
    cursor = QTextCursor(doc)
    cursor.setPosition(0)
    char_fmt = cursor.charFormat()
    assert char_fmt.fontWeight() == QFont.Weight.Bold


def test_apply_to_document_position_alignment(renderer: HighlightRenderer) -> None:
    """Test that cursor positions align with start_pos/end_pos.

    This is the core fix for the hover detection bug.
    """
    from PySide6.QtWidgets import QTextBrowser

    browser = QTextBrowser()
    doc = browser.document()

    # Create a sentence with known vocab positions
    vocab = [_make_vocab("猫", 0, 1, level=4)]  # position 0-1
    grammar = [_make_grammar("g1", "食べている", 1, 6, level=2)]  # position 1-6
    analysis = AnalysisResult(tokens=[], vocab_hits=vocab, grammar_hits=grammar)

    text = "猫食べている"
    renderer.apply_to_document(doc, text, analysis, user_level=4)

    # Verify document length matches original text length
    assert len(doc.toPlainText()) == len(text)

    # Verify that position 0 is vocab
    hit = renderer.get_highlight_at_position(0, analysis)
    assert isinstance(hit, VocabHit)

    # Verify that position 2 is grammar
    hit = renderer.get_highlight_at_position(2, analysis)
    assert isinstance(hit, GrammarHit)


def test_apply_to_document_grammar_suppresses_vocab(renderer: HighlightRenderer) -> None:
    """Test that grammar suppresses fully covered vocab."""
    from PySide6.QtWidgets import QTextBrowser
    from PySide6.QtGui import QColor, QTextCursor

    browser = QTextBrowser()
    doc = browser.document()
    vocab = [_make_vocab("食べ", 0, 2, level=3)]
    grammar = [_make_grammar("g1", "食べている", 0, 5, level=2)]
    analysis = AnalysisResult(tokens=[], vocab_hits=vocab, grammar_hits=grammar)

    renderer.apply_to_document(doc, "食べている", analysis, user_level=4)

    # Document should have grammar color at position 0
    cursor = QTextCursor(doc)
    cursor.setPosition(0)
    char_fmt = cursor.charFormat()
    # Grammar N2 color is #F9A825
    expected_color = QColor("#F9A825")
    assert char_fmt.foreground().color().name() == expected_color.name()


def test_apply_to_document_non_overlapping_both_highlighted(
    renderer: HighlightRenderer,
) -> None:
    """Test that non-overlapping vocab and grammar both get highlighted."""
    from PySide6.QtWidgets import QTextBrowser
    from PySide6.QtGui import QColor, QTextCursor

    browser = QTextBrowser()
    doc = browser.document()
    vocab = [_make_vocab("猫", 0, 1, level=4)]
    grammar = [_make_grammar("g1", "食べている", 1, 6, level=2)]
    analysis = AnalysisResult(tokens=[], vocab_hits=vocab, grammar_hits=grammar)

    renderer.apply_to_document(doc, "猫食べている", analysis, user_level=4)

    # Position 0 should have vocab color (N4: #C8E6C9)
    cursor = QTextCursor(doc)
    cursor.setPosition(0)
    vocab_color = QColor("#C8E6C9")
    assert cursor.charFormat().foreground().color().name() == vocab_color.name()

    # Position 1 should have grammar color (N2: #F9A825)
    cursor.setPosition(1)
    grammar_color = QColor("#F9A825")
    assert cursor.charFormat().foreground().color().name() == grammar_color.name()


def test_apply_to_document_custom_colors() -> None:
    """Test that custom colors are applied correctly."""
    from PySide6.QtWidgets import QTextBrowser
    from PySide6.QtGui import QColor, QTextCursor

    custom_colors = {
        4: {"vocab": "#FF0000", "grammar": "#00FF00"},
    }
    renderer = HighlightRenderer(jlpt_colors=custom_colors)

    browser = QTextBrowser()
    doc = browser.document()
    vocab = [_make_vocab("猫", 0, 1, level=4)]
    analysis = AnalysisResult(tokens=[], vocab_hits=vocab, grammar_hits=[])

    renderer.apply_to_document(doc, "猫", analysis, user_level=4)

    cursor = QTextCursor(doc)
    cursor.setPosition(0)
    expected_color = QColor("#FF0000")
    assert cursor.charFormat().foreground().color().name() == expected_color.name()


def test_apply_to_document_update_colors() -> None:
    """Test that update_colors changes subsequent rendering."""
    from PySide6.QtWidgets import QTextBrowser
    from PySide6.QtGui import QColor, QTextCursor

    renderer = HighlightRenderer()
    new_colors = {
        4: {"vocab": "#AABBCC", "grammar": "#DDEEFF"},
    }
    renderer.update_colors(new_colors)

    browser = QTextBrowser()
    doc = browser.document()
    vocab = [_make_vocab("猫", 0, 1, level=4)]
    analysis = AnalysisResult(tokens=[], vocab_hits=vocab, grammar_hits=[])

    renderer.apply_to_document(doc, "猫", analysis, user_level=4)

    cursor = QTextCursor(doc)
    cursor.setPosition(0)
    expected_color = QColor("#AABBCC")
    assert cursor.charFormat().foreground().color().name() == expected_color.name()
```

#### 3.4.3 保留的测试

以下测试验证 `JLPT_COLORS` 结构和 `get_highlight_at_position()` 方法，保持不变：

- `test_jlpt_colors_has_all_five_levels`
- `test_jlpt_colors_each_level_has_vocab_and_grammar_keys`
- `test_jlpt_colors_exact_values`
- `test_get_highlight_at_position_returns_grammar_over_vocab`
- `test_get_highlight_at_position_returns_vocab_when_no_grammar`
- `test_get_highlight_at_position_returns_none_outside_all_hits`
- `test_get_highlight_at_position_boundary_inclusive_start`
- `test_get_highlight_at_position_boundary_exclusive_end`
- `test_get_highlight_at_position_empty_analysis_returns_none`
- `test_get_highlight_at_position_grammar_at_pos_with_no_vocab`

---

## 四、迁移步骤

### Phase 1: highlight.py 重写

1. 新增 PySide6 导入
2. 新增 `apply_to_document()` 方法
3. 移除 `build_rich_text()` 方法
4. 移除 `_render_spans()` 方法
5. 移除 `import html` 模块

### Phase 2: overlay.py 更新

1. 新增 `QTextBlockFormat`, `QTextCursor` 导入
2. 新增 `_set_centered_plain_text()` 辅助函数
3. 修改 `_render_in_browser()` 使用新 API
4. 修改 `on_asr_ready()` 使用新辅助函数
5. 修改 `set_status()` 使用新辅助函数
6. 移除 `_centered_html()` 函数

### Phase 3: sentence_detail.py 更新

1. 修改 `_build_japanese_section()` 使用 `setPlainText()` + 居中
2. 移除 `HighlightRenderer` 和 `_EMPTY_ANALYSIS` 导入

### Phase 4: 测试更新

1. 移除 `build_rich_text()` 相关测试
2. 新增 `apply_to_document()` 测试用例
3. 保持 `get_highlight_at_position()` 和 `JLPT_COLORS` 测试不变

### Phase 5: 验证

1. 运行完整测试套件: `pytest tests/`
2. 手动测试 hover 功能
3. 验证颜色显示正确
4. 验证居中对齐正确

---

## 五、风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| `QTextCharFormat` 与 HTML 渲染外观差异 | 低 | 颜色、加粗、居中均可完全对等实现 |
| `sentence_detail.py` 需要修改 | 低 | 简单修改，只是文本+居中 |
| 性能差异 | 低 | `QTextCharFormat` 直接操作文档，性能相当或更好 |
| 测试覆盖不足 | 中 | 新增完整的 `apply_to_document()` 测试 |
| 代码回滚困难 | 低 | Git 版本控制可随时回滚 |

---

## 六、文件变更清单

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| [`src/ui/highlight.py`](src/ui/highlight.py) | **重写** | 新增 `apply_to_document()`，移除 HTML 相关代码 |
| [`src/ui/overlay.py`](src/ui/overlay.py) | 修改 | 修改渲染逻辑，新增 `_set_centered_plain_text()`，移除 `_centered_html()` |
| [`src/ui/sentence_detail.py`](src/ui/sentence_detail.py) | 修改 | 使用 `setPlainText()` + 居中替代 HTML |
| [`tests/test_highlight.py`](tests/test_highlight.py) | 修改 | 移除 HTML 测试，新增 `apply_to_document()` 测试 |

---

## 七、验收标准

1. **功能验收**
   - [ ] Hover 检测准确命中正确的 vocab/grammar
   - [ ] 颜色显示与原 HTML 方案一致
   - [ ] 文本居中对齐正确
   - [ ] 状态文本（"Initializing..." 等）显示正常
   - [ ] `sentence_detail.py` 文本显示正常

2. **测试验收**
   - [ ] 所有现有 `get_highlight_at_position()` 测试通过
   - [ ] 所有 `JLPT_COLORS` 测试通过
   - [ ] 新增 `apply_to_document()` 测试通过
   - [ ] 位置对齐测试验证 bug 修复

3. **回归验收**
   - [ ] 历史导航功能正常
   - [ ] 配置热更新功能正常
   - [ ] tooltip 显示正常

4. **代码质量**
   - [ ] `ruff check .` 通过
   - [ ] `mypy src/` 通过
   - [ ] 无未使用的导入