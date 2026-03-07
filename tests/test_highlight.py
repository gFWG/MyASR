"""Tests for src/ui/highlight.py — HighlightRenderer."""

import html
from html.parser import HTMLParser

import pytest

from src.db.models import AnalysisResult, GrammarHit, VocabHit
from src.ui.highlight import HighlightRenderer


@pytest.fixture
def renderer() -> HighlightRenderer:
    return HighlightRenderer()


@pytest.fixture
def empty_analysis() -> AnalysisResult:
    return AnalysisResult(tokens=[], vocab_hits=[], grammar_hits=[])


def _make_vocab(surface: str, start: int, end: int, level: int = 3) -> VocabHit:
    return VocabHit(
        surface=surface,
        lemma=surface,
        pos="動詞",
        jlpt_level=level,
        user_level=4,
        start_pos=start,
        end_pos=end,
    )


def _make_grammar(rule_id: str, text: str, start: int, end: int, level: int = 2) -> GrammarHit:
    return GrammarHit(
        rule_id=rule_id,
        matched_text=text,
        jlpt_level=level,
        confidence_type="high",
        description="test grammar",
        start_pos=start,
        end_pos=end,
    )


class _HTMLValidator(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.errors: list[str] = []

    def handle_error(self, message: str) -> None:
        self.errors.append(message)


def _is_valid_html(fragment: str) -> bool:
    validator = _HTMLValidator()
    try:
        validator.feed(fragment)
    except Exception:
        return False
    return len(validator.errors) == 0


# ------------------------------------------------------------------ #
# JLPT_COLORS structure                                               #
# ------------------------------------------------------------------ #


def test_jlpt_colors_has_all_four_levels(renderer: HighlightRenderer) -> None:
    assert set(renderer.JLPT_COLORS.keys()) == {1, 2, 3, 4}


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
# build_rich_text — edge cases                                        #
# ------------------------------------------------------------------ #


def test_build_rich_text_empty_text_returns_empty_string(
    renderer: HighlightRenderer, empty_analysis: AnalysisResult
) -> None:
    result = renderer.build_rich_text("", empty_analysis, user_level=3)
    assert result == ""


def test_build_rich_text_no_hits_returns_escaped_plain_text(
    renderer: HighlightRenderer, empty_analysis: AnalysisResult
) -> None:
    result = renderer.build_rich_text("食べる", empty_analysis, user_level=3)
    # Output is wrapped in a centering table; the escaped text appears inside it
    assert html.escape("食べる") in result
    assert "<span" not in result


def test_build_rich_text_html_escapes_special_chars(
    renderer: HighlightRenderer, empty_analysis: AnalysisResult
) -> None:
    result = renderer.build_rich_text("<script>alert(1)</script>", empty_analysis, user_level=3)
    assert "<script>" not in result
    assert "&lt;script&gt;" in result


# ------------------------------------------------------------------ #
# build_rich_text — grammar-over-vocab priority                       #
# ------------------------------------------------------------------ #


def test_build_rich_text_grammar_suppresses_fully_covered_vocab(
    renderer: HighlightRenderer,
) -> None:
    vocab = [_make_vocab("食べ", 0, 2, level=3)]
    grammar = [_make_grammar("g1", "食べている", 0, 5, level=2)]
    analysis = AnalysisResult(tokens=[], vocab_hits=vocab, grammar_hits=grammar)
    result = renderer.build_rich_text("食べている", analysis, user_level=4)

    # Grammar color (N2) present
    assert "#F9A825" in result
    # Vocab color (N3) absent — suppressed by grammar
    assert "#BBDEFB" not in result


def test_build_rich_text_non_overlapping_hits_both_colors_present(
    renderer: HighlightRenderer,
) -> None:
    vocab = [_make_vocab("猫", 0, 1, level=4)]
    grammar = [_make_grammar("g1", "食べている", 1, 6, level=2)]
    analysis = AnalysisResult(tokens=[], vocab_hits=vocab, grammar_hits=grammar)
    result = renderer.build_rich_text("猫食べている", analysis, user_level=4)

    # Both colors should be present
    assert "#C8E6C9" in result  # N4 vocab
    assert "#F9A825" in result  # N2 grammar


def test_build_rich_text_partial_overlap_vocab_not_suppressed(
    renderer: HighlightRenderer,
) -> None:
    # Vocab at (0,3), grammar only covers (1,3) — NOT a full cover
    vocab = [_make_vocab("食べて", 0, 3, level=3)]
    grammar = [_make_grammar("g1", "べて", 1, 3, level=2)]
    analysis = AnalysisResult(tokens=[], vocab_hits=vocab, grammar_hits=grammar)
    result = renderer.build_rich_text("食べている", analysis, user_level=4)

    # Vocab color should be present (partial overlap, not suppressed)
    assert "#BBDEFB" in result
    assert "#F9A825" in result


def test_build_rich_text_grammar_exactly_equals_vocab_range_suppresses(
    renderer: HighlightRenderer,
) -> None:
    vocab = [_make_vocab("食べ", 0, 2, level=3)]
    grammar = [_make_grammar("g1", "食べ", 0, 2, level=2)]
    analysis = AnalysisResult(tokens=[], vocab_hits=vocab, grammar_hits=grammar)
    result = renderer.build_rich_text("食べる", analysis, user_level=4)

    assert "#F9A825" in result  # grammar N2
    assert "#BBDEFB" not in result  # vocab N3 suppressed


def test_build_rich_text_grammar_larger_than_vocab_suppresses(
    renderer: HighlightRenderer,
) -> None:
    vocab = [_make_vocab("食べ", 1, 3, level=3)]
    grammar = [_make_grammar("g1", "て食べている", 0, 6, level=1)]
    analysis = AnalysisResult(tokens=[], vocab_hits=vocab, grammar_hits=grammar)
    result = renderer.build_rich_text("て食べている", analysis, user_level=4)

    assert "#D32F2F" in result  # grammar N1
    assert "#BBDEFB" not in result  # vocab N3 suppressed


# ------------------------------------------------------------------ #
# build_rich_text — HTML structure                                    #
# ------------------------------------------------------------------ #


def test_build_rich_text_output_is_valid_html(renderer: HighlightRenderer) -> None:
    vocab = [_make_vocab("猫", 0, 1, level=4)]
    grammar = [_make_grammar("g1", "食べている", 1, 6, level=2)]
    analysis = AnalysisResult(tokens=[], vocab_hits=vocab, grammar_hits=grammar)
    result = renderer.build_rich_text("猫食べている", analysis, user_level=4)
    assert _is_valid_html(result)


def test_build_rich_text_contains_span_with_font_weight_bold(
    renderer: HighlightRenderer,
) -> None:
    vocab = [_make_vocab("猫", 0, 1, level=4)]
    analysis = AnalysisResult(tokens=[], vocab_hits=vocab, grammar_hits=[])
    result = renderer.build_rich_text("猫", analysis, user_level=4)
    assert "font-weight: bold" in result


def test_build_rich_text_plain_text_outside_spans_is_escaped(
    renderer: HighlightRenderer,
) -> None:
    vocab = [_make_vocab("猫", 2, 3, level=4)]
    analysis = AnalysisResult(tokens=[], vocab_hits=vocab, grammar_hits=[])
    result = renderer.build_rich_text("AB猫CD", analysis, user_level=4)
    assert "AB" in result
    assert "CD" in result
    assert "font-weight: bold" in result


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
# Multiple vocab hits with no grammar                                 #
# ------------------------------------------------------------------ #


def test_build_rich_text_multiple_vocab_hits_all_colored(
    renderer: HighlightRenderer,
) -> None:
    vocab = [
        _make_vocab("猫", 0, 1, level=4),
        _make_vocab("犬", 1, 2, level=3),
    ]
    analysis = AnalysisResult(tokens=[], vocab_hits=vocab, grammar_hits=[])
    result = renderer.build_rich_text("猫犬", analysis, user_level=4)

    assert "#C8E6C9" in result  # N4 vocab
    assert "#BBDEFB" in result  # N3 vocab


# ------------------------------------------------------------------ #
# build_rich_text — centering table wrapper                           #
# ------------------------------------------------------------------ #


def test_build_rich_text_contains_centering_table(
    renderer: HighlightRenderer, empty_analysis: AnalysisResult
) -> None:
    result = renderer.build_rich_text("食べる", empty_analysis, user_level=3)
    assert "<table" in result


def test_build_rich_text_no_inline_block(
    renderer: HighlightRenderer, empty_analysis: AnalysisResult
) -> None:
    result = renderer.build_rich_text("食べる", empty_analysis, user_level=3)
    assert "inline-block" not in result
