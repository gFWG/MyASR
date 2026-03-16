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
        """Return filtered analysis based on current user config.

        This is the SINGLE SOURCE OF TRUTH for both rendering and hover detection.

        Filter logic:
        - Vocab: show where jlpt_level <= user_level (harder than user)
        - Grammar: show where jlpt_level <= user_level (user level and below)

        Args:
            user_level: User's current JLPT level (1-5, where 1=N1 hardest).
            enable_vocab: Whether to include vocab hits.
            enable_grammar: Whether to include grammar hits.

        Returns:
            AnalysisResult with filtered vocab_hits and grammar_hits.
        """
        if self.analysis is None:
            return AnalysisResult(tokens=[], vocab_hits=[], grammar_hits=[])

        vocab_hits = []
        if enable_vocab:
            vocab_hits = [h for h in self.analysis.vocab_hits if h.jlpt_level <= user_level]

        grammar_hits = []
        if enable_grammar:
            grammar_hits = [h for h in self.analysis.grammar_hits if h.jlpt_level <= user_level]

        return AnalysisResult(
            tokens=self.analysis.tokens,
            vocab_hits=vocab_hits,
            grammar_hits=grammar_hits,
        )


@dataclass
class AudioSegment:
    """Audio segment extracted by VAD for ASR processing.

    Attributes:
        samples: Raw float32 audio samples at 16kHz.
        duration_sec: Duration of the segment in seconds.
    """

    samples: np.ndarray
    duration_sec: float
