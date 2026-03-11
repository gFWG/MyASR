"""Tests for src/ui/overlay.py — OverlayWindow."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from src.config import AppConfig
from src.db.models import AnalysisResult, GrammarHit, SentenceResult, VocabHit
from src.ui.overlay import OverlayWindow, _centered_html


@pytest.fixture
def overlay(qapp: QApplication) -> OverlayWindow:
    with patch(
        "src.ui.overlay.HighlightRenderer.build_rich_text",
        return_value="<b>テスト</b>",
    ):
        return OverlayWindow(AppConfig())


def _make_result(japanese_text: str = "テスト文") -> SentenceResult:
    return SentenceResult(
        japanese_text=japanese_text,
        analysis=AnalysisResult(tokens=[], vocab_hits=[], grammar_hits=[]),
    )


def test_overlay_has_window_flags(overlay: OverlayWindow) -> None:
    flags = overlay.windowFlags()
    assert flags & Qt.WindowType.FramelessWindowHint
    assert flags & Qt.WindowType.WindowStaysOnTopHint
    assert flags & Qt.WindowType.Tool


def test_overlay_initial_size_uses_config_defaults(overlay: OverlayWindow) -> None:
    assert overlay.width() == 800
    assert overlay.height() == 120


def test_overlay_uses_custom_dimensions(qapp: QApplication) -> None:
    with patch(
        "src.ui.overlay.HighlightRenderer.build_rich_text",
        return_value="<b>テスト</b>",
    ):
        window = OverlayWindow(AppConfig(overlay_width=640, overlay_height=110))
    assert window.width() == 640
    assert window.height() == 110


def test_set_status_updates_jp_browser(overlay: OverlayWindow) -> None:
    overlay.set_status("Listening...")
    assert "Listening..." in overlay._jp_browser.toPlainText()


def test_centered_html_wraps_and_escapes() -> None:
    result = _centered_html("<script>x</script>")
    assert "<table" in result
    assert 'align="center"' in result
    assert "&lt;script&gt;x&lt;/script&gt;" in result


def test_on_sentence_ready_stores_result_and_history(overlay: OverlayWindow) -> None:
    result = _make_result()
    with patch(
        "src.ui.overlay.HighlightRenderer.build_rich_text",
        return_value="<b>テスト</b>",
    ):
        overlay.on_sentence_ready(result)
    assert overlay._current_result is result
    assert overlay._history == [result]
    assert overlay._history_index == 0


def test_on_sentence_ready_filters_vocab_when_disabled(overlay: OverlayWindow) -> None:
    overlay._enable_vocab = False
    vocab_hit = VocabHit(
        surface="食べ",
        lemma="食べる",
        pos="動詞",
        jlpt_level=4,
        user_level=3,
        start_pos=0,
        end_pos=2,
    )
    result = SentenceResult(
        japanese_text="食べる",
        analysis=AnalysisResult(tokens=[], vocab_hits=[vocab_hit], grammar_hits=[]),
    )
    captured: list[AnalysisResult] = []

    def capture_analysis(text: str, analysis: AnalysisResult, user_level: int) -> str:
        del text, user_level
        captured.append(analysis)
        return "<b>食べる</b>"

    with patch("src.ui.overlay.HighlightRenderer.build_rich_text", side_effect=capture_analysis):
        overlay.on_sentence_ready(result)

    assert len(captured) == 1
    assert captured[0].vocab_hits == []


def test_on_sentence_ready_filters_grammar_when_disabled(overlay: OverlayWindow) -> None:
    overlay._enable_grammar = False
    grammar_hit = GrammarHit(
        rule_id="te-form",
        matched_text="食べて",
        jlpt_level=4,
        confidence_type="exact",
        description="te-form",
        start_pos=0,
        end_pos=3,
    )
    result = SentenceResult(
        japanese_text="食べている",
        analysis=AnalysisResult(tokens=[], vocab_hits=[], grammar_hits=[grammar_hit]),
    )
    captured: list[AnalysisResult] = []

    def capture_analysis(text: str, analysis: AnalysisResult, user_level: int) -> str:
        del text, user_level
        captured.append(analysis)
        return "<b>食べている</b>"

    with patch("src.ui.overlay.HighlightRenderer.build_rich_text", side_effect=capture_analysis):
        overlay.on_sentence_ready(result)

    assert len(captured) == 1
    assert captured[0].grammar_hits == []


def test_history_respects_max_history_from_config(qapp: QApplication) -> None:
    with patch(
        "src.ui.overlay.HighlightRenderer.build_rich_text",
        return_value="<b>テスト</b>",
    ):
        window = OverlayWindow(AppConfig(max_history=3))

    for idx in range(5):
        window.on_sentence_ready(_make_result(japanese_text=f"sentence {idx}"))

    assert len(window._history) == 3
    assert [item.japanese_text for item in window._history] == [
        "sentence 2",
        "sentence 3",
        "sentence 4",
    ]
    assert window._history_index == 2


def test_prev_and_next_sentence_navigation(overlay: OverlayWindow) -> None:
    first = _make_result(japanese_text="first")
    second = _make_result(japanese_text="second")

    overlay.on_sentence_ready(first)
    overlay.on_sentence_ready(second)

    overlay._prev_sentence()
    assert overlay._history_index == 0
    assert overlay._current_result is first

    overlay._next_sentence()
    assert overlay._history_index == 1
    assert overlay._current_result is second


def test_navigation_noop_on_empty_history(overlay: OverlayWindow) -> None:
    overlay._prev_sentence()
    overlay._next_sentence()
    assert overlay._history_index == -1


def test_arrow_buttons_always_visible_on_init(overlay: OverlayWindow) -> None:
    assert not overlay._prev_btn.isHidden()
    assert not overlay._next_btn.isHidden()
    assert not overlay._prev_btn.isEnabled()
    assert not overlay._next_btn.isEnabled()


def test_arrow_buttons_state_after_history_navigation(overlay: OverlayWindow) -> None:
    first = _make_result(japanese_text="first")
    second = _make_result(japanese_text="second")

    overlay.on_sentence_ready(first)
    assert not overlay._prev_btn.isEnabled()
    assert not overlay._next_btn.isEnabled()

    overlay.on_sentence_ready(second)
    assert overlay._prev_btn.isEnabled()
    assert not overlay._next_btn.isEnabled()

    overlay._prev_sentence()
    assert not overlay._prev_btn.isEnabled()
    assert overlay._next_btn.isEnabled()


def test_on_config_changed_updates_runtime_settings(overlay: OverlayWindow) -> None:
    config = AppConfig(
        overlay_opacity=0.5,
        user_jlpt_level=2,
        enable_vocab_highlight=False,
        enable_grammar_highlight=False,
        max_history=5,
    )
    overlay.on_config_changed(config)

    assert overlay.windowOpacity() == pytest.approx(0.5, abs=0.01)
    assert overlay._user_level == 2
    assert overlay._enable_vocab is False
    assert overlay._enable_grammar is False
    assert overlay._max_history == 5


def test_edge_at_detects_corners_and_edges(overlay: OverlayWindow) -> None:
    assert overlay._edge_at(overlay.rect().center()) == ""
    assert overlay._edge_at(overlay.rect().topLeft()) == "tl"
    assert overlay._edge_at(overlay.rect().topRight()) == "tr"
    assert overlay._edge_at(overlay.rect().bottomLeft()) == "bl"
    assert overlay._edge_at(overlay.rect().bottomRight()) == "br"
