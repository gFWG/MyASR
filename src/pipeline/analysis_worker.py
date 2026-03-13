"""Analysis worker thread: consumes ASRResult objects, emits SentenceResult objects."""

import logging
import queue
from datetime import datetime
from typing import Any

from PySide6.QtCore import QThread, Signal

from src.models import SentenceResult
from src.pipeline.types import ASRResult

logger = logging.getLogger(__name__)


class AnalysisWorker(QThread):
    """QThread that consumes ASRResult objects, runs analysis, emits SentenceResult.

    Reads from ``text_queue``, processes each result through ``PreprocessingPipeline``,
    and emits ``sentence_ready`` with the resulting ``SentenceResult``.

    Signals:
        sentence_ready: Emitted with each ``SentenceResult`` produced by analysis.
        error_occurred: Emitted with an error message string when an exception is caught
            inside the run loop.  The worker continues after emitting.

    Args:
        text_queue: Input queue of ``ASRResult`` objects from ASR worker.
        analysis_pipeline: Initialised ``PreprocessingPipeline`` instance (injected).
        config: Worker configuration dict (currently unused but reserved for future options).
    """

    sentence_ready = Signal(object)
    error_occurred = Signal(str)

    def __init__(
        self,
        text_queue: queue.Queue[ASRResult],
        analysis_pipeline: Any,
        config: dict[str, Any],
    ) -> None:
        super().__init__()
        self._text_queue = text_queue
        self._analysis_pipeline = analysis_pipeline
        self._config = config
        self._running: bool = False

    def run(self) -> None:
        """Main analysis loop.

        Reads ``ASRResult`` objects from ``_text_queue`` in a loop with a 0.1 s timeout.
        Each result is analysed and emitted as a ``SentenceResult`` via ``sentence_ready``.
        """
        self._running = True

        while self._running:
            try:
                asr_result = self._text_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            try:
                self._process_one(asr_result)
            except Exception as exc:  # noqa: BLE001  # broad catch — must not crash worker
                logger.error("Analysis failed for segment %s: %s", asr_result.segment_id, exc)
                self.error_occurred.emit(str(exc))

    def _process_one(self, asr_result: ASRResult) -> None:
        """Process a single ASRResult: analyse and emit.

        Args:
            asr_result: The transcription result to process.
        """

        analysis = self._analysis_pipeline.process(asr_result.text)

        # Emit SentenceResult
        sentence_result = SentenceResult(
            japanese_text=asr_result.text,
            analysis=analysis,
            created_at=datetime.now(),
        )
        self.sentence_ready.emit(sentence_result)
        logger.debug(
            "Analysis complete for segment %s: vocab=%d, grammar=%d",
            asr_result.segment_id,
            len(analysis.vocab_hits),
            len(analysis.grammar_hits),
        )

    def stop(self) -> None:
        """Signal the analysis worker to stop and wait up to 2 seconds for it to finish."""
        self._running = False
        self.quit()
        self.wait(2000)
