"""Preprocessing pipeline for Japanese text analysis."""

import logging
import time

from src.analysis.grammar import GrammarMatcher
from src.analysis.jlpt_vocab import JLPTVocabLookup
from src.analysis.tokenizer import FugashiTokenizer
from src.config import AppConfig
from src.db.models import AnalysisResult

logger = logging.getLogger(__name__)


class PreprocessingPipeline:
    """Orchestrates Japanese text analysis: tokenize → vocab → grammar.

    Shares a single fugashi.Tagger via FugashiTokenizer.
    """

    def __init__(self, config: AppConfig) -> None:
        """Initialize all pipeline components.

        Args:
            config: AppConfig with JLPT user level.
        """
        self._config = config
        self._tokenizer = FugashiTokenizer()
        self._vocab_lookup = JLPTVocabLookup("data/vocabulary.csv")
        self._grammar_matcher = GrammarMatcher("data/grammar_rules.json")

    def process(self, text: str) -> AnalysisResult:
        """Run the full analysis pipeline on a Japanese text.

        Args:
            text: Japanese text to analyse (may be empty).

        Returns:
            AnalysisResult with tokens, vocab_hits, and grammar_hits.
        """
        start = time.perf_counter()

        tokens = self._tokenizer.tokenize(text)
        vocab_hits = self._vocab_lookup.find_beyond_level(
            tokens, self._config.user_jlpt_level, text=text
        )
        grammar_hits = self._grammar_matcher.match(text, self._config.user_jlpt_level)

        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.debug("Pipeline processed %d chars in %.1f ms", len(text), elapsed_ms)

        return AnalysisResult(
            tokens=tokens,
            vocab_hits=vocab_hits,
            grammar_hits=grammar_hits,
        )
