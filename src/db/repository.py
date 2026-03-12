"""Learning repository for MyASR database CRUD operations."""

import csv
import io
import json
import logging
import sqlite3

from src.db.models import HighlightGrammar, HighlightVocab, SentenceRecord
from src.pipeline.types import ASRResult

logger = logging.getLogger(__name__)


class LearningRepository:
    """Repository for learning records in the MyASR database.

    Handles all CRUD operations for sentence records and their associated
    vocabulary and grammar highlights.

    Each instance owns its own ``sqlite3.Connection`` so it is safe to use
    from the thread that created it.  Pass a *db_path* to let the repository
    open (and later close) the connection itself, **or** pass an existing
    *conn* for backwards-compatible / test usage.

    Args:
        db_path: Filesystem path (or ``":memory:"``) to the SQLite database.
            If provided, the repository opens a new connection with WAL mode
            and foreign-key enforcement.
        conn: An already-open ``sqlite3.Connection``.  Mutually exclusive
            with *db_path*.

    Raises:
        ValueError: If neither or both of *db_path* and *conn* are supplied.
    """

    def __init__(
        self,
        db_path: str | None = None,
        conn: sqlite3.Connection | None = None,
    ) -> None:
        if db_path is not None and conn is not None:
            raise ValueError("Supply db_path or conn, not both")
        if db_path is None and conn is None:
            raise ValueError("Supply one of db_path or conn")

        if db_path is not None:
            self._conn = sqlite3.connect(db_path)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._owns_conn = True
        else:
            assert conn is not None  # for type narrowing
            self._conn = conn
            self._owns_conn = False

    def close(self) -> None:
        """Close the underlying connection if this repository owns it."""
        if self._owns_conn:
            self._conn.close()

    def insert_partial(self, asr_result: ASRResult) -> int:
        """Insert a sentence record with NULL translation and explanation.

        Args:
            asr_result: ASRResult containing transcribed text and segment_id.

        Returns:
            The auto-generated row ID (integer) of the inserted record.
        """
        from datetime import datetime

        cursor = self._conn.execute(
            """
            INSERT INTO sentence_records
                (japanese_text, source_context, created_at)
            VALUES (?, ?, ?)
            """,
            (
                asr_result.text,
                asr_result.segment_id,
                datetime.now().isoformat(),
            ),
        )
        row_id = cursor.lastrowid
        if row_id is None:
            raise RuntimeError("Failed to get lastrowid after INSERT")
        self._conn.commit()
        logger.info("Inserted partial sentence record id=%d", row_id)
        return row_id

    def insert_sentence(
        self,
        record: SentenceRecord,
        vocab: list[HighlightVocab],
        grammar: list[HighlightGrammar],
    ) -> tuple[int, list[int], list[int]]:
        """Insert record + all highlights in a single transaction.

        Args:
            record: SentenceRecord to insert (id should be None).
            vocab: List of HighlightVocab items to insert.
            grammar: List of HighlightGrammar items to insert.

        Returns:
            Tuple of (sentence_id, vocab_ids, grammar_ids) with the auto-generated
            integer IDs of the inserted sentence and highlight records.
        """
        try:
            cursor = self._conn.execute(
                """
                INSERT INTO sentence_records
                    (japanese_text, source_context, created_at)
                VALUES (?, ?, ?)
                """,
                (
                    record.japanese_text,
                    record.source_context,
                    record.created_at,
                ),
            )
            sentence_id = cursor.lastrowid
            if sentence_id is None:
                raise RuntimeError("Failed to get lastrowid after INSERT")

            vocab_ids: list[int] = []
            for v in vocab:
                vcursor = self._conn.execute(
                    """
                    INSERT INTO highlight_vocab
                        (sentence_id, surface, lemma, pos, jlpt_level,
                         tooltip_shown, vocab_id, pronunciation, definition)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        sentence_id,
                        v.surface,
                        v.lemma,
                        v.pos,
                        v.jlpt_level,
                        int(v.tooltip_shown),
                        v.vocab_id,
                        v.pronunciation,
                        v.definition,
                    ),
                )
                if vcursor.lastrowid is not None:
                    vocab_ids.append(vcursor.lastrowid)

            grammar_ids: list[int] = []
            for g in grammar:
                gcursor = self._conn.execute(
                    """
                    INSERT INTO highlight_grammar
                        (sentence_id, rule_id, pattern, jlpt_level, word,
                         description, tooltip_shown)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        sentence_id,
                        g.rule_id,
                        g.pattern,
                        g.jlpt_level,
                        g.word,
                        g.description,
                        int(g.tooltip_shown),
                    ),
                )
                if gcursor.lastrowid is not None:
                    grammar_ids.append(gcursor.lastrowid)

            self._conn.commit()
            logger.info(
                "Inserted sentence record id=%d, vocab_ids=%s, grammar_ids=%s",
                sentence_id,
                vocab_ids,
                grammar_ids,
            )
            return (sentence_id, vocab_ids, grammar_ids)
        except Exception:
            self._conn.rollback()
            logger.exception("Failed to insert sentence record")
            raise

    def get_sentences(self, limit: int = 50, offset: int = 0) -> list[SentenceRecord]:
        """Fetch recent records ordered by created_at DESC.

        Args:
            limit: Maximum number of records to return.
            offset: Number of records to skip.

        Returns:
            List of SentenceRecord ordered newest first.
        """
        cursor = self._conn.execute(
            """
            SELECT id, japanese_text, source_context, created_at
            FROM sentence_records
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        )
        rows = cursor.fetchall()
        return [
            SentenceRecord(
                id=row[0],
                japanese_text=row[1],
                source_context=row[2],
                created_at=row[3],
            )
            for row in rows
        ]

    def search_sentences(self, query: str) -> list[SentenceRecord]:
        """Full-text search on japanese_text using LIKE.

        Args:
            query: Search string to look for in japanese_text.

        Returns:
            List of matching SentenceRecord items.
        """
        pattern = f"%{query}%"
        cursor = self._conn.execute(
            """
            SELECT id, japanese_text, source_context, created_at
            FROM sentence_records
            WHERE japanese_text LIKE ?
            ORDER BY created_at DESC
            """,
            (pattern,),
        )
        rows = cursor.fetchall()
        return [
            SentenceRecord(
                id=row[0],
                japanese_text=row[1],
                source_context=row[2],
                created_at=row[3],
            )
            for row in rows
        ]

    def mark_tooltip_shown(self, highlight_type: str, highlight_id: int) -> None:
        """Set tooltip_shown=1 on vocab or grammar table based on highlight_type.

        Args:
            highlight_type: Either 'vocab' or 'grammar'.
            highlight_id: Primary key ID of the highlight record.

        Raises:
            ValueError: If highlight_type is not 'vocab' or 'grammar'.
        """
        if highlight_type == "vocab":
            table = "highlight_vocab"
        elif highlight_type == "grammar":
            table = "highlight_grammar"
        else:
            raise ValueError(
                f"Invalid highlight_type: {highlight_type!r}. Must be 'vocab' or 'grammar'."
            )

        self._conn.execute(
            f"UPDATE {table} SET tooltip_shown=1 WHERE id=?",  # noqa: S608
            (highlight_id,),
        )
        self._conn.commit()
        logger.info("Marked tooltip_shown for %s id=%d", highlight_type, highlight_id)

    def export_records(
        self,
        format: str = "json",
        date_from: str | None = None,
        date_to: str | None = None,
        include_highlights: bool = True,
    ) -> str:
        """Export sentence records with optional date filtering and highlights.

        Args:
            format: Output format, "json" or "csv".
            date_from: ISO date string lower bound (inclusive), e.g. "2024-01-01".
            date_to: ISO date string upper bound (inclusive), e.g. "2024-12-31".
            include_highlights: If True, embed vocab/grammar highlight data.

        Returns:
            Serialized string in the requested format.

        Raises:
            ValueError: If format is not 'json' or 'csv'.
        """
        where_clauses: list[str] = []
        params: list[object] = []

        if date_from is not None:
            where_clauses.append("created_at >= ?")
            params.append(date_from)
        if date_to is not None:
            where_clauses.append("created_at <= ?")
            params.append(date_to)

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        cursor = self._conn.execute(
            f"""
            SELECT id, japanese_text, source_context, created_at
            FROM sentence_records
            {where_sql}
            ORDER BY created_at DESC
            """,  # noqa: S608
            params,
        )
        rows = cursor.fetchall()

        columns = [
            "id",
            "japanese_text",
            "source_context",
            "created_at",
        ]

        if format == "json":
            records: list[dict[str, object]] = []
            for row in rows:
                record = dict(zip(columns, row))
                if include_highlights:
                    sentence_id = row[0]
                    vcursor = self._conn.execute(
                        """
                        SELECT surface, lemma, jlpt_level, pos, vocab_id, pronunciation, definition
                        FROM highlight_vocab
                        WHERE sentence_id = ?
                        """,
                        (sentence_id,),
                    )
                    vocab_highlights = [
                        {
                            "surface": vrow[0],
                            "lemma": vrow[1],
                            "jlpt_level": vrow[2],
                            "pos": vrow[3],
                            "vocab_id": vrow[4],
                            "pronunciation": vrow[5],
                            "definition": vrow[6],
                        }
                        for vrow in vcursor.fetchall()
                    ]

                    gcursor = self._conn.execute(
                        """
                        SELECT pattern, jlpt_level, description
                        FROM highlight_grammar
                        WHERE sentence_id = ?
                        """,
                        (sentence_id,),
                    )
                    grammar_highlights = [
                        {
                            "pattern": grow[0],
                            "jlpt_level": grow[1],
                            "description": grow[2],
                        }
                        for grow in gcursor.fetchall()
                    ]

                    record["vocab_highlights"] = vocab_highlights
                    record["grammar_highlights"] = grammar_highlights
                records.append(record)
            return json.dumps(records, ensure_ascii=False, indent=2)
        elif format == "csv":
            output = io.StringIO()
            writer = csv.writer(output)
            if include_highlights:
                writer.writerow(
                    columns
                    + [
                        "vocab_count",
                        "grammar_count",
                        "vocab_lemmas",
                        "grammar_rules",
                        "vocab_ids",
                        "vocab_pronunciations",
                        "vocab_definitions",
                    ]
                )
            else:
                writer.writerow(columns)

            for row in rows:
                sentence_id = row[0]
                if include_highlights:
                    vcursor = self._conn.execute(
                        """
                        SELECT lemma, vocab_id, pronunciation, definition
                        FROM highlight_vocab WHERE sentence_id = ?
                        """,
                        (sentence_id,),
                    )
                    vocab_rows = vcursor.fetchall()
                    vocab_lemmas = [vrow[0] for vrow in vocab_rows]
                    vocab_ids = [str(vrow[1]) for vrow in vocab_rows]
                    vocab_pronunciations = [vrow[2] for vrow in vocab_rows]
                    vocab_definitions = [vrow[3] for vrow in vocab_rows]

                    gcursor = self._conn.execute(
                        """
                        SELECT pattern FROM highlight_grammar WHERE sentence_id = ?
                        """,
                        (sentence_id,),
                    )
                    grammar_patterns = [grow[0] for grow in gcursor.fetchall()]

                    extra_cols = [
                        len(vocab_lemmas),
                        len(grammar_patterns),
                        ";".join(vocab_lemmas),
                        ";".join(grammar_patterns),
                        ";".join(vocab_ids),
                        ";".join(vocab_pronunciations),
                        ";".join(vocab_definitions),
                    ]
                    writer.writerow(list(row) + extra_cols)
                else:
                    writer.writerow(row)
            return output.getvalue()
        else:
            raise ValueError(f"Unsupported export format: {format!r}. Use 'json' or 'csv'.")

    def get_sentences_filtered(
        self,
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "created_at",
        sort_order: str = "DESC",
        query: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[SentenceRecord]:
        """Get filtered and paginated sentence records.

        Args:
            limit: Maximum number of records to return.
            offset: Number of records to skip.
            sort_by: Column to sort by — must be 'created_at' or 'japanese_text'.
            sort_order: Sort direction — must be 'ASC' or 'DESC'.
            query: Optional search string matched against japanese_text and chinese_translation.
            date_from: Optional ISO date string; only records on or after this date.
            date_to: Optional ISO date string; only records on or before this date.

        Returns:
            List of SentenceRecord matching the given filters.

        Raises:
            ValueError: If sort_by or sort_order is not an allowed value.
        """
        _valid_sort_by = {"created_at", "japanese_text"}
        _valid_sort_order = {"ASC", "DESC"}
        if sort_by not in _valid_sort_by:
            raise ValueError(f"Invalid sort_by: {sort_by}")
        if sort_order not in _valid_sort_order:
            raise ValueError(f"Invalid sort_order: {sort_order}")

        where_clauses: list[str] = []
        params: list[object] = []

        if query is not None:
            where_clauses.append("japanese_text LIKE ?")
            params.append(f"%{query}%")
        if date_from is not None:
            where_clauses.append("created_at >= ?")
            params.append(date_from)
        if date_to is not None:
            where_clauses.append("created_at <= ?")
            params.append(date_to)

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        order_sql = f"ORDER BY {sort_by} {sort_order}"

        params.append(limit)
        params.append(offset)

        cursor = self._conn.execute(
            f"""
            SELECT id, japanese_text, source_context, created_at
            FROM sentence_records
            {where_sql}
            {order_sql}
            LIMIT ? OFFSET ?
            """,  # noqa: S608
            params,
        )
        rows = cursor.fetchall()
        return [
            SentenceRecord(
                id=row[0],
                japanese_text=row[1],
                source_context=row[2],
                created_at=row[3],
            )
            for row in rows
        ]

    def get_sentence_count(
        self,
        query: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> int:
        """Return count of sentences matching filters.

        Args:
            query: Optional search string matched against japanese_text.
            date_from: Optional ISO date string; only records on or after this date.
            date_to: Optional ISO date string; only records on or before this date.

        Returns:
            Integer count of matching sentence records.
        """
        where_clauses: list[str] = []
        params: list[object] = []

        if query is not None:
            where_clauses.append("japanese_text LIKE ?")
            params.append(f"%{query}%")
        if date_from is not None:
            where_clauses.append("created_at >= ?")
            params.append(date_from)
        if date_to is not None:
            where_clauses.append("created_at <= ?")
            params.append(date_to)

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        cursor = self._conn.execute(
            f"SELECT COUNT(*) FROM sentence_records {where_sql}",  # noqa: S608
            params,
        )
        row = cursor.fetchone()
        return int(row[0])

    def get_sentence_with_highlights(
        self,
        sentence_id: int,
    ) -> tuple[SentenceRecord, list[HighlightVocab], list[HighlightGrammar]] | None:
        """Get a sentence with all its vocab and grammar highlights.

        Args:
            sentence_id: Primary key of the sentence_records row.

        Returns:
            Tuple of (SentenceRecord, list[HighlightVocab], list[HighlightGrammar]),
            or None if the sentence does not exist.
        """
        cursor = self._conn.execute(
            """
            SELECT id, japanese_text, source_context, created_at
            FROM sentence_records
            WHERE id = ?
            """,
            (sentence_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None

        sentence = SentenceRecord(
            id=row[0],
            japanese_text=row[1],
            source_context=row[2],
            created_at=row[3],
        )

        vcursor = self._conn.execute(
            """
            SELECT id, sentence_id, surface, lemma, pos, jlpt_level,
                   tooltip_shown, vocab_id, pronunciation, definition
            FROM highlight_vocab
            WHERE sentence_id = ?
            """,
            (sentence_id,),
        )
        vocab_list = [
            HighlightVocab(
                id=vrow[0],
                sentence_id=vrow[1],
                surface=vrow[2],
                lemma=vrow[3],
                pos=vrow[4],
                jlpt_level=vrow[5],
                tooltip_shown=bool(vrow[6]),
                vocab_id=int(vrow[7]),
                pronunciation=str(vrow[8]),
                definition=str(vrow[9]),
            )
            for vrow in vcursor.fetchall()
        ]

        gcursor = self._conn.execute(
            """
            SELECT id, sentence_id, rule_id, pattern, jlpt_level, word,
                   description, tooltip_shown
            FROM highlight_grammar
            WHERE sentence_id = ?
            """,
            (sentence_id,),
        )
        grammar_list = [
            HighlightGrammar(
                id=grow[0],
                sentence_id=grow[1],
                rule_id=grow[2],
                pattern=grow[3],
                jlpt_level=grow[4],
                word=grow[5],
                description=grow[6],
                tooltip_shown=bool(grow[7]),
            )
            for grow in gcursor.fetchall()
        ]

        return (sentence, vocab_list, grammar_list)

    def delete_before(self, cutoff_date: str) -> int:
        """Delete records before ISO date. Returns count of deleted records.

        Args:
            cutoff_date: ISO 8601 date/datetime string. Records with created_at
                strictly before this value will be deleted.

        Returns:
            Number of records deleted.
        """
        cursor = self._conn.execute(
            "DELETE FROM sentence_records WHERE created_at < ?",
            (cutoff_date,),
        )
        count = cursor.rowcount
        self._conn.commit()
        logger.info("Deleted %d sentence records before %s", count, cutoff_date)
        return count
