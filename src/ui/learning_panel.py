"""Learning history browser panel for MyASR."""

from __future__ import annotations

import logging
import math
from datetime import date, timedelta
from pathlib import Path

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.db.models import SentenceRecord
from src.db.repository import LearningRepository
from src.db.schema import init_db

logger = logging.getLogger(__name__)

PAGE_SIZE = 50


class LearningPanel(QWidget):
    """History browser widget with search, date filters, and pagination.

    Displays sentence records from the learning database in a paginated table.
    Supports full-text search, date range filtering, and double-click to open
    the sentence detail dialog.

    Args:
        db_path: Path to the SQLite database file.
        parent: Optional parent widget.
    """

    def __init__(self, db_path: str | Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._db_path = Path(db_path)
        self._conn = init_db(str(self._db_path))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._repo = LearningRepository(conn=self._conn)
        self._current_page = 1
        self._total_pages = 1

        self._build_ui()
        self._refresh_table()

    def _build_ui(self) -> None:
        """Build and lay out all child widgets."""
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(8, 8, 8, 8)
        root_layout.setSpacing(6)

        # ── top bar: search + date filters ──────────────────────────────────
        top_bar = QHBoxLayout()

        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("Search Japanese…")
        self._search_edit.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        top_bar.addWidget(self._search_edit)

        top_bar.addWidget(QLabel("From:"))
        self._date_from = QDateEdit()
        self._date_from.setCalendarPopup(True)
        self._date_from.setDate(QDate.currentDate().addDays(-30))
        self._date_from.setDisplayFormat("yyyy-MM-dd")
        top_bar.addWidget(self._date_from)

        top_bar.addWidget(QLabel("To:"))
        self._date_to = QDateEdit()
        self._date_to.setCalendarPopup(True)
        self._date_to.setDate(QDate.currentDate())
        self._date_to.setDisplayFormat("yyyy-MM-dd")
        top_bar.addWidget(self._date_to)

        search_btn = QPushButton("Search")
        search_btn.clicked.connect(self._on_search_clicked)
        top_bar.addWidget(search_btn)

        root_layout.addLayout(top_bar)

        # ── table ────────────────────────────────────────────────────────────
        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(
            ["Created At", "Japanese Text", "Vocab Count"],
        )
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.doubleClicked.connect(self._on_row_double_clicked)

        header = self._table.horizontalHeader()
        for col in range(2):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(2, 90)

        root_layout.addWidget(self._table)

        # ── pagination bar ───────────────────────────────────────────────────
        pagination_bar = QHBoxLayout()

        self._prev_btn = QPushButton("← Previous")
        self._prev_btn.setEnabled(False)
        self._prev_btn.clicked.connect(self._on_prev_clicked)
        pagination_bar.addWidget(self._prev_btn)

        pagination_bar.addStretch()

        self._page_label = QLabel("Page 1 of 1")
        self._page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pagination_bar.addWidget(self._page_label)

        pagination_bar.addStretch()

        self._next_btn = QPushButton("Next →")
        self._next_btn.setEnabled(False)
        self._next_btn.clicked.connect(self._on_next_clicked)
        pagination_bar.addWidget(self._next_btn)

        root_layout.addLayout(pagination_bar)

        # ── bottom bar: export / delete ──────────────────────────────────────
        bottom_bar = QHBoxLayout()

        export_btn = QPushButton("Export…")
        export_btn.clicked.connect(self._open_export_dialog)
        bottom_bar.addWidget(export_btn)

        bottom_bar.addStretch()

        delete_btn = QPushButton("Delete by Date…")
        delete_btn.clicked.connect(self._on_delete_by_date_clicked)
        bottom_bar.addWidget(delete_btn)

        root_layout.addLayout(bottom_bar)

    # ── private helpers ──────────────────────────────────────────────────────

    def _get_filter_params(self) -> tuple[str | None, str | None, str | None]:
        """Return (query, date_from_iso, date_to_iso) from current UI state."""
        raw_query = self._search_edit.text().strip()
        query: str | None = raw_query if raw_query else None
        date_from = self._date_from.date().toString("yyyy-MM-dd")
        date_to = self._date_to.date().toString("yyyy-MM-dd")
        return query, date_from, date_to

    def _refresh_table(self) -> None:
        """Reload table from DB for the current page and filter state."""
        query, date_from, date_to = self._get_filter_params()

        total = self._repo.get_sentence_count(
            query=query,
            date_from=date_from,
            date_to=date_to,
        )
        self._total_pages = max(1, math.ceil(total / PAGE_SIZE))

        if self._current_page > self._total_pages:
            self._current_page = self._total_pages

        offset = (self._current_page - 1) * PAGE_SIZE
        records = self._repo.get_sentences_filtered(
            limit=PAGE_SIZE,
            offset=offset,
            query=query,
            date_from=date_from,
            date_to=date_to,
        )

        self._table.setRowCount(0)
        for row_idx, record in enumerate(records):
            self._table.insertRow(row_idx)
            self._set_row(row_idx, record)

        self._page_label.setText(f"Page {self._current_page} of {self._total_pages}")
        self._prev_btn.setEnabled(self._current_page > 1)
        self._next_btn.setEnabled(self._current_page < self._total_pages)

        logger.debug(
            "Refreshed table: page=%d/%d, records=%d",
            self._current_page,
            self._total_pages,
            len(records),
        )

    def _set_row(self, row_idx: int, record: SentenceRecord) -> None:
        """Populate one table row from a SentenceRecord."""
        created_at_item = QTableWidgetItem(record.created_at)
        created_at_item.setData(Qt.ItemDataRole.UserRole, record.id)
        self._table.setItem(row_idx, 0, created_at_item)

        self._table.setItem(row_idx, 1, QTableWidgetItem(record.japanese_text))

        # Vocab count: fetch highlights for this record
        vocab_count = 0
        if record.id is not None:
            result = self._repo.get_sentence_with_highlights(record.id)
            if result is not None:
                _, vocab_hits, _ = result
                vocab_count = len(vocab_hits)
        count_item = QTableWidgetItem(str(vocab_count))
        count_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self._table.setItem(row_idx, 2, count_item)

    # ── slots ────────────────────────────────────────────────────────────────

    def _on_search_clicked(self) -> None:
        self._current_page = 1
        self._refresh_table()

    def _on_prev_clicked(self) -> None:
        if self._current_page > 1:
            self._current_page -= 1
            self._refresh_table()

    def _on_next_clicked(self) -> None:
        if self._current_page < self._total_pages:
            self._current_page += 1
            self._refresh_table()

    def _on_row_double_clicked(self) -> None:
        """Open SentenceDetailDialog for the selected row."""
        selected_rows = self._table.selectedItems()
        if not selected_rows:
            return

        current_row = self._table.currentRow()
        sentence_id_data = self._table.item(current_row, 0)
        if sentence_id_data is None:
            return

        sentence_id = sentence_id_data.data(Qt.ItemDataRole.UserRole)
        if sentence_id is None:
            return

        result = self._repo.get_sentence_with_highlights(int(sentence_id))
        if result is None:
            logger.warning("Sentence id=%s not found in DB", sentence_id)
            return

        sentence, vocab_hits, grammar_hits = result

        # Lazy import to avoid ImportError when sentence_detail.py does not yet exist
        try:
            from src.ui import sentence_detail  # noqa: PLC0415

            dialog = sentence_detail.SentenceDetailDialog(
                sentence=sentence,
                vocab_hits=vocab_hits,
                grammar_hits=grammar_hits,
                parent=self,
            )
            dialog.exec()
        except ImportError:
            logger.warning("SentenceDetailDialog not yet available (sentence_detail.py missing)")

    def _open_export_dialog(self) -> None:
        """Open the export dialog with date range, format, and highlights options.

        Displays a QDialog that lets the user configure export parameters,
        then calls export_records() and writes the result to a chosen file.
        """
        dialog = QDialog(self)
        dialog.setWindowTitle("Export Records")
        dialog.setMinimumWidth(360)

        layout = QVBoxLayout(dialog)
        layout.setSpacing(10)

        # ── Date range ───────────────────────────────────────────────────────
        date_group = QGroupBox("Date Range")
        date_form = QVBoxLayout(date_group)

        from_row = QHBoxLayout()
        from_row.addWidget(QLabel("From:"))
        export_date_from = QDateEdit()
        export_date_from.setCalendarPopup(True)
        export_date_from.setDisplayFormat("yyyy-MM-dd")
        export_date_from.setDate(self._date_from.date())
        from_row.addWidget(export_date_from)
        date_form.addLayout(from_row)

        to_row = QHBoxLayout()
        to_row.addWidget(QLabel("To:  "))
        export_date_to = QDateEdit()
        export_date_to.setCalendarPopup(True)
        export_date_to.setDisplayFormat("yyyy-MM-dd")
        export_date_to.setDate(self._date_to.date())
        to_row.addWidget(export_date_to)
        date_form.addLayout(to_row)

        layout.addWidget(date_group)

        # ── Format selection ─────────────────────────────────────────────────
        format_group = QGroupBox("Format")
        format_layout = QHBoxLayout(format_group)
        json_radio = QRadioButton("JSON")
        csv_radio = QRadioButton("CSV")
        json_radio.setChecked(True)
        format_layout.addWidget(json_radio)
        format_layout.addWidget(csv_radio)
        layout.addWidget(format_group)

        # ── Options ──────────────────────────────────────────────────────────
        highlights_check = QCheckBox("Include highlights")
        highlights_check.setChecked(True)
        layout.addWidget(highlights_check)

        # ── Buttons ──────────────────────────────────────────────────────────
        button_box = QDialogButtonBox()
        export_btn = button_box.addButton("Export", QDialogButtonBox.ButtonRole.AcceptRole)
        cancel_btn = button_box.addButton("Cancel", QDialogButtonBox.ButtonRole.RejectRole)
        # cancel_btn is used implicitly via rejected signal; suppress unused warning
        _ = cancel_btn
        _ = export_btn
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        # ── Gather parameters ─────────────────────────────────────────────────
        fmt = "json" if json_radio.isChecked() else "csv"
        date_from_str = export_date_from.date().toString("yyyy-MM-dd")
        date_to_str = export_date_to.date().toString("yyyy-MM-dd")
        include_highlights = highlights_check.isChecked()

        file_filter = "JSON Files (*.json)" if fmt == "json" else "CSV Files (*.csv)"
        default_suffix = ".json" if fmt == "json" else ".csv"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Export",
            f"export{default_suffix}",
            file_filter,
        )
        if not file_path:
            return

        try:
            content = self._repo.export_records(
                format=fmt,
                date_from=date_from_str,
                date_to=date_to_str,
                include_highlights=include_highlights,
            )
            Path(file_path).write_text(content, encoding="utf-8")
            logger.info("Exported records to %s (format=%s)", file_path, fmt)
            QMessageBox.information(
                self,
                "Export Complete",
                f"Records exported successfully to:\n{file_path}",
            )
        except Exception as exc:
            logger.error("Export failed: %s", exc)
            QMessageBox.critical(
                self,
                "Export Failed",
                f"Failed to export records:\n{exc}",
            )

    def _on_delete_by_date_clicked(self) -> None:
        """Prompt user for a cutoff date and delete records older than it."""
        default_date = (date.today() - timedelta(days=30)).strftime("%Y-%m-%d")
        cutoff, ok = QInputDialog.getText(
            self,
            "Delete by Date",
            "Delete all records BEFORE this date (YYYY-MM-DD):",
            text=default_date,
        )
        if not ok or not cutoff.strip():
            return

        cutoff = cutoff.strip()
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Delete ALL records with created_at < {cutoff!r}?\n\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        deleted = self._repo.delete_before(cutoff)
        logger.info("Deleted %d records before %s", deleted, cutoff)
        QMessageBox.information(
            self,
            "Deleted",
            f"Deleted {deleted} record(s) before {cutoff}.",
        )
        self.refresh()

    # ── public API ───────────────────────────────────────────────────────────

    def refresh(self) -> None:
        """Reset to page 1 and reload the table from the database."""
        self._current_page = 1
        self._refresh_table()

    def closeEvent(self, event: QCloseEvent) -> None:
        """Close the database connection before the widget is destroyed."""
        self._conn.close()
        super().closeEvent(event)
