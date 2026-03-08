"""Pipeline data types."""

from dataclasses import dataclass, field

import numpy as np


@dataclass(frozen=True, slots=True)
class SpeechSegment:
    """Audio segment extracted by VAD for ASR processing.

    Attributes:
        audio: Raw float32 audio samples at 16kHz.
        sample_rate: Sample rate in Hz (typically 16000).
        timestamp: Unix timestamp when segment was captured.
        segment_id: Unique identifier for this segment (uuid4 string).
    """

    audio: np.ndarray
    sample_rate: int
    timestamp: float
    segment_id: str


@dataclass(frozen=True, slots=True)
class ASRResult:
    """Result from ASR transcription.

    Attributes:
        text: Transcribed text.
        segment_id: ID of the audio segment that was transcribed.
        elapsed_ms: Processing time in milliseconds.
        db_row_id: Database row ID assigned after ``insert_partial()``, or None
            if the record has not been persisted yet.
    """

    text: str
    segment_id: str
    elapsed_ms: float
    db_row_id: int | None = field(default=None)


@dataclass(frozen=True, slots=True)
class TranslationResult:
    """Result from LLM translation.

    Attributes:
        translation: Translated text (e.g., Chinese), or None if translation failed.
        explanation: Grammar/vocab explanation, or None if not generated.
        segment_id: ID of the segment that was translated.
        elapsed_ms: Processing time in milliseconds.
    """

    translation: str | None
    explanation: str | None
    segment_id: str
    elapsed_ms: float


@dataclass(frozen=True, slots=True)
class PipelineStageMetrics:
    """Metrics for a single pipeline stage execution.

    Attributes:
        stage: Name of the pipeline stage (e.g., 'vad', 'asr', 'translation').
        start_time: Start time in seconds (from time.perf_counter()).
        end_time: End time in seconds (from time.perf_counter()).
        elapsed_ms: Processing time in milliseconds.
    """

    stage: str
    start_time: float
    end_time: float
    elapsed_ms: float


__all__ = ["ASRResult", "PipelineStageMetrics", "SpeechSegment", "TranslationResult"]
