"""Transparent PySide6 overlay window for Japanese text display.

Displays JLPT-highlighted Japanese text with Chinese translation.
Supports drag to move, Ctrl+T to toggle single/dual-line mode,
and hover detection for vocabulary/grammar tooltips.
"""

from __future__ import annotations

import html as _html
import logging

from PySide6.QtCore import QEvent, QObject, QPoint, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QKeySequence,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QShortcut,
)
from PySide6.QtWidgets import (
    QApplication,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from src.db.models import GrammarHit, SentenceResult, VocabHit
from src.ui.highlight import HighlightRenderer

logger = logging.getLogger(__name__)

_WINDOW_WIDTH = 800
_WINDOW_HEIGHT = 120
_JP_FONT_SIZE = 16
_CN_FONT_SIZE = 14
_BG_COLOR = QColor(30, 30, 30, 200)
_CORNER_RADIUS = 12

_FONT_FAMILIES = ["Segoe UI", "Yu Gothic UI", "Noto Sans CJK JP", "sans-serif"]


def _make_font(size: int) -> QFont:
    font = QFont(_FONT_FAMILIES, size)
    font.setStyleHint(QFont.StyleHint.SansSerif)
    return font


def _make_browser(font_size: int) -> QTextBrowser:
    browser = QTextBrowser()
    browser.setReadOnly(True)
    browser.setFont(_make_font(font_size))
    browser.setFrameShape(QTextBrowser.Shape.NoFrame)
    browser.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    browser.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    browser.setStyleSheet("background: transparent; border: none;")
    browser.setOpenLinks(False)
    return browser


class OverlayWindow(QWidget):
    """Transparent frameless overlay window for Japanese text + Chinese translation.

    Displays JLPT-highlighted Japanese text and Chinese translation in a
    semi-transparent rounded-corner overlay. Supports drag to move, Ctrl+T
    to toggle display mode, and hover detection for vocab/grammar hits.

    Signals:
        highlight_hovered: Emitted when the cursor hovers over a highlighted
            word or grammar pattern. Arguments are the hit
            (VocabHit | GrammarHit) and the global cursor position.
    """

    highlight_hovered = Signal(object, object)  # (VocabHit|GrammarHit, QPoint)

    def __init__(self, user_level: int = 5, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._user_level = user_level

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        self.resize(_WINDOW_WIDTH, _WINDOW_HEIGHT)

        screen_geo = QApplication.primaryScreen().geometry()
        x = screen_geo.center().x() - _WINDOW_WIDTH // 2
        y = screen_geo.bottom() - _WINDOW_HEIGHT - 40
        self.move(x, y)

        self._mode: int = 0
        self._drag_pos: QPoint | None = None
        self._current_result: SentenceResult | None = None
        self._renderer = HighlightRenderer()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(2)

        self._jp_browser = _make_browser(_JP_FONT_SIZE)
        self._cn_browser = _make_browser(_CN_FONT_SIZE)

        layout.addWidget(self._jp_browser)
        layout.addWidget(self._cn_browser)

        self._jp_browser.setMouseTracking(True)
        self._jp_browser.viewport().setMouseTracking(True)
        self._jp_browser.viewport().installEventFilter(self)

        QShortcut(QKeySequence("Ctrl+T"), self).activated.connect(self._toggle_mode)

        self.set_status("Initializing...")

    def on_sentence_ready(self, result: SentenceResult) -> None:
        """Display a new sentence result in the overlay.

        Args:
            result: Pipeline output containing Japanese text, Chinese
                translation, and JLPT analysis data.
        """
        self._current_result = result

        if result.analysis is not None:
            rich_text = self._renderer.build_rich_text(
                result.japanese_text,
                result.analysis,
                user_level=self._user_level,
            )
        else:
            rich_text = _html.escape(result.japanese_text)

        self._jp_browser.setHtml(rich_text)

        translation = result.chinese_translation or result.explanation or "Translation unavailable"
        self._cn_browser.setPlainText(translation)

        logger.debug("on_sentence_ready: displayed sentence id=%s", result.sentence_id)

    def set_status(self, text: str) -> None:
        """Display a status message (e.g. 'Initializing...', 'Listening...').

        Clears the Chinese browser and sets JP browser to plain status text.

        Args:
            text: Status string to display in the JP browser.
        """
        self._jp_browser.setPlainText(text)
        self._cn_browser.setPlainText("")
        logger.debug("set_status: %s", text)

    def _toggle_mode(self) -> None:
        self._mode = 1 - self._mode
        self._cn_browser.setVisible(self._mode == 0)
        logger.debug("_toggle_mode: mode=%d", self._mode)

    def _handle_hover_at_viewport_pos(self, viewport_pos: QPoint) -> None:
        if self._current_result is None or self._current_result.analysis is None:
            return

        cursor = self._jp_browser.cursorForPosition(viewport_pos)
        char_pos = cursor.position()

        hit: VocabHit | GrammarHit | None = self._renderer.get_highlight_at_position(
            char_pos,
            self._current_result.analysis,
        )
        if hit is not None:
            global_pos = self._jp_browser.viewport().mapToGlobal(viewport_pos)
            self.highlight_hovered.emit(hit, global_pos)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(_BG_COLOR)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(self.rect(), _CORNER_RADIUS, _CORNER_RADIUS)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if event.buttons() & Qt.MouseButton.LeftButton and self._drag_pos is not None:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = None
        super().mouseReleaseEvent(event)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is self._jp_browser.viewport() and isinstance(event, QMouseEvent):
            if event.type() == QEvent.Type.MouseMove:
                self._handle_hover_at_viewport_pos(event.position().toPoint())
        return super().eventFilter(watched, event)
