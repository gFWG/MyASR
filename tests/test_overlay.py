"""Tests for src/ui/overlay.py — OverlayWindow."""

from __future__ import annotations

import sys
from unittest.mock import patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from src.db.models import AnalysisResult, SentenceResult
from src.ui.overlay import OverlayWindow


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    assert isinstance(app, QApplication)
    return app


@pytest.fixture
def overlay(qapp: QApplication) -> OverlayWindow:
    with patch(
        "src.ui.overlay.HighlightRenderer.build_rich_text",
        return_value="<b>テスト</b>",
    ):
        window = OverlayWindow()
    return window


def _make_result(
    japanese_text: str = "テスト文",
    chinese_translation: str | None = "测试句",
    explanation: str | None = None,
) -> SentenceResult:
    analysis = AnalysisResult(tokens=[], vocab_hits=[], grammar_hits=[])
    return SentenceResult(
        japanese_text=japanese_text,
        chinese_translation=chinese_translation,
        explanation=explanation,
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


def test_overlay_initial_mode_is_zero(overlay: OverlayWindow) -> None:
    assert overlay._mode == 0


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


def test_on_sentence_ready_sets_cn_browser_text(overlay: OverlayWindow) -> None:
    result = _make_result(chinese_translation="测试")
    with patch(
        "src.ui.overlay.HighlightRenderer.build_rich_text",
        return_value="<b>テスト</b>",
    ):
        overlay.on_sentence_ready(result)
    assert "测试" in overlay._cn_browser.toPlainText()


def test_on_sentence_ready_no_translation_shows_unavailable(
    overlay: OverlayWindow,
) -> None:
    result = _make_result(chinese_translation=None, explanation=None)
    with patch(
        "src.ui.overlay.HighlightRenderer.build_rich_text",
        return_value="<b>テスト</b>",
    ):
        overlay.on_sentence_ready(result)
    assert "Translation unavailable" in overlay._cn_browser.toPlainText()


def test_on_sentence_ready_explanation_fallback(overlay: OverlayWindow) -> None:
    result = _make_result(chinese_translation=None, explanation="Grammar explanation")
    with patch(
        "src.ui.overlay.HighlightRenderer.build_rich_text",
        return_value="<b>テスト</b>",
    ):
        overlay.on_sentence_ready(result)
    assert "Grammar explanation" in overlay._cn_browser.toPlainText()


def test_toggle_mode_changes_from_zero_to_one(overlay: OverlayWindow) -> None:
    overlay._mode = 0
    overlay._toggle_mode()
    assert overlay._mode == 1


def test_toggle_mode_changes_from_one_to_zero(overlay: OverlayWindow) -> None:
    overlay._mode = 1
    overlay._toggle_mode()
    assert overlay._mode == 0


def test_toggle_mode_hides_cn_browser_in_mode_one(overlay: OverlayWindow) -> None:
    overlay._mode = 0
    overlay._toggle_mode()
    assert overlay._cn_browser.isHidden()


def test_toggle_mode_shows_cn_browser_in_mode_zero(overlay: OverlayWindow) -> None:
    overlay._mode = 1
    overlay._toggle_mode()
    assert not overlay._cn_browser.isHidden()


def test_set_status_updates_jp_browser(overlay: OverlayWindow) -> None:
    overlay.set_status("Listening...")
    assert "Listening..." in overlay._jp_browser.toPlainText()


def test_set_status_clears_cn_browser(overlay: OverlayWindow) -> None:
    overlay._cn_browser.setPlainText("Some previous text")
    overlay.set_status("Waiting...")
    assert overlay._cn_browser.toPlainText() == ""


def test_overlay_has_jp_and_cn_browsers(overlay: OverlayWindow) -> None:
    assert overlay._jp_browser is not None
    assert overlay._cn_browser is not None


def test_overlay_browsers_read_only(overlay: OverlayWindow) -> None:
    assert overlay._jp_browser.isReadOnly()
    assert overlay._cn_browser.isReadOnly()


def test_overlay_renderer_stored_as_instance(overlay: OverlayWindow) -> None:
    from src.ui.highlight import HighlightRenderer

    assert isinstance(overlay._renderer, HighlightRenderer)
