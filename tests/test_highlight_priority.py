"""Tests for Grammar vs Vocab conflict resolution in HighlightRenderer.

The conflict resolution is handled by AnalysisResult.resolve_conflicts(),
which is called by SentenceResult.get_display_analysis().
These tests verify that the renderer correctly uses the resolved data.
"""

from collections.abc import Iterator

import pytest
from PySide6.QtGui import QColor, QTextCursor
from PySide6.QtWidgets import QApplication, QTextBrowser

from src.models import AnalysisResult, GrammarHit, VocabHit
from src.ui.highlight import HighlightRenderer


@pytest.fixture
def renderer() -> HighlightRenderer:
    return HighlightRenderer()


@pytest.fixture
def qtextbrowser(qapp: QApplication) -> Iterator[QTextBrowser]:
    browser = QTextBrowser()
    yield browser
    browser.deleteLater()


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


def test_single_fragment_covering_word_takes_priority(
    renderer: HighlightRenderer, qtextbrowser: QTextBrowser
) -> None:
    """When grammar fully contains vocab and is longer, grammar wins."""
    raw_analysis = AnalysisResult(
        tokens=[],
        vocab_hits=[_make_vocab("べて", 1, 3, level=3)],
        grammar_hits=[_make_grammar("g1", "食べて", 0, 3, level=2)],
    )
    # Resolve conflicts (grammar wins because it's longer)
    analysis = raw_analysis.resolve_conflicts()

    renderer.apply_to_document(qtextbrowser.document(), "食べて", analysis, user_level=4)

    cursor = QTextCursor(qtextbrowser.document())
    cursor.setPosition(2)
    assert cursor.charFormat().foreground().color().name() == QColor("#F9A825").name()
    assert isinstance(renderer.get_highlight_at_position(1, analysis), GrammarHit)


def test_multi_fragment_overlap_suppresses_entire_rule(
    renderer: HighlightRenderer, qtextbrowser: QTextBrowser
) -> None:
    """When multi-fragment grammar overlaps with vocab, grammar is suppressed."""
    raw_analysis = AnalysisResult(
        tokens=[],
        vocab_hits=[_make_vocab("なら", 3, 5, level=4)],
        grammar_hits=[
            _make_grammar("g1", "がXXなら", 0, 5, level=2, matched_parts=((0, 1), (3, 5)))
        ],
    )
    # Resolve conflicts (grammar suppressed because fragment overlaps vocab)
    analysis = raw_analysis.resolve_conflicts()

    renderer.apply_to_document(qtextbrowser.document(), "がXXなら", analysis, user_level=4)

    cursor = QTextCursor(qtextbrowser.document())
    cursor.setPosition(1)
    assert cursor.charFormat().foreground().color().name() != QColor("#F9A825").name()
    cursor.setPosition(4)
    assert cursor.charFormat().foreground().color().name() == QColor("#C8E6C9").name()
    assert renderer.get_highlight_at_position(0, analysis) is None
    assert isinstance(renderer.get_highlight_at_position(3, analysis), VocabHit)


def test_multi_fragment_non_overlapping_rule_still_highlights(
    renderer: HighlightRenderer, qtextbrowser: QTextBrowser
) -> None:
    """Multi-fragment grammar with vocab in filler region: both are preserved."""
    raw_analysis = AnalysisResult(
        tokens=[],
        vocab_hits=[_make_vocab("XX", 1, 3, level=4)],
        grammar_hits=[
            _make_grammar("g1", "がXXなら", 0, 5, level=2, matched_parts=((0, 1), (3, 5)))
        ],
    )
    # Resolve conflicts (no overlap, both preserved)
    analysis = raw_analysis.resolve_conflicts()

    renderer.apply_to_document(qtextbrowser.document(), "がXXなら", analysis, user_level=4)

    cursor = QTextCursor(qtextbrowser.document())
    # Position 0 is grammar keyword part
    cursor.setPosition(1)
    assert cursor.charFormat().foreground().color().name() == QColor("#F9A825").name()
    # Position 1 is filler with vocab
    cursor.setPosition(2)
    assert cursor.charFormat().foreground().color().name() == QColor("#C8E6C9").name()
    # Position 3 is grammar keyword part
    cursor.setPosition(4)
    assert cursor.charFormat().foreground().color().name() == QColor("#F9A825").name()
    # Hover detection: grammar keyword parts return GrammarHit
    assert isinstance(renderer.get_highlight_at_position(0, analysis), GrammarHit)
    # Hover detection: filler with vocab returns VocabHit
    assert isinstance(renderer.get_highlight_at_position(1, analysis), VocabHit)
    # Hover detection: grammar keyword part returns GrammarHit
    assert isinstance(renderer.get_highlight_at_position(3, analysis), GrammarHit)


def test_multi_fragment_shorter_vocab_contained_in_fragment_grammar_wins(
    renderer: HighlightRenderer, qtextbrowser: QTextBrowser
) -> None:
    """Multi-fragment grammar with vocab shorter than fragment: grammar wins.

    This tests the fix for the bug where "とか...とか" grammar was suppressed
    by the single-character vocab "と".

    Text: "XXとかYYとか"
    Positions: X(0) X(1) と(2) か(3) Y(4) Y(5) と(6) か(7) - total 8 chars

    Scenario:
    - Grammar "とか～とか" has fragments at (2,4) and (6,8), each length 2
    - Vocab "と" at (2,3) has length 1, fully contained in fragment (2,4)
    - Since vocab length (1) < fragment length (2) and vocab is fully contained,
      the grammar fragment wins → entire grammar preserved, vocab suppressed.

    Note: Qt charFormat() returns the format of the character BEFORE the cursor position.
    To check the format of character at position N, we use setPosition(N+1).
    """
    raw_analysis = AnalysisResult(
        tokens=[],
        vocab_hits=[_make_vocab("と", 2, 3, level=1)],
        grammar_hits=[
            _make_grammar(
                "g1", "XXとかYYとか", 0, 8, level=2, matched_parts=((2, 4), (6, 8))
            )
        ],
    )
    # Resolve conflicts (grammar wins because fragment is longer than vocab)
    analysis = raw_analysis.resolve_conflicts()

    renderer.apply_to_document(qtextbrowser.document(), "XXとかYYとか", analysis, user_level=4)

    cursor = QTextCursor(qtextbrowser.document())
    # Fragment (2,4) covers characters at positions 2 and 3 ("と" and "か")
    # To check format at position N, setPosition(N+1) checks the char at position N
    cursor.setPosition(3)  # checks char at position 2 ("と")
    assert cursor.charFormat().foreground().color().name() == QColor("#F9A825").name()
    cursor.setPosition(4)  # checks char at position 3 ("か")
    assert cursor.charFormat().foreground().color().name() == QColor("#F9A825").name()
    # Fragment (6,8) covers characters at positions 6 and 7
    cursor.setPosition(7)  # checks char at position 6 ("と")
    assert cursor.charFormat().foreground().color().name() == QColor("#F9A825").name()
    cursor.setPosition(8)  # checks char at position 7 ("か")
    assert cursor.charFormat().foreground().color().name() == QColor("#F9A825").name()
    # Hover detection: grammar keyword parts return GrammarHit
    assert isinstance(renderer.get_highlight_at_position(2, analysis), GrammarHit)
    assert isinstance(renderer.get_highlight_at_position(6, analysis), GrammarHit)
    # Vocab "と" is suppressed because it's fully covered by grammar fragment
    vocab_hits = [h for h in analysis.vocab_hits if h.start_pos == 2]
    assert len(vocab_hits) == 0


def test_multi_fragment_vocab_equal_length_fragment_vocab_wins(
    renderer: HighlightRenderer, qtextbrowser: QTextBrowser
) -> None:
    """Multi-fragment grammar with vocab length >= fragment length: vocab wins.

    When vocab length equals fragment length, vocab wins (same rule as single-fragment).

    Text: "XXとかYYとか"
    Positions: X(0) X(1) と(2) か(3) Y(4) Y(5) と(6) か(7) - total 8 chars

    Scenario:
    - Grammar has fragments at (2,4) and (6,8), each length 2
    - Vocab "とか" at (2,4) has length 2, exactly matching fragment
    - Since vocab length (2) >= fragment length (2), vocab wins → grammar suppressed.

    Note: Qt charFormat() returns the format of the character BEFORE the cursor position.
    """
    raw_analysis = AnalysisResult(
        tokens=[],
        vocab_hits=[_make_vocab("とか", 2, 4, level=3)],
        grammar_hits=[
            _make_grammar(
                "g1", "XXとかYYとか", 0, 8, level=2, matched_parts=((2, 4), (6, 8))
            )
        ],
    )
    # Resolve conflicts (vocab wins because length >= fragment)
    analysis = raw_analysis.resolve_conflicts()

    renderer.apply_to_document(qtextbrowser.document(), "XXとかYYとか", analysis, user_level=4)

    cursor = QTextCursor(qtextbrowser.document())
    # Vocab "とか" covers positions 2-3, grammar is suppressed
    cursor.setPosition(3)  # checks char at position 2 ("と")
    assert cursor.charFormat().foreground().color().name() == QColor("#BBDEFB").name()
    cursor.setPosition(4)  # checks char at position 3 ("か")
    assert cursor.charFormat().foreground().color().name() == QColor("#BBDEFB").name()
    # Grammar should be completely suppressed
    assert len(analysis.grammar_hits) == 0
    assert isinstance(renderer.get_highlight_at_position(2, analysis), VocabHit)


def test_multi_fragment_vocab_partial_overlap_vocab_wins(
    renderer: HighlightRenderer, qtextbrowser: QTextBrowser
) -> None:
    """Multi-fragment grammar with vocab partially overlapping fragment: vocab wins.

    When vocab partially overlaps fragment (not fully contained), vocab wins.

    Text: "XXとかYYとか"
    Positions: X(0) X(1) と(2) か(3) Y(4) Y(5) と(6) か(7) - total 8 chars

    Scenario:
    - Grammar has fragments at (2,4) and (6,8)
    - Vocab "かY" at (3,5) partially overlaps fragment (2,4)
    - Since vocab is not fully contained in fragment, vocab wins → grammar suppressed.
    """
    raw_analysis = AnalysisResult(
        tokens=[],
        vocab_hits=[_make_vocab("かY", 3, 5, level=3)],
        grammar_hits=[
            _make_grammar(
                "g1", "XXとかYYとか", 0, 8, level=2, matched_parts=((2, 4), (6, 8))
            )
        ],
    )
    # Resolve conflicts (vocab wins due to partial overlap)
    analysis = raw_analysis.resolve_conflicts()

    # Grammar should be suppressed
    assert len(analysis.grammar_hits) == 0
    # Vocab should be preserved
    assert len(analysis.vocab_hits) == 1
    assert isinstance(renderer.get_highlight_at_position(3, analysis), VocabHit)
