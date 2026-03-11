"""Tests for JLPT vocabulary lookup."""

import pytest

from src.analysis.jlpt_vocab import JLPTVocabLookup, VocabEntry
from src.db.models import Token

VOCAB_PATH = "data/vocabulary.csv"


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


def test_find_beyond_level_with_positions() -> None:
    """Test that start_pos and end_pos are correctly calculated from text."""
    v = JLPTVocabLookup(VOCAB_PATH)
    text = "彼は概念を持っている"
    tokens = [
        Token("彼", "彼", "名詞"),
        Token("は", "は", "助詞"),
        Token("概念", "概念", "名詞"),
        Token("を", "を", "助詞"),
        Token("持っ", "持つ", "動詞"),
        Token("て", "て", "助詞"),
        Token("いる", "いる", "動詞"),
    ]
    hits = v.find_beyond_level(tokens, user_level=3, text=text)
    # 概念 is N1 (level=1), 1 < 3 → beyond level
    concept_hits = [h for h in hits if h.lemma == "概念"]
    assert len(concept_hits) == 1
    hit = concept_hits[0]
    assert hit.start_pos == 2
    assert hit.end_pos == 4
    assert text[hit.start_pos : hit.end_pos] == hit.surface


def test_find_beyond_level_with_positions_duplicate_tokens() -> None:
    """Test that duplicate tokens get distinct positions."""
    v = JLPTVocabLookup(VOCAB_PATH)
    text = "概念ん概念"
    tokens = [
        Token("概念", "概念", "名詞"),
        Token("ん", "ん", "助詞"),
        Token("概念", "概念", "名詞"),
    ]
    hits = v.find_beyond_level(tokens, user_level=3, text=text)
    # Both 概念 tokens should be found with different positions
    assert len(hits) == 2
    assert hits[0].start_pos == 0
    assert hits[0].end_pos == 2
    assert hits[1].start_pos == 3
    assert hits[1].end_pos == 5
    assert text[hits[0].start_pos : hits[0].end_pos] == "概念"
    assert text[hits[1].start_pos : hits[1].end_pos] == "概念"


def test_find_beyond_level_without_text_returns_zeros() -> None:
    """Test that positions are 0 when text is not provided."""
    v = JLPTVocabLookup(VOCAB_PATH)
    tokens = [Token("概念", "概念", "名詞")]
    hits = v.find_beyond_level(tokens, user_level=3)
    assert len(hits) == 1
    assert hits[0].start_pos == 0
    assert hits[0].end_pos == 0


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
        ("驚く", 4),
        ("概念", 1),
    ],
)
def test_lookup_parametrize(word: str, expected: int) -> None:
    v = JLPTVocabLookup(VOCAB_PATH)
    assert v.lookup(word) == expected


def test_lookup_entry_returns_vocab_entry() -> None:
    v = JLPTVocabLookup(VOCAB_PATH)
    entry = v.lookup_entry("食べる")
    assert entry is not None
    assert isinstance(entry, VocabEntry)
    assert entry.lemma == "食べる"
    assert entry.level == 5
    assert entry.pronunciation == "タベル"
    assert "eat" in entry.definition.lower()
    assert entry.vocab_id > 0


def test_lookup_entry_returns_none_for_unknown() -> None:
    v = JLPTVocabLookup(VOCAB_PATH)
    assert v.lookup_entry("xyznotaword") is None


def test_find_beyond_level_populates_vocab_entry_fields() -> None:
    """VocabHit gets vocab_id, pronunciation, definition from VocabEntry."""
    v = JLPTVocabLookup(VOCAB_PATH)
    tokens = [Token("概念", "概念", "名詞")]
    hits = v.find_beyond_level(tokens, user_level=3)
    assert len(hits) == 1
    hit = hits[0]
    assert hit.vocab_id > 0
    assert hit.pronunciation == "ガイネン"
    assert "concept" in hit.definition.lower() or "notion" in hit.definition.lower()


def test_dash_stripping_in_find_beyond_level() -> None:
    """Fugashi compound lemmas like '食べる-動詞' are stripped before lookup."""
    v = JLPTVocabLookup(VOCAB_PATH)
    # 概念 is N1; simulate fugashi producing a compound lemma
    tokens = [Token("概念", "概念-名詞", "名詞")]
    hits = v.find_beyond_level(tokens, user_level=3)
    assert len(hits) == 1
    assert hits[0].lemma == "概念-名詞"


def test_duplicate_lemma_keeps_easiest_level() -> None:
    """When same lemma appears at multiple levels, easiest (highest int) wins."""
    v = JLPTVocabLookup(VOCAB_PATH)
    # 間 appears as N3 and N4 in CSV; N4(4) > N3(3) so N4 should win
    result = v.lookup("間")
    assert result == 4
