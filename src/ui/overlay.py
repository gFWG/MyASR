"""Transparent PySide6 overlay window for Japanese text display.

Displays JLPT-highlighted Japanese text with Chinese translation.
Supports drag to move, configurable shortcuts, sentence history
navigation, and hover detection for vocabulary/grammar tooltips.
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
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from src.config import AppConfig, jlpt_colors_to_renderer_format, save_config
from src.db.models import AnalysisResult, GrammarHit, SentenceResult, VocabHit
from src.pipeline.types import ASRResult, LLMResult
from src.ui.highlight import HighlightRenderer
from src.ui.shortcuts import GlobalShortcutManager

logger = logging.getLogger(__name__)

_JP_FONT_SIZE = 16
_CN_FONT_SIZE = 14
_BG_COLOR = QColor(30, 30, 30, 200)
_CORNER_RADIUS = 12
_MAX_HISTORY = 10
_RESIZE_MARGIN = 8
_SINGLE_MODE_HEIGHT_RATIO = 0.6

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


class OverlayWindow(QWidget):
    """Transparent frameless overlay window for Japanese text + Chinese translation.

    Displays JLPT-highlighted Japanese text and Chinese translation in a
    semi-transparent rounded-corner overlay. Supports drag to move,
    configurable shortcuts, sentence history navigation, and hover
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

        self._display_mode: str = config.overlay_display_mode
        self._single_sub_mode: str = "jp"
        self._drag_pos: QPoint | None = None
        self._current_result: SentenceResult | None = None
        self._renderer = HighlightRenderer(jlpt_colors_to_renderer_format(config.jlpt_colors))
        self._history: list[SentenceResult] = []
        self._history_index: int = -1

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

        self._cn_browser.setMouseTracking(True)
        self._cn_browser.viewport().setMouseTracking(True)
        self._cn_browser.viewport().installEventFilter(self)

        self.setMouseTracking(True)
        self._resize_edge: str = ""
        self._resize_origin: QPoint | None = None
        self._resize_geo: QRect | None = None
        self._both_mode_height: int = config.overlay_height

        self._shortcut_mgr = GlobalShortcutManager(config, self)
        self._shortcut_mgr.toggle_display_triggered.connect(self._toggle_mode)
        self._shortcut_mgr.prev_sentence_triggered.connect(self._prev_sentence)
        self._shortcut_mgr.next_sentence_triggered.connect(self._next_sentence)
        self._shortcut_mgr.start()

        self._apply_display_mode()

        self.set_status("Initializing...")

    def _apply_display_mode(self) -> None:
        if self._display_mode == "both":
            self._jp_browser.setVisible(True)
            self._cn_browser.setVisible(True)
            self.resize(self.width(), self._both_mode_height)
        else:
            self._jp_browser.setVisible(self._single_sub_mode == "jp")
            self._cn_browser.setVisible(self._single_sub_mode == "cn")
            shrunk = max(
                self.minimumHeight(),
                int(self._both_mode_height * _SINGLE_MODE_HEIGHT_RATIO),
            )
            self.resize(self.width(), shrunk)

    def _center_on_screen(self) -> None:
        screen_geo = QApplication.primaryScreen().geometry()
        x = screen_geo.center().x() - self.width() // 2
        y = screen_geo.bottom() - self.height() - 40
        self.move(x, y)

    def on_sentence_ready(self, result: SentenceResult) -> None:
        """Display a new sentence result and add it to history.

        Args:
            result: Pipeline output containing Japanese text, Chinese
                translation, and JLPT analysis data.
        """
        self._current_result = result

        self._history.append(result)
        if len(self._history) > _MAX_HISTORY:
            self._history.pop(0)
        self._history_index = len(self._history) - 1

        self._render_result(result)
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

        translation = result.chinese_translation or result.explanation or "LLM unavailable"
        self._cn_browser.setHtml(_centered_html(translation))

    def on_asr_ready(self, result: ASRResult) -> None:
        """Show ASR text immediately with 'Translating...' placeholder.

        Args:
            result: ASR output containing Japanese text.
        """
        self._jp_browser.setHtml(_centered_html(result.text))
        self._cn_browser.setHtml(_centered_html("Translating…", color="#AAAAAA"))
        logger.debug("on_asr_ready: segment_id=%s", result.segment_id)

    def on_llm_ready(self, result: LLMResult) -> None:
        """Update display with LLM output when it arrives async.

        Args:
            result: LLM output. translation/explanation may be None
                if LLM failed gracefully.
        """
        text = result.translation or result.explanation or "LLM unavailable"

        self._cn_browser.setHtml(_centered_html(text))
        logger.debug("on_llm_ready: segment_id=%s", result.segment_id)

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
        old_mode = self._display_mode
        self._display_mode = config.overlay_display_mode

        self._jp_browser.setFont(_make_font(config.overlay_font_size_jp))
        self._cn_browser.setFont(_make_font(config.overlay_font_size_cn))

        if old_mode == "both" and config.overlay_display_mode == "single":
            self._both_mode_height = self.height()

        self._shortcut_mgr.update_shortcuts(config)
        self._renderer.update_colors(jlpt_colors_to_renderer_format(config.jlpt_colors))
        self._apply_display_mode()

        if self._current_result is not None:
            self._render_result(self._current_result)

        logger.debug(
            "on_config_changed: opacity=%.2f user_level=%d jp_font=%d cn_font=%d "
            "vocab=%s grammar=%s display_mode=%s",
            config.overlay_opacity,
            config.user_jlpt_level,
            config.overlay_font_size_jp,
            config.overlay_font_size_cn,
            config.enable_vocab_highlight,
            config.enable_grammar_highlight,
            config.overlay_display_mode,
        )

    def set_status(self, text: str) -> None:
        """Display a status message (e.g. 'Initializing...', 'Listening...').

        Args:
            text: Status string to display in the JP browser.
        """
        self._jp_browser.setHtml(_centered_html(text))
        self._cn_browser.setHtml("")
        logger.debug("set_status: %s", text)

    def _toggle_mode(self) -> None:
        if self._display_mode == "both":
            # Switch from both → single(jp)
            self._both_mode_height = self.height()
            self._display_mode = "single"
            self._single_sub_mode = "jp"
        elif self._single_sub_mode == "jp":
            # single(jp) → single(cn)
            self._single_sub_mode = "cn"
        else:
            # single(cn) → both
            self._display_mode = "both"
        self._apply_display_mode()
        logger.debug(
            "_toggle_mode: display_mode=%s sub_mode=%s",
            self._display_mode,
            self._single_sub_mode,
        )

    def _prev_sentence(self) -> None:
        if not self._history or self._history_index <= 0:
            return
        self._history_index -= 1
        result = self._history[self._history_index]
        self._current_result = result
        self._render_result(result)
        logger.debug("_prev_sentence: index=%d", self._history_index)

    def _next_sentence(self) -> None:
        if not self._history or self._history_index >= len(self._history) - 1:
            return
        self._history_index += 1
        result = self._history[self._history_index]
        self._current_result = result
        self._render_result(result)
        logger.debug("_next_sentence: index=%d", self._history_index)

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
        if self._display_mode == "both":
            self._both_mode_height = self.height()
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
        cn_vp = self._cn_browser.viewport()
        is_browser_viewport = watched is jp_vp or watched is cn_vp

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
        self._shortcut_mgr.stop()
        super().closeEvent(event)
