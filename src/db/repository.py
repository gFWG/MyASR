"""Learning repository for MyASR database CRUD operations."""

import csv
import io
import json
import logging
import sqlite3

from src.db.models import HighlightGrammar, HighlightVocab, SentenceRecord

logger = logging.getLogger(__name__)


class LearningRepository:
    """Repository for learning records in the MyASR database.

    Handles all CRUD operations for sentence records and their associated
    vocabulary and grammar highlights.
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

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
                    (japanese_text, chinese_translation, explanation,
                     source_context, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    record.japanese_text,
                    record.chinese_translation,
                    record.explanation,
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
                         is_beyond_level, tooltip_shown)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        sentence_id,
                        v.surface,
                        v.lemma,
                        v.pos,
                        v.jlpt_level,
                        int(v.is_beyond_level),
                        int(v.tooltip_shown),
                    ),
                )
                if vcursor.lastrowid is not None:
                    vocab_ids.append(vcursor.lastrowid)

            grammar_ids: list[int] = []
            for g in grammar:
                gcursor = self._conn.execute(
                    """
                    INSERT INTO highlight_grammar
                        (sentence_id, rule_id, pattern, jlpt_level, confidence_type,
                         description, is_beyond_level, tooltip_shown)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        sentence_id,
                        g.rule_id,
                        g.pattern,
                        g.jlpt_level,
                        g.confidence_type,
                        g.description,
                        int(g.is_beyond_level),
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
            SELECT id, japanese_text, chinese_translation, explanation,
                   source_context, created_at
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
                chinese_translation=row[2],
                explanation=row[3],
                source_context=row[4],
                created_at=row[5],
            )
            for row in rows
        ]

    def search_sentences(self, query: str) -> list[SentenceRecord]:
        """Full-text search on japanese_text and chinese_translation using LIKE.

        Args:
            query: Search string to look for in japanese_text or chinese_translation.

        Returns:
            List of matching SentenceRecord items.
        """
        pattern = f"%{query}%"
        cursor = self._conn.execute(
            """
            SELECT id, japanese_text, chinese_translation, explanation,
                   source_context, created_at
            FROM sentence_records
            WHERE japanese_text LIKE ? OR chinese_translation LIKE ?
            ORDER BY created_at DESC
            """,
            (pattern, pattern),
        )
        rows = cursor.fetchall()
        return [
            SentenceRecord(
                id=row[0],
                japanese_text=row[1],
                chinese_translation=row[2],
                explanation=row[3],
                source_context=row[4],
                created_at=row[5],
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

    def export_records(self, format: str = "json") -> str:
        """Export all records as JSON or CSV string.

        Args:
            format: Export format — 'json' or 'csv'.

        Returns:
            String representation of all sentence_records in the given format.

        Raises:
            ValueError: If format is not 'json' or 'csv'.
        """
        cursor = self._conn.execute(
            """
            SELECT id, japanese_text, chinese_translation, explanation,
                   source_context, created_at
            FROM sentence_records
            ORDER BY created_at DESC
            """
        )
        rows = cursor.fetchall()

        columns = [
            "id",
            "japanese_text",
            "chinese_translation",
            "explanation",
            "source_context",
            "created_at",
        ]

        if format == "json":
            records = [dict(zip(columns, row)) for row in rows]
            return json.dumps(records, ensure_ascii=False)
        elif format == "csv":
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(columns)
            writer.writerows(rows)
            return output.getvalue()
        else:
            raise ValueError(f"Unsupported export format: {format!r}. Use 'json' or 'csv'.")

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
