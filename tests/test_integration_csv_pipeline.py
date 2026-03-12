"""End-to-end integration test: CSV→tokenize→lookup→DB→read back.

Verifies the full vocabulary pipeline from loading the CSV file through
JLPT lookup and DB persistence with pronunciation/definition round-trip.
"""

import pytest

from src.analysis.jlpt_vocab import JLPTVocabLookup
from src.db.models import HighlightVocab, SentenceRecord, Token
from src.db.repository import LearningRepository
from src.db.schema import init_db

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


# ---------------------------------------------------------------------------
# DB round-trip: insert HighlightVocab → read back with get_sentence_with_highlights
# ---------------------------------------------------------------------------


def test_db_roundtrip_pronunciation_definition(tmp_path: pytest.TempPathFactory) -> None:
    """Insert sentence+vocab highlight; read back via get_sentence_with_highlights."""
    db_path = str(tmp_path / "test.db")  # type: ignore[operator]
    conn = init_db(db_path)
    repo = LearningRepository(conn=conn)

    sentence = SentenceRecord(
        id=None,
        japanese_text="概念を学ぶ",
        source_context="test",
        created_at="2026-03-11T00:00:00",
    )
    vocab_highlight = HighlightVocab(
        id=None,
        sentence_id=0,  # assigned by repo
        surface="概念",
        lemma="概念",
        pos="名詞",
        jlpt_level=1,
        tooltip_shown=False,
        vocab_id=1652,
        pronunciation="ガイネン",
        definition="general idea, concept, notion",
    )

    sentence_id, vocab_ids, _ = repo.insert_sentence(sentence, [vocab_highlight], [])

    assert sentence_id > 0
    assert len(vocab_ids) == 1

    result = repo.get_sentence_with_highlights(sentence_id)
    assert result is not None

    returned_sentence, returned_vocab, returned_grammar = result
    assert returned_sentence.japanese_text == "概念を学ぶ"
    assert len(returned_vocab) == 1
    assert len(returned_grammar) == 0

    hv = returned_vocab[0]
    assert hv.vocab_id == 1652
    assert hv.pronunciation == "ガイネン"
    assert hv.definition == "general idea, concept, notion"
    assert hv.jlpt_level == 1

    conn.close()


def test_db_roundtrip_multiple_vocab_hits(tmp_path: pytest.TempPathFactory) -> None:
    """Multiple vocab hits in one sentence round-trip correctly."""
    db_path = str(tmp_path / "test_multi.db")  # type: ignore[operator]
    conn = init_db(db_path)
    repo = LearningRepository(conn=conn)

    lookup = JLPTVocabLookup(VOCAB_PATH)
    text = "概念を学ぶ"
    tokens = [
        Token(surface="概念", lemma="概念", pos="名詞"),
        Token(surface="学ぶ", lemma="学ぶ", pos="動詞"),
    ]
    hits = lookup.find_all_vocab(tokens, text=text)
    assert len(hits) >= 1

    sentence = SentenceRecord(
        id=None,
        japanese_text=text,
        source_context="integration_test",
        created_at="2026-03-11T00:00:01",
    )
    vocab_highlights = [
        HighlightVocab(
            id=None,
            sentence_id=0,
            surface=hit.surface,
            lemma=hit.lemma,
            pos=hit.pos,
            jlpt_level=hit.jlpt_level,
            tooltip_shown=False,
            vocab_id=hit.vocab_id,
            pronunciation=hit.pronunciation,
            definition=hit.definition,
        )
        for hit in hits
    ]

    sentence_id, vocab_ids, _ = repo.insert_sentence(sentence, vocab_highlights, [])
    result = repo.get_sentence_with_highlights(sentence_id)
    assert result is not None

    _, returned_vocab, _ = result
    assert len(returned_vocab) == len(hits)

    # Verify each returned vocab has correct fields from CSV
    for rv in returned_vocab:
        assert rv.vocab_id > 0
        assert rv.pronunciation != ""
        assert rv.definition != ""

    conn.close()


# ---------------------------------------------------------------------------
# End-to-end: CSV→lookup→DB→export
# ---------------------------------------------------------------------------


def test_e2e_csv_to_db_export_preserves_pronunciation(
    tmp_path: pytest.TempPathFactory,
) -> None:
    """Export JSON preserves pronunciation/definition through the full pipeline."""
    import json

    db_path = str(tmp_path / "export_test.db")  # type: ignore[operator]
    conn = init_db(db_path)
    repo = LearningRepository(conn=conn)

    lookup = JLPTVocabLookup(VOCAB_PATH)
    entry = lookup.lookup_entry("概念")
    assert entry is not None

    sentence = SentenceRecord(
        id=None,
        japanese_text="概念の理解",
        source_context="export_test",
        created_at="2026-03-11T00:00:02",
    )
    vocab_highlight = HighlightVocab(
        id=None,
        sentence_id=0,
        surface="概念",
        lemma="概念",
        pos="名詞",
        jlpt_level=entry.level,
        tooltip_shown=False,
        vocab_id=entry.vocab_id,
        pronunciation=entry.pronunciation,
        definition=entry.definition,
    )

    repo.insert_sentence(sentence, [vocab_highlight], [])

    exported = repo.export_records(format="json", include_highlights=True)
    records = json.loads(exported)

    assert len(records) == 1
    vocab_highlights = records[0]["vocab_highlights"]
    assert len(vocab_highlights) == 1

    vh = vocab_highlights[0]
    assert vh["pronunciation"] == "ガイネン"
    assert "concept" in vh["definition"].lower() or "notion" in vh["definition"].lower()
    assert vh["vocab_id"] == entry.vocab_id

    conn.close()


def test_csv_missing_file_raises() -> None:
    """JLPTVocabLookup raises FileNotFoundError for nonexistent path."""
    with pytest.raises(FileNotFoundError):
        JLPTVocabLookup("data/nonexistent_vocab.csv")


def test_db_get_sentence_with_highlights_missing_returns_none(
    tmp_path: pytest.TempPathFactory,
) -> None:
    """get_sentence_with_highlights returns None for nonexistent sentence_id."""
    db_path = str(tmp_path / "empty.db")  # type: ignore[operator]
    conn = init_db(db_path)
    repo = LearningRepository(conn=conn)

    result = repo.get_sentence_with_highlights(99999)
    assert result is None

    conn.close()
