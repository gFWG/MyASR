"""Application entry point for MyASR Japanese learning overlay.

Wires together the audio pipeline, overlay UI, tooltip, and learning repository
into a runnable application.
"""

import logging
import signal
import sqlite3
import sys

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication

from src.config import AppConfig, load_config
from src.db.models import GrammarHit, SentenceResult, VocabHit
from src.db.repository import LearningRepository
from src.db.schema import init_db
from src.pipeline import PipelineWorker
from src.ui.overlay import OverlayWindow
from src.ui.tooltip import TooltipPopup
from src.ui.tray import SystemTrayManager

logger = logging.getLogger(__name__)


def _open_settings() -> None:
    logger.info("Settings dialog requested (not yet implemented)")


def _open_learning_panel() -> None:
    logger.info("Learning panel requested (not yet implemented)")


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

        tray.quit_requested.connect(app.quit)
        tray.toggle_overlay.connect(lambda: overlay.setVisible(not overlay.isVisible()))
        tray.settings_requested.connect(_open_settings)
        tray.history_requested.connect(_open_learning_panel)

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
