"""Database schema and initialization for MyASR."""

import logging
import sqlite3
from sqlite3 import OperationalError

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
    word TEXT,
    description TEXT,
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

    # Versioned migrations using PRAGMA user_version.
    cursor = conn.execute("PRAGMA user_version")
    user_version: int = cursor.fetchone()[0]

    if user_version < 1:
        try:
            conn.execute("ALTER TABLE highlight_grammar DROP COLUMN confidence_type")
        except OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE highlight_grammar ADD COLUMN word TEXT")
        except OperationalError:
            pass
        conn.execute("PRAGMA user_version = 1")
        conn.commit()

    # Migration version 2: Remove is_beyond_level column from highlight tables.
    # SQLite doesn't support DROP COLUMN, so we recreate the tables.
    if user_version < 2:
        # Check if is_beyond_level column exists in highlight_vocab
        cursor = conn.execute("PRAGMA table_info(highlight_vocab)")
        columns = [row[1] for row in cursor.fetchall()]
        if "is_beyond_level" in columns:
            # Recreate highlight_vocab without is_beyond_level
            conn.execute("""
                CREATE TABLE highlight_vocab_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sentence_id INTEGER NOT NULL,
                    surface TEXT NOT NULL,
                    lemma TEXT NOT NULL,
                    pos TEXT NOT NULL,
                    jlpt_level INTEGER,
                    tooltip_shown INTEGER NOT NULL DEFAULT 0,
                    vocab_id INTEGER NOT NULL DEFAULT 0,
                    pronunciation TEXT NOT NULL DEFAULT '',
                    definition TEXT NOT NULL DEFAULT '',
                    FOREIGN KEY (sentence_id) REFERENCES sentence_records(id) ON DELETE CASCADE
                )
            """)
            conn.execute("""
                INSERT INTO highlight_vocab_new
                    (id, sentence_id, surface, lemma, pos, jlpt_level, tooltip_shown, vocab_id, pronunciation, definition)
                SELECT id, sentence_id, surface, lemma, pos, jlpt_level, tooltip_shown, vocab_id, pronunciation, definition
                FROM highlight_vocab
            """)
            conn.execute("DROP TABLE highlight_vocab")
            conn.execute("ALTER TABLE highlight_vocab_new RENAME TO highlight_vocab")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_highlight_vocab_sentence ON highlight_vocab(sentence_id)")

        # Check if is_beyond_level column exists in highlight_grammar
        cursor = conn.execute("PRAGMA table_info(highlight_grammar)")
        columns = [row[1] for row in cursor.fetchall()]
        if "is_beyond_level" in columns:
            # Recreate highlight_grammar without is_beyond_level
            conn.execute("""
                CREATE TABLE highlight_grammar_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sentence_id INTEGER NOT NULL,
                    rule_id TEXT NOT NULL,
                    pattern TEXT NOT NULL,
                    jlpt_level INTEGER,
                    word TEXT,
                    description TEXT,
                    tooltip_shown INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY (sentence_id) REFERENCES sentence_records(id) ON DELETE CASCADE
                )
            """)
            conn.execute("""
                INSERT INTO highlight_grammar_new
                    (id, sentence_id, rule_id, pattern, jlpt_level, word, description, tooltip_shown)
                SELECT id, sentence_id, rule_id, pattern, jlpt_level, word, description, tooltip_shown
                FROM highlight_grammar
            """)
            conn.execute("DROP TABLE highlight_grammar")
            conn.execute("ALTER TABLE highlight_grammar_new RENAME TO highlight_grammar")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_highlight_grammar_sentence ON highlight_grammar(sentence_id)")

        conn.execute("PRAGMA user_version = 2")
        conn.commit()

    logger.info("Database initialized at %s", db_path)
    return conn
