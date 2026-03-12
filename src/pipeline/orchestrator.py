"""Pipeline orchestrator: coordinates VadWorker and AsrWorker.

The orchestrator is a plain Python class (not a QThread).  It owns the
inter-stage queues, instantiates the worker threads, and wires their
signals to caller-provided callbacks via :meth:`connect_signals`.
"""

import logging
import queue
from collections.abc import Callable
from typing import Any

import numpy as np

from src.analysis.pipeline import PreprocessingPipeline
from src.asr.qwen_asr import QwenASR
from src.audio.backends import WasapiLoopbackCapture
from src.config import AppConfig
from src.db.models import SentenceResult
from src.pipeline.analysis_worker import AnalysisWorker
from src.pipeline.asr_worker import AsrWorker
from src.pipeline.types import ASRResult, SpeechSegment
from src.pipeline.vad_worker import VadWorker
from src.vad.silero import SileroVAD

logger = logging.getLogger(__name__)


class PipelineOrchestrator:
    """Coordinator that wires VadWorker → AsrWorker via queues.

    This class is NOT a thread.  It creates the inter-stage queues, instantiates
    worker threads with injected models, and exposes a simple :meth:`start` /
    :meth:`stop` lifecycle and a :meth:`put_audio` method for feeding audio
    chunks into the pipeline.

    Args:
        config: Pipeline configuration dict.  Recognised keys mirror
            ``AppConfig`` fields plus worker-specific overrides:
            ``"sample_rate"`` (int, default 16000),
            ``"asr_batch_size"`` (int, default 4),
            ``"asr_flush_timeout_ms"`` (int, default 500),
            ``"db_path"`` (str, default ``":memory:"``).
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self._config = config

        # ── Inter-stage queues ──────────────────────────────────────────────
        self._audio_queue: queue.Queue[np.ndarray] = queue.Queue(maxsize=1000)
        self._segment_queue: queue.Queue[SpeechSegment] = queue.Queue(maxsize=20)
        self._text_queue: queue.Queue[ASRResult] = queue.Queue(maxsize=50)

        # ── Models (heavy GPU objects — created at construction time) ───────
        vad_model = SileroVAD(
            threshold=config.get("vad_threshold", 0.5),
            min_silence_ms=config.get("vad_min_silence_ms", 300),
            min_speech_ms=config.get("vad_min_speech_ms", 400),
            sample_rate=config.get("sample_rate", 16000),
        )

        asr_model = QwenASR(model_path=config.get("model_path"))

        # ── Workers ─────────────────────────────────────────────────────────
        self._vad_worker = VadWorker(
            audio_queue=self._audio_queue,
            segment_queue=self._segment_queue,
            vad=vad_model,
            config=config,
        )
        self._asr_worker = AsrWorker(
            segment_queue=self._segment_queue,
            text_queue=self._text_queue,
            asr=asr_model,
            config=config,
        )

        # ── Analysis worker (ASRResult → SentenceResult with DB persistence) ──
        # PreprocessingPipeline no longer needs AppConfig - filtering happens at display time.
        analysis_pipeline = PreprocessingPipeline()
        self._analysis_worker = AnalysisWorker(
            text_queue=self._text_queue,
            analysis_pipeline=analysis_pipeline,
            db_path=config.get("db_path", ":memory:"),
            config=config,
        )

        # ── Audio capture (started in start(), stopped in stop()) ────────────
        # Each call to start() re-starts capture; WasapiLoopbackCapture feeds
        # raw PCM chunks into put_audio(), which enqueues them for VadWorker.
        self._capture = WasapiLoopbackCapture(
            sample_rate=config.get("sample_rate", 16000),
        )

        self._running: bool = False

        logger.info("PipelineOrchestrator initialised")

    # ── Lifecycle ────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start audio capture then all worker threads (capture → VAD → ASR)."""
        logger.info("Starting audio capture and pipeline workers: capture → VAD → ASR")
        self._capture.start(callback=self.put_audio)
        self._vad_worker.start()
        self._asr_worker.start()
        self._analysis_worker.start()
        self._running = True

    def stop(self) -> None:
        """Stop all worker threads then audio capture (ASR → VAD → capture).

        Each worker is stopped then waited on for up to 3 seconds to allow
        in-flight items to drain gracefully before the upstream worker stops.
        Audio capture is stopped last so any in-flight chunks can still be drained.
        """
        logger.info("Stopping pipeline workers: analysis → ASR → VAD → capture")
        self._analysis_worker.stop()
        self._analysis_worker.wait(3000)
        self._asr_worker.stop()
        self._asr_worker.wait(3000)
        self._vad_worker.stop()
        self._vad_worker.wait(3000)
        self._capture.stop()
        self._running = False

    # ── Audio ingress ────────────────────────────────────────────────────────

    def put_audio(self, chunk: np.ndarray) -> None:
        """Feed a raw audio chunk into the pipeline.

        The chunk is placed non-blockingly into the audio queue.  If the queue
        is full the chunk is dropped and a warning is logged — the caller is
        never blocked.

        Args:
            chunk: 1-D float32 numpy array of audio samples at 16 kHz.
        """
        try:
            self._audio_queue.put_nowait(chunk)
        except queue.Full:
            logger.warning(
                "Audio queue full — dropping audio chunk (len=%d samples)",
                len(chunk),
            )

    # ── Signal wiring ────────────────────────────────────────────────────────

    def connect_signals(
        self,
        on_asr_ready: Callable[[ASRResult], None],
        on_sentence_ready: Callable[[SentenceResult], None] | None = None,
    ) -> None:
        """Connect worker output signals to caller-provided callbacks.

        Args:
            on_asr_ready: Callable connected to ``AsrWorker.asr_ready``.
                Receives an ``ASRResult`` object.
            on_sentence_ready: Optional callable connected to
                ``AnalysisWorker.sentence_ready``.  Receives a
                ``SentenceResult`` object.
        """
        self._asr_worker.asr_ready.connect(on_asr_ready)
        if on_sentence_ready is not None:
            self._analysis_worker.sentence_ready.connect(on_sentence_ready)

    # ── Signal properties ────────────────────────────────────────────────────

    @property
    def asr_ready(self) -> Any:  # PySide6 Signal has no usable stub type
        """The ``asr_ready`` signal forwarded from :class:`AsrWorker`."""
        return self._asr_worker.asr_ready

    @property
    def error_occurred(self) -> list[Any]:  # PySide6 Signal has no usable stub type
        """List of ``error_occurred`` signals from all workers.

        Callers can iterate and connect each signal to a single handler:

        .. code-block:: python

            for sig in orchestrator.error_occurred:
                sig.connect(my_error_handler)
        """
        return [
            self._vad_worker.error_occurred,
            self._asr_worker.error_occurred,
            self._analysis_worker.error_occurred,
        ]

    # ── Hot-reload config ─────────────────────────────────────────────────────

    def on_config_changed(self, config: AppConfig) -> None:
        """Apply live config changes to pipeline components.

        Currently supports hot-reloading VAD parameters:
        - vad_threshold
        - vad_min_silence_ms
        - vad_min_speech_ms

        Note: Some config changes (sample_rate, db_path, model_path) require
        a full pipeline restart and cannot be hot-reloaded.

        Args:
            config: Updated application configuration.
        """
        # Update internal config dict
        self._config["vad_threshold"] = config.vad_threshold
        self._config["vad_min_silence_ms"] = config.vad_min_silence_ms
        self._config["vad_min_speech_ms"] = config.vad_min_speech_ms

        # Update VAD parameters dynamically
        self._vad_worker.update_vad_params(
            threshold=config.vad_threshold,
            min_silence_ms=config.vad_min_silence_ms,
            min_speech_ms=config.vad_min_speech_ms,
        )

        logger.info(
            "PipelineOrchestrator config updated: threshold=%.2f, min_silence=%dms, "
            "min_speech=%dms",
            config.vad_threshold,
            config.vad_min_silence_ms,
            config.vad_min_speech_ms,
        )
