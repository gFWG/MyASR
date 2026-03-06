"""PipelineWorker: QThread that runs the Audio→VAD→ASR→Preprocessing→LLM pipeline."""

import logging
import queue
import sqlite3
from typing import Any

import numpy as np
from PySide6.QtCore import QThread, Signal

from src.analysis.pipeline import PreprocessingPipeline
from src.asr.qwen_asr import QwenASR
from src.audio.capture import AudioCapture
from src.config import AppConfig
from src.db.models import HighlightGrammar, HighlightVocab, SentenceRecord, SentenceResult
from src.db.repository import LearningRepository
from src.exceptions import ASRError, AudioCaptureError
from src.llm.ollama_client import OllamaClient
from src.vad.silero import SileroVAD

logger = logging.getLogger(__name__)


class PipelineWorker(QThread):
    """QThread that runs the Audio→VAD→ASR→Preprocessing→LLM pipeline.

    Emits sentence_ready with a SentenceResult when transcription + analysis complete.
    Emits error_occurred with an error string for fatal/non-fatal errors.
    """

    sentence_ready = Signal(object)  # emits SentenceResult
    error_occurred = Signal(str)

    def __init__(
        self, config: AppConfig, db_conn: sqlite3.Connection | None = None, parent: Any = None
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._audio_capture = AudioCapture(sample_rate=config.sample_rate)
        self._vad = SileroVAD(sample_rate=config.sample_rate)
        self._asr = QwenASR()
        self._preprocessing = PreprocessingPipeline(config)
        # Limit queue to ~16s of audio (500 chunks × 512 samples @ 16kHz)
        # to prevent unbounded memory growth when ASR is slower than capture.
        self._audio_queue: queue.Queue[np.ndarray] = queue.Queue(maxsize=500)
        self._running = False
        self._llm = OllamaClient(config)
        self._repo: LearningRepository | None = (
            LearningRepository(db_conn) if db_conn is not None else None
        )

    def _enqueue_audio(self, chunk: np.ndarray) -> None:
        """Enqueue an audio chunk, dropping it if the queue is full."""
        try:
            self._audio_queue.put_nowait(chunk)
        except queue.Full:
            logger.warning("Audio queue full — dropping chunk (ASR may be falling behind)")

    def run(self) -> None:
        """Main thread loop: capture → VAD → ASR → preprocessing → LLM → emit."""
        self._running = True
        try:
            self._audio_capture.start(callback=self._enqueue_audio)
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

                translation, explanation = self._llm.translate(text)

                result = SentenceResult(
                    japanese_text=text,
                    chinese_translation=translation,
                    explanation=explanation,
                    analysis=analysis,
                )
                self.sentence_ready.emit(result)

                if self._repo is not None:
                    try:
                        record, vocab_recs, grammar_recs = self._to_db_records(result)
                        self._repo.insert_sentence(record, vocab_recs, grammar_recs)
                    except Exception:
                        logger.exception("Failed to write sentence to database")

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
        while not self._audio_queue.empty():
            try:
                self._audio_queue.get_nowait()
            except queue.Empty:
                break
        try:
            self._vad.reset()
        except Exception as exc:
            logger.warning("Error resetting VAD: %s", exc)
        try:
            self._asr.unload()
        except Exception as exc:
            logger.warning("Error unloading ASR: %s", exc)

    def _to_db_records(
        self, result: SentenceResult
    ) -> tuple[SentenceRecord, list[HighlightVocab], list[HighlightGrammar]]:
        """Convert a SentenceResult into DB record types for LearningRepository."""
        record = SentenceRecord(
            id=None,
            japanese_text=result.japanese_text,
            chinese_translation=result.chinese_translation,
            explanation=result.explanation,
            source_context=None,
            created_at=result.created_at.isoformat(),
        )
        vocab_recs = [
            HighlightVocab(
                id=None,
                sentence_id=0,
                surface=vh.surface,
                lemma=vh.lemma,
                pos=vh.pos,
                jlpt_level=vh.jlpt_level,
                is_beyond_level=True,
                tooltip_shown=False,
            )
            for vh in result.analysis.vocab_hits
        ]
        grammar_recs = [
            HighlightGrammar(
                id=None,
                sentence_id=0,
                rule_id=gh.rule_id,
                pattern=gh.matched_text,
                jlpt_level=gh.jlpt_level,
                confidence_type=gh.confidence_type,
                description=gh.description,
                is_beyond_level=True,
                tooltip_shown=False,
            )
            for gh in result.analysis.grammar_hits
        ]
        return record, vocab_recs, grammar_recs
