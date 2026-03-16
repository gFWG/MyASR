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
    analysis = AnalysisResult(
        tokens=[],
        vocab_hits=[_make_vocab("べて", 1, 3, level=3)],
        grammar_hits=[_make_grammar("g1", "食べて", 0, 3, level=2)],
    )

    renderer.apply_to_document(qtextbrowser.document(), "食べて", analysis, user_level=4)

    cursor = QTextCursor(qtextbrowser.document())
    cursor.setPosition(2)
    assert cursor.charFormat().foreground().color().name() == QColor("#F9A825").name()
    assert isinstance(renderer.get_highlight_at_position(1, analysis), GrammarHit)


def test_multi_fragment_overlap_suppresses_entire_rule(
    renderer: HighlightRenderer, qtextbrowser: QTextBrowser
) -> None:
    analysis = AnalysisResult(
        tokens=[],
        vocab_hits=[_make_vocab("なら", 3, 5, level=4)],
        grammar_hits=[
            _make_grammar("g1", "がXXなら", 0, 5, level=2, matched_parts=((0, 1), (3, 5)))
        ],
    )

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
    analysis = AnalysisResult(
        tokens=[],
        vocab_hits=[_make_vocab("XX", 1, 3, level=4)],
        grammar_hits=[
            _make_grammar("g1", "がXXなら", 0, 5, level=2, matched_parts=((0, 1), (3, 5)))
        ],
    )

    renderer.apply_to_document(qtextbrowser.document(), "がXXなら", analysis, user_level=4)

    cursor = QTextCursor(qtextbrowser.document())
    cursor.setPosition(1)
    assert cursor.charFormat().foreground().color().name() == QColor("#F9A825").name()
    cursor.setPosition(2)
    assert cursor.charFormat().foreground().color().name() == QColor("#C8E6C9").name()
    cursor.setPosition(4)
    assert cursor.charFormat().foreground().color().name() == QColor("#F9A825").name()
    assert isinstance(renderer.get_highlight_at_position(0, analysis), GrammarHit)
    assert isinstance(renderer.get_highlight_at_position(1, analysis), VocabHit)
    assert isinstance(renderer.get_highlight_at_position(3, analysis), GrammarHit)
