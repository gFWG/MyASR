"""LLM worker thread: consumes ASRResult objects, emits TranslationResult objects."""

import asyncio
import logging
import queue
from typing import Any

from PySide6.QtCore import QThread, Signal

from src.db.repository import LearningRepository
from src.exceptions import LLMTimeoutError, LLMUnavailableError
from src.llm.ollama_client import AsyncOllamaClient
from src.pipeline.perf import StageTimer
from src.pipeline.types import ASRResult, LLMResult

logger = logging.getLogger(__name__)


class LlmWorker(QThread):
    """QThread that consumes ASRResult objects and emits TranslationResult objects via LLM.

    Reads from ``text_queue``, calls the async LLM client for each item, and places
    results non-blockingly into ``result_queue``.  On ``LLMTimeoutError`` or
    ``LLMUnavailableError``, emits a ``TranslationResult`` with ``translation=None``
    and continues processing — no retry logic, no crash.

    Signals:
        error_occurred: Emitted with an error message string when an unexpected
            exception is caught inside the run loop.
        translation_ready: Emitted with each ``TranslationResult`` produced.

    Args:
        text_queue: Input queue of ``ASRResult`` objects from ASR stage.
        result_queue: Output queue of ``TranslationResult`` objects for downstream.
        llm_client: Initialised async LLM client (injected, not created here).
        db_path: Path to the SQLite database file, or None to skip DB writes.
            A fresh ``LearningRepository`` is created inside ``run()`` so that
            the sqlite3 connection is owned by this thread (thread-affinity rule).
        config: Worker configuration dict (currently unused, reserved for future use).
    """

    error_occurred = Signal(str)
    translation_ready = Signal(object)

    def __init__(
        self,
        text_queue: queue.Queue[ASRResult],
        result_queue: queue.Queue[LLMResult],
        llm_client: AsyncOllamaClient,
        db_path: str | None = None,
        config: dict[str, Any] | None = None,
    ) -> None:
        super().__init__()
        self._text_queue = text_queue
        self._result_queue = result_queue
        self._llm_client = llm_client
        self._db_path = db_path
        self._db_repo: LearningRepository | None = None
        self._config: dict[str, Any] = config if config is not None else {}
        self._running: bool = False

    def run(self) -> None:
        """Main LLM processing loop.

        Creates a fresh asyncio event loop for this thread, runs the async
        processing coroutine until stopped, then closes the loop in a finally block.
        A fresh LearningRepository is created here (in the worker thread) to
        satisfy sqlite3 thread-affinity requirements.
        """
        self._db_repo = LearningRepository(self._db_path) if self._db_path else None
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._process_loop())
        finally:
            tasks = [t for t in asyncio.all_tasks(loop) if not t.done()]
            loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
            loop.run_until_complete(self._llm_client.close())
            if self._db_repo is not None:
                self._db_repo.close()
            loop.close()

    async def _process_loop(self) -> None:
        """Async coroutine: dequeue ASRResults and translate them one by one."""
        self._running = True
        while self._running:
            try:
                asr_result = self._text_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            translation_result = await self._translate_one(asr_result)
            self._dispatch(translation_result)

    async def _translate_one(self, asr_result: ASRResult) -> LLMResult:
        """Call the LLM client and build a TranslationResult.

        Returns a result with ``translation=None`` on LLM errors instead of raising.
        """
        translation: str | None = None
        explanation: str | None = None

        with StageTimer("llm_translate") as timer:
            try:
                translation, explanation = await self._llm_client.translate_async(
                    asr_result.text, ""
                )
            except LLMTimeoutError as exc:
                logger.warning("LLM timeout for segment %s: %s", asr_result.segment_id, exc)
            except LLMUnavailableError as exc:
                logger.warning("LLM unavailable for segment %s: %s", asr_result.segment_id, exc)

        elapsed_ms = timer.result.elapsed_ms

        result = LLMResult(
            translation=translation,
            explanation=explanation,
            segment_id=asr_result.segment_id,
            elapsed_ms=elapsed_ms,
        )

        try:
            if self._db_repo is not None:
                if asr_result.db_row_id is not None:
                    self._db_repo.update_translation(
                        asr_result.db_row_id,
                        translation,
                        explanation,
                    )
                else:
                    logger.warning(
                        "No db_row_id on asr_result %s, skipping DB update",
                        asr_result.segment_id,
                    )
        except Exception as exc:  # noqa: BLE001  # DB errors must not crash the LLM thread
            logger.warning(
                "DB update_translation failed for segment %s: %s",
                asr_result.segment_id,
                exc,
            )

        return result

    def _dispatch(self, result: LLMResult) -> None:
        """Emit signal and put result into result_queue non-blockingly."""
        self.translation_ready.emit(result)
        try:
            self._result_queue.put_nowait(result)
        except queue.Full:
            logger.warning(
                "Result queue full — dropping TranslationResult for segment %s",
                result.segment_id,
            )

    def update_client(self, client: AsyncOllamaClient) -> None:
        """Replace the LLM client with a new one (hot-reload on config change)."""
        self._llm_client = client

    def stop(self) -> None:
        """Signal the LLM worker to stop and wait up to 2 seconds for it to finish."""
        self._running = False
        self.quit()
        self.wait(2000)
