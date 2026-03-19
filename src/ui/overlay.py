"""Transparent PySide6 overlay window for Japanese text display.

Displays JLPT-highlighted Japanese text. Supports drag to move,
sentence history navigation, and hover detection for vocabulary/grammar tooltips.
"""

from __future__ import annotations

import logging
import math

from PySide6.QtCore import QEvent, QObject, QPoint, QRect, Qt, QTimer, Signal
from PySide6.QtGui import (
    QCloseEvent,
    QColor,
    QContextMenuEvent,
    QCursor,
    QFont,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QResizeEvent,
    QTextBlockFormat,
    QTextCursor,
)
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from src.config import AppConfig, jlpt_colors_to_renderer_format, save_config
from src.models import GrammarHit, SentenceResult, VocabHit
from src.pipeline.types import ASRResult
from src.ui.highlight import HighlightRenderer
from src.ui.history import HistoryManager
from src.ui.menu_factory import create_context_menu

logger = logging.getLogger(__name__)

_BG_COLOR = QColor(30, 30, 30, 200)
_CORNER_RADIUS = 12
_RESIZE_MARGIN = 8
_ARROW_BTN_WIDTH = 28
_BASE_OUTER_GAP = 6
_BASE_MIDDLE_GAP = 6
_OUTER_MARGINS = 12
_MIN_OUTER_GAP = 2
_MIN_MIDDLE_GAP = 2
_MIN_OUTER_MARGINS = 6
_MIN_WINDOW_HEIGHT = 56
_DOC_MARGIN = 1.0
_CONTENT_SAFETY_PADDING = 2

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
    QPushButton:disabled {{
        background-color: rgba(255, 255, 255, 10);
        color: rgba(255, 255, 255, 40);
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
    browser.document().setDocumentMargin(_DOC_MARGIN)
    browser.setFrameShape(QTextBrowser.Shape.NoFrame)
    browser.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    browser.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    browser.setStyleSheet("background: transparent; border: none; color: #EEEEEE;")
    browser.setOpenLinks(False)
    # Disable default context menu and text selection
    browser.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
    browser.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
    return browser


def _set_centered_plain_text(
    browser: QTextBrowser, text: str, color: str = "#EEEEEE"
) -> None:
    """Set plain text with center alignment in a QTextBrowser.

    Args:
        browser: The QTextBrowser to update.
        text: The plain text to display.
        color: Foreground color as hex string (default: #EEEEEE).
    """
    doc = browser.document()
    doc.setPlainText(text)

    # Set default text color via stylesheet
    browser.setStyleSheet(f"background: transparent; border: none; color: {color};")

    # Center align all blocks
    cursor = QTextCursor(doc)
    cursor.select(QTextCursor.SelectionType.Document)

    block_fmt = QTextBlockFormat()
    block_fmt.setAlignment(Qt.AlignmentFlag.AlignCenter)
    cursor.setBlockFormat(block_fmt)


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
    btn.setEnabled(False)
    return btn


class OverlayWindow(QWidget):
    """Transparent frameless overlay window for JLPT-highlighted Japanese text.

    Displays JLPT-highlighted Japanese text in a semi-transparent rounded-corner
    overlay. Supports drag to move, sentence history navigation, and hover
    detection for vocabulary/grammar tooltips.

    Signals:
        highlight_hovered: Emitted when the cursor hovers over a highlighted
            word or grammar pattern. Arguments are the hit
            (VocabHit | GrammarHit), the global cursor position, and the
            SentenceResult that contains the highlighted text.
        highlight_left: Emitted when the cursor leaves the browser viewport,
            indicating the tooltip should be hidden.
        settings_requested: Emitted when user requests to open settings dialog.
        toggle_overlay: Emitted when user requests to toggle overlay visibility.
        quit_requested: Emitted when user requests to quit the application.
    """

    highlight_hovered = Signal(object, object, object)
    highlight_left = Signal()
    dedup_reset = Signal()
    settings_requested = Signal()
    toggle_overlay = Signal()
    quit_requested = Signal()

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
        self.setMinimumSize(400, _MIN_WINDOW_HEIGHT)
        self.setMaximumSize(screen_width, 400)

        self._center_on_screen()

        self._drag_pos: QPoint | None = None
        self._current_result: SentenceResult | None = None
        self._renderer = HighlightRenderer(jlpt_colors_to_renderer_format(config.jlpt_colors))
        self._history = HistoryManager(config.max_history)
        self._manual_spacing_delta = config.overlay_manual_spacing_delta

        self._outer_layout = QVBoxLayout(self)
        self._outer_layout.setContentsMargins(
            _OUTER_MARGINS,
            _OUTER_MARGINS,
            _OUTER_MARGINS,
            _OUTER_MARGINS,
        )
        self._outer_layout.setSpacing(0)

        self._top_spacer = QSpacerItem(
            0,
            _BASE_OUTER_GAP,
            QSizePolicy.Policy.Minimum,
            QSizePolicy.Policy.Fixed,
        )
        self._outer_layout.addItem(self._top_spacer)

        # Preview browser: shown when browsing history, displays the latest result
        self._preview_browser = _make_browser(config.overlay_font_size_jp)
        self._preview_browser.setVisible(False)
        self._outer_layout.addWidget(self._preview_browser)

        self._middle_spacer = QSpacerItem(
            0,
            0,
            QSizePolicy.Policy.Minimum,
            QSizePolicy.Policy.Fixed,
        )
        self._outer_layout.addItem(self._middle_spacer)

        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(4)

        self._prev_btn = _make_arrow_button("◀")
        self._prev_btn.clicked.connect(self._prev_sentence)

        self._jp_browser = _make_browser(config.overlay_font_size_jp)

        self._next_btn = _make_arrow_button("▶")
        self._next_btn.clicked.connect(self._next_sentence)

        content_layout.addWidget(self._prev_btn)
        content_layout.addWidget(self._jp_browser, 1)
        content_layout.addWidget(self._next_btn)
        self._outer_layout.addLayout(content_layout)

        self._bottom_spacer = QSpacerItem(
            0,
            _BASE_OUTER_GAP,
            QSizePolicy.Policy.Minimum,
            QSizePolicy.Policy.Fixed,
        )
        self._outer_layout.addItem(self._bottom_spacer)

        self._jp_browser.setMouseTracking(True)
        self._jp_browser.viewport().setMouseTracking(True)
        self._jp_browser.viewport().installEventFilter(self)

        self._preview_browser.setMouseTracking(True)
        self._preview_browser.viewport().setMouseTracking(True)
        self._preview_browser.viewport().installEventFilter(self)

        self.setMouseTracking(True)
        self._resize_edge: str = ""
        self._resize_origin: QPoint | None = None
        self._resize_geo: QRect | None = None
        self._is_manual_resize: bool = False

        self.set_status("Initializing...")
        self._update_arrow_visibility()

    def _center_on_screen(self) -> None:
        screen_geo = QApplication.primaryScreen().geometry()
        x = screen_geo.center().x() - self.width() // 2
        y = screen_geo.bottom() - self.height() - 40
        self.move(x, y)

    def on_sentence_ready(self, result: SentenceResult) -> None:
        """Display a new sentence result and add it to history.

        In LIVE mode (not browsing): render the new sentence in the main browser.
        In BROWSE mode (browsing history): keep the browsed sentence in the main
        browser and update the preview browser with the new latest result.

        Args:
            result: Pipeline output containing Japanese text and JLPT analysis data.
        """
        self._history.add(result)

        if self._history.is_browsing:
            # BROWSE mode - update preview browser with latest
            if self._history.latest is not None:
                self._render_in_browser(self._preview_browser, self._history.latest)
            self._preview_browser.setVisible(True)
        else:
            # LIVE mode - show latest in main browser
            if self._history.current is not None:
                self._current_result = self._history.current
                self._render_result(self._current_result)
            self.dedup_reset.emit()

        self._update_arrow_visibility()
        QTimer.singleShot(0, self._adjust_height_to_content)
        logger.debug(
            "on_sentence_ready: text=%s is_browsing=%s",
            result.japanese_text[:20] if result.japanese_text else "",
            self._history.is_browsing,
        )

    def _render_in_browser(self, browser: "QTextBrowser", result: SentenceResult) -> None:
        """Render a SentenceResult into the given browser widget.

        Uses SentenceResult.get_display_analysis() as the single source of truth.

        Args:
            browser: The QTextBrowser to render into.
            result: The sentence result to render.
        """
        doc = browser.document()

        if result.analysis is not None:
            # Use get_display_analysis() - SINGLE SOURCE OF TRUTH
            display_analysis = result.get_display_analysis(
                user_level=self._user_level,
                enable_vocab=self._enable_vocab,
                enable_grammar=self._enable_grammar,
            )
            self._renderer.apply_to_document(
                doc,
                result.japanese_text,
                display_analysis,
                user_level=self._user_level,
            )
        else:
            doc.setPlainText(result.japanese_text)

        # Center align all blocks
        cursor = QTextCursor(doc)
        cursor.select(QTextCursor.SelectionType.Document)
        block_fmt = QTextBlockFormat()
        block_fmt.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cursor.setBlockFormat(block_fmt)

    def _render_result(self, result: SentenceResult) -> None:
        """Render a result into the active browser and schedule height adjustment."""
        self._render_in_browser(self._jp_browser, result)
        # Defer height adjustment to allow document layout
        QTimer.singleShot(0, self._adjust_height_to_content)

    def on_asr_ready(self, result: ASRResult) -> None:
        """Show ASR text immediately.

        Args:
            result: ASR output containing Japanese text.
        """
        if self._history.is_browsing:
            _set_centered_plain_text(self._preview_browser, result.text)
        else:
            _set_centered_plain_text(self._jp_browser, result.text)
        QTimer.singleShot(0, self._adjust_height_to_content)
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
        self._manual_spacing_delta = config.overlay_manual_spacing_delta

        # Update font on both widget and document for HTML content
        new_font = _make_font(config.overlay_font_size_jp)
        self._jp_browser.setFont(new_font)
        self._jp_browser.document().setDefaultFont(new_font)
        self._preview_browser.setFont(new_font)
        self._preview_browser.document().setDefaultFont(new_font)

        self._renderer.update_colors(jlpt_colors_to_renderer_format(config.jlpt_colors))

        # Resize history capacity
        self._history.resize(config.max_history)

        # Re-render current sentence in main browser
        if self._current_result is not None:
            self._render_result(self._current_result)

        # Re-render latest sentence in preview browser (if in BROWSE mode)
        # This ensures config changes affect both browsers immediately
        if self._preview_browser.isVisible() and self._history.latest is not None:
            self._render_in_browser(self._preview_browser, self._history.latest)

        # Adjust height if no content
        if self._current_result is None:
            QTimer.singleShot(0, self._adjust_height_to_content)

        self._update_arrow_visibility()
        self._apply_spacing_distribution()

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
        _set_centered_plain_text(self._jp_browser, text)
        QTimer.singleShot(0, self._adjust_height_to_content)
        logger.debug("set_status: %s", text)

    def _prev_sentence(self) -> None:
        if not self._history.go_prev():
            return

        # Show preview browser when first entering BROWSE mode
        if self._history.latest is not None and not self._preview_browser.isVisible():
            self._render_in_browser(self._preview_browser, self._history.latest)
            self._preview_browser.setVisible(True)

        if self._history.current is not None:
            self._current_result = self._history.current
            self._render_result(self._current_result)
        self._update_arrow_visibility()
        logger.debug("_prev_sentence: cursor=%s", self._history.cursor_index)

    def _next_sentence(self) -> None:
        if not self._history.can_go_next:
            return

        self._history.go_next()  # May enter LIVE mode

        if not self._history.is_browsing:
            # Returned to LIVE mode
            self._preview_browser.setVisible(False)
            self.dedup_reset.emit()

        if self._history.current is not None:
            self._current_result = self._history.current
            self._render_result(self._current_result)
        self._update_arrow_visibility()
        logger.debug(
            "_next_sentence: cursor=%s is_browsing=%s",
            self._history.cursor_index,
            self._history.is_browsing,
        )

    def _update_arrow_visibility(self) -> None:
        """Enable/disable arrow buttons based on history navigation state.

        Buttons remain always visible for a consistent layout; only their
        enabled state (and therefore their visual opacity) changes.
        """
        self._prev_btn.setEnabled(self._history.can_go_prev)
        self._next_btn.setEnabled(self._history.can_go_next)

    def _spacing_distribution(self) -> tuple[int, int, int]:
        font_scale = max(0.7, self._jp_browser.fontInfo().pointSizeF() / 16.0)
        base_outer_gap = max(_MIN_OUTER_GAP, int(round(_BASE_OUTER_GAP * font_scale)))

        if self._preview_browser.isVisible():
            base_middle_gap = max(_MIN_MIDDLE_GAP, int(round(_BASE_MIDDLE_GAP * font_scale)))
            base_top = base_outer_gap
            base_middle = base_middle_gap
            base_bottom = base_outer_gap
            segments = 3
        else:
            base_top = base_outer_gap
            base_middle = 0
            base_bottom = base_outer_gap
            segments = 2

        min_delta, max_delta = self._spacing_delta_bounds(base_top, base_middle, base_bottom)
        clamped_delta = max(min_delta, min(max_delta, self._manual_spacing_delta))
        self._manual_spacing_delta = clamped_delta

        if clamped_delta >= 0:
            extra_per_segment, remainder = divmod(clamped_delta, segments)
            top = base_top + extra_per_segment + (1 if remainder > 0 else 0)
            middle = base_middle + extra_per_segment + (1 if remainder > 1 else 0)
            bottom = base_bottom + extra_per_segment
        else:
            reduction = -clamped_delta
            dec_per_segment, remainder = divmod(reduction, segments)
            top = base_top - dec_per_segment - (1 if remainder > 0 else 0)
            middle = base_middle - dec_per_segment - (1 if remainder > 1 else 0)
            bottom = base_bottom - dec_per_segment

        top = max(_MIN_OUTER_GAP, top)
        bottom = max(_MIN_OUTER_GAP, bottom)
        if self._preview_browser.isVisible():
            middle = max(_MIN_MIDDLE_GAP, middle)
        else:
            middle = 0

        return top, middle, bottom

    def _spacing_delta_bounds(self, base_top: int, base_middle: int, base_bottom: int) -> tuple[int, int]:
        base_total = base_top + base_middle + base_bottom
        min_total = (
            (_MIN_OUTER_GAP * 2) + (_MIN_MIDDLE_GAP if self._preview_browser.isVisible() else 0)
        )
        min_delta = min_total - base_total
        max_delta = max(0, self.maximumHeight() - self._base_auto_height())
        return min_delta, max_delta

    def _dynamic_min_height(self) -> int:
        font_scale = max(0.7, self._jp_browser.fontInfo().pointSizeF() / 16.0)
        base_outer_gap = max(_MIN_OUTER_GAP, int(round(_BASE_OUTER_GAP * font_scale)))
        base_middle_gap = max(_MIN_MIDDLE_GAP, int(round(_BASE_MIDDLE_GAP * font_scale)))
        base_top = base_outer_gap
        base_bottom = base_outer_gap
        base_middle = base_middle_gap if self._preview_browser.isVisible() else 0

        min_delta, _ = self._spacing_delta_bounds(base_top, base_middle, base_bottom)
        return int(math.ceil(self._base_auto_height() + min_delta))

    def _apply_spacing_distribution(self) -> None:
        top, middle, bottom = self._spacing_distribution()
        scaled_outer_margins = max(
            _MIN_OUTER_MARGINS,
            int(round(_OUTER_MARGINS * max(0.7, self._jp_browser.fontInfo().pointSizeF() / 16.0))),
        )
        self._outer_layout.setContentsMargins(
            scaled_outer_margins,
            scaled_outer_margins,
            scaled_outer_margins,
            scaled_outer_margins,
        )
        self._top_spacer.changeSize(0, top, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self._middle_spacer.changeSize(0, middle, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self._bottom_spacer.changeSize(0, bottom, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)

        layout = self.layout()
        if layout is not None:
            layout.invalidate()

    def _content_height(self, browser: "QTextBrowser") -> float:
        doc = browser.document()
        viewport_width = max(1, browser.viewport().width())
        doc.setTextWidth(viewport_width)
        return doc.size().height()

    def _base_auto_height(self) -> int:
        font_scale = max(0.7, self._jp_browser.fontInfo().pointSizeF() / 16.0)
        base_outer_gap = max(_MIN_OUTER_GAP, int(round(_BASE_OUTER_GAP * font_scale)))
        base_middle_gap = max(_MIN_MIDDLE_GAP, int(round(_BASE_MIDDLE_GAP * font_scale)))
        scaled_outer_margins = max(_MIN_OUTER_MARGINS, int(round(_OUTER_MARGINS * font_scale)))

        jp_height = self._content_height(self._jp_browser)
        preview_height = self._content_height(self._preview_browser) if self._preview_browser.isVisible() else 0.0
        spacing_height = (2 * base_outer_gap) + (base_middle_gap if self._preview_browser.isVisible() else 0)
        content_padding = _CONTENT_SAFETY_PADDING * (2 if self._preview_browser.isVisible() else 1)
        total_height = jp_height + preview_height + (2 * scaled_outer_margins) + spacing_height + content_padding
        return int(math.ceil(total_height))

    def _clamp_height(self, height: int) -> int:
        min_height = max(self.minimumHeight(), _MIN_WINDOW_HEIGHT, self._dynamic_min_height())
        return max(min_height, min(self.maximumHeight(), height))

    def _sync_manual_spacing_from_current_height(self) -> None:
        base_height = self._base_auto_height()
        self._manual_spacing_delta = self.height() - base_height
        self._spacing_distribution()
        self._apply_spacing_distribution()

    def _adjust_height_to_content(self) -> None:
        """Resize overlay height to fit text content.

        Calculates the ideal height based on the document content and resizes
        the window while respecting minimum and maximum height constraints.
        When in BROWSE mode (both browsers visible) the heights are summed.
        """
        self._apply_spacing_distribution()
        total_height = self._base_auto_height() + max(0, self._manual_spacing_delta)
        new_height = self._clamp_height(total_height)

        # Only resize if height differs significantly (avoid jitter)
        if abs(self.height() - new_height) > 2:
            self.resize(self.width(), new_height)

    def _handle_hover_at_viewport_pos(
        self,
        browser: "QTextBrowser",
        result: "SentenceResult | None",
        viewport_pos: QPoint,
    ) -> None:
        """Emit highlight_hovered for the highlighted word under the cursor.

        Uses SentenceResult.get_display_analysis() as the single source of truth,
        ensuring consistency with rendering.

        Args:
            browser: The browser widget in whose viewport the hover occurred.
            result: The SentenceResult currently displayed in that browser.
            viewport_pos: Mouse position in viewport-local coordinates.
        """
        if result is None or result.analysis is None:
            self.highlight_left.emit()
            return

        cursor = browser.cursorForPosition(viewport_pos)
        char_pos = cursor.position()

        # Use get_display_analysis() - SAME DATA SOURCE AS RENDERING
        display_analysis = result.get_display_analysis(
            user_level=self._user_level,
            enable_vocab=self._enable_vocab,
            enable_grammar=self._enable_grammar,
        )

        hit: VocabHit | GrammarHit | None = self._renderer.get_highlight_at_position(
            char_pos,
            display_analysis,
        )
        if hit is not None:
            global_pos = browser.viewport().mapToGlobal(viewport_pos)
            self.highlight_hovered.emit(hit, global_pos, result)
        else:
            self.highlight_left.emit()

    def _save_size(self) -> None:
        self._config.overlay_width = self.width()
        self._config.overlay_height = self.height()
        self._config.overlay_manual_spacing_delta = self._manual_spacing_delta
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
        min_w, min_h = self.minimumWidth(), self._dynamic_min_height()
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
        if not self._is_manual_resize and event.oldSize().width() != event.size().width():
            QTimer.singleShot(0, self._adjust_height_to_content)
        QTimer.singleShot(500, self._save_size)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            edge = self._edge_at(event.pos())
            if edge:
                self._resize_edge = edge
                self._resize_origin = event.globalPosition().toPoint()
                self._resize_geo = QRect(self.geometry())
                self._is_manual_resize = True
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
            had_resize = bool(self._resize_edge)
            resize_edge = self._resize_edge
            if had_resize:
                self._sync_manual_spacing_from_current_height()
                if "l" in resize_edge or "r" in resize_edge:
                    QTimer.singleShot(0, self._adjust_height_to_content)

            self._drag_pos = None
            self._resize_edge = ""
            self._resize_origin = None
            self._resize_geo = None
            self._is_manual_resize = False

            if had_resize:
                self._save_size()
        super().mouseReleaseEvent(event)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        jp_vp = self._jp_browser.viewport()
        prev_vp = self._preview_browser.viewport()
        is_jp_viewport = watched is jp_vp
        is_prev_viewport = watched is prev_vp
        is_browser_viewport = is_jp_viewport or is_prev_viewport

        if is_browser_viewport and isinstance(event, QMouseEvent):
            etype = event.type()

            # Hover detection — route to correct browser + result
            no_left_btn = not (event.buttons() & Qt.MouseButton.LeftButton)
            if etype == QEvent.Type.MouseMove and no_left_btn:
                if is_jp_viewport:
                    self._handle_hover_at_viewport_pos(
                        self._jp_browser, self._current_result, event.position().toPoint()
                    )
                elif is_prev_viewport:
                    self._handle_hover_at_viewport_pos(
                        self._preview_browser, self._history.latest, event.position().toPoint()
                    )

            # Drag-to-move — only on the main jp_browser viewport
            if is_jp_viewport:
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

        # Handle Leave event to hide tooltip when mouse exits viewport
        if is_browser_viewport and event.type() == QEvent.Type.Leave:
            self.highlight_left.emit()

        # Handle context menu for browser viewports
        if is_browser_viewport and event.type() == QEvent.Type.ContextMenu:
            assert isinstance(event, QContextMenuEvent)
            menu = create_context_menu(
                parent=self,
                on_settings=self.settings_requested.emit,
                on_toggle=self.toggle_overlay.emit,
                on_quit=self.quit_requested.emit,
                overlay_visible=self.isVisible(),
            )
            menu.exec(event.globalPos())
            return True

        return super().eventFilter(watched, event)

    def closeEvent(self, event: QCloseEvent) -> None:
        super().closeEvent(event)

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:  # noqa: F821
        """Show context menu with settings, toggle, and quit actions."""
        menu = create_context_menu(
            parent=self,
            on_settings=self.settings_requested.emit,
            on_toggle=self.toggle_overlay.emit,
            on_quit=self.quit_requested.emit,
            overlay_visible=self.isVisible(),
        )
        menu.exec(event.globalPos())
