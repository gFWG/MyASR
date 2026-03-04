"""Complexity scoring for Japanese text analysis."""

import logging
from typing import Optional, Protocol

import jreadability

from src.config import AppConfig
from src.db.models import GrammarHit, VocabHit

logger = logging.getLogger(__name__)


class TaggerProtocol(Protocol):
    def __call__(self, text: str) -> object: ...


class ComplexityScorer:
    """Score complexity of Japanese text using multiple signals."""

    def __init__(
        self,
        config: AppConfig,
        tagger: Optional[TaggerProtocol] = None,
    ) -> None:
        """Initialize scorer with configuration and optional shared tagger.

        Args:
            config: AppConfig with complexity thresholds.
            tagger: Optional shared fugashi.Tagger to avoid double dictionary load.
                If None, jreadability will create its own.
        """
        self._config = config
        self._tagger = tagger

    def score(
        self,
        vocab_hits: list[VocabHit],
        grammar_hits: list[GrammarHit],
        text: str,
    ) -> tuple[float, bool]:
        """Compute complexity score and classification.

        IMPORTANT: jreadability uses INVERTED semantics.
        Higher readability score = EASIER text.
        "これは猫です" → ~6.20 (easy), complex academic text → ~1.11 (hard).
        Threshold: score < 3.0 = complex (LOWER score = HARDER text).

        Args:
            vocab_hits: Beyond-level vocabulary hits (already filtered).
            grammar_hits: Grammar hits (all levels, may include high-level matches).
            text: Raw Japanese text for jreadability analysis.

        Returns:
            Tuple of (complexity_score: float, is_complex: bool).
        """
        vocab_count = len(vocab_hits)

        n1_grammar_count = sum(1 for g in grammar_hits if g.jlpt_level == 1)

        ambiguous_count = sum(1 for g in grammar_hits if g.confidence_type == "ambiguous")

        readability_score: float
        if text.strip():
            readability_score = jreadability.compute_readability(text, tagger=self._tagger)
        else:
            readability_score = 10.0

        is_complex = False
        if vocab_count >= self._config.complexity_vocab_threshold:
            is_complex = True
        if n1_grammar_count >= self._config.complexity_n1_grammar_threshold:
            is_complex = True
        if readability_score < self._config.complexity_readability_threshold:
            is_complex = True
        if ambiguous_count >= self._config.complexity_ambiguous_grammar_threshold:
            is_complex = True

        readability_component = max(0.0, 10.0 - readability_score)
        vocab_component = min(10.0, vocab_count * 2.0)
        grammar_component = min(10.0, n1_grammar_count * 3.0)
        ambiguous_component = min(10.0, ambiguous_count * 2.0)
        complexity_score = (
            vocab_component * 0.35
            + grammar_component * 0.35
            + readability_component * 0.2
            + ambiguous_component * 0.1
        )

        logger.debug(
            "Complexity: vocab=%d, n1_grammar=%d, ambiguous=%d, readability=%.2f → "
            "score=%.2f, is_complex=%s",
            vocab_count,
            n1_grammar_count,
            ambiguous_count,
            readability_score,
            complexity_score,
            is_complex,
        )
        return (complexity_score, is_complex)
