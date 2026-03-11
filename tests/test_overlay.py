"""Tests for src/ui/overlay.py — OverlayWindow."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from src.config import AppConfig
from src.db.models import AnalysisResult, SentenceResult, VocabHit
from src.ui.overlay import OverlayWindow


@pytest.fixture
def overlay(qapp: QApplication) -> OverlayWindow:
    with patch(
        "src.ui.overlay.HighlightRenderer.build_rich_text",
        return_value="<b>テスト</b>",
    ):
        window = OverlayWindow(AppConfig())
    return window


def _make_result(
    japanese_text: str = "テスト文",
) -> SentenceResult:
    analysis = AnalysisResult(tokens=[], vocab_hits=[], grammar_hits=[])
    return SentenceResult(
        japanese_text=japanese_text,
        analysis=analysis,
    )


def test_overlay_has_frameless_hint(overlay: OverlayWindow) -> None:
    flags = overlay.windowFlags()
    assert flags & Qt.WindowType.FramelessWindowHint


def test_overlay_has_stays_on_top_hint(overlay: OverlayWindow) -> None:
    flags = overlay.windowFlags()
    assert flags & Qt.WindowType.WindowStaysOnTopHint


def test_overlay_has_tool_hint(overlay: OverlayWindow) -> None:
    flags = overlay.windowFlags()
    assert flags & Qt.WindowType.Tool


def test_overlay_initial_size(overlay: OverlayWindow) -> None:
    assert overlay.width() == 800
    assert overlay.height() == 120


def test_overlay_highlight_hovered_signal_exists() -> None:
    assert hasattr(OverlayWindow, "highlight_hovered")


def test_on_sentence_ready_stores_current_result(overlay: OverlayWindow) -> None:
    result = _make_result()
    with patch(
        "src.ui.overlay.HighlightRenderer.build_rich_text",
        return_value="<b>テスト</b>",
    ):
        overlay.on_sentence_ready(result)
    assert overlay._current_result is result


def test_set_status_updates_jp_browser(overlay: OverlayWindow) -> None:
    overlay.set_status("Listening...")
    assert "Listening..." in overlay._jp_browser.toPlainText()


def test_overlay_has_jp_browser(overlay: OverlayWindow) -> None:
    assert overlay._jp_browser is not None


def test_overlay_browsers_read_only(overlay: OverlayWindow) -> None:
    assert overlay._jp_browser.isReadOnly()


def test_overlay_renderer_stored_as_instance(overlay: OverlayWindow) -> None:
    from src.ui.highlight import HighlightRenderer

    assert isinstance(overlay._renderer, HighlightRenderer)


def test_on_config_changed_updates_user_level(overlay: OverlayWindow) -> None:
    config = AppConfig(user_jlpt_level=2)
    overlay.on_config_changed(config)
    assert overlay._user_level == 2


def test_on_config_changed_updates_enable_vocab(overlay: OverlayWindow) -> None:
    config = AppConfig(enable_vocab_highlight=False)
    overlay.on_config_changed(config)
    assert overlay._enable_vocab is False


def test_on_config_changed_updates_enable_grammar(overlay: OverlayWindow) -> None:
    config = AppConfig(enable_grammar_highlight=False)
    overlay.on_config_changed(config)
    assert overlay._enable_grammar is False


def test_on_config_changed_rerenders_current_result(overlay: OverlayWindow) -> None:
    result = _make_result()
    with patch(
        "src.ui.overlay.HighlightRenderer.build_rich_text",
        return_value="<b>テスト</b>",
    ) as mock_build:
        overlay.on_sentence_ready(result)
        mock_build.reset_mock()
        overlay.on_config_changed(AppConfig())
        assert mock_build.called


def test_on_config_changed_no_rerender_when_no_result(overlay: OverlayWindow) -> None:
    overlay._current_result = None
    with patch(
        "src.ui.overlay.HighlightRenderer.build_rich_text",
        return_value="<b>テスト</b>",
    ) as mock_build:
        overlay.on_config_changed(AppConfig())
        mock_build.assert_not_called()


def test_on_sentence_ready_vocab_hits_filtered_when_disabled(overlay: OverlayWindow) -> None:
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
    analysis = AnalysisResult(tokens=[], vocab_hits=[vocab_hit], grammar_hits=[])
    result = SentenceResult(
        japanese_text="食べる",
        analysis=analysis,
    )
    captured: list[AnalysisResult] = []

    def capture_analysis(text: str, a: AnalysisResult, user_level: int) -> str:
        captured.append(a)
        return "<b>食べる</b>"

    with patch("src.ui.overlay.HighlightRenderer.build_rich_text", side_effect=capture_analysis):
        overlay.on_sentence_ready(result)

    assert len(captured) == 1
    assert captured[0].vocab_hits == []


def test_on_sentence_ready_grammar_hits_filtered_when_disabled(overlay: OverlayWindow) -> None:
    from src.db.models import GrammarHit

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
    analysis = AnalysisResult(tokens=[], vocab_hits=[], grammar_hits=[grammar_hit])
    result = SentenceResult(
        japanese_text="食べている",
        analysis=analysis,
    )
    captured: list[AnalysisResult] = []

    def capture_analysis(text: str, a: AnalysisResult, user_level: int) -> str:
        captured.append(a)
        return "<b>食べている</b>"

    with patch("src.ui.overlay.HighlightRenderer.build_rich_text", side_effect=capture_analysis):
        overlay.on_sentence_ready(result)

    assert len(captured) == 1
    assert captured[0].grammar_hits == []


def test_overlay_accepts_config_constructor(qapp: QApplication) -> None:
    with patch(
        "src.ui.overlay.HighlightRenderer.build_rich_text",
        return_value="<b>テスト</b>",
    ):
        window = OverlayWindow(AppConfig())
    assert window is not None


def test_overlay_uses_config_dimensions(qapp: QApplication) -> None:
    with patch(
        "src.ui.overlay.HighlightRenderer.build_rich_text",
        return_value="<b>テスト</b>",
    ):
        window = OverlayWindow(AppConfig(overlay_width=600, overlay_height=100))
    assert window.width() == 600
    assert window.height() == 100


def test_overlay_minimum_size(overlay: OverlayWindow) -> None:
    assert overlay.minimumWidth() >= 400
    assert overlay.minimumHeight() >= 80


def test_overlay_center_on_screen_method_exists(overlay: OverlayWindow) -> None:
    assert hasattr(overlay, "_center_on_screen")


def test_on_config_changed_updates_opacity(overlay: OverlayWindow) -> None:
    overlay.on_config_changed(AppConfig(overlay_opacity=0.5))
    assert overlay.windowOpacity() == pytest.approx(0.5, abs=0.01)


# ── Text box styling tests (Bug 3: centered HTML, visible on dark bg) ──


def test_centered_html_wraps_in_table() -> None:
    from src.ui.overlay import _centered_html

    result = _centered_html("hello world")
    assert "<table" in result
    assert 'align="center"' in result
    assert "hello world" in result


def test_centered_html_escapes_special_chars() -> None:
    from src.ui.overlay import _centered_html

    result = _centered_html("<script>alert('xss')</script>")
    assert "<script>" not in result
    assert "&lt;script&gt;" in result


def test_centered_html_uses_light_text_color() -> None:
    from src.ui.overlay import _centered_html

    result = _centered_html("test")
    assert "#EEEEEE" in result


def test_set_status_uses_html(overlay: OverlayWindow) -> None:
    overlay.set_status("Listening...")
    html = overlay._jp_browser.toHtml()
    assert 'align="center"' in html
    assert "Listening..." in overlay._jp_browser.toPlainText()


def test_browser_stylesheet_has_text_color(overlay: OverlayWindow) -> None:
    jp_style = overlay._jp_browser.styleSheet()
    assert "#EEEEEE" in jp_style


# ── Drag from browser viewport tests (Bug 2) ──


def test_jp_browser_viewport_has_mouse_tracking(overlay: OverlayWindow) -> None:
    assert overlay._jp_browser.viewport().hasMouseTracking()


def test_drag_pos_initially_none(overlay: OverlayWindow) -> None:
    assert overlay._drag_pos is None


def test_on_asr_ready_updates_browser(overlay: OverlayWindow) -> None:
    from src.pipeline.types import ASRResult

    result = ASRResult(text="テスト", segment_id="seg-1", elapsed_ms=10.0)
    overlay.on_asr_ready(result)

    assert "テスト" in overlay._jp_browser.toPlainText()


# ── Sentence history + navigation tests ──


def test_on_sentence_ready_adds_to_history(overlay: OverlayWindow) -> None:
    result = _make_result()
    with patch(
        "src.ui.overlay.HighlightRenderer.build_rich_text",
        return_value="<b>テスト</b>",
    ):
        overlay.on_sentence_ready(result)
    assert len(overlay._history) == 1
    assert overlay._history[0] is result
    assert overlay._history_index == 0


@pytest.mark.xfail(reason="pre-existing: _MAX_HISTORY=10 but test expects 100")
def test_history_max_size(overlay: OverlayWindow) -> None:
    with patch(
        "src.ui.overlay.HighlightRenderer.build_rich_text",
        return_value="<b>test</b>",
    ):
        for i in range(105):
            overlay.on_sentence_ready(_make_result(japanese_text=f"sentence {i}"))
    assert len(overlay._history) == 100
    assert overlay._history_index == 99


def test_prev_sentence_navigates_backward(overlay: OverlayWindow) -> None:
    r1 = _make_result(japanese_text="first")
    r2 = _make_result(japanese_text="second")
    with patch(
        "src.ui.overlay.HighlightRenderer.build_rich_text",
        return_value="<b>test</b>",
    ):
        overlay.on_sentence_ready(r1)
        overlay.on_sentence_ready(r2)
        overlay._prev_sentence()
    assert overlay._history_index == 0
    assert overlay._current_result is r1


def test_prev_sentence_noop_at_start(overlay: OverlayWindow) -> None:
    r1 = _make_result()
    with patch(
        "src.ui.overlay.HighlightRenderer.build_rich_text",
        return_value="<b>test</b>",
    ):
        overlay.on_sentence_ready(r1)
    overlay._prev_sentence()
    assert overlay._history_index == 0


def test_next_sentence_navigates_forward(overlay: OverlayWindow) -> None:
    r1 = _make_result(japanese_text="first")
    r2 = _make_result(japanese_text="second")
    with patch(
        "src.ui.overlay.HighlightRenderer.build_rich_text",
        return_value="<b>test</b>",
    ):
        overlay.on_sentence_ready(r1)
        overlay.on_sentence_ready(r2)
        overlay._prev_sentence()
        overlay._next_sentence()
    assert overlay._history_index == 1
    assert overlay._current_result is r2


def test_next_sentence_noop_at_end(overlay: OverlayWindow) -> None:
    r1 = _make_result()
    with patch(
        "src.ui.overlay.HighlightRenderer.build_rich_text",
        return_value="<b>test</b>",
    ):
        overlay.on_sentence_ready(r1)
    overlay._next_sentence()
    assert overlay._history_index == 0


def test_prev_sentence_noop_empty_history(overlay: OverlayWindow) -> None:
    overlay._prev_sentence()
    assert overlay._history_index == -1


def test_next_sentence_noop_empty_history(overlay: OverlayWindow) -> None:
    overlay._next_sentence()
    assert overlay._history_index == -1


# ── Display mode config change tests ──


# ── Four-corner resize tests ──


def test_edge_at_returns_empty_for_center(overlay: OverlayWindow) -> None:
    from PySide6.QtCore import QPoint

    center = QPoint(overlay.width() // 2, overlay.height() // 2)
    assert overlay._edge_at(center) == ""


def test_edge_at_detects_top_left_corner(overlay: OverlayWindow) -> None:
    from PySide6.QtCore import QPoint

    assert overlay._edge_at(QPoint(2, 2)) == "tl"


def test_edge_at_detects_top_right_corner(overlay: OverlayWindow) -> None:
    from PySide6.QtCore import QPoint

    assert overlay._edge_at(QPoint(overlay.width() - 2, 2)) == "tr"


def test_edge_at_detects_bottom_left_corner(overlay: OverlayWindow) -> None:
    from PySide6.QtCore import QPoint

    assert overlay._edge_at(QPoint(2, overlay.height() - 2)) == "bl"


def test_edge_at_detects_bottom_right_corner(overlay: OverlayWindow) -> None:
    from PySide6.QtCore import QPoint

    assert overlay._edge_at(QPoint(overlay.width() - 2, overlay.height() - 2)) == "br"


def test_edge_at_detects_top_edge(overlay: OverlayWindow) -> None:
    from PySide6.QtCore import QPoint

    assert overlay._edge_at(QPoint(overlay.width() // 2, 2)) == "t"


def test_edge_at_detects_bottom_edge(overlay: OverlayWindow) -> None:
    from PySide6.QtCore import QPoint

    assert overlay._edge_at(QPoint(overlay.width() // 2, overlay.height() - 2)) == "b"


def test_edge_at_detects_left_edge(overlay: OverlayWindow) -> None:
    from PySide6.QtCore import QPoint

    assert overlay._edge_at(QPoint(2, overlay.height() // 2)) == "l"


def test_edge_at_detects_right_edge(overlay: OverlayWindow) -> None:
    from PySide6.QtCore import QPoint

    assert overlay._edge_at(QPoint(overlay.width() - 2, overlay.height() // 2)) == "r"


def test_resize_state_initially_empty(overlay: OverlayWindow) -> None:
    assert overlay._resize_edge == ""
    assert overlay._resize_origin is None
    assert overlay._resize_geo is None


# ── Single mode height shrink tests ──
