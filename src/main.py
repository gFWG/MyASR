"""Application entry point for MyASR Japanese learning overlay.

Wires together the audio pipeline, overlay UI, and tooltip
into a runnable application.
"""

import logging
import signal
import sys
from pathlib import Path

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication

from src.asr.model_resources import resolve_model_load_path
from src.config import AppConfig, load_config
from src.exceptions import ModelResourceError
from src.models import GrammarHit, SentenceResult, VocabHit
from src.pipeline.orchestrator import PipelineOrchestrator
from src.ui.overlay import OverlayWindow
from src.ui.settings import SettingsDialog
from src.ui.tooltip import TooltipPopup
from src.ui.tray import SystemTrayManager

logger = logging.getLogger(__name__)


def _cleanup(pipeline: PipelineOrchestrator | None) -> None:
    """Stop the pipeline.

    Args:
        pipeline: The running PipelineOrchestrator to stop.
    """
    if pipeline is None:
        return

    try:
        pipeline.stop()
    except Exception:
        logger.exception("Error stopping pipeline during cleanup")


def _active_model_directory(model_path: str) -> str:
    candidate = Path(model_path).expanduser()
    try:
        if candidate.is_dir():
            return str(candidate.resolve(strict=False))
    except OSError:
        logger.exception("Failed to inspect active model directory: %s", model_path)
    return ""


def _build_pipeline_config(config: AppConfig) -> tuple[dict[str, object], str]:
    model_path = resolve_model_load_path(config.asr_model, config.asr_model_local_path)
    pipeline_config: dict[str, object] = {
        "sample_rate": config.sample_rate,
        "asr_batch_size": 4,
        "asr_flush_timeout_ms": 500,
        "vad_threshold": config.vad_threshold,
        "vad_min_silence_ms": config.vad_min_silence_ms,
        "vad_min_speech_ms": config.vad_min_speech_ms,
        "model_path": model_path,
    }
    return pipeline_config, _active_model_directory(model_path)


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
        app_instance = QApplication.instance()
        app = app_instance if isinstance(app_instance, QApplication) else QApplication(sys.argv)

        app.setQuitOnLastWindowClosed(False)

        config: AppConfig = load_config()

        overlay = OverlayWindow(config)
        tooltip = TooltipPopup()
        tray = SystemTrayManager()
        pipeline: PipelineOrchestrator | None = None
        runtime_resource_config = config
        active_model_directory = ""

        try:
            pipeline_config, active_model_directory = _build_pipeline_config(config)
            pipeline = PipelineOrchestrator(config=pipeline_config)
        except ModelResourceError as exc:
            runtime_resource_config = AppConfig(asr_model="", asr_model_local_path="")
            logger.error("ASR model resources are not ready: %s", exc)
            overlay.set_status(f"ASR model path error: {exc}")
        except Exception as exc:
            runtime_resource_config = AppConfig(asr_model="", asr_model_local_path="")
            logger.exception("Failed to initialise ASR pipeline")
            overlay.set_status(f"ASR startup failed: {exc}")

        def _on_pipeline_error(msg: str) -> None:
            logger.error("Pipeline error: %s", msg)
            overlay.set_status(f"Error: {msg}")

        if pipeline is not None:
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
            if pipeline is not None:
                pipeline.on_config_changed(new_config)

        def _open_settings() -> None:
            nonlocal _settings_dialog
            if _settings_dialog is not None and _settings_dialog.isVisible():
                _settings_dialog.raise_()
                _settings_dialog.activateWindow()
                return
            _settings_dialog = SettingsDialog(
                current_config,
                runtime_config=runtime_resource_config,
                active_model_directory=active_model_directory,
            )
            _settings_dialog.config_changed.connect(_on_config_changed)
            _settings_dialog.show()

        def _toggle_overlay() -> None:
            """Toggle overlay visibility and update tray menu state."""
            new_visible = not overlay.isVisible()
            overlay.setVisible(new_visible)
            tray.update_overlay_visibility(new_visible)

        # Connect signals from both tray and overlay using shared handlers
        for source in (tray, overlay):
            source.quit_requested.connect(app.quit)
            source.toggle_overlay.connect(_toggle_overlay)
            source.settings_requested.connect(_open_settings)

        signal.signal(signal.SIGINT, lambda *_: app.quit())
        app.aboutToQuit.connect(lambda: _cleanup(pipeline))

        if pipeline is not None:
            try:
                pipeline.connect_signals(
                    overlay.on_asr_ready,
                    on_sentence_ready=overlay.on_sentence_ready,
                )
                pipeline.start()
                overlay.set_status("Listening...")
            except Exception as exc:
                logger.exception("Failed to start pipeline")
                overlay.set_status(f"ASR startup failed: {exc}")
                _cleanup(pipeline)
                pipeline = None
                runtime_resource_config = AppConfig(asr_model="", asr_model_local_path="")
                active_model_directory = ""

        overlay.show()

        sys.exit(app.exec())

    except Exception:
        logger.exception("Fatal error in main")
        raise


if __name__ == "__main__":
    main()
