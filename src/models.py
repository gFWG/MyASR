"""Data models for MyASR pipeline and UI."""

from dataclasses import dataclass, field
from datetime import datetime

import numpy as np


@dataclass
class Token:
    surface: str
    lemma: str
    pos: str
    pos2: str = ""
    cType: str = ""
    cForm: str = ""


@dataclass
class VocabHit:
    surface: str
    lemma: str
    pos: str
    jlpt_level: int
    start_pos: int
    end_pos: int
    vocab_id: int = 0
    pronunciation: str = ""
    definition: str = ""


@dataclass
class GrammarHit:
    rule_id: str
    matched_text: str
    word: str
    jlpt_level: int
    description: str
    start_pos: int
    end_pos: int
    matched_parts: tuple[tuple[int, int], ...] = ()


@dataclass
class AnalysisResult:
    tokens: list[Token]
    vocab_hits: list[VocabHit]
    grammar_hits: list[GrammarHit]

    def resolve_conflicts(self) -> "AnalysisResult":
        """Resolve overlapping vocab and grammar hits.

        This ensures that no position in the text has both a vocab and grammar highlight.
        The resolved result is the SINGLE SOURCE OF TRUTH for rendering and hover detection.

        Conflict resolution rules:
        1. Single-fragment grammar vs vocab:
           - Vocab wins if length >= grammar length (including equal length)
           - Vocab wins if partially overlapping (not fully contained in grammar)
           - Grammar wins only if vocab is fully contained AND shorter than grammar
        2. Multi-fragment grammar: Each fragment is checked independently using the
           same rules as single-fragment grammar. If ALL fragments win, the grammar
           is preserved. If ANY fragment loses, the entire grammar is suppressed.
        3. Vocab that is fully covered by a dominant grammar fragment is suppressed.

        Returns:
            A new AnalysisResult with non-overlapping vocab_hits and grammar_hits.
        """
        if not self.vocab_hits and not self.grammar_hits:
            return AnalysisResult(tokens=self.tokens, vocab_hits=[], grammar_hits=[])

        # Sort vocab by start_pos ascending, end_pos descending (longer first at same start)
        sorted_vocab = sorted(self.vocab_hits, key=lambda h: (h.start_pos, -h.end_pos))

        resolved_grammar: list[GrammarHit] = []
        dominant_grammar_spans: list[tuple[int, int]] = []

        # Process grammar hits
        for gh in self.grammar_hits:
            fragments = gh.matched_parts if gh.matched_parts else ((gh.start_pos, gh.end_pos),)

            if len(fragments) == 1:
                start, end = fragments[0]
                if self._single_fragment_grammar_wins(start, end, sorted_vocab):
                    resolved_grammar.append(gh)
                    dominant_grammar_spans.append((start, end))
                continue

            # Multi-fragment grammar: all fragments must win for grammar to be preserved
            all_fragments_win = all(
                self._single_fragment_grammar_wins(part_start, part_end, sorted_vocab)
                for part_start, part_end in fragments
            )
            if all_fragments_win:
                resolved_grammar.append(gh)
                dominant_grammar_spans.extend(fragments)

        # Process vocab hits
        resolved_vocab: list[VocabHit] = []
        for vh in sorted_vocab:
            if self._is_fully_covered_by_grammar(vh.start_pos, vh.end_pos, dominant_grammar_spans):
                continue
            resolved_vocab.append(vh)

        return AnalysisResult(
            tokens=self.tokens,
            vocab_hits=resolved_vocab,
            grammar_hits=resolved_grammar,
        )

    @staticmethod
    def _single_fragment_grammar_wins(
        grammar_start: int,
        grammar_end: int,
        vocab_hits: list[VocabHit],
    ) -> bool:
        """Check if a single-fragment grammar should win over overlapping vocab.

        The grammar wins ONLY if:
        - No vocab overlaps with the grammar span, OR
        - All overlapping vocabs are shorter than the grammar (and fully contained)

        Vocab wins (grammar suppressed) when:
        - Vocab length >= grammar length (including equal length)
        - Vocab partially overlaps grammar (not fully contained)

        Args:
            grammar_start: Start position of the grammar span.
            grammar_end: End position of the grammar span.
            vocab_hits: Sorted list of vocab hits (by start_pos, then -end_pos).

        Returns:
            True if the grammar should be displayed, False if suppressed by vocab.
        """
        grammar_length = grammar_end - grammar_start

        for vh in vocab_hits:
            if vh.start_pos >= grammar_end:
                break
            if vh.end_pos <= grammar_start:
                continue

            # Check for ANY overlap
            if vh.start_pos < grammar_end and vh.end_pos > grammar_start:
                vocab_length = vh.end_pos - vh.start_pos

                # Rule 1: Vocab length >= grammar length → vocab wins
                if vocab_length >= grammar_length:
                    return False

                # Rule 2: Partial overlap (vocab not fully contained) → vocab wins
                is_fully_contained = (grammar_start <= vh.start_pos and vh.end_pos <= grammar_end)
                if not is_fully_contained:
                    return False

                # Rule 3: Vocab fully contained but shorter than grammar → grammar wins
                # (continue checking other vocabs)

        return True

    @staticmethod
    def _overlaps_any_vocab(start: int, end: int, vocab_hits: list[VocabHit]) -> bool:
        """Check if a span overlaps with any vocab hit.

        Args:
            start: Start position of the span.
            end: End position of the span.
            vocab_hits: Sorted list of vocab hits.

        Returns:
            True if the span overlaps with any vocab hit.
        """
        for vh in vocab_hits:
            if vh.start_pos >= end:
                break
            if start < vh.end_pos and vh.start_pos < end:
                return True
        return False

    @staticmethod
    def _is_fully_covered_by_grammar(
        start: int,
        end: int,
        grammar_spans: list[tuple[int, int]],
    ) -> bool:
        """Check if a span is fully covered by any grammar span.

        Args:
            start: Start position of the span.
            end: End position of the span.
            grammar_spans: List of (start, end) tuples for dominant grammar spans.

        Returns:
            True if the span is fully contained within any grammar span.
        """
        for gs_start, gs_end in grammar_spans:
            if gs_start <= start and end <= gs_end:
                return True
        return False


@dataclass
class SentenceResult:
    japanese_text: str
    analysis: AnalysisResult
    created_at: datetime = field(default_factory=datetime.now)

    def get_display_analysis(
        self,
        user_level: int,
        enable_vocab: bool = True,
        enable_grammar: bool = True,
    ) -> AnalysisResult:
        """Return filtered and conflict-resolved analysis based on current user config.

        This is the SINGLE SOURCE OF TRUTH for both rendering and hover detection.

        Processing pipeline:
        1. Filter by user_level: show hits where jlpt_level <= user_level
        2. Resolve conflicts: ensure no position has both vocab and grammar highlights

        Conflict resolution rules:
        - Single-fragment grammar vs vocab: vocab wins if length >= grammar or partially overlaps
        - Multi-fragment grammar: suppressed if any fragment overlaps vocab
        - Vocab fully covered by dominant grammar (and shorter): suppressed

        Args:
            user_level: User's current JLPT level (1-5, where 1=N1 hardest).
            enable_vocab: Whether to include vocab hits.
            enable_grammar: Whether to include grammar hits.

        Returns:
            AnalysisResult with non-overlapping vocab_hits and grammar_hits.
        """
        if self.analysis is None:
            return AnalysisResult(tokens=[], vocab_hits=[], grammar_hits=[])

        # Step 1: Filter by user level
        filtered = AnalysisResult(
            tokens=self.analysis.tokens,
            vocab_hits=[h for h in self.analysis.vocab_hits if h.jlpt_level <= user_level] if enable_vocab else [],
            grammar_hits=[h for h in self.analysis.grammar_hits if h.jlpt_level <= user_level] if enable_grammar else [],
        )

        # Step 2: Resolve conflicts between vocab and grammar
        return filtered.resolve_conflicts()


@dataclass
class AudioSegment:
    """Audio segment extracted by VAD for ASR processing.

    Attributes:
        samples: Raw float32 audio samples at 16kHz.
        duration_sec: Duration of the segment in seconds.
    """

    samples: np.ndarray
    duration_sec: float
