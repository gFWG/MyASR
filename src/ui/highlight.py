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
_GrammarSpan: TypeAlias = tuple[int, int, GrammarHit]
_VocabSpan: TypeAlias = tuple[int, int, VocabHit]


class HighlightRenderer:
    """Renders Japanese text with JLPT-level color highlights using QTextCharFormat.

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
        self._cached_analysis: AnalysisResult | None = None
        self._cached_spans: tuple[list[_GrammarSpan], list[_VocabSpan]] | None = None

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

        resolved_grammar_spans, resolved_vocab_spans = self._get_resolved_highlight_spans(analysis)

        grammar_spans: list[_Span] = [
            (start, end, self._grammar_color(hit.jlpt_level), _TYPE_GRAMMAR)
            for start, end, hit in resolved_grammar_spans
        ]
        vocab_spans: list[_Span] = [
            (start, end, self._vocab_color(hit.jlpt_level), _TYPE_VOCAB)
            for start, end, hit in resolved_vocab_spans
        ]

        def _sort_key(span: _Span) -> tuple[int, int]:
            start, _end, _color, span_type = span
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
        grammar_spans, vocab_spans = self._get_resolved_highlight_spans(analysis)

        for start, end, grammar_hit in grammar_spans:
            if start <= position < end:
                return grammar_hit

        for start, end, vocab_hit in vocab_spans:
            if start <= position < end:
                return vocab_hit

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

    def _resolve_highlight_spans(
        self,
        analysis: AnalysisResult,
    ) -> tuple[list[_GrammarSpan], list[_VocabSpan]]:
        sorted_vocab_hits = sorted(
            analysis.vocab_hits,
            key=lambda hit: (hit.start_pos, -hit.end_pos),
        )

        grammar_spans: list[_GrammarSpan] = []
        dominant_single_grammar_spans: list[tuple[int, int]] = []

        for gh in analysis.grammar_hits:
            fragments = gh.matched_parts if gh.matched_parts else ((gh.start_pos, gh.end_pos),)

            if len(fragments) == 1:
                start, end = fragments[0]
                if self._single_fragment_grammar_wins(start, end, sorted_vocab_hits):
                    grammar_spans.append((start, end, gh))
                    dominant_single_grammar_spans.append((start, end))
                continue

            if any(
                self._overlaps_any_vocab(part_start, part_end, sorted_vocab_hits)
                for part_start, part_end in fragments
            ):
                logger.debug(
                    "Grammar rule %s suppressed because one or more fragments overlap vocab",
                    gh.rule_id,
                )
                continue

            for part_start, part_end in fragments:
                grammar_spans.append((part_start, part_end, gh))

        vocab_spans: list[_VocabSpan] = []
        for vh in sorted_vocab_hits:
            if self._is_fully_covered_by_grammar(
                vh.start_pos, vh.end_pos, dominant_single_grammar_spans
            ):
                logger.debug(
                    "Vocab span [%d,%d] suppressed by grammar coverage",
                    vh.start_pos,
                    vh.end_pos,
                )
                continue
            vocab_spans.append((vh.start_pos, vh.end_pos, vh))

        return grammar_spans, vocab_spans

    def _get_resolved_highlight_spans(
        self,
        analysis: AnalysisResult,
    ) -> tuple[list[_GrammarSpan], list[_VocabSpan]]:
        if self._cached_analysis is analysis and self._cached_spans is not None:
            return self._cached_spans

        resolved_spans = self._resolve_highlight_spans(analysis)
        self._cached_analysis = analysis
        self._cached_spans = resolved_spans
        return resolved_spans

    @staticmethod
    def _single_fragment_grammar_wins(
        grammar_start: int,
        grammar_end: int,
        vocab_hits: list[VocabHit],
    ) -> bool:
        grammar_length = grammar_end - grammar_start

        for vh in vocab_hits:
            if vh.start_pos >= grammar_end:
                break
            if vh.end_pos <= grammar_start:
                continue
            if not HighlightRenderer._contains_span(
                grammar_start,
                grammar_end,
                vh.start_pos,
                vh.end_pos,
            ):
                continue

            vocab_length = vh.end_pos - vh.start_pos
            if vocab_length > grammar_length:
                logger.debug(
                    "Grammar span [%d,%d] suppressed by longer vocab span [%d,%d]",
                    grammar_start,
                    grammar_end,
                    vh.start_pos,
                    vh.end_pos,
                )
                return False

        return True

    @staticmethod
    def _overlaps_any_vocab(start: int, end: int, vocab_hits: list[VocabHit]) -> bool:
        for vh in vocab_hits:
            if vh.start_pos >= end:
                break
            if start < vh.end_pos and vh.start_pos < end:
                return True
        return False

    @staticmethod
    def _contains_span(
        outer_start: int,
        outer_end: int,
        inner_start: int,
        inner_end: int,
    ) -> bool:
        return outer_start <= inner_start and inner_end <= outer_end

    @staticmethod
    def _is_fully_covered_by_grammar(
        start: int,
        end: int,
        grammar_spans: list[tuple[int, int]],
    ) -> bool:
        for gs_start, gs_end in grammar_spans:
            if gs_start <= start and end <= gs_end:
                return True
        return False
