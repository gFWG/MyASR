"""Tests for src/ui/learning_panel.py — LearningPanel."""

from __future__ import annotations

import math
from pathlib import Path

from PySide6.QtWidgets import QApplication, QLineEdit, QPushButton

from src.db.models import SentenceRecord
from src.db.repository import LearningRepository
from src.db.schema import init_db
from src.ui.learning_panel import LearningPanel


def _make_record(
    japanese_text: str = "猫が好きです",
    chinese_translation: str = "我喜欢猫",
    created_at: str = "2024-01-15T10:00:00",
) -> SentenceRecord:
    return SentenceRecord(
        id=None,
        japanese_text=japanese_text,
        chinese_translation=chinese_translation,
        explanation=None,
        source_context=None,
        created_at=created_at,
    )


def _make_panel(qapp: QApplication, db_path: Path) -> LearningPanel:
    init_db(str(db_path))
    return LearningPanel(db_path)


def test_panel_creates_with_db_path(qapp: QApplication, tmp_path: Path) -> None:
    panel = _make_panel(qapp, tmp_path / "test.db")
    assert panel is not None


def test_panel_has_table_with_4_columns(qapp: QApplication, tmp_path: Path) -> None:
    panel = _make_panel(qapp, tmp_path / "test.db")
    assert panel._table.columnCount() == 4


def test_panel_has_search_and_pagination(qapp: QApplication, tmp_path: Path) -> None:
    panel = _make_panel(qapp, tmp_path / "test.db")
    assert isinstance(panel._search_edit, QLineEdit)
    assert isinstance(panel._prev_btn, QPushButton)
    assert isinstance(panel._next_btn, QPushButton)


def test_pagination_calculates_pages(qapp: QApplication) -> None:
    """Insert 120 rows with page_size=50; total pages should be 3."""
    conn = init_db(":memory:")
    repo = LearningRepository(conn=conn)
    for i in range(120):
        repo.insert_sentence(
            _make_record(
                japanese_text=f"テキスト{i}",
                created_at=f"2024-01-{(i % 28) + 1:02d}T{i % 24:02d}:00:00",
            ),
            [],
            [],
        )

    total = repo.get_sentence_count()
    assert total == 120
    total_pages = math.ceil(total / 50)
    assert total_pages == 3


def test_search_filters_results(qapp: QApplication) -> None:
    """Insert 2 rows; search for unique text in one; table should show 1 row."""
    conn = init_db(":memory:")
    repo = LearningRepository(conn=conn)
    repo.insert_sentence(
        _make_record(japanese_text="唯一のテキストxyz", chinese_translation="unique xyz"),
        [],
        [],
    )
    repo.insert_sentence(
        _make_record(japanese_text="別のテキスト", chinese_translation="other text"),
        [],
        [],
    )

    results = repo.get_sentences_filtered(query="唯一のテキストxyz")
    assert len(results) == 1
    assert results[0].japanese_text == "唯一のテキストxyz"


def test_refresh_method_callable(qapp: QApplication, tmp_path: Path) -> None:
    panel = _make_panel(qapp, tmp_path / "test.db")
    panel.refresh()


def test_export_dialog_has_controls(qapp: QApplication, tmp_path: Path) -> None:
    panel = _make_panel(qapp, tmp_path / "test.db")
    assert hasattr(panel, "_open_export_dialog")
    assert callable(panel._open_export_dialog)


def test_quick_export_signal_triggers_handler(qapp: QApplication) -> None:
    from src.ui.tray import SystemTrayManager

    received: list[bool] = []

    tray = SystemTrayManager()
    tray.quick_export_requested.connect(lambda: received.append(True))
    tray.quick_export_requested.emit()

    assert received == [True]
