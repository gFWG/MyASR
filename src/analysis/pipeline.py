"""Preprocessing pipeline for Japanese text analysis."""

import logging
import time

from src.analysis.complexity import ComplexityScorer
from src.analysis.grammar import GrammarMatcher
from src.analysis.jlpt_vocab import JLPTVocabLookup
from src.analysis.tokenizer import FugashiTokenizer
from src.config import AppConfig
from src.db.models import AnalysisResult

logger = logging.getLogger(__name__)


class PreprocessingPipeline:
    """Orchestrates Japanese text analysis: tokenize → vocab → grammar → complexity.

    Shares a single fugashi.Tagger between FugashiTokenizer and ComplexityScorer
    to avoid loading the Unidic dictionary twice.
    """

    def __init__(self, config: AppConfig) -> None:
        """Initialize all pipeline components.

        Args:
            config: AppConfig with thresholds and JLPT user level.
        """
        self._config = config
        self._tokenizer = FugashiTokenizer()
        self._vocab_lookup = JLPTVocabLookup("data/jlpt_vocab.json")
        self._grammar_matcher = GrammarMatcher("data/grammar_rules.json")
        # Share tagger between tokenizer and scorer to avoid double Unidic load
        self._scorer = ComplexityScorer(config, tagger=self._tokenizer.tagger)

    def process(self, text: str) -> AnalysisResult:
        """Run the full analysis pipeline on a Japanese text.

        Args:
            text: Japanese text to analyse (may be empty).

        Returns:
            AnalysisResult with tokens, vocab_hits, grammar_hits, complexity_score
            and is_complex flag.
        """
        start = time.perf_counter()

        tokens = self._tokenizer.tokenize(text)
        vocab_hits = self._vocab_lookup.find_beyond_level(tokens, self._config.user_jlpt_level)
        grammar_hits = self._grammar_matcher.match(text, self._config.user_jlpt_level)
        complexity_score, is_complex = self._scorer.score(vocab_hits, grammar_hits, text)

        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.debug("Pipeline processed %d chars in %.1f ms", len(text), elapsed_ms)

        return AnalysisResult(
            tokens=tokens,
            vocab_hits=vocab_hits,
            grammar_hits=grammar_hits,
            complexity_score=complexity_score,
            is_complex=is_complex,
        )
