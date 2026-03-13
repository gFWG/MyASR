"""Tests for FugashiTokenizer."""

from src.analysis.tokenizer import FugashiTokenizer
from src.models import Token


def test_tokenize_known_sentence_returns_tokens() -> None:
    """Tokenizing a known sentence returns Token objects."""
    t = FugashiTokenizer()
    tokens = t.tokenize("昨日友達と映画を見に行きました")
    assert len(tokens) >= 5
    assert all(isinstance(tok, Token) for tok in tokens)


def test_tokenize_known_sentence_contains_expected_lemmas() -> None:
    """Known sentence contains expected lemmas."""
    t = FugashiTokenizer()
    tokens = t.tokenize("昨日友達と映画を見に行きました")
    lemmas = [tok.lemma for tok in tokens]
    assert "映画" in lemmas


def test_tokenize_empty_string_returns_empty() -> None:
    """Empty string returns empty list."""
    t = FugashiTokenizer()
    assert t.tokenize("") == []


def test_tokenize_punctuation_only_returns_empty() -> None:
    """Punctuation-only input returns empty list."""
    t = FugashiTokenizer()
    result = t.tokenize("。！？、")
    assert result == []


def test_tagger_property_returns_fugashi_tagger() -> None:
    """Tagger property returns fugashi.Tagger instance."""
    t = FugashiTokenizer()
    import fugashi

    assert isinstance(t.tagger, fugashi.Tagger)


def test_tokenize_mixed_content() -> None:
    """Sentence with kanji, hiragana, katakana all tokenized."""
    t = FugashiTokenizer()
    tokens = t.tokenize("東京タワーへ行きます")
    assert len(tokens) >= 2
