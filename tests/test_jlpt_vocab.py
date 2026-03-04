"""Tests for JLPT vocabulary lookup."""

import pytest

from src.analysis.jlpt_vocab import JLPTVocabLookup
from src.db.models import Token

VOCAB_PATH = "data/jlpt_vocab.json"


def test_lookup_returns_correct_level_n5() -> None:
    v = JLPTVocabLookup(VOCAB_PATH)
    assert v.lookup("食べる") == 5


def test_lookup_returns_correct_level_n1() -> None:
    v = JLPTVocabLookup(VOCAB_PATH)
    assert v.lookup("概念") == 1


def test_lookup_returns_none_for_unknown() -> None:
    v = JLPTVocabLookup(VOCAB_PATH)
    assert v.lookup("xyznotaword") is None


def test_find_beyond_level_flags_hard_words() -> None:
    """N1 word (jlpt_level=1) beyond user_level=3."""
    v = JLPTVocabLookup(VOCAB_PATH)
    tokens = [Token("食べ", "食べる", "動詞"), Token("概念", "概念", "名詞")]
    hits = v.find_beyond_level(tokens, user_level=3)
    # 概念 is N1 (level=1), 1 < 3 → beyond level
    assert any(h.lemma == "概念" for h in hits)
    # 食べる is N5 (level=5), 5 > 3 → NOT beyond level
    assert not any(h.lemma == "食べる" for h in hits)


def test_find_beyond_level_user_level_1_no_hits() -> None:
    """N1 user sees nothing as beyond level."""
    v = JLPTVocabLookup(VOCAB_PATH)
    tokens = [Token("概念", "概念", "名詞")]  # N1 word
    hits = v.find_beyond_level(tokens, user_level=1)
    assert hits == []  # 1 < 1 is False


def test_find_beyond_level_empty_tokens() -> None:
    v = JLPTVocabLookup(VOCAB_PATH)
    assert v.find_beyond_level([], user_level=3) == []


@pytest.mark.parametrize(
    "word,expected",
    [
        ("食べる", 5),
        ("映画", 4),
        ("概念", 1),
    ],
)
def test_lookup_parametrize(word: str, expected: int) -> None:
    v = JLPTVocabLookup(VOCAB_PATH)
    assert v.lookup(word) == expected
