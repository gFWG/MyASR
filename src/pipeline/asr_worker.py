"""ASR worker thread: consumes SpeechSegment objects, emits ASRResult objects."""

import logging
import queue
import time
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QThread, Signal

from src.asr.qwen_asr import QwenASR
from src.exceptions import ASRError
from src.pipeline.types import ASRResult, SpeechSegment
from src.profiling.timer import StageTimer

if TYPE_CHECKING:
    from src.profiling.profiler import PipelineProfiler

logger = logging.getLogger(__name__)


class AsrWorker(QThread):
    """QThread that consumes SpeechSegments and emits ASRResult objects via batched ASR.

    Reads from ``segment_queue``, collects segments into a batch, and flushes
    the batch to ``QwenASR.transcribe_batch()`` when either the batch is full
    (``asr_batch_size``) or ``asr_flush_timeout_ms`` milliseconds have elapsed
    since the last flush.  Results are placed non-blockingly into ``text_queue``
    and emitted via ``asr_ready``.

    Signals:
        error_occurred: Emitted with an error message string when an exception
            is caught inside the run loop.  The worker continues after emitting.
        asr_ready: Emitted with each ``ASRResult`` produced by a batch call.

    Args:
        segment_queue: Input queue of ``SpeechSegment`` objects from VAD.
        text_queue: Output queue of ``ASRResult`` objects for downstream stages.
        asr: Initialised ``QwenASR`` instance (injected, not created here).
        config: Worker configuration dict.  Recognised keys:
            ``"asr_batch_size"`` (int, default 4) — number of segments per batch;
            ``"asr_flush_timeout_ms"`` (int, default 500) — max ms before flushing
            a partial batch.
    """

    error_occurred = Signal(str)
    asr_ready = Signal(object)

    def __init__(
        self,
        segment_queue: queue.Queue[SpeechSegment],
        text_queue: queue.Queue[ASRResult],
        asr: QwenASR,
        config: dict[str, Any],
        profiler: "PipelineProfiler | None" = None,
    ) -> None:
        super().__init__()
        self._segment_queue = segment_queue
        self._text_queue = text_queue
        self._asr = asr
        self._config = config
        self._profiler = profiler
        self._running: bool = False

    def run(self) -> None:
        """Main ASR batch processing loop.

        Collects segments from ``_segment_queue`` into a batch and flushes when
        the batch reaches ``asr_batch_size`` or the flush timeout elapses.  Each
        batch call is timed via ``StageTimer``.  Results are emitted and placed
        into ``_text_queue`` non-blockingly.
        """
        self._running = True
        batch_size: int = self._config.get("asr_batch_size", 4)
        flush_timeout_ms: float = float(self._config.get("asr_flush_timeout_ms", 500))
        flush_timeout_s = flush_timeout_ms / 1000.0

        batch: list[SpeechSegment] = []
        last_flush = time.monotonic()

        while self._running:
            elapsed_since_flush = time.monotonic() - last_flush
            should_flush = len(batch) >= batch_size or (
                batch and elapsed_since_flush >= flush_timeout_s
            )

            if should_flush:
                self._flush_batch(batch)
                batch = []
                last_flush = time.monotonic()
                continue

            try:
                seg = self._segment_queue.get(timeout=0.05)
                batch.append(seg)
            except queue.Empty:
                pass  # expected: no segment yet, will flush on timeout if batch is non-empty

        if batch:
            self._flush_batch(batch)

    def _flush_batch(self, batch: list[SpeechSegment]) -> None:
        """Run a batch through ASR and dispatch each result."""
        with StageTimer("asr_batch", self._profiler) as timer:
            try:
                results = self._asr.transcribe_batch(batch)
            except ASRError as exc:
                logger.error("ASR batch failed: %s", exc, exc_info=True)
                self.error_occurred.emit(str(exc))
                return
            except Exception as exc:
                logger.error("Unexpected ASR error: %s", exc, exc_info=True)
                self.error_occurred.emit(str(exc))
                return

        logger.debug(
            "ASR batch: %d in → %d results in %.1f ms",
            len(batch),
            len(results),
            timer.elapsed_ms,
        )

        for result in results:
            self.asr_ready.emit(result)
            try:
                self._text_queue.put_nowait(result)
            except queue.Full:
                logger.warning(
                    "Text queue full — dropping ASRResult for segment %s",
                    result.segment_id,
                )

    def stop(self) -> None:
        """Signal the ASR worker to stop and wait up to 2 seconds for it to finish."""
        self._running = False
        self.quit()
        self.wait(2000)
