"""Database schema and initialization for MyASR."""

import logging
import sqlite3

logger = logging.getLogger(__name__)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS sentence_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    japanese_text TEXT NOT NULL,
    source_context TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sentence_created_at ON sentence_records(created_at);

CREATE TABLE IF NOT EXISTS highlight_vocab (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sentence_id INTEGER NOT NULL REFERENCES sentence_records(id) ON DELETE CASCADE,
    surface TEXT NOT NULL,
    lemma TEXT NOT NULL,
    pos TEXT NOT NULL,
    jlpt_level INTEGER,
    is_beyond_level INTEGER NOT NULL DEFAULT 0,
    tooltip_shown INTEGER NOT NULL DEFAULT 0,
    vocab_id INTEGER NOT NULL DEFAULT 0,
    pronunciation TEXT NOT NULL DEFAULT '',
    definition TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_highlight_vocab_sentence ON highlight_vocab(sentence_id);

CREATE TABLE IF NOT EXISTS highlight_grammar (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sentence_id INTEGER NOT NULL REFERENCES sentence_records(id) ON DELETE CASCADE,
    rule_id TEXT NOT NULL,
    pattern TEXT NOT NULL,
    jlpt_level INTEGER,
    confidence_type TEXT NOT NULL,
    description TEXT,
    is_beyond_level INTEGER NOT NULL DEFAULT 0,
    tooltip_shown INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_highlight_grammar_sentence ON highlight_grammar(sentence_id);

CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def init_db(db_path: str) -> sqlite3.Connection:
    """Initialize the database with the schema.

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        sqlite3.Connection with the database initialized.
    """
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA_SQL)

    # Migrate existing databases: add new columns if they do not yet exist.
    migrations = [
        "ALTER TABLE highlight_vocab ADD COLUMN vocab_id INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE highlight_vocab ADD COLUMN pronunciation TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE highlight_vocab ADD COLUMN definition TEXT NOT NULL DEFAULT ''",
    ]
    for stmt in migrations:
        try:
            conn.execute(stmt)
            conn.commit()
        except sqlite3.OperationalError:
            # Column already exists — safe to ignore.
            pass

    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    logger.info("Database initialized at %s", db_path)
    return conn
