"""Frameless floating tooltip widget for JLPT vocabulary and grammar info.

Shows vocabulary or grammar hit details on hover, emits a deduplication signal
to track which items have been recorded per sentence.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPaintEvent
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from src.db.models import GrammarHit, VocabHit

logger = logging.getLogger(__name__)

_FONT_FAMILIES = "Segoe UI, Yu Gothic UI, Noto Sans CJK JP, sans-serif"
_FONT_SIZE = 12
_BG_COLOR = QColor(40, 40, 40, 230)
_CORNER_RADIUS = 8
_TOOLTIP_OFFSET = 8
_MAX_WIDTH = 300

# Grammar background colors from HighlightRenderer.JLPT_COLORS
_JLPT_GRAMMAR_COLORS: dict[int, str] = {
    4: "#4CAF50",
    3: "#1976D2",
    2: "#F9A825",
    1: "#D32F2F",
}
_DEFAULT_LEVEL_COLOR = "#888888"


def _make_label(font_size: int = _FONT_SIZE) -> QLabel:
    label = QLabel()
    font = QFont(_FONT_FAMILIES, font_size)
    font.setStyleHint(QFont.StyleHint.SansSerif)
    label.setFont(font)
    label.setWordWrap(True)
    label.setStyleSheet("background: transparent; color: white;")
    return label


class TooltipPopup(QWidget):
    """Frameless floating tooltip for JLPT vocabulary and grammar hits.

    Shows level badge, word/pattern, and description in a semi-transparent
    rounded-corner popup. Emits ``record_triggered`` once per unique
    (sentence_id, type, highlight_id) tuple to support deduplication.

    Signals:
        record_triggered: Emitted when a new highlight is shown for the first
            time in a sentence context. Arguments are the type string
            ('vocab' or 'grammar') and the highlight_id integer.
    """

    record_triggered = Signal(str, int)  # ('vocab'|'grammar', highlight_id)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setMaximumWidth(_MAX_WIDTH)

        self._shown: set[tuple[int | None, str, int]] = set()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        self._level_label = _make_label(font_size=11)
        self._word_label = _make_label(font_size=13)
        self._pronunciation_label = _make_label(font_size=11)
        self._pronunciation_label.setStyleSheet(
            "background: transparent; color: rgba(255, 255, 255, 0.7);"
        )
        self._desc_label = _make_label(font_size=11)

        layout.addWidget(self._level_label)
        layout.addWidget(self._word_label)
        layout.addWidget(self._pronunciation_label)
        layout.addWidget(self._desc_label)

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def show_for_vocab(
        self,
        hit: VocabHit,
        position: QPoint,
        sentence_id: int | None,
        highlight_id: int,
    ) -> None:
        """Show the tooltip for a vocabulary hit.

        Args:
            hit: The VocabHit to display.
            position: Global screen position to anchor the tooltip near.
            sentence_id: Current sentence ID for deduplication tracking.
            highlight_id: Unique ID for this highlight entry.
        """
        key: tuple[int | None, str, int] = (sentence_id, "vocab", highlight_id)

        if key not in self._shown:
            self._shown.add(key)
            self.record_triggered.emit("vocab", highlight_id)
            logger.debug(
                "record_triggered: vocab highlight_id=%d sentence_id=%s",
                highlight_id,
                sentence_id,
            )

        level_color = _JLPT_GRAMMAR_COLORS.get(hit.jlpt_level, _DEFAULT_LEVEL_COLOR)
        self._level_label.setText(f"N{hit.jlpt_level}")
        self._level_label.setStyleSheet(
            f"background: {level_color}; color: white; border-radius: 4px; padding: 1px 4px;"
        )
        self._word_label.setText(f"{hit.lemma} ({hit.surface})")

        if hit.pronunciation:
            self._pronunciation_label.setText(hit.pronunciation)
            self._pronunciation_label.show()
        else:
            self._pronunciation_label.hide()

        if hit.definition:
            self._desc_label.setText(f"{hit.pos} • {hit.definition}")
            self._desc_label.show()
        elif hit.pos:
            self._desc_label.setText(hit.pos)
            self._desc_label.show()
        else:
            self._desc_label.hide()

        self.adjustSize()
        self._position_near(position)
        self.show()

    def show_for_grammar(
        self,
        hit: GrammarHit,
        position: QPoint,
        sentence_id: int | None,
        highlight_id: int,
    ) -> None:
        """Show the tooltip for a grammar hit.

        Args:
            hit: The GrammarHit to display.
            position: Global screen position to anchor the tooltip near.
            sentence_id: Current sentence ID for deduplication tracking.
            highlight_id: Unique ID for this highlight entry.
        """
        key: tuple[int | None, str, int] = (sentence_id, "grammar", highlight_id)

        if key not in self._shown:
            self._shown.add(key)
            self.record_triggered.emit("grammar", highlight_id)
            logger.debug(
                "record_triggered: grammar highlight_id=%d sentence_id=%s",
                highlight_id,
                sentence_id,
            )

        level_color = _JLPT_GRAMMAR_COLORS.get(hit.jlpt_level, _DEFAULT_LEVEL_COLOR)
        self._level_label.setText(f"N{hit.jlpt_level}")
        self._level_label.setStyleSheet(
            f"background: {level_color}; color: white; border-radius: 4px; padding: 1px 4px;"
        )
        self._word_label.setText(hit.matched_text)
        self._pronunciation_label.hide()
        description = hit.description or "Grammar pattern"
        self._desc_label.setText(f"{hit.confidence_type}: {description}")
        self._desc_label.show()

        self.adjustSize()
        self._position_near(position)
        self.show()

    def hide_tooltip(self) -> None:
        """Hide the tooltip widget."""
        self.hide()

    def reset_dedup(self) -> None:
        """Clear the deduplication set so signals fire again on next show."""
        self._shown.clear()
        logger.debug("reset_dedup: cleared deduplication set")

    # ------------------------------------------------------------------ #
    # Private helpers                                                      #
    # ------------------------------------------------------------------ #

    def _position_near(self, position: QPoint) -> None:
        """Move the tooltip above or below position, staying on screen.

        Args:
            position: Global screen position to anchor near.
        """
        y = position.y() - self.sizeHint().height() - _TOOLTIP_OFFSET
        if y < 0:
            y = position.y() + _TOOLTIP_OFFSET
        self.move(position.x(), y)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(_BG_COLOR)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(self.rect(), _CORNER_RADIUS, _CORNER_RADIUS)
