"""PipelineWorker: QThread that runs the Audio→VAD→ASR→Preprocessing pipeline."""

import logging
import queue
from typing import Any

import numpy as np
from PySide6.QtCore import QThread, Signal

from src.analysis.pipeline import PreprocessingPipeline
from src.asr.qwen_asr import QwenASR
from src.audio.capture import AudioCapture
from src.config import AppConfig
from src.db.models import SentenceResult
from src.exceptions import ASRError, AudioCaptureError
from src.vad.silero import SileroVAD

logger = logging.getLogger(__name__)


class PipelineWorker(QThread):
    """QThread that runs the Audio→VAD→ASR→Preprocessing pipeline.

    Emits sentence_ready with a SentenceResult when transcription + analysis complete.
    Emits error_occurred with an error string for fatal/non-fatal errors.
    """

    sentence_ready = Signal(object)  # emits SentenceResult
    error_occurred = Signal(str)

    def __init__(self, config: AppConfig, parent: Any = None) -> None:
        super().__init__(parent)
        self._config = config
        self._audio_capture = AudioCapture(sample_rate=config.sample_rate)
        self._vad = SileroVAD(sample_rate=config.sample_rate)
        self._asr = QwenASR()
        self._preprocessing = PreprocessingPipeline(config)
        self._audio_queue: queue.Queue[np.ndarray] = queue.Queue()
        self._running = False

    def run(self) -> None:
        """Main thread loop: capture → VAD → ASR → preprocessing → emit."""
        self._running = True
        try:
            self._audio_capture.start(callback=lambda chunk: self._audio_queue.put(chunk))
        except AudioCaptureError as exc:
            logger.error("Failed to start audio capture: %s", exc)
            self.error_occurred.emit(str(exc))
            self._running = False
            return

        while self._running:
            try:
                chunk = self._audio_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            try:
                segments = self._vad.process_chunk(chunk)
            except Exception as exc:
                logger.error("VAD error: %s", exc)
                self.error_occurred.emit(str(exc))
                continue

            if not segments:
                continue

            for segment in segments:
                try:
                    text = self._asr.transcribe(
                        segment.samples, sample_rate=self._config.sample_rate
                    )
                except ASRError as exc:
                    logger.warning("ASR error (skipping segment): %s", exc)
                    continue

                if not text:
                    continue

                try:
                    analysis = self._preprocessing.process(text)
                except Exception as exc:
                    logger.error("Preprocessing error: %s", exc)
                    self.error_occurred.emit(str(exc))
                    continue

                result = SentenceResult(
                    japanese_text=text,
                    chinese_translation=None,
                    explanation=None,
                    analysis=analysis,
                )
                self.sentence_ready.emit(result)

        self._cleanup()

    def stop(self) -> None:
        """Signal the pipeline to stop and wait for thread to exit."""
        self._running = False
        self.quit()
        self.wait(5000)

    def _cleanup(self) -> None:
        """Clean up all resources after run loop exits."""
        try:
            self._audio_capture.stop()
        except Exception as exc:
            logger.warning("Error stopping audio capture: %s", exc)
        try:
            self._vad.reset()
        except Exception as exc:
            logger.warning("Error resetting VAD: %s", exc)
        try:
            self._asr.unload()
        except Exception as exc:
            logger.warning("Error unloading ASR: %s", exc)
