"""JLPT vocabulary and grammar highlight renderer using QTextCharFormat.

Renders highlighted Japanese text directly to QTextDocument, ensuring
cursor positions align perfectly with VocabHit/GrammarHit offsets.

Note: Conflict resolution between vocab and grammar is handled by
AnalysisResult.resolve_conflicts(), which is called by SentenceResult.get_display_analysis().
This ensures that HighlightRenderer and hover detection use the exact same data.
"""

import logging
from typing import TypeAlias

from PySide6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor, QTextDocument

from src.models import AnalysisResult, GrammarHit, VocabHit

logger = logging.getLogger(__name__)

_Span: TypeAlias = tuple[int, int, str]


class HighlightRenderer:
    """Renders Japanese text with JLPT-level color highlights using QTextCharFormat.

    Works directly with QTextDocument to ensure position alignment.

    The input AnalysisResult must already have conflicts resolved via
    AnalysisResult.resolve_conflicts() (typically called by get_display_analysis()).

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

        IMPORTANT: The analysis must be conflict-resolved (via get_display_analysis())
        before passing to this method. No vocab/grammar conflict resolution is performed here.

        Note: For GrammarHit with matched_parts, only the keyword parts are highlighted,
        not the filler text between them.

        Args:
            document: The QTextDocument to format.
            japanese_text: The raw Japanese string to render.
            analysis: Conflict-resolved analysis result (from get_display_analysis()).
            user_level: The user's current JLPT level (1–5). Unused but kept for API parity.
        """
        # Set plain text first - this ensures position alignment
        document.setPlainText(japanese_text)

        if not japanese_text:
            return

        # Build spans for rendering
        # For grammar with matched_parts, only highlight those parts (not filler)
        grammar_spans: list[_Span] = []
        for gh in analysis.grammar_hits:
            parts = gh.matched_parts if gh.matched_parts else ((gh.start_pos, gh.end_pos),)
            for part_start, part_end in parts:
                grammar_spans.append((part_start, part_end, self._grammar_color(gh.jlpt_level)))

        vocab_spans: list[_Span] = [
            (vh.start_pos, vh.end_pos, self._vocab_color(vh.jlpt_level))
            for vh in analysis.vocab_hits
        ]

        # Since resolve_conflicts() ensures no overlaps, sort by start position only
        all_spans = grammar_spans + vocab_spans
        all_spans.sort(key=lambda span: span[0])

        cursor = QTextCursor(document)

        for start, end, color in all_spans:
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

        IMPORTANT: The analysis must be conflict-resolved (via get_display_analysis())
        before passing to this method. No vocab/grammar conflict resolution is performed here.

        Note: For GrammarHit with matched_parts, only positions within those parts
        are considered as matching the grammar hit (filler positions return None or vocab).

        Args:
            position: Zero-based character index into the Japanese text.
            analysis: Conflict-resolved analysis result (from get_display_analysis()).

        Returns:
            The first ``GrammarHit`` whose range contains *position*, or the
            first ``VocabHit`` if no grammar hit matches, or ``None``.
        """
        # Grammar first (higher priority for hover display)
        # For matched_parts, only check keyword positions
        for gh in analysis.grammar_hits:
            parts = gh.matched_parts if gh.matched_parts else ((gh.start_pos, gh.end_pos),)
            for part_start, part_end in parts:
                if part_start <= position < part_end:
                    return gh

        # Then vocab
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
