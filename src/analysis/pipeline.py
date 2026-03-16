"""Preprocessing pipeline for Japanese text analysis."""

import logging
import time

from src.analysis.grammar import GrammarMatcher
from src.analysis.jlpt_vocab import JLPTVocabLookup
from src.analysis.tokenizer import FugashiTokenizer, merge_prefix_compounds
from src.models import AnalysisResult

logger = logging.getLogger(__name__)


class PreprocessingPipeline:
    """Orchestrates Japanese text analysis: tokenize → vocab → grammar.

    Shares a single fugashi.Tagger via FugashiTokenizer.
    """

    def __init__(self) -> None:
        """Initialize all pipeline components.

        Note: No config needed - analysis returns ALL matches, filtering happens at display time.
        """
        self._tokenizer = FugashiTokenizer()
        self._vocab_lookup = JLPTVocabLookup("data/vocabulary.csv")
        self._grammar_matcher = GrammarMatcher("data/grammar.json")

    def process(self, text: str) -> AnalysisResult:
        """Run the full analysis pipeline on a Japanese text.

        Returns ALL vocab and grammar matches without filtering.
        Display-time filtering is handled by SentenceResult.get_display_analysis().

        Args:
            text: Japanese text to analyse (may be empty).

        Returns:
            AnalysisResult with tokens, vocab_hits, and grammar_hits.
        """
        start = time.perf_counter()

        tokens = self._tokenizer.tokenize(text)
        tokens = merge_prefix_compounds(tokens, self._vocab_lookup.vocab_entries)
        vocab_hits = self._vocab_lookup.find_all_vocab(tokens, text=text)
        grammar_hits = self._grammar_matcher.match_all(text)

        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.debug("Pipeline processed %d chars in %.1f ms", len(text), elapsed_ms)

        return AnalysisResult(
            tokens=tokens,
            vocab_hits=vocab_hits,
            grammar_hits=grammar_hits,
        )
