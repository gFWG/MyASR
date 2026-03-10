"""Transparent PySide6 overlay window for Japanese text display.

Displays JLPT-highlighted Japanese text. Supports drag to move,
sentence history navigation, and hover detection for vocabulary/grammar tooltips.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QEvent, QObject, QPoint, QRect, Qt, QTimer, Signal
from PySide6.QtGui import (
    QCloseEvent,
    QColor,
    QCursor,
    QFont,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QResizeEvent,
)
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from src.config import AppConfig, jlpt_colors_to_renderer_format, save_config
from src.db.models import AnalysisResult, GrammarHit, SentenceResult, VocabHit
from src.pipeline.types import ASRResult
from src.ui.highlight import HighlightRenderer

logger = logging.getLogger(__name__)

_JP_FONT_SIZE = 16
_BG_COLOR = QColor(30, 30, 30, 200)
_CORNER_RADIUS = 12
_RESIZE_MARGIN = 8
_ARROW_BTN_WIDTH = 28

_FONT_FAMILIES = ["Segoe UI", "Yu Gothic UI", "Noto Sans CJK JP", "sans-serif"]

_ARROW_BTN_STYLE = """
    QPushButton {{
        background-color: rgba(255, 255, 255, {opacity});
        border: none;
        border-radius: 6px;
        color: rgba(255, 255, 255, {text_opacity});
        font-size: 18px;
        font-weight: bold;
        padding: 0px;
    }}
    QPushButton:hover {{
        background-color: rgba(255, 255, 255, 60);
    }}
    QPushButton:pressed {{
        background-color: rgba(255, 255, 255, 80);
    }}
"""


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
    browser.setStyleSheet("background: transparent; border: none; color: #EEEEEE;")
    browser.setOpenLinks(False)
    return browser


def _centered_html(text: str, color: str = "#EEEEEE") -> str:
    """Wrap plain text in centered HTML for QTextBrowser display."""
    import html as _h

    escaped = _h.escape(text)
    return (
        '<table align="center" width="95%">'
        f'<tr><td align="center" style="color: {color};">{escaped}</td></tr>'
        "</table>"
    )


def _make_arrow_button(text: str) -> QPushButton:
    """Create a translucent arrow button for sentence navigation.

    Args:
        text: Arrow character to display (e.g. "◀" or "▶").

    Returns:
        Configured QPushButton with translucent styling.
    """
    btn = QPushButton(text)
    btn.setFixedWidth(_ARROW_BTN_WIDTH)
    btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
    btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    btn.setStyleSheet(_ARROW_BTN_STYLE.format(opacity=30, text_opacity=180))
    return btn


class OverlayWindow(QWidget):
    """Transparent frameless overlay window for JLPT-highlighted Japanese text.

    Displays JLPT-highlighted Japanese text in a semi-transparent rounded-corner
    overlay. Supports drag to move, sentence history navigation, and hover
    detection for vocabulary/grammar tooltips.

    Signals:
        highlight_hovered: Emitted when the cursor hovers over a highlighted
            word or grammar pattern. Arguments are the hit
            (VocabHit | GrammarHit) and the global cursor position.
    """

    highlight_hovered = Signal(object, object)

    def __init__(self, config: AppConfig, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = config
        self._user_level = config.user_jlpt_level
        self._enable_vocab: bool = config.enable_vocab_highlight
        self._enable_grammar: bool = config.enable_grammar_highlight
        self._max_history: int = config.max_history

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowOpacity(config.overlay_opacity)

        self.resize(config.overlay_width, config.overlay_height)

        screen_width = QApplication.primaryScreen().geometry().width()
        self.setMinimumSize(400, 80)
        self.setMaximumSize(screen_width, 400)

        self._center_on_screen()

        self._drag_pos: QPoint | None = None
        self._current_result: SentenceResult | None = None
        self._renderer = HighlightRenderer(jlpt_colors_to_renderer_format(config.jlpt_colors))
        self._history: list[SentenceResult] = []
        self._history_index: int = -1

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(8, 8, 8, 8)
        outer_layout.setSpacing(2)

        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(4)

        self._prev_btn = _make_arrow_button("◀")
        self._prev_btn.clicked.connect(self._prev_sentence)

        self._jp_browser = _make_browser(_JP_FONT_SIZE)

        self._next_btn = _make_arrow_button("▶")
        self._next_btn.clicked.connect(self._next_sentence)

        content_layout.addWidget(self._prev_btn)
        content_layout.addWidget(self._jp_browser, 1)
        content_layout.addWidget(self._next_btn)
        outer_layout.addLayout(content_layout)

        self._jp_browser.setMouseTracking(True)
        self._jp_browser.viewport().setMouseTracking(True)
        self._jp_browser.viewport().installEventFilter(self)

        self.setMouseTracking(True)
        self._resize_edge: str = ""
        self._resize_origin: QPoint | None = None
        self._resize_geo: QRect | None = None

        self.set_status("Initializing...")
        self._update_arrow_visibility()

    def _center_on_screen(self) -> None:
        screen_geo = QApplication.primaryScreen().geometry()
        x = screen_geo.center().x() - self.width() // 2
        y = screen_geo.bottom() - self.height() - 40
        self.move(x, y)

    def on_sentence_ready(self, result: SentenceResult) -> None:
        """Display a new sentence result and add it to history.

        Args:
            result: Pipeline output containing Japanese text and JLPT analysis data.
        """
        self._current_result = result

        self._history.append(result)
        if len(self._history) > self._max_history:
            self._history.pop(0)
        self._history_index = len(self._history) - 1

        self._render_result(result)
        self._update_arrow_visibility()
        logger.debug("on_sentence_ready: displayed sentence id=%s", result.sentence_id)

    def _render_result(self, result: SentenceResult) -> None:
        if result.analysis is not None:
            filtered_analysis = AnalysisResult(
                tokens=result.analysis.tokens,
                vocab_hits=result.analysis.vocab_hits if self._enable_vocab else [],
                grammar_hits=result.analysis.grammar_hits if self._enable_grammar else [],
            )
            rich_text = self._renderer.build_rich_text(
                result.japanese_text,
                filtered_analysis,
                user_level=self._user_level,
            )
        else:
            rich_text = _centered_html(result.japanese_text)

        self._jp_browser.setHtml(rich_text)

    def on_asr_ready(self, result: ASRResult) -> None:
        """Show ASR text immediately.

        Args:
            result: ASR output containing Japanese text.
        """
        self._jp_browser.setHtml(_centered_html(result.text))
        logger.debug("on_asr_ready: segment_id=%s", result.segment_id)

    def on_config_changed(self, config: AppConfig) -> None:
        """Apply live config changes to the overlay without restarting.

        Args:
            config: Updated application configuration.
        """
        self._config = config
        self.setWindowOpacity(config.overlay_opacity)
        self._user_level = config.user_jlpt_level
        self._enable_vocab = config.enable_vocab_highlight
        self._enable_grammar = config.enable_grammar_highlight
        self._max_history = config.max_history

        self._jp_browser.setFont(_make_font(config.overlay_font_size_jp))

        self._renderer.update_colors(jlpt_colors_to_renderer_format(config.jlpt_colors))

        # Trim history if max was reduced
        while len(self._history) > self._max_history:
            self._history.pop(0)
            self._history_index = max(0, self._history_index - 1)

        if self._current_result is not None:
            self._render_result(self._current_result)

        self._update_arrow_visibility()

        logger.debug(
            "on_config_changed: opacity=%.2f user_level=%d jp_font=%d vocab=%s grammar=%s"
            " max_history=%d",
            config.overlay_opacity,
            config.user_jlpt_level,
            config.overlay_font_size_jp,
            config.enable_vocab_highlight,
            config.enable_grammar_highlight,
            config.max_history,
        )

    def set_status(self, text: str) -> None:
        """Display a status message (e.g. 'Initializing...', 'Listening...').

        Args:
            text: Status string to display in the JP browser.
        """
        self._jp_browser.setHtml(_centered_html(text))
        logger.debug("set_status: %s", text)

    def _prev_sentence(self) -> None:
        if not self._history or self._history_index <= 0:
            return
        self._history_index -= 1
        result = self._history[self._history_index]
        self._current_result = result
        self._render_result(result)
        self._update_arrow_visibility()
        logger.debug("_prev_sentence: index=%d", self._history_index)

    def _next_sentence(self) -> None:
        if not self._history or self._history_index >= len(self._history) - 1:
            return
        self._history_index += 1
        result = self._history[self._history_index]
        self._current_result = result
        self._render_result(result)
        self._update_arrow_visibility()
        logger.debug("_next_sentence: index=%d", self._history_index)

    def _update_arrow_visibility(self) -> None:
        """Show/hide arrow buttons based on history navigation state."""
        can_go_prev = len(self._history) > 0 and self._history_index > 0
        can_go_next = len(self._history) > 0 and self._history_index < len(self._history) - 1
        self._prev_btn.setVisible(can_go_prev)
        self._next_btn.setVisible(can_go_next)

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

    def _save_size(self) -> None:
        self._config.overlay_width = self.width()
        self._config.overlay_height = self.height()
        save_config(self._config)

    def _edge_at(self, pos: QPoint) -> str:
        """Return a string indicating which resize edge/corner the position is in.

        Returns one of: "tl", "tr", "bl", "br", "t", "b", "l", "r", or "".
        """
        x, y = pos.x(), pos.y()
        w, h = self.width(), self.height()
        m = _RESIZE_MARGIN

        on_left = x < m
        on_right = x > w - m
        on_top = y < m
        on_bottom = y > h - m

        if on_top and on_left:
            return "tl"
        if on_top and on_right:
            return "tr"
        if on_bottom and on_left:
            return "bl"
        if on_bottom and on_right:
            return "br"
        if on_top:
            return "t"
        if on_bottom:
            return "b"
        if on_left:
            return "l"
        if on_right:
            return "r"
        return ""

    def _update_cursor_for_edge(self, edge: str) -> None:
        """Set cursor shape to match the resize edge."""
        cursor_map: dict[str, Qt.CursorShape] = {
            "tl": Qt.CursorShape.SizeFDiagCursor,
            "br": Qt.CursorShape.SizeFDiagCursor,
            "tr": Qt.CursorShape.SizeBDiagCursor,
            "bl": Qt.CursorShape.SizeBDiagCursor,
            "t": Qt.CursorShape.SizeVerCursor,
            "b": Qt.CursorShape.SizeVerCursor,
            "l": Qt.CursorShape.SizeHorCursor,
            "r": Qt.CursorShape.SizeHorCursor,
        }
        if edge in cursor_map:
            self.setCursor(QCursor(cursor_map[edge]))
        else:
            self.unsetCursor()

    def _apply_resize(self, global_pos: QPoint) -> None:
        """Resize the window based on the active edge and mouse position."""
        if not self._resize_edge or self._resize_origin is None or self._resize_geo is None:
            return

        dx = global_pos.x() - self._resize_origin.x()
        dy = global_pos.y() - self._resize_origin.y()
        geo = QRect(self._resize_geo)
        edge = self._resize_edge
        min_w, min_h = self.minimumWidth(), self.minimumHeight()
        max_w, max_h = self.maximumWidth(), self.maximumHeight()

        if "r" in edge:
            new_w = max(min_w, min(max_w, geo.width() + dx))
            geo.setWidth(new_w)
        if "b" in edge:
            new_h = max(min_h, min(max_h, geo.height() + dy))
            geo.setHeight(new_h)
        if "l" in edge:
            new_w = max(min_w, min(max_w, geo.width() - dx))
            geo.setLeft(geo.right() - new_w + 1)
        if "t" in edge:
            new_h = max(min_h, min(max_h, geo.height() - dy))
            geo.setTop(geo.bottom() - new_h + 1)

        self.setGeometry(geo)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(_BG_COLOR)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(self.rect(), _CORNER_RADIUS, _CORNER_RADIUS)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        QTimer.singleShot(500, self._save_size)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            edge = self._edge_at(event.pos())
            if edge:
                self._resize_edge = edge
                self._resize_origin = event.globalPosition().toPoint()
                self._resize_geo = QRect(self.geometry())
                return
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if event.buttons() & Qt.MouseButton.LeftButton:
            if self._resize_edge:
                self._apply_resize(event.globalPosition().toPoint())
                return
            if self._drag_pos is not None:
                self.move(event.globalPosition().toPoint() - self._drag_pos)
                return
        else:
            self._update_cursor_for_edge(self._edge_at(event.pos()))
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = None
            self._resize_edge = ""
            self._resize_origin = None
            self._resize_geo = None
        super().mouseReleaseEvent(event)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        jp_vp = self._jp_browser.viewport()
        is_browser_viewport = watched is jp_vp

        if is_browser_viewport and isinstance(event, QMouseEvent):
            etype = event.type()

            if watched is jp_vp and etype == QEvent.Type.MouseMove:
                if not (event.buttons() & Qt.MouseButton.LeftButton):
                    self._handle_hover_at_viewport_pos(event.position().toPoint())

            if etype == QEvent.Type.MouseButtonPress:
                if event.button() == Qt.MouseButton.LeftButton:
                    self._drag_pos = (
                        event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                    )
                    return True
            elif etype == QEvent.Type.MouseMove:
                if event.buttons() & Qt.MouseButton.LeftButton and self._drag_pos is not None:
                    self.move(event.globalPosition().toPoint() - self._drag_pos)
                    return True
            elif etype == QEvent.Type.MouseButtonRelease:
                if event.button() == Qt.MouseButton.LeftButton:
                    self._drag_pos = None
                    return True

        return super().eventFilter(watched, event)

    def closeEvent(self, event: QCloseEvent) -> None:
        super().closeEvent(event)
