import csv
import io
import json
import sqlite3

import pytest

from src.db.models import HighlightGrammar, HighlightVocab, SentenceRecord
from src.db.repository import LearningRepository
from src.db.schema import init_db
from src.pipeline.types import ASRResult


@pytest.fixture
def repo() -> LearningRepository:
    conn = init_db(":memory:")
    return LearningRepository(conn=conn)


def make_record(
    id: int | None = None,
    japanese_text: str = "猫が好きです",
    source_context: str | None = None,
    created_at: str = "2024-01-15T10:00:00",
) -> SentenceRecord:
    return SentenceRecord(
        id=id,
        japanese_text=japanese_text,
        source_context=source_context,
        created_at=created_at,
    )


def make_vocab(
    id: int | None = None,
    sentence_id: int = 0,
    surface: str = "猫",
    lemma: str = "猫",
    pos: str = "名詞",
    jlpt_level: int | None = 5,
    is_beyond_level: bool = False,
    tooltip_shown: bool = False,
) -> HighlightVocab:
    return HighlightVocab(
        id=id,
        sentence_id=sentence_id,
        surface=surface,
        lemma=lemma,
        pos=pos,
        jlpt_level=jlpt_level,
        is_beyond_level=is_beyond_level,
        tooltip_shown=tooltip_shown,
    )


def make_grammar(
    id: int | None = None,
    sentence_id: int = 0,
    rule_id: str = "N4_past",
    pattern: str = "た",
    jlpt_level: int | None = 4,
    confidence_type: str = "high",
    description: str | None = "Past tense",
    is_beyond_level: bool = False,
    tooltip_shown: bool = False,
) -> HighlightGrammar:
    return HighlightGrammar(
        id=id,
        sentence_id=sentence_id,
        rule_id=rule_id,
        pattern=pattern,
        jlpt_level=jlpt_level,
        confidence_type=confidence_type,
        description=description,
        is_beyond_level=is_beyond_level,
        tooltip_shown=tooltip_shown,
    )


def test_insert_returns_positive_id(repo: LearningRepository) -> None:
    sentence_id, vocab_ids, grammar_ids = repo.insert_sentence(make_record(), [], [])
    assert isinstance(sentence_id, int)
    assert sentence_id >= 1
    assert vocab_ids == []
    assert grammar_ids == []


def test_insert_and_retrieve_roundtrip(repo: LearningRepository) -> None:
    rec = make_record(
        japanese_text="昨日映画を見た",
        source_context="movie",
    )
    sentence_id, _vocab_ids, _grammar_ids = repo.insert_sentence(rec, [], [])
    rows = repo.get_sentences(limit=10)
    assert len(rows) == 1
    r = rows[0]
    assert r.id == sentence_id
    assert r.japanese_text == "昨日映画を見た"
    assert r.source_context == "movie"
    assert r.created_at == "2024-01-15T10:00:00"


def test_insert_with_empty_vocab_grammar(repo: LearningRepository) -> None:
    sentence_id, vocab_ids, grammar_ids = repo.insert_sentence(make_record(), [], [])
    assert sentence_id >= 1
    assert vocab_ids == []
    assert grammar_ids == []
    rows = repo.get_sentences()
    assert len(rows) == 1


def test_insert_with_vocab_and_grammar(repo: LearningRepository) -> None:
    vocab = [make_vocab(surface="映画", lemma="映画", jlpt_level=4)]
    grammar = [make_grammar(rule_id="N4_past", pattern="た")]
    sentence_id, vocab_ids, grammar_ids = repo.insert_sentence(make_record(), vocab, grammar)
    assert sentence_id >= 1
    assert len(vocab_ids) == 1
    assert all(vid > 0 for vid in vocab_ids)
    assert len(grammar_ids) == 1
    assert all(gid > 0 for gid in grammar_ids)
    rows = repo.get_sentences()
    assert len(rows) == 1


def test_insert_returns_correct_id_counts_for_multiple_highlights(
    repo: LearningRepository,
) -> None:
    vocab = [
        make_vocab(surface="映画", lemma="映画", jlpt_level=4),
        make_vocab(surface="猫", lemma="猫", jlpt_level=5),
    ]
    grammar = [
        make_grammar(rule_id="N4_past", pattern="た"),
        make_grammar(rule_id="N3_te", pattern="て"),
        make_grammar(rule_id="N5_masu", pattern="ます"),
    ]
    sentence_id, vocab_ids, grammar_ids = repo.insert_sentence(make_record(), vocab, grammar)
    assert sentence_id >= 1
    assert len(vocab_ids) == 2
    assert all(vid > 0 for vid in vocab_ids)
    assert len(set(vocab_ids)) == 2
    assert len(grammar_ids) == 3
    assert all(gid > 0 for gid in grammar_ids)
    assert len(set(grammar_ids)) == 3


def test_get_sentences_ordering(repo: LearningRepository) -> None:
    repo.insert_sentence(
        make_record(japanese_text="first", created_at="2024-01-01T00:00:00"), [], []
    )
    repo.insert_sentence(
        make_record(japanese_text="second", created_at="2024-06-01T00:00:00"), [], []
    )
    repo.insert_sentence(
        make_record(japanese_text="third", created_at="2024-03-01T00:00:00"), [], []
    )
    rows = repo.get_sentences()
    assert rows[0].japanese_text == "second"
    assert rows[1].japanese_text == "third"
    assert rows[2].japanese_text == "first"


def test_get_sentences_limit_offset(repo: LearningRepository) -> None:
    for i in range(5):
        repo.insert_sentence(
            make_record(japanese_text=f"text{i}", created_at=f"2024-01-0{i + 1}T00:00:00"),
            [],
            [],
        )
    page1 = repo.get_sentences(limit=2, offset=0)
    page2 = repo.get_sentences(limit=2, offset=2)
    assert len(page1) == 2
    assert len(page2) == 2
    assert page1[0].japanese_text != page2[0].japanese_text


def test_search_finds_matching_records(repo: LearningRepository) -> None:
    r1 = make_record(japanese_text="猫が好きです")
    r2 = make_record(japanese_text="犬が好きです")
    repo.insert_sentence(r1, [], [])
    repo.insert_sentence(r2, [], [])
    results = repo.search_sentences("猫")
    assert len(results) == 1
    assert results[0].japanese_text == "猫が好きです"


def test_search_returns_empty_for_no_match(repo: LearningRepository) -> None:
    repo.insert_sentence(make_record(japanese_text="猫が好きです"), [], [])
    results = repo.search_sentences("鳥")
    assert results == []


def test_search_matches_japanese_text(repo: LearningRepository) -> None:
    repo.insert_sentence(make_record(japanese_text="猫が好きです"), [], [])
    results = repo.search_sentences("猫")
    assert len(results) == 1


def test_mark_tooltip_shown_vocab(repo: LearningRepository) -> None:
    vocab = [make_vocab()]
    sentence_id, _vocab_ids, _grammar_ids = repo.insert_sentence(make_record(), vocab, [])

    conn: sqlite3.Connection = repo._conn
    cursor = conn.execute("SELECT id FROM highlight_vocab WHERE sentence_id=?", (sentence_id,))
    vocab_id = cursor.fetchone()[0]

    cursor2 = conn.execute("SELECT tooltip_shown FROM highlight_vocab WHERE id=?", (vocab_id,))
    assert cursor2.fetchone()[0] == 0

    repo.mark_tooltip_shown("vocab", vocab_id)

    cursor3 = conn.execute("SELECT tooltip_shown FROM highlight_vocab WHERE id=?", (vocab_id,))
    assert cursor3.fetchone()[0] == 1


def test_mark_tooltip_shown_grammar(repo: LearningRepository) -> None:
    grammar = [make_grammar()]
    sentence_id, _vocab_ids, _grammar_ids = repo.insert_sentence(make_record(), [], grammar)

    conn: sqlite3.Connection = repo._conn
    cursor = conn.execute("SELECT id FROM highlight_grammar WHERE sentence_id=?", (sentence_id,))
    grammar_id = cursor.fetchone()[0]

    repo.mark_tooltip_shown("grammar", grammar_id)

    cursor2 = conn.execute("SELECT tooltip_shown FROM highlight_grammar WHERE id=?", (grammar_id,))
    assert cursor2.fetchone()[0] == 1


def test_mark_tooltip_shown_invalid_type_raises(repo: LearningRepository) -> None:
    with pytest.raises(ValueError, match="Invalid highlight_type"):
        repo.mark_tooltip_shown("unknown", 1)


def test_export_records_json(repo: LearningRepository) -> None:
    repo.insert_sentence(make_record(japanese_text="テスト"), [], [])
    repo.insert_sentence(make_record(japanese_text="第二文"), [], [])
    result = repo.export_records("json")
    data = json.loads(result)
    assert isinstance(data, list)
    assert len(data) == 2
    texts = [d["japanese_text"] for d in data]
    assert "テスト" in texts
    assert "第二文" in texts


def test_export_records_csv(repo: LearningRepository) -> None:
    repo.insert_sentence(make_record(japanese_text="テスト"), [], [])
    result = repo.export_records("csv")
    reader = csv.reader(io.StringIO(result))
    rows = list(reader)
    assert rows[0][1] == "japanese_text"
    assert any(row[1] == "テスト" for row in rows[1:])


def test_export_records_json_empty(repo: LearningRepository) -> None:
    result = repo.export_records("json")
    data = json.loads(result)
    assert data == []


def test_export_records_invalid_format_raises(repo: LearningRepository) -> None:
    with pytest.raises(ValueError, match="Unsupported export format"):
        repo.export_records("xml")


def test_delete_before_removes_old_records(repo: LearningRepository) -> None:
    old = make_record(japanese_text="old", created_at="2023-01-01T00:00:00")
    new = make_record(japanese_text="new", created_at="2024-06-01T00:00:00")
    repo.insert_sentence(old, [], [])
    repo.insert_sentence(new, [], [])
    count = repo.delete_before("2024-01-01")
    assert count == 1
    remaining = repo.get_sentences()
    assert len(remaining) == 1
    assert remaining[0].japanese_text == "new"


def test_delete_before_returns_zero_when_nothing_deleted(repo: LearningRepository) -> None:
    repo.insert_sentence(make_record(created_at="2025-01-01T00:00:00"), [], [])
    count = repo.delete_before("2020-01-01")
    assert count == 0
    assert len(repo.get_sentences()) == 1


def test_delete_before_cascades_to_highlights(repo: LearningRepository) -> None:
    vocab = [make_vocab()]
    grammar = [make_grammar()]
    repo.insert_sentence(
        make_record(japanese_text="old", created_at="2023-01-01T00:00:00"),
        vocab,
        grammar,
    )
    count = repo.delete_before("2024-01-01")
    assert count == 1
    conn: sqlite3.Connection = repo._conn
    v_count = conn.execute("SELECT COUNT(*) FROM highlight_vocab").fetchone()[0]
    g_count = conn.execute("SELECT COUNT(*) FROM highlight_grammar").fetchone()[0]
    assert v_count == 0
    assert g_count == 0


def test_export_records_backward_compat(repo: LearningRepository) -> None:
    repo.insert_sentence(make_record(japanese_text="後方互換"), [], [])
    result = repo.export_records()
    assert isinstance(result, str)
    data = json.loads(result)
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["japanese_text"] == "後方互換"


def test_export_records_json_with_highlights(repo: LearningRepository) -> None:
    vocab = [make_vocab(surface="猫", lemma="猫", jlpt_level=5)]
    grammar = [make_grammar(pattern="た")]
    repo.insert_sentence(make_record(japanese_text="猫が来た"), vocab, grammar)
    result = repo.export_records("json")
    data = json.loads(result)
    assert len(data) == 1
    record = data[0]
    assert "vocab_highlights" in record
    assert "grammar_highlights" in record
    assert isinstance(record["vocab_highlights"], list)
    assert len(record["vocab_highlights"]) == 1
    assert record["vocab_highlights"][0]["lemma"] == "猫"


def test_export_records_csv_with_highlights(repo: LearningRepository) -> None:
    vocab = [make_vocab(surface="映画", lemma="映画", jlpt_level=4)]
    repo.insert_sentence(make_record(japanese_text="映画を見た"), vocab, [])
    result = repo.export_records("csv")
    reader = csv.reader(io.StringIO(result))
    rows = list(reader)
    header = rows[0]
    assert "vocab_count" in header
    assert "grammar_count" in header
    assert "vocab_lemmas" in header
    assert "grammar_rules" in header


def test_export_records_date_filtering(repo: LearningRepository) -> None:
    repo.insert_sentence(
        make_record(japanese_text="january", created_at="2024-01-15T00:00:00"), [], []
    )
    repo.insert_sentence(
        make_record(japanese_text="march", created_at="2024-03-20T00:00:00"), [], []
    )
    repo.insert_sentence(
        make_record(japanese_text="december", created_at="2024-12-01T00:00:00"), [], []
    )
    result = repo.export_records("json", date_from="2024-02-01", date_to="2024-11-30")
    data = json.loads(result)
    assert len(data) == 1
    assert data[0]["japanese_text"] == "march"


def test_export_records_without_highlights(repo: LearningRepository) -> None:
    vocab = [make_vocab(surface="猫", lemma="猫", jlpt_level=5)]
    repo.insert_sentence(make_record(japanese_text="猫がいる"), vocab, [])
    result = repo.export_records("json", include_highlights=False)
    data = json.loads(result)
    assert len(data) == 1
    record = data[0]
    assert "vocab_highlights" not in record
    assert "grammar_highlights" not in record


def test_get_sentences_filtered_pagination(repo: LearningRepository) -> None:
    for i in range(5):
        repo.insert_sentence(
            make_record(japanese_text=f"page_text{i}", created_at=f"2024-01-0{i + 1}T00:00:00"),
            [],
            [],
        )
    page1 = repo.get_sentences_filtered(limit=2, offset=0)
    page2 = repo.get_sentences_filtered(limit=2, offset=2)
    assert len(page1) == 2
    assert len(page2) == 2
    assert {r.japanese_text for r in page1}.isdisjoint({r.japanese_text for r in page2})


def test_get_sentences_filtered_query_filter(repo: LearningRepository) -> None:
    repo.insert_sentence(make_record(japanese_text="特別な文章abc"), [], [])
    repo.insert_sentence(make_record(japanese_text="普通の文章"), [], [])
    results = repo.get_sentences_filtered(query="特別な文章abc")
    assert len(results) == 1
    assert results[0].japanese_text == "特別な文章abc"


def test_get_sentences_filtered_date_range(repo: LearningRepository) -> None:
    repo.insert_sentence(
        make_record(japanese_text="date_early", created_at="2023-01-01T00:00:00"),
        [],
        [],
    )
    repo.insert_sentence(
        make_record(japanese_text="date_mid", created_at="2024-06-01T00:00:00"),
        [],
        [],
    )
    repo.insert_sentence(
        make_record(japanese_text="date_late", created_at="2025-01-01T00:00:00"),
        [],
        [],
    )
    results = repo.get_sentences_filtered(date_from="2024-01-01", date_to="2024-12-31")
    texts = [r.japanese_text for r in results]
    assert "date_mid" in texts
    assert "date_early" not in texts
    assert "date_late" not in texts


def test_get_sentences_filtered_invalid_sort_raises(repo: LearningRepository) -> None:
    with pytest.raises(ValueError, match="Invalid sort_by"):
        repo.get_sentences_filtered(sort_by="id")


def test_get_sentence_count_matches_filtered(repo: LearningRepository) -> None:
    repo.insert_sentence(make_record(japanese_text="カウントテストaaa"), [], [])
    repo.insert_sentence(make_record(japanese_text="カウントテストbbb"), [], [])
    repo.insert_sentence(make_record(japanese_text="別の文"), [], [])
    count = repo.get_sentence_count(query="カウントテスト")
    filtered = repo.get_sentences_filtered(query="カウントテスト")
    assert count == len(filtered)
    assert count == 2


def test_get_sentence_with_highlights_found(repo: LearningRepository) -> None:
    vocab = [make_vocab(surface="映画", lemma="映画", jlpt_level=4)]
    grammar = [make_grammar(rule_id="N4_past", pattern="た")]
    sentence_id, _v, _g = repo.insert_sentence(make_record(), vocab, grammar)
    result = repo.get_sentence_with_highlights(sentence_id)
    assert result is not None
    record, vocab_list, grammar_list = result
    assert isinstance(record, SentenceRecord)
    assert len(vocab_list) == 1
    assert len(grammar_list) == 1


def test_get_sentence_with_highlights_not_found(repo: LearningRepository) -> None:
    result = repo.get_sentence_with_highlights(999999)
    assert result is None


def test_constructor_requires_db_path_or_conn() -> None:
    with pytest.raises(ValueError, match="Supply one of"):
        LearningRepository()


def test_constructor_rejects_both_db_path_and_conn() -> None:
    conn = init_db(":memory:")
    with pytest.raises(ValueError, match="Supply db_path or conn, not both"):
        LearningRepository(db_path=":memory:", conn=conn)


def test_constructor_with_db_path(tmp_path: object) -> None:
    from pathlib import Path

    db_path = str(Path(str(tmp_path)) / "test.db")
    init_db(db_path)
    repo = LearningRepository(db_path=db_path)
    sentence_id, _, _ = repo.insert_sentence(make_record(), [], [])
    assert sentence_id >= 1
    repo.close()


def test_close_only_closes_owned_connection() -> None:
    conn = init_db(":memory:")
    repo = LearningRepository(conn=conn)
    repo.close()
    conn.execute("SELECT 1")


def test_close_closes_owned_connection(tmp_path: object) -> None:
    from pathlib import Path

    db_path = str(Path(str(tmp_path)) / "test.db")
    init_db(db_path)
    repo = LearningRepository(db_path=db_path)
    repo.close()
    with pytest.raises(Exception):
        repo._conn.execute("SELECT 1")


def test_separate_repos_same_db_file(tmp_path: object) -> None:
    from pathlib import Path

    db_path = str(Path(str(tmp_path)) / "test.db")
    init_db(db_path)
    repo1 = LearningRepository(db_path=db_path)
    repo2 = LearningRepository(db_path=db_path)
    sentence_id, _, _ = repo1.insert_sentence(make_record(), [], [])
    assert sentence_id >= 1
    assert repo2.get_sentence_count() == 1
    repo1.close()
    repo2.close()


# Two-phase write tests



