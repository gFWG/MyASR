"""JLPT vocabulary and grammar highlight renderer using QTextCharFormat.

Renders highlighted Japanese text directly to QTextDocument, ensuring
cursor positions align perfectly with VocabHit/GrammarHit offsets.
"""

import logging
from typing import TypeAlias

from PySide6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor, QTextDocument

from src.models import AnalysisResult, GrammarHit, VocabHit

logger = logging.getLogger(__name__)

_TYPE_GRAMMAR = "grammar"
_TYPE_VOCAB = "vocab"

_Span: TypeAlias = tuple[int, int, str, str]


class HighlightRenderer:
    """Renders Japanese text with JLPT-level color highlights using QTextCharFormat.

    Grammar highlights take priority over overlapping vocab highlights.
    Works directly with QTextDocument to ensure position alignment.

    Attributes:
        JLPT_COLORS: Default mapping from JLPT level (1–5) to vocab/grammar hex colors.
    """

    JLPT_COLORS: dict[int, dict[str, str]] = {
        5: {"vocab": "#E8F5E9", "grammar": "#81C784"},
        4: {"vocab": "#C8E6C9", "grammar": "#4CAF50"},
        3: {"vocab": "#BBDEFB", "grammar": "#1976D2"},
        2: {"vocab": "#FFF9C4", "grammar": "#F9A825"},
        1: {"vocab": "#FFCDD2", "grammar": "#D32F2F"},
    }

    def __init__(self, jlpt_colors: dict[int, dict[str, str]] | None = None) -> None:
        self._colors: dict[int, dict[str, str]] = jlpt_colors or dict(self.JLPT_COLORS)

    def update_colors(self, jlpt_colors: dict[int, dict[str, str]]) -> None:
        """Update the JLPT color mapping at runtime.

        Args:
            jlpt_colors: Mapping from JLPT level (1–5) to vocab/grammar hex colors.
        """
        self._colors = jlpt_colors

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def apply_to_document(
        self,
        document: QTextDocument,
        japanese_text: str,
        analysis: AnalysisResult,
        user_level: int,
    ) -> None:
        """Apply JLPT highlights directly to a QTextDocument using QTextCharFormat.

        This method bypasses HTML entirely, ensuring that cursor positions
        align perfectly with VocabHit/GrammarHit start_pos/end_pos values.

        Args:
            document: The QTextDocument to format.
            japanese_text: The raw Japanese string to render.
            analysis: Pipeline analysis result containing vocab and grammar hits.
            user_level: The user's current JLPT level (1–5). Unused but kept for API parity.
        """
        # Set plain text first - this ensures position alignment
        document.setPlainText(japanese_text)

        if not japanese_text:
            return

        # Build spans list
        grammar_spans: list[_Span] = []
        for gh in analysis.grammar_hits:
            color = self._grammar_color(gh.jlpt_level)
            grammar_spans.append((gh.start_pos, gh.end_pos, color, _TYPE_GRAMMAR))

        vocab_spans: list[_Span] = []
        for vh in analysis.vocab_hits:
            if self._is_fully_covered(vh.start_pos, vh.end_pos, grammar_spans):
                logger.debug(
                    "Vocab span [%d,%d] suppressed by grammar coverage",
                    vh.start_pos,
                    vh.end_pos,
                )
                continue
            color = self._vocab_color(vh.jlpt_level)
            vocab_spans.append((vh.start_pos, vh.end_pos, color, _TYPE_VOCAB))

        # Apply formatting via QTextCursor
        # Process grammar first (higher priority), then vocab
        # Sort by start position, but grammar comes before vocab at same position
        def _sort_key(span: _Span) -> tuple[int, int]:
            start, _end, _color, span_type = span
            # Grammar has priority 0, vocab has priority 1
            type_priority = 0 if span_type == _TYPE_GRAMMAR else 1
            return (start, type_priority)

        all_spans = grammar_spans + vocab_spans
        all_spans.sort(key=_sort_key)

        cursor = QTextCursor(document)

        for start, end, color, _span_type in all_spans:
            cursor.setPosition(start)
            cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)

            fmt = QTextCharFormat()
            fmt.setForeground(QColor(color))
            fmt.setFontWeight(QFont.Weight.Bold)
            cursor.setCharFormat(fmt)

    def get_highlight_at_position(
        self,
        position: int,
        analysis: AnalysisResult,
    ) -> VocabHit | GrammarHit | None:
        """Return the highlight hit at a character position, grammar-first.

        Args:
            position: Zero-based character index into the Japanese text.
            analysis: Pipeline analysis result.

        Returns:
            The first ``GrammarHit`` whose range contains *position*, or the
            first ``VocabHit`` if no grammar hit matches, or ``None``.
        """
        for gh in analysis.grammar_hits:
            if gh.start_pos <= position < gh.end_pos:
                return gh

        for vh in analysis.vocab_hits:
            if vh.start_pos <= position < vh.end_pos:
                return vh

        return None

    # ------------------------------------------------------------------ #
    # Private helpers                                                      #
    # ------------------------------------------------------------------ #

    def _grammar_color(self, jlpt_level: int) -> str:
        """Return the grammar hex color for a JLPT level, defaulting to N4."""
        return self._colors.get(jlpt_level, self._colors.get(4, self.JLPT_COLORS[4]))["grammar"]

    def _vocab_color(self, jlpt_level: int) -> str:
        """Return the vocab hex color for a JLPT level, defaulting to N4."""
        return self._colors.get(jlpt_level, self._colors.get(4, self.JLPT_COLORS[4]))["vocab"]

    @staticmethod
    def _is_fully_covered(
        start: int,
        end: int,
        grammar_spans: list[_Span],
    ) -> bool:
        """Return True if [start, end) is fully contained in any grammar span."""
        for gs_start, gs_end, _color, _type in grammar_spans:
            if gs_start <= start and end <= gs_end:
                return True
        return False
