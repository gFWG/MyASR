"""Application entry point for MyASR Japanese learning overlay.

Wires together the audio pipeline, overlay UI, tooltip, and learning repository
into a runnable application.
"""

import logging
import signal
import sqlite3
import sys
from pathlib import Path

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from src.config import AppConfig, load_config
from src.db.models import GrammarHit, SentenceResult, VocabHit
from src.db.repository import LearningRepository
from src.db.schema import init_db
from src.pipeline import PipelineWorker
from src.ui.learning_panel import LearningPanel
from src.ui.overlay import OverlayWindow
from src.ui.settings import SettingsDialog
from src.ui.tooltip import TooltipPopup
from src.ui.tray import SystemTrayManager

logger = logging.getLogger(__name__)


def _cleanup(pipeline: PipelineWorker, conn: sqlite3.Connection) -> None:
    """Stop the pipeline and close the database connection.

    Args:
        pipeline: The running PipelineWorker thread to stop.
        conn: The SQLite connection to close.
    """
    try:
        pipeline.stop()
    except Exception:
        logger.exception("Error stopping pipeline during cleanup")

    try:
        conn.close()
    except Exception:
        logger.exception("Error closing database connection during cleanup")


def main() -> None:
    """Initialize and run the MyASR overlay application.

    Sets up logging, creates all components, wires signals, and enters
    the Qt event loop.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    try:
        app: QApplication = QApplication.instance() or QApplication(sys.argv)  # type: ignore[assignment]  # instance() returns QCoreApplication|None but we always get QApplication here

        app.setQuitOnLastWindowClosed(False)

        config: AppConfig = load_config()
        conn: sqlite3.Connection = init_db(config.db_path)
        repo = LearningRepository(conn)

        overlay = OverlayWindow(config)
        tooltip = TooltipPopup()
        pipeline = PipelineWorker(config, db_conn=conn)
        tray = SystemTrayManager()

        pipeline.sentence_ready.connect(overlay.on_sentence_ready)

        def _on_pipeline_error(msg: str) -> None:
            logger.error("Pipeline error: %s", msg)
            overlay.set_status(f"Error: {msg}")

        pipeline.error_occurred.connect(_on_pipeline_error)

        def _on_highlight_hovered(hit: VocabHit | GrammarHit, point: QPoint) -> None:
            result: SentenceResult | None = overlay._current_result
            sentence_id: int | None = result.sentence_id if result is not None else None

            highlight_id = 0
            if result is not None:
                if isinstance(hit, VocabHit):
                    vocab_ids = result.highlight_vocab_ids or []
                    analysis = result.analysis
                    if analysis is not None:
                        try:
                            idx = analysis.vocab_hits.index(hit)
                            if idx < len(vocab_ids):
                                highlight_id = vocab_ids[idx]
                        except ValueError:
                            highlight_id = 0
                else:
                    grammar_ids = result.highlight_grammar_ids or []
                    analysis = result.analysis
                    if analysis is not None:
                        try:
                            idx = analysis.grammar_hits.index(hit)
                            if idx < len(grammar_ids):
                                highlight_id = grammar_ids[idx]
                        except ValueError:
                            highlight_id = 0

            if isinstance(hit, VocabHit):
                tooltip.show_for_vocab(hit, point, sentence_id, highlight_id)
            else:
                tooltip.show_for_grammar(hit, point, sentence_id, highlight_id)

        overlay.highlight_hovered.connect(_on_highlight_hovered)
        tooltip.record_triggered.connect(repo.mark_tooltip_shown)

        # TODO(F4): QTimer(60s) -> review_repo.get_queue_count() -> tray.update_review_badge(count)

        _settings_dialog: SettingsDialog | None = None

        def _open_settings() -> None:
            nonlocal _settings_dialog
            if _settings_dialog is not None and _settings_dialog.isVisible():
                _settings_dialog.raise_()
                _settings_dialog.activateWindow()
                return
            _settings_dialog = SettingsDialog(config)
            _settings_dialog.config_changed.connect(overlay.on_config_changed)
            _settings_dialog.config_changed.connect(pipeline.update_config)
            _settings_dialog.show()

        tray.quit_requested.connect(app.quit)
        tray.toggle_overlay.connect(lambda: overlay.setVisible(not overlay.isVisible()))
        tray.settings_requested.connect(_open_settings)

        _learning_panel: LearningPanel | None = None

        def _open_learning_panel() -> None:
            nonlocal _learning_panel
            if _learning_panel is not None and _learning_panel.isVisible():
                _learning_panel.raise_()
                _learning_panel.activateWindow()
                return
            _learning_panel = LearningPanel(config.db_path)
            _learning_panel.show()

        tray.history_requested.connect(_open_learning_panel)

        def _quick_export() -> None:
            file_path, _ = QFileDialog.getSaveFileName(
                None,
                "Quick Export",
                "",
                "JSON Files (*.json)",
            )
            if not file_path:
                return
            try:
                json_str = repo.export_records("json")
                Path(file_path).write_text(json_str, encoding="utf-8")
                QMessageBox.information(None, "Export Complete", f"Exported to {file_path}")
            except Exception as e:
                QMessageBox.critical(None, "Export Failed", str(e))

        tray.quick_export_requested.connect(_quick_export)

        signal.signal(signal.SIGINT, lambda *_: app.quit())
        app.aboutToQuit.connect(lambda: _cleanup(pipeline, conn))

        pipeline.start()
        overlay.set_status("Listening...")
        overlay.show()

        sys.exit(app.exec())

    except Exception:
        logger.exception("Fatal error in main")
        raise


if __name__ == "__main__":
    main()
