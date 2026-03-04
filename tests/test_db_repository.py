import csv
import io
import json
import sqlite3

import pytest

from src.db.models import HighlightGrammar, HighlightVocab, SentenceRecord
from src.db.repository import LearningRepository
from src.db.schema import init_db


@pytest.fixture
def repo() -> LearningRepository:
    conn = init_db(":memory:")
    return LearningRepository(conn)


def make_record(
    id: int | None = None,
    japanese_text: str = "猫が好きです",
    chinese_translation: str | None = "我喜欢猫",
    explanation: str | None = None,
    complexity_score: float = 1.0,
    is_complex: bool = False,
    source_context: str | None = None,
    created_at: str = "2024-01-15T10:00:00",
) -> SentenceRecord:
    return SentenceRecord(
        id=id,
        japanese_text=japanese_text,
        chinese_translation=chinese_translation,
        explanation=explanation,
        complexity_score=complexity_score,
        is_complex=is_complex,
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
    rid = repo.insert_sentence(make_record(), [], [])
    assert isinstance(rid, int)
    assert rid >= 1


def test_insert_and_retrieve_roundtrip(repo: LearningRepository) -> None:
    rec = make_record(
        japanese_text="昨日映画を見た",
        chinese_translation="昨天看了电影",
        complexity_score=2.5,
        is_complex=True,
        source_context="movie",
    )
    rid = repo.insert_sentence(rec, [], [])
    rows = repo.get_sentences(limit=10)
    assert len(rows) == 1
    r = rows[0]
    assert r.id == rid
    assert r.japanese_text == "昨日映画を見た"
    assert r.chinese_translation == "昨天看了电影"
    assert r.complexity_score == 2.5
    assert r.is_complex is True
    assert r.source_context == "movie"
    assert r.created_at == "2024-01-15T10:00:00"


def test_insert_with_empty_vocab_grammar(repo: LearningRepository) -> None:
    rid = repo.insert_sentence(make_record(), [], [])
    assert rid >= 1
    rows = repo.get_sentences()
    assert len(rows) == 1


def test_insert_with_vocab_and_grammar(repo: LearningRepository) -> None:
    vocab = [make_vocab(surface="映画", lemma="映画", jlpt_level=4)]
    grammar = [make_grammar(rule_id="N4_past", pattern="た")]
    rid = repo.insert_sentence(make_record(), vocab, grammar)
    assert rid >= 1
    rows = repo.get_sentences()
    assert len(rows) == 1


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
    r1 = make_record(japanese_text="猫が好きです", chinese_translation="我喜欢猫")
    r2 = make_record(japanese_text="犬が好きです", chinese_translation="我喜欢狗")
    repo.insert_sentence(r1, [], [])
    repo.insert_sentence(r2, [], [])
    results = repo.search_sentences("猫")
    assert len(results) == 1
    assert results[0].japanese_text == "猫が好きです"


def test_search_returns_empty_for_no_match(repo: LearningRepository) -> None:
    repo.insert_sentence(make_record(japanese_text="猫が好きです"), [], [])
    results = repo.search_sentences("鳥")
    assert results == []


def test_search_matches_chinese_translation(repo: LearningRepository) -> None:
    repo.insert_sentence(make_record(chinese_translation="我喜欢猫"), [], [])
    results = repo.search_sentences("喜欢")
    assert len(results) == 1


def test_mark_tooltip_shown_vocab(repo: LearningRepository) -> None:
    vocab = [make_vocab()]
    rid = repo.insert_sentence(make_record(), vocab, [])

    conn: sqlite3.Connection = repo._conn
    cursor = conn.execute("SELECT id FROM highlight_vocab WHERE sentence_id=?", (rid,))
    vocab_id = cursor.fetchone()[0]

    cursor2 = conn.execute("SELECT tooltip_shown FROM highlight_vocab WHERE id=?", (vocab_id,))
    assert cursor2.fetchone()[0] == 0

    repo.mark_tooltip_shown("vocab", vocab_id)

    cursor3 = conn.execute("SELECT tooltip_shown FROM highlight_vocab WHERE id=?", (vocab_id,))
    assert cursor3.fetchone()[0] == 1


def test_mark_tooltip_shown_grammar(repo: LearningRepository) -> None:
    grammar = [make_grammar()]
    rid = repo.insert_sentence(make_record(), [], grammar)

    conn: sqlite3.Connection = repo._conn
    cursor = conn.execute("SELECT id FROM highlight_grammar WHERE sentence_id=?", (rid,))
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
