"""Analysis worker thread: consumes ASRResult objects, emits SentenceResult objects."""

import logging
import queue
from datetime import datetime
from typing import Any

from PySide6.QtCore import QThread, Signal

from src.db.models import HighlightGrammar, HighlightVocab, SentenceRecord, SentenceResult
from src.db.repository import LearningRepository
from src.pipeline.types import ASRResult

logger = logging.getLogger(__name__)


class AnalysisWorker(QThread):
    """QThread that consumes ASRResult objects, runs analysis, persists to DB, emits
    SentenceResult.

    Reads from ``text_queue``, processes each result through ``PreprocessingPipeline``,
    persists the sentence and highlights to SQLite via ``LearningRepository``, and emits
    ``sentence_ready`` with the resulting ``SentenceResult``.

    Signals:
        sentence_ready: Emitted with each ``SentenceResult`` produced by analysis.
        error_occurred: Emitted with an error message string when an exception is caught
            inside the run loop.  The worker continues after emitting.

    Args:
        text_queue: Input queue of ``ASRResult`` objects from ASR worker.
        analysis_pipeline: Initialised ``PreprocessingPipeline`` instance (injected).
        db_path: Filesystem path (or ``":memory:"``) to the SQLite database.
        config: Worker configuration dict (currently unused but reserved for future options).
    """

    sentence_ready = Signal(object)
    error_occurred = Signal(str)

    def __init__(
        self,
        text_queue: queue.Queue[ASRResult],
        analysis_pipeline: Any,
        db_path: str,
        config: dict[str, Any],
    ) -> None:
        super().__init__()
        self._text_queue = text_queue
        self._analysis_pipeline = analysis_pipeline
        self._db_path = db_path
        self._config = config
        self._running: bool = False

    def run(self) -> None:
        """Main analysis loop.

        Creates a thread-local ``LearningRepository`` (DB connections must be opened in the
        thread that uses them), then reads ``ASRResult`` objects from ``_text_queue`` in a
        loop with a 0.1 s timeout.  Each result is analysed, persisted, and emitted as a
        ``SentenceResult`` via ``sentence_ready``.
        """
        # Thread-local DB connection (thread-safety: must be created in this thread)
        db_repo = LearningRepository(db_path=self._db_path)
        self._running = True

        try:
            while self._running:
                try:
                    asr_result = self._text_queue.get(timeout=0.1)
                except queue.Empty:
                    continue

                try:
                    self._process_one(asr_result, db_repo)
                except Exception as exc:  # noqa: BLE001  # broad catch — must not crash worker
                    logger.error("Analysis failed for segment %s: %s", asr_result.segment_id, exc)
                    self.error_occurred.emit(str(exc))
        finally:
            db_repo.close()

    def _process_one(self, asr_result: ASRResult, db_repo: LearningRepository) -> None:
        """Process a single ASRResult: analyse, persist, emit.

        Args:
            asr_result: The transcription result to process.
            db_repo: Thread-local repository for DB persistence.
        """

        analysis = self._analysis_pipeline.process(asr_result.text)

        # Build SentenceRecord — created_at as ISO string
        record = SentenceRecord(
            id=None,
            japanese_text=asr_result.text,
            source_context=asr_result.segment_id,
            created_at=datetime.now().isoformat(),
        )

        # Build highlight lists from AnalysisResult
        vocab_highlights = [
            HighlightVocab(
                id=None,
                sentence_id=0,  # will be assigned by DB; placeholder
                surface=hit.surface,
                lemma=hit.lemma,
                pos=hit.pos,
                jlpt_level=hit.jlpt_level,
                is_beyond_level=hit.jlpt_level > hit.user_level,
                tooltip_shown=False,
                vocab_id=hit.vocab_id,
                pronunciation=hit.pronunciation,
                definition=hit.definition,
            )
            for hit in analysis.vocab_hits
        ]

        grammar_highlights = [
            HighlightGrammar(
                id=None,
                sentence_id=0,  # will be assigned by DB; placeholder
                rule_id=hit.rule_id,
                pattern=hit.word,
                word=hit.word,
                jlpt_level=hit.jlpt_level,
                description=hit.description,
                is_beyond_level=True,  # grammar hits are always beyond user level by definition
                tooltip_shown=False,
            )
            for hit in analysis.grammar_hits
        ]

        # Persist and get auto-assigned IDs
        sentence_id, vocab_ids, grammar_ids = db_repo.insert_sentence(
            record, vocab_highlights, grammar_highlights
        )

        # Emit SentenceResult
        sentence_result = SentenceResult(
            japanese_text=asr_result.text,
            analysis=analysis,
            created_at=datetime.now(),
            sentence_id=sentence_id,
            highlight_vocab_ids=vocab_ids,
            highlight_grammar_ids=grammar_ids,
        )
        self.sentence_ready.emit(sentence_result)
        logger.debug(
            "Analysis complete for segment %s: sentence_id=%d, vocab=%d, grammar=%d",
            asr_result.segment_id,
            sentence_id,
            len(vocab_ids),
            len(grammar_ids),
        )

    def stop(self) -> None:
        """Signal the analysis worker to stop and wait up to 2 seconds for it to finish."""
        self._running = False
        self.quit()
        self.wait(2000)
