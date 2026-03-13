"""End-to-end integration test: CSV→tokenize→lookup.

Verifies the full vocabulary pipeline from loading the CSV file through
JLPT lookup with pronunciation/definition.
"""

import pytest

from src.analysis.jlpt_vocab import JLPTVocabLookup
from src.db.models import Token

VOCAB_PATH = "data/vocabulary.csv"

# ---------------------------------------------------------------------------
# CSV loading
# ---------------------------------------------------------------------------


def test_csv_loads_expected_entry_count() -> None:
    """CSV contains ~8293 data rows (one header row in file)."""
    lookup = JLPTVocabLookup(VOCAB_PATH)
    # After deduplication by easiest level, count may be slightly lower.
    # The raw CSV has 8293 data rows; we expect at least 8000 unique lemmas.
    entry_count = len(lookup._vocab)  # noqa: SLF001
    assert entry_count >= 8000, f"Expected ≥8000 entries, got {entry_count}"


# ---------------------------------------------------------------------------
# CSV → lookup
# ---------------------------------------------------------------------------


def test_known_word_returns_correct_pronunciation() -> None:
    """概念 (N1) must return pronunciation='ガイネン'."""
    lookup = JLPTVocabLookup(VOCAB_PATH)
    entry = lookup.lookup_entry("概念")
    assert entry is not None
    assert entry.pronunciation == "ガイネン"
    assert entry.vocab_id > 0
    assert entry.definition != ""


def test_known_n5_word_returns_entry() -> None:
    """食べる (N5) must have pronunciation='タベル' and 'eat' in definition."""
    lookup = JLPTVocabLookup(VOCAB_PATH)
    entry = lookup.lookup_entry("食べる")
    assert entry is not None
    assert entry.pronunciation == "タベル"
    assert "eat" in entry.definition.lower()
    assert entry.level == 5
    assert entry.vocab_id > 0


# ---------------------------------------------------------------------------
# CSV → tokenize → lookup
# ---------------------------------------------------------------------------


def test_find_all_vocab_hit_fields() -> None:
    """VocabHit from CSV lookup must have vocab_id, pronunciation, definition."""
    lookup = JLPTVocabLookup(VOCAB_PATH)
    tokens = [Token(surface="概念", lemma="概念", pos="名詞")]
    hits = lookup.find_all_vocab(tokens, text="概念")

    assert len(hits) == 1
    hit = hits[0]
    assert hit.vocab_id > 0
    assert hit.pronunciation == "ガイネン"
    assert "concept" in hit.definition.lower() or "notion" in hit.definition.lower()
    assert hit.jlpt_level == 1
    assert hit.start_pos == 0
    assert hit.end_pos == 2


def test_find_all_vocab_returns_all_levels() -> None:
    """find_all_vocab returns all vocab matches regardless of level."""
    lookup = JLPTVocabLookup(VOCAB_PATH)
    tokens = [Token(surface="食べ", lemma="食べる", pos="動詞")]
    hits = lookup.find_all_vocab(tokens)
    # 食べる is N5, should be found
    assert len(hits) == 1
    assert hits[0].jlpt_level == 5


def test_find_all_vocab_multi_token_positions() -> None:
    """start_pos/end_pos are correct when multiple tokens appear in text."""
    lookup = JLPTVocabLookup(VOCAB_PATH)
    text = "彼は概念を理解した"
    tokens = [
        Token(surface="彼", lemma="彼", pos="名詞"),
        Token(surface="は", lemma="は", pos="助詞"),
        Token(surface="概念", lemma="概念", pos="名詞"),
        Token(surface="を", lemma="を", pos="助詞"),
        Token(surface="理解", lemma="理解", pos="名詞"),
    ]
    hits = lookup.find_all_vocab(tokens, text=text)
    concept_hits = [h for h in hits if h.lemma == "概念"]
    assert len(concept_hits) == 1
    ch = concept_hits[0]
    assert text[ch.start_pos : ch.end_pos] == "概念"


def test_csv_missing_file_raises() -> None:
    """JLPTVocabLookup raises FileNotFoundError for nonexistent path."""
    with pytest.raises(FileNotFoundError):
        JLPTVocabLookup("data/nonexistent_vocab.csv")
