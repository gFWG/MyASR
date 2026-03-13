"""VAD worker thread: consumes audio chunks, emits SpeechSegment objects."""

import logging
import queue
import time
import uuid
from typing import Any

import numpy as np
from PySide6.QtCore import QThread, Signal

from src.models import AudioSegment
from src.pipeline.perf import StageTimer
from src.pipeline.types import SpeechSegment
from src.vad.silero import SileroVAD

logger = logging.getLogger(__name__)


class VadWorker(QThread):
    """QThread that consumes raw audio chunks and emits speech segments via VAD.

    Reads from ``audio_queue``, runs each chunk through Silero VAD, converts
    detected ``AudioSegment`` objects into ``SpeechSegment`` pipeline types,
    and places them into ``segment_queue``.  If ``segment_queue`` is full the
    segment is dropped and a warning is logged — the worker never blocks.

    Signals:
        error_occurred: Emitted with an error message string when an exception
            is caught inside the run loop.  The worker continues after emitting.
        segment_ready: Emitted with each ``SpeechSegment`` produced by VAD.

    Args:
        audio_queue: Input queue of raw float32 audio chunks (16 kHz, mono).
        segment_queue: Output queue of ``SpeechSegment`` objects for downstream
            ASR processing.  The caller creates and owns this queue.
        vad: Initialised ``SileroVAD`` instance (injected, not created here).
        config: Worker configuration dict.  Recognised keys:
            ``"sample_rate"`` (int, default 16000) — sample rate passed into
            ``SpeechSegment``; ``"segment_queue_maxsize"`` (int, default 20) —
            informational only, the queue is passed in already created.
    """

    error_occurred = Signal(str)
    segment_ready = Signal(object)

    def __init__(
        self,
        audio_queue: queue.Queue[np.ndarray],
        segment_queue: queue.Queue[SpeechSegment],
        vad: SileroVAD,
        config: dict[str, Any],
    ) -> None:
        super().__init__()
        self._audio_queue = audio_queue
        self._segment_queue = segment_queue
        self._vad = vad
        self._config = config
        self._running: bool = False

    def run(self) -> None:
        """Main VAD processing loop.

        Reads audio chunks from ``_audio_queue`` with a 100ms timeout so the
        loop remains responsive to ``stop()`` without busy-waiting.  Each chunk
        is timed via ``StageTimer`` and passed to the VAD.  Completed speech
        segments are converted to ``SpeechSegment`` and placed non-blockingly
        into ``_segment_queue``.
        """
        self._running = True
        sample_rate: int = self._config.get("sample_rate", 16000)

        while self._running:
            try:
                chunk = self._audio_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            try:
                with StageTimer("vad_process") as _timer:
                    result: list[AudioSegment] | None = self._vad.process_chunk(chunk)
            except Exception as exc:
                logger.error("VAD process_chunk failed: %s", exc, exc_info=True)
                self.error_occurred.emit(str(exc))
                continue

            if result is None:
                continue

            for audio_segment in result:
                speech_segment = SpeechSegment(
                    audio=audio_segment.samples,
                    sample_rate=sample_rate,
                    timestamp=time.monotonic(),
                    segment_id=str(uuid.uuid4()),
                )
                try:
                    self._segment_queue.put_nowait(speech_segment)
                    self.segment_ready.emit(speech_segment)
                except queue.Full:
                    logger.warning(
                        "Segment queue full — dropping speech segment (duration=%.3fs)",
                        audio_segment.duration_sec,
                    )

    def stop(self) -> None:
        """Signal the VAD worker to stop and wait up to 2 seconds for it to finish."""
        self._running = False
        self.quit()
        self.wait(2000)

    def update_vad_params(
        self,
        threshold: float | None = None,
        min_silence_ms: int | None = None,
        min_speech_ms: int | None = None,
    ) -> None:
        """Update VAD parameters dynamically.

        Thread-safe: Can be called while the worker is running.
        Changes take effect immediately for subsequent audio chunks.

        Args:
            threshold: New speech probability threshold (0.0–1.0).
            min_silence_ms: New minimum silence duration in ms.
            min_speech_ms: New minimum speech duration in ms.
        """
        self._vad.update_params(
            threshold=threshold,
            min_silence_ms=min_silence_ms,
            min_speech_ms=min_speech_ms,
        )
