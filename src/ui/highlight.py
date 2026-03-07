"""HTML highlight renderer for JLPT vocabulary and grammar annotations.

Pure Python — no Qt/PySide6 imports. Produces HTML span markup with JLPT-level
colors. Grammar spans take priority over overlapping vocab spans.
"""

import html
import logging
from typing import TypeAlias

from src.db.models import AnalysisResult, GrammarHit, VocabHit

logger = logging.getLogger(__name__)

_TYPE_GRAMMAR = "grammar"
_TYPE_VOCAB = "vocab"

_Span: TypeAlias = tuple[int, int, str, str]


class HighlightRenderer:
    """Renders Japanese text as HTML with JLPT-level color highlights.

    Grammar highlights take priority over overlapping vocab highlights.
    All text is HTML-escaped to prevent XSS.

    Attributes:
        JLPT_COLORS: Mapping from JLPT level (1–4) to vocab/grammar hex colors.
    """

    JLPT_COLORS: dict[int, dict[str, str]] = {
        4: {"vocab": "#C8E6C9", "grammar": "#4CAF50"},
        3: {"vocab": "#BBDEFB", "grammar": "#1976D2"},
        2: {"vocab": "#FFF9C4", "grammar": "#F9A825"},
        1: {"vocab": "#FFCDD2", "grammar": "#D32F2F"},
    }

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def build_rich_text(
        self,
        japanese_text: str,
        analysis: AnalysisResult,
        user_level: int,
    ) -> str:
        """Build HTML string with JLPT-colored spans for the given text.

        Grammar spans have priority: a vocab span fully covered by a grammar
        span is dropped. Partial overlaps are NOT split — the vocab span is
        kept as-is if not *fully* covered by any single grammar span.

        Args:
            japanese_text: The raw Japanese string to render.
            analysis: Pipeline analysis result containing vocab and grammar hits.
            user_level: The user's current JLPT level (1–5). Unused by the
                renderer itself but accepted for forward-compatibility.

        Returns:
            HTML string with ``<span>`` elements for highlighted regions, or
            ``""`` for empty input, or plain HTML-escaped text when no hits
            exist.
        """
        if not japanese_text:
            return ""

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

        all_spans: list[_Span] = grammar_spans + vocab_spans
        all_spans.sort(key=lambda s: s[0])

        if not all_spans:
            return html.escape(japanese_text)

        return self._render_spans(japanese_text, all_spans)

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
        return self.JLPT_COLORS.get(jlpt_level, self.JLPT_COLORS[4])["grammar"]

    def _vocab_color(self, jlpt_level: int) -> str:
        """Return the vocab hex color for a JLPT level, defaulting to N4."""
        return self.JLPT_COLORS.get(jlpt_level, self.JLPT_COLORS[4])["vocab"]

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

    @staticmethod
    def _render_spans(
        text: str,
        spans: list[_Span],
    ) -> str:
        """Assemble HTML from sorted, non-necessarily-contiguous spans.

        Characters outside all spans are emitted as plain HTML-escaped text.
        """
        parts: list[str] = []
        cursor = 0

        for start, end, color, _span_type in spans:
            # Text before this span
            if cursor < start:
                parts.append(html.escape(text[cursor:start]))

            # The span itself
            span_text = html.escape(text[start:end])
            parts.append(f'<span style="color: {color}; font-weight: bold;">{span_text}</span>')
            cursor = end

        # Trailing plain text
        if cursor < len(text):
            parts.append(html.escape(text[cursor:]))

        return "".join(parts)
