"""Tests for src.db.schema module."""

import sqlite3
from pathlib import Path

from src.db.schema import init_db


def test_init_db_creates_all_tables(tmp_path: Path) -> None:
    db_path = str(tmp_path / "test.db")
    conn = init_db(db_path)
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = {r[0] for r in cur.fetchall()}
    conn.close()
    assert "sentence_records" in tables
    assert "highlight_vocab" in tables
    assert "highlight_grammar" in tables
    assert "app_settings" in tables


def test_init_db_wal_mode_enabled(tmp_path: Path) -> None:
    db_path = str(tmp_path / "test.db")
    conn = init_db(db_path)
    wal = conn.execute("PRAGMA journal_mode").fetchone()[0]
    conn.close()
    assert wal == "wal", f"Expected WAL, got {wal}"


def test_init_db_foreign_keys_enabled(tmp_path: Path) -> None:
    db_path = str(tmp_path / "test.db")
    conn = init_db(db_path)
    fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    conn.close()
    assert fk == 1, f"Expected FK=1, got {fk}"


def test_init_db_schema_columns(tmp_path: Path) -> None:
    db_path = str(tmp_path / "test.db")
    conn = init_db(db_path)

    cur = conn.execute("PRAGMA table_info(sentence_records)")
    sentence_cols = {r[1] for r in cur.fetchall()}
    assert "id" in sentence_cols
    assert "japanese_text" in sentence_cols
    assert "source_context" in sentence_cols
    assert "created_at" in sentence_cols

    cur = conn.execute("PRAGMA table_info(highlight_vocab)")
    vocab_cols = {r[1] for r in cur.fetchall()}
    assert "id" in vocab_cols
    assert "sentence_id" in vocab_cols
    assert "surface" in vocab_cols
    assert "lemma" in vocab_cols
    assert "pos" in vocab_cols
    assert "jlpt_level" in vocab_cols
    assert "is_beyond_level" in vocab_cols
    assert "tooltip_shown" in vocab_cols
    assert "vocab_id" in vocab_cols
    assert "pronunciation" in vocab_cols
    assert "definition" in vocab_cols

    cur = conn.execute("PRAGMA table_info(highlight_grammar)")
    grammar_cols = {r[1] for r in cur.fetchall()}
    assert "id" in grammar_cols
    assert "sentence_id" in grammar_cols
    assert "rule_id" in grammar_cols
    assert "pattern" in grammar_cols
    assert "jlpt_level" in grammar_cols
    assert "confidence_type" in grammar_cols
    assert "description" in grammar_cols
    assert "is_beyond_level" in grammar_cols
    assert "tooltip_shown" in grammar_cols

    cur = conn.execute("PRAGMA table_info(app_settings)")
    settings_cols = {r[1] for r in cur.fetchall()}
    assert "key" in settings_cols
    assert "value" in settings_cols

    conn.close()


def test_init_db_idempotent(tmp_path: Path) -> None:
    db_path = str(tmp_path / "test.db")
    conn1 = init_db(db_path)
    conn1.close()
    conn2 = init_db(db_path)
    conn2.close()


def test_init_db_returns_connection(tmp_path: Path) -> None:
    db_path = str(tmp_path / "test.db")
    conn = init_db(db_path)
    assert isinstance(conn, sqlite3.Connection)
    conn.close()


def test_init_db_memory_database() -> None:
    conn = init_db(":memory:")
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = {r[0] for r in cur.fetchall()}
    assert "sentence_records" in tables
    assert "highlight_vocab" in tables
    assert "highlight_grammar" in tables
    assert "app_settings" in tables
    conn.close()


def test_init_db_creates_indexes(tmp_path: Path) -> None:
    db_path = str(tmp_path / "test.db")
    conn = init_db(db_path)
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='index' ORDER BY name")
    indexes = {r[0] for r in cur.fetchall()}
    conn.close()
    assert "idx_sentence_created_at" in indexes
    assert "idx_highlight_vocab_sentence" in indexes
    assert "idx_highlight_grammar_sentence" in indexes


def test_init_db_migrates_old_database(tmp_path: Path) -> None:
    db_path = str(tmp_path / "old.db")
    old_schema = """
    CREATE TABLE IF NOT EXISTS sentence_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        japanese_text TEXT NOT NULL,
        source_context TEXT,
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS highlight_vocab (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sentence_id INTEGER NOT NULL REFERENCES sentence_records(id) ON DELETE CASCADE,
        surface TEXT NOT NULL,
        lemma TEXT NOT NULL,
        pos TEXT NOT NULL,
        jlpt_level INTEGER,
        is_beyond_level INTEGER NOT NULL DEFAULT 0,
        tooltip_shown INTEGER NOT NULL DEFAULT 0
    );
    """
    old_conn = sqlite3.connect(db_path)
    old_conn.executescript(old_schema)
    old_conn.close()

    conn = init_db(db_path)
    cur = conn.execute("PRAGMA table_info(highlight_vocab)")
    cols = {r[1] for r in cur.fetchall()}
    conn.close()

    assert "vocab_id" in cols
    assert "pronunciation" in cols
    assert "definition" in cols
