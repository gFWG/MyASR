"""Tests for src/ui/tooltip.py — TooltipPopup."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication

from src.models import GrammarHit, VocabHit
from src.ui.tooltip import TooltipPopup


@pytest.fixture
def tooltip(qapp: QApplication) -> TooltipPopup:
    return TooltipPopup()


def _make_vocab_hit(
    surface: str = "食べ",
    lemma: str = "食べる",
    pos: str = "動詞",
    jlpt_level: int = 5,
    pronunciation: str = "",
    definition: str = "",
) -> VocabHit:
    return VocabHit(
        surface=surface,
        lemma=lemma,
        pos=pos,
        jlpt_level=jlpt_level,
        start_pos=0,
        end_pos=len(surface),
        pronunciation=pronunciation,
        definition=definition,
    )


def _make_grammar_hit(
    matched_text: str = "ながら",
    jlpt_level: int = 3,
    word: str = "ても",
    description: str = "while doing",
) -> GrammarHit:
    return GrammarHit(
        rule_id="N3_nagara",
        matched_text=matched_text,
        jlpt_level=jlpt_level,
        word=word,
        description=description,
        start_pos=0,
        end_pos=len(matched_text),
    )


def test_tooltip_has_frameless_hint(tooltip: TooltipPopup) -> None:
    from PySide6.QtCore import Qt

    flags = tooltip.windowFlags()
    assert flags & Qt.WindowType.FramelessWindowHint


def test_tooltip_has_stays_on_top_hint(tooltip: TooltipPopup) -> None:
    from PySide6.QtCore import Qt

    flags = tooltip.windowFlags()
    assert flags & Qt.WindowType.WindowStaysOnTopHint


def test_tooltip_has_tool_hint(tooltip: TooltipPopup) -> None:
    from PySide6.QtCore import Qt

    flags = tooltip.windowFlags()
    assert flags & Qt.WindowType.Tool


def test_tooltip_max_width(tooltip: TooltipPopup) -> None:
    assert tooltip.maximumWidth() == 300


def test_show_for_vocab_sets_level_label(tooltip: TooltipPopup) -> None:
    hit = _make_vocab_hit(jlpt_level=2)
    tooltip.show_for_vocab(hit, QPoint(100, 100))
    assert tooltip._level_label.text() == "N2"


def test_show_for_vocab_sets_word_label(tooltip: TooltipPopup) -> None:
    hit = _make_vocab_hit(lemma="食べる", surface="食べ")
    tooltip.show_for_vocab(hit, QPoint(100, 100))
    assert "食べる" in tooltip._word_label.text()
    assert "食べ" in tooltip._word_label.text()


def test_show_for_vocab_sets_desc_label(tooltip: TooltipPopup) -> None:
    hit = _make_vocab_hit(pos="動詞")
    tooltip.show_for_vocab(hit, QPoint(100, 100))
    assert tooltip._desc_label.text() == "動詞"
    assert not tooltip._desc_label.isHidden()


def test_show_for_vocab_with_definition(tooltip: TooltipPopup) -> None:
    hit = _make_vocab_hit(pos="動詞", definition="to eat")
    tooltip.show_for_vocab(hit, QPoint(100, 100))
    assert tooltip._desc_label.text() == "動詞 • to eat"
    assert not tooltip._desc_label.isHidden()


def test_show_for_vocab_with_pronunciation(tooltip: TooltipPopup) -> None:
    hit = _make_vocab_hit(pronunciation="タベル")
    tooltip.show_for_vocab(hit, QPoint(100, 100))
    assert tooltip._pronunciation_label.text() == "タベル"
    assert not tooltip._pronunciation_label.isHidden()


def test_show_for_vocab_without_pronunciation_hides_label(tooltip: TooltipPopup) -> None:
    hit = _make_vocab_hit(pronunciation="")
    tooltip.show_for_vocab(hit, QPoint(100, 100))
    assert tooltip._pronunciation_label.isHidden()


def test_show_for_vocab_empty_pos_and_def(tooltip: TooltipPopup) -> None:
    hit = _make_vocab_hit(pos="", definition="")
    tooltip.show_for_vocab(hit, QPoint(100, 100))
    assert tooltip._desc_label.isHidden()


def test_show_for_vocab_makes_widget_visible(tooltip: TooltipPopup) -> None:
    hit = _make_vocab_hit()
    tooltip.show_for_vocab(hit, QPoint(100, 100))
    assert not tooltip.isHidden()


def test_show_for_grammar_sets_word_label(tooltip: TooltipPopup) -> None:
    hit = _make_grammar_hit(word="ながら")
    tooltip.show_for_grammar(hit, QPoint(100, 100))
    assert "ながら" in tooltip._word_label.text()


def test_show_for_grammar_sets_level_label(tooltip: TooltipPopup) -> None:
    hit = _make_grammar_hit(jlpt_level=3)
    tooltip.show_for_grammar(hit, QPoint(100, 100))
    assert tooltip._level_label.text() == "N3"


def test_show_for_grammar_sets_desc_label(tooltip: TooltipPopup) -> None:
    hit = _make_grammar_hit(word="ても", description="while doing")
    tooltip.show_for_grammar(hit, QPoint(100, 100))
    assert "while doing" in tooltip._desc_label.text()
    assert not tooltip._desc_label.isHidden()
    assert tooltip._pronunciation_label.isHidden()


def test_hide_tooltip_hides_widget(tooltip: TooltipPopup) -> None:
    hit = _make_vocab_hit()
    tooltip.show_for_vocab(hit, QPoint(100, 100))
    assert not tooltip.isHidden()
    tooltip.hide_tooltip()
    assert tooltip.isHidden()


def test_reset_dedup_is_noop(tooltip: TooltipPopup) -> None:
    """reset_dedup exists for API compatibility but is a no-op."""
    # Should not raise
    tooltip.reset_dedup()


def test_shown_set_not_used(tooltip: TooltipPopup) -> None:
    """After removing DB persistence, tooltip no longer tracks shown state."""
    # The _shown attribute was removed; ensure API still works
    hit = _make_vocab_hit()
    tooltip.show_for_vocab(hit, QPoint(100, 100))
    assert not tooltip.isHidden()
