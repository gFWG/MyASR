"""Tests for src/ui/highlight.py — HighlightRenderer."""

import pytest
from PySide6.QtGui import QColor, QFont, QTextCursor
from PySide6.QtWidgets import QApplication, QTextBrowser

from src.models import AnalysisResult, GrammarHit, VocabHit
from src.ui.highlight import HighlightRenderer


@pytest.fixture
def renderer() -> HighlightRenderer:
    return HighlightRenderer()


@pytest.fixture
def qtextbrowser(qapp: QApplication) -> QTextBrowser:
    """Create a QTextBrowser for testing with proper Qt application context."""
    browser = QTextBrowser()
    yield browser
    browser.deleteLater()


@pytest.fixture
def empty_analysis() -> AnalysisResult:
    return AnalysisResult(tokens=[], vocab_hits=[], grammar_hits=[])


def _make_vocab(surface: str, start: int, end: int, level: int = 3) -> VocabHit:
    return VocabHit(
        surface=surface,
        lemma=surface,
        pos="動詞",
        jlpt_level=level,
        start_pos=start,
        end_pos=end,
    )


def _make_grammar(
    rule_id: str,
    text: str,
    start: int,
    end: int,
    level: int = 2,
    matched_parts: tuple[tuple[int, int], ...] = (),
) -> GrammarHit:
    return GrammarHit(
        rule_id=rule_id,
        matched_text=text,
        jlpt_level=level,
        word="ながら",
        description="test grammar",
        start_pos=start,
        end_pos=end,
        matched_parts=matched_parts,
    )


# ------------------------------------------------------------------ #
# JLPT_COLORS structure                                               #
# ------------------------------------------------------------------ #


def test_jlpt_colors_has_all_five_levels(renderer: HighlightRenderer) -> None:
    assert set(renderer.JLPT_COLORS.keys()) == {1, 2, 3, 4, 5}


def test_jlpt_colors_each_level_has_vocab_and_grammar_keys(renderer: HighlightRenderer) -> None:
    for level, colors in renderer.JLPT_COLORS.items():
        assert "vocab" in colors, f"Level {level} missing vocab key"
        assert "grammar" in colors, f"Level {level} missing grammar key"


def test_jlpt_colors_exact_values(renderer: HighlightRenderer) -> None:
    assert renderer.JLPT_COLORS[4]["vocab"] == "#C8E6C9"
    assert renderer.JLPT_COLORS[4]["grammar"] == "#4CAF50"
    assert renderer.JLPT_COLORS[3]["vocab"] == "#BBDEFB"
    assert renderer.JLPT_COLORS[3]["grammar"] == "#1976D2"
    assert renderer.JLPT_COLORS[2]["vocab"] == "#FFF9C4"
    assert renderer.JLPT_COLORS[2]["grammar"] == "#F9A825"
    assert renderer.JLPT_COLORS[1]["vocab"] == "#FFCDD2"
    assert renderer.JLPT_COLORS[1]["grammar"] == "#D32F2F"


# ------------------------------------------------------------------ #
# get_highlight_at_position                                           #
# ------------------------------------------------------------------ #


def test_get_highlight_at_position_returns_grammar_over_vocab(
    renderer: HighlightRenderer,
) -> None:
    vocab = [_make_vocab("食べ", 0, 2, level=3)]
    grammar = [_make_grammar("g1", "食べている", 0, 5, level=2)]
    analysis = AnalysisResult(tokens=[], vocab_hits=vocab, grammar_hits=grammar)

    hit = renderer.get_highlight_at_position(1, analysis)
    assert isinstance(hit, GrammarHit)
    assert hit.rule_id == "g1"


def test_get_highlight_at_position_returns_vocab_when_no_grammar(
    renderer: HighlightRenderer,
) -> None:
    vocab = [_make_vocab("猫", 0, 1, level=4)]
    analysis = AnalysisResult(tokens=[], vocab_hits=vocab, grammar_hits=[])

    hit = renderer.get_highlight_at_position(0, analysis)
    assert isinstance(hit, VocabHit)
    assert hit.surface == "猫"


def test_get_highlight_at_position_returns_none_outside_all_hits(
    renderer: HighlightRenderer,
) -> None:
    vocab = [_make_vocab("猫", 0, 1, level=4)]
    grammar = [_make_grammar("g1", "食べ", 2, 4, level=2)]
    analysis = AnalysisResult(tokens=[], vocab_hits=vocab, grammar_hits=grammar)

    hit = renderer.get_highlight_at_position(10, analysis)
    assert hit is None


def test_get_highlight_at_position_boundary_inclusive_start(
    renderer: HighlightRenderer,
) -> None:
    vocab = [_make_vocab("猫", 3, 6, level=4)]
    analysis = AnalysisResult(tokens=[], vocab_hits=vocab, grammar_hits=[])

    hit = renderer.get_highlight_at_position(3, analysis)
    assert isinstance(hit, VocabHit)


def test_get_highlight_at_position_boundary_exclusive_end(
    renderer: HighlightRenderer,
) -> None:
    vocab = [_make_vocab("猫", 3, 6, level=4)]
    analysis = AnalysisResult(tokens=[], vocab_hits=vocab, grammar_hits=[])

    hit = renderer.get_highlight_at_position(6, analysis)
    assert hit is None


def test_get_highlight_at_position_empty_analysis_returns_none(
    renderer: HighlightRenderer, empty_analysis: AnalysisResult
) -> None:
    hit = renderer.get_highlight_at_position(0, empty_analysis)
    assert hit is None


def test_get_highlight_at_position_grammar_at_pos_with_no_vocab(
    renderer: HighlightRenderer,
) -> None:
    grammar = [_make_grammar("g2", "てい", 3, 5, level=3)]
    analysis = AnalysisResult(tokens=[], vocab_hits=[], grammar_hits=grammar)

    hit = renderer.get_highlight_at_position(4, analysis)
    assert isinstance(hit, GrammarHit)
    assert hit.rule_id == "g2"


# ------------------------------------------------------------------ #
# apply_to_document — QTextCharFormat API                           #
# ------------------------------------------------------------------ #


def test_apply_to_document_empty_text(
    renderer: HighlightRenderer, qtextbrowser: QTextBrowser
) -> None:
    """Test that empty text results in empty document."""
    doc = qtextbrowser.document()
    analysis = AnalysisResult(tokens=[], vocab_hits=[], grammar_hits=[])

    renderer.apply_to_document(doc, "", analysis, user_level=3)

    assert doc.toPlainText() == ""


def test_apply_to_document_plain_text_no_hits(
    renderer: HighlightRenderer, qtextbrowser: QTextBrowser
) -> None:
    """Test that text without hits is set as plain text."""
    doc = qtextbrowser.document()
    analysis = AnalysisResult(tokens=[], vocab_hits=[], grammar_hits=[])

    renderer.apply_to_document(doc, "食べる", analysis, user_level=3)

    assert doc.toPlainText() == "食べる"


def test_apply_to_document_vocab_highlight(
    renderer: HighlightRenderer, qtextbrowser: QTextBrowser
) -> None:
    """Test that vocab hits get highlighted with correct color."""
    doc = qtextbrowser.document()
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


def test_apply_to_document_position_alignment(
    renderer: HighlightRenderer, qtextbrowser: QTextBrowser
) -> None:
    """Test that cursor positions align with start_pos/end_pos.

    This is the core fix for the hover detection bug.
    """
    doc = qtextbrowser.document()

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


def test_apply_to_document_grammar_suppresses_vocab(
    renderer: HighlightRenderer, qtextbrowser: QTextBrowser
) -> None:
    """Test that grammar suppresses fully covered vocab."""
    doc = qtextbrowser.document()
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
    renderer: HighlightRenderer, qtextbrowser: QTextBrowser
) -> None:
    """Test that non-overlapping vocab and grammar both get highlighted."""
    doc = qtextbrowser.document()
    vocab = [_make_vocab("猫", 0, 1, level=4)]
    grammar = [_make_grammar("g1", "食べている", 1, 6, level=2)]
    analysis = AnalysisResult(tokens=[], vocab_hits=vocab, grammar_hits=grammar)

    renderer.apply_to_document(doc, "猫食べている", analysis, user_level=4)

    # charFormat() returns format of character BEFORE cursor position.
    # To get format at position N, move cursor to N+1.
    cursor = QTextCursor(doc)

    # Position 0 should have vocab color (N4: #C8E6C9)
    cursor.setPosition(1)  # charFormat() returns format of char at position 0
    vocab_color = QColor("#C8E6C9")
    assert cursor.charFormat().foreground().color().name() == vocab_color.name()

    # Position 1 should have grammar color (N2: #F9A825)
    cursor.setPosition(2)  # charFormat() returns format of char at position 1
    grammar_color = QColor("#F9A825")
    assert cursor.charFormat().foreground().color().name() == grammar_color.name()


def test_apply_to_document_multiple_vocab_hits(
    renderer: HighlightRenderer, qtextbrowser: QTextBrowser
) -> None:
    """Test that multiple vocab hits all get highlighted."""
    doc = qtextbrowser.document()
    vocab = [
        _make_vocab("猫", 0, 1, level=4),
        _make_vocab("犬", 1, 2, level=3),
    ]
    analysis = AnalysisResult(tokens=[], vocab_hits=vocab, grammar_hits=[])

    renderer.apply_to_document(doc, "猫犬", analysis, user_level=4)

    # charFormat() returns format of character BEFORE cursor position.
    cursor = QTextCursor(doc)

    # Position 0 should have N4 vocab color
    cursor.setPosition(1)  # charFormat() returns format of char at position 0
    vocab_n4_color = QColor("#C8E6C9")
    assert cursor.charFormat().foreground().color().name() == vocab_n4_color.name()

    # Position 1 should have N3 vocab color
    cursor.setPosition(2)  # charFormat() returns format of char at position 1
    vocab_n3_color = QColor("#BBDEFB")
    assert cursor.charFormat().foreground().color().name() == vocab_n3_color.name()


def test_apply_to_document_custom_colors(qtextbrowser: QTextBrowser) -> None:
    """Test that custom colors are applied correctly."""
    doc = qtextbrowser.document()

    custom_colors = {
        4: {"vocab": "#FF0000", "grammar": "#00FF00"},
    }
    renderer = HighlightRenderer(jlpt_colors=custom_colors)

    vocab = [_make_vocab("猫", 0, 1, level=4)]
    analysis = AnalysisResult(tokens=[], vocab_hits=vocab, grammar_hits=[])

    renderer.apply_to_document(doc, "猫", analysis, user_level=4)

    # charFormat() returns format of character BEFORE cursor position.
    cursor = QTextCursor(doc)
    cursor.setPosition(1)  # charFormat() returns format of char at position 0
    expected_color = QColor("#FF0000")
    assert cursor.charFormat().foreground().color().name() == expected_color.name()


def test_apply_to_document_update_colors(qtextbrowser: QTextBrowser) -> None:
    """Test that update_colors changes subsequent rendering."""
    doc = qtextbrowser.document()

    renderer = HighlightRenderer()
    new_colors = {
        4: {"vocab": "#AABBCC", "grammar": "#DDEEFF"},
    }
    renderer.update_colors(new_colors)

    vocab = [_make_vocab("猫", 0, 1, level=4)]
    analysis = AnalysisResult(tokens=[], vocab_hits=vocab, grammar_hits=[])

    renderer.apply_to_document(doc, "猫", analysis, user_level=4)

    # charFormat() returns format of character BEFORE cursor position.
    cursor = QTextCursor(doc)
    cursor.setPosition(1)  # charFormat() returns format of char at position 0
    expected_color = QColor("#AABBCC")
    assert cursor.charFormat().foreground().color().name() == expected_color.name()


def test_apply_to_document_default_colors(qtextbrowser: QTextBrowser) -> None:
    """Test that default renderer uses default JLPT colors."""
    doc = qtextbrowser.document()

    renderer = HighlightRenderer()
    vocab = [_make_vocab("猫", 0, 1, level=4)]
    analysis = AnalysisResult(tokens=[], vocab_hits=vocab, grammar_hits=[])

    renderer.apply_to_document(doc, "猫", analysis, user_level=4)

    # charFormat() returns format of character BEFORE cursor position.
    cursor = QTextCursor(doc)
    cursor.setPosition(1)  # charFormat() returns format of char at position 0
    expected_color = QColor("#C8E6C9")  # default N4 vocab color
    assert cursor.charFormat().foreground().color().name() == expected_color.name()


def test_apply_to_document_partial_overlap_both_present(
    renderer: HighlightRenderer, qtextbrowser: QTextBrowser
) -> None:
    """Test that partial overlap results in both vocab and grammar highlighted."""
    doc = qtextbrowser.document()

    # Vocab at (0,3), grammar only covers (1,3) — NOT a full cover
    vocab = [_make_vocab("食べて", 0, 3, level=3)]
    grammar = [_make_grammar("g1", "べて", 1, 3, level=2)]
    analysis = AnalysisResult(tokens=[], vocab_hits=vocab, grammar_hits=grammar)

    renderer.apply_to_document(doc, "食べている", analysis, user_level=4)

    # charFormat() returns format of character BEFORE cursor position.
    cursor = QTextCursor(doc)

    # Position 0 should have vocab color (not suppressed)
    cursor.setPosition(1)  # charFormat() returns format of char at position 0
    vocab_color = QColor("#BBDEFB")  # N3 vocab
    assert cursor.charFormat().foreground().color().name() == vocab_color.name()

    # Position 1 should have grammar color
    cursor.setPosition(2)  # charFormat() returns format of char at position 1
    grammar_color = QColor("#F9A825")  # N2 grammar
    assert cursor.charFormat().foreground().color().name() == grammar_color.name()


# ------------------------------------------------------------------ #
# Multi-part grammar highlighting (matched_parts)                     #
# ------------------------------------------------------------------ #


def test_get_highlight_at_position_grammar_parts_only(
    renderer: HighlightRenderer,
) -> None:
    """Grammar hit with matched_parts: only part positions return the hit."""
    # matched_parts=((0,1),(3,5)), full range [0,6), text length=6
    grammar = [_make_grammar("g1", "がXXなら", 0, 6, level=2, matched_parts=((0, 1), (3, 5)))]
    analysis = AnalysisResult(tokens=[], vocab_hits=[], grammar_hits=grammar)

    # Positions inside keyword parts return the hit
    assert isinstance(renderer.get_highlight_at_position(0, analysis), GrammarHit)
    assert isinstance(renderer.get_highlight_at_position(3, analysis), GrammarHit)
    assert isinstance(renderer.get_highlight_at_position(4, analysis), GrammarHit)

    # Positions in filler (1, 2) return None
    assert renderer.get_highlight_at_position(1, analysis) is None
    assert renderer.get_highlight_at_position(2, analysis) is None

    # Position at end (6) returns None
    assert renderer.get_highlight_at_position(6, analysis) is None


def test_get_highlight_at_position_grammar_fallback_full_range(
    renderer: HighlightRenderer,
) -> None:
    """Grammar hit with empty matched_parts falls back to full range."""
    grammar = [_make_grammar("g2", "てから", 0, 3, level=5, matched_parts=())]
    analysis = AnalysisResult(tokens=[], vocab_hits=[], grammar_hits=grammar)

    # All positions in [0, 3) return the hit
    assert isinstance(renderer.get_highlight_at_position(0, analysis), GrammarHit)
    assert isinstance(renderer.get_highlight_at_position(1, analysis), GrammarHit)
    assert isinstance(renderer.get_highlight_at_position(2, analysis), GrammarHit)

    # Position at end returns None
    assert renderer.get_highlight_at_position(3, analysis) is None


def test_apply_to_document_multi_part_grammar_partial_highlight(
    renderer: HighlightRenderer, qtextbrowser: QTextBrowser
) -> None:
    """Multi-part grammar only highlights keyword parts; filler gets no grammar color."""
    doc = qtextbrowser.document()
    # text: 'がXXなら' (6 chars), parts at (0,1) and (3,5)
    text = "がXXなら"
    grammar = [_make_grammar("g1", text, 0, 6, level=2, matched_parts=((0, 1), (3, 5)))]
    analysis = AnalysisResult(tokens=[], vocab_hits=[], grammar_hits=grammar)

    renderer.apply_to_document(doc, text, analysis, user_level=4)

    cursor = QTextCursor(doc)
    grammar_color = QColor("#F9A825")  # N2 grammar

    # Position 0 (が) — keyword part → grammar color
    cursor.setPosition(1)
    assert cursor.charFormat().foreground().color().name() == grammar_color.name()

    # Position 1 (X filler) — NOT a keyword part → no grammar color (default)
    cursor.setPosition(2)
    assert cursor.charFormat().foreground().color().name() != grammar_color.name()

    # Position 3 (な) — keyword part → grammar color
    cursor.setPosition(4)
    assert cursor.charFormat().foreground().color().name() == grammar_color.name()


def test_vocab_not_suppressed_in_grammar_filler_gap(
    renderer: HighlightRenderer, qtextbrowser: QTextBrowser
) -> None:
    """Vocab in the filler region between grammar parts is NOT suppressed."""
    doc = qtextbrowser.document()
    # grammar: parts=(0,1) and (3,5) in range [0,6); filler at [1,3)
    # vocab: [1,3) — sits entirely in filler
    text = "がXXなら "  # 6 chars (trailing space for end boundary clarity)
    grammar = [_make_grammar("g1", "がXXなら", 0, 6, level=2, matched_parts=((0, 1), (3, 5)))]
    vocab = [_make_vocab("XX", 1, 3, level=4)]
    analysis = AnalysisResult(tokens=[], vocab_hits=vocab, grammar_hits=grammar)

    renderer.apply_to_document(doc, text, analysis, user_level=4)

    cursor = QTextCursor(doc)
    vocab_color = QColor("#C8E6C9")  # N4 vocab

    # Position 1 (filler, has vocab) → vocab color, not grammar color
    cursor.setPosition(2)
    assert cursor.charFormat().foreground().color().name() == vocab_color.name()


def test_vocab_suppressed_within_grammar_part(
    renderer: HighlightRenderer, qtextbrowser: QTextBrowser
) -> None:
    """Vocab fully inside a keyword part is suppressed by grammar color."""
    doc = qtextbrowser.document()
    # grammar: single part covering full range [0,3); vocab also [0,3)
    text = "なら"
    grammar = [_make_grammar("g1", text, 0, 2, level=2, matched_parts=((0, 2),))]
    vocab = [_make_vocab("なら", 0, 2, level=4)]
    analysis = AnalysisResult(tokens=[], vocab_hits=vocab, grammar_hits=grammar)

    renderer.apply_to_document(doc, text, analysis, user_level=4)

    cursor = QTextCursor(doc)
    grammar_color = QColor("#F9A825")  # N2 grammar

    # Position 1 (middle of matched part) → grammar color (vocab suppressed)
    cursor.setPosition(2)
    assert cursor.charFormat().foreground().color().name() == grammar_color.name()
