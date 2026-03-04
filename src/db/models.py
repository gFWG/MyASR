"""Data models for MyASR database and pipeline."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class SentenceRecord:
    id: int | None
    japanese_text: str
    chinese_translation: str | None
    explanation: str | None
    complexity_score: float
    is_complex: bool
    source_context: str | None
    created_at: str


@dataclass
class HighlightVocab:
    id: int | None
    sentence_id: int
    surface: str
    lemma: str
    pos: str
    jlpt_level: int | None
    is_beyond_level: bool
    tooltip_shown: bool


@dataclass
class HighlightGrammar:
    id: int | None
    sentence_id: int
    rule_id: str
    pattern: str
    jlpt_level: int | None
    confidence_type: str
    description: str | None
    is_beyond_level: bool
    tooltip_shown: bool


@dataclass
class Token:
    surface: str
    lemma: str
    pos: str


@dataclass
class VocabHit:
    surface: str
    lemma: str
    pos: str
    jlpt_level: int
    user_level: int


@dataclass
class GrammarHit:
    rule_id: str
    matched_text: str
    jlpt_level: int
    confidence_type: str
    description: str


@dataclass
class AnalysisResult:
    tokens: list[Token]
    vocab_hits: list[VocabHit]
    grammar_hits: list[GrammarHit]
    complexity_score: float
    is_complex: bool


@dataclass
class SentenceResult:
    japanese_text: str
    chinese_translation: str | None
    explanation: str | None
    analysis: AnalysisResult
    created_at: datetime = field(default_factory=datetime.now)
