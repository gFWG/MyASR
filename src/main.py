"""Application entry point for MyASR Japanese learning overlay.

Wires together the audio pipeline, overlay UI, and tooltip
into a runnable application.
"""

import logging
import signal
import sys

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication

from src.config import AppConfig, load_config
from src.db.models import GrammarHit, SentenceResult, VocabHit
from src.pipeline.orchestrator import PipelineOrchestrator
from src.ui.overlay import OverlayWindow
from src.ui.settings import SettingsDialog
from src.ui.tooltip import TooltipPopup
from src.ui.tray import SystemTrayManager

logger = logging.getLogger(__name__)


def _cleanup(pipeline: PipelineOrchestrator) -> None:
    """Stop the pipeline.

    Args:
        pipeline: The running PipelineOrchestrator to stop.
    """
    try:
        pipeline.stop()
    except Exception:
        logger.exception("Error stopping pipeline during cleanup")


def main() -> None:
    """Initialize and run the MyASR overlay application.

    Sets up logging, creates all components, wires signals, and enters
    the Qt event loop.
    """
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    try:
        app: QApplication = QApplication.instance() or QApplication(sys.argv)  # type: ignore[assignment]  # instance() returns QCoreApplication|None but we always get QApplication here

        app.setQuitOnLastWindowClosed(False)

        config: AppConfig = load_config()

        overlay = OverlayWindow(config)
        tooltip = TooltipPopup()

        pipeline_config: dict[str, object] = {
            "sample_rate": config.sample_rate,
            "asr_batch_size": 4,
            "asr_flush_timeout_ms": 500,
        }
        pipeline = PipelineOrchestrator(config=pipeline_config)
        tray = SystemTrayManager()

        def _on_pipeline_error(msg: str) -> None:
            logger.error("Pipeline error: %s", msg)
            overlay.set_status(f"Error: {msg}")

        for error_signal in pipeline.error_occurred:
            error_signal.connect(_on_pipeline_error)

        def _on_highlight_hovered(
            hit: VocabHit | GrammarHit, point: QPoint, _result: SentenceResult | None
        ) -> None:
            if isinstance(hit, VocabHit):
                tooltip.show_for_vocab(hit, point)
            else:
                tooltip.show_for_grammar(hit, point)

        overlay.highlight_hovered.connect(_on_highlight_hovered)
        overlay.highlight_left.connect(tooltip.hide_tooltip)
        overlay.dedup_reset.connect(tooltip.reset_dedup)

        _settings_dialog: SettingsDialog | None = None
        current_config: AppConfig = config

        def _on_config_changed(new_config: AppConfig) -> None:
            nonlocal current_config
            current_config = new_config
            overlay.on_config_changed(new_config)
            pipeline.on_config_changed(new_config)

        def _open_settings() -> None:
            nonlocal _settings_dialog
            if _settings_dialog is not None and _settings_dialog.isVisible():
                _settings_dialog.raise_()
                _settings_dialog.activateWindow()
                return
            _settings_dialog = SettingsDialog(current_config)
            _settings_dialog.config_changed.connect(_on_config_changed)
            _settings_dialog.show()

        tray.quit_requested.connect(app.quit)
        tray.toggle_overlay.connect(lambda: overlay.setVisible(not overlay.isVisible()))
        tray.settings_requested.connect(_open_settings)

        signal.signal(signal.SIGINT, lambda *_: app.quit())
        app.aboutToQuit.connect(lambda: _cleanup(pipeline))

        pipeline.connect_signals(overlay.on_asr_ready, on_sentence_ready=overlay.on_sentence_ready)
        pipeline.start()
        overlay.set_status("Listening...")
        overlay.show()

        sys.exit(app.exec())

    except Exception:
        logger.exception("Fatal error in main")
        raise


if __name__ == "__main__":
    main()
