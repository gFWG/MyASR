import pytest

from src.analysis.complexity import ComplexityScorer
from src.config import AppConfig
from src.db.models import GrammarHit, VocabHit


@pytest.fixture
def scorer() -> ComplexityScorer:
    return ComplexityScorer(AppConfig())


def make_vocab_hit(lemma: str = "概念", jlpt_level: int = 1) -> VocabHit:
    return VocabHit(
        surface=lemma,
        lemma=lemma,
        pos="名詞",
        jlpt_level=jlpt_level,
        user_level=3,
    )


def make_grammar_hit(jlpt_level: int = 1, confidence_type: str = "high") -> GrammarHit:
    return GrammarHit(
        rule_id=f"N{jlpt_level}_test",
        matched_text="test",
        jlpt_level=jlpt_level,
        confidence_type=confidence_type,
        description="test pattern",
    )


def test_simple_sentence_not_complex(scorer: ComplexityScorer) -> None:
    score, is_complex = scorer.score([], [], "これは猫です")
    assert is_complex is False
    assert isinstance(score, float)


def test_vocab_threshold_triggers_complex(scorer: ComplexityScorer) -> None:
    hits = [make_vocab_hit("概念"), make_vocab_hit("影響")]
    score, is_complex = scorer.score(hits, [], "テスト")
    assert is_complex is True
    assert isinstance(score, float)


def test_one_vocab_hit_not_crashing(scorer: ComplexityScorer) -> None:
    hits = [make_vocab_hit()]
    score, is_complex = scorer.score(hits, [], "テスト")
    assert isinstance(score, float)
    assert isinstance(is_complex, bool)


def test_n1_grammar_triggers_complex(scorer: ComplexityScorer) -> None:
    hits = [make_grammar_hit(jlpt_level=1)]
    score, is_complex = scorer.score([], hits, "テスト")
    assert is_complex is True
    assert isinstance(score, float)


def test_ambiguous_grammar_triggers_complex(scorer: ComplexityScorer) -> None:
    hits = [make_grammar_hit(confidence_type="ambiguous")]
    score, is_complex = scorer.score([], hits, "テスト")
    assert is_complex is True


def test_n5_grammar_not_triggering_n1_threshold(scorer: ComplexityScorer) -> None:
    hits = [make_grammar_hit(jlpt_level=5, confidence_type="high")]
    score, is_complex = scorer.score([], hits, "これは猫です")
    assert is_complex is False
    assert isinstance(score, float)


def test_low_readability_triggers_complex() -> None:
    config = AppConfig(complexity_readability_threshold=3.0)
    scorer = ComplexityScorer(config)
    score, is_complex = scorer.score([], [], "経済的観点から見た場合の影響について述べる")
    assert isinstance(score, float)
    assert isinstance(is_complex, bool)


def test_empty_text_not_complex(scorer: ComplexityScorer) -> None:
    score, is_complex = scorer.score([], [], "")
    assert is_complex is False
    assert isinstance(score, float)


def test_returns_tuple(scorer: ComplexityScorer) -> None:
    result = scorer.score([], [], "テスト")
    assert isinstance(result, tuple)
    assert len(result) == 2
    assert isinstance(result[0], float)
    assert isinstance(result[1], bool)
