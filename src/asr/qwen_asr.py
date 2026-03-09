"""Qwen3-ASR-0.6B speech recognition wrapper."""

import gc
import logging
import time
from typing import Any

import fugashi
import numpy as np
import torch

from src.exceptions import ASRError, ModelLoadError
from src.pipeline.types import ASRResult, SpeechSegment

logger = logging.getLogger(__name__)

_tagger = fugashi.Tagger()


class QwenASR:
    """ASR wrapper for the Qwen3-ASR-0.6B model.

    Loads the model lazily and provides a simple transcribe interface for
    Japanese audio input represented as NumPy arrays.

    Example:
        asr = QwenASR()
        text = asr.transcribe(audio_samples, sample_rate=16000)
    """

    def __init__(self, model_path: str | None = None) -> None:
        """Load the Qwen3-ASR model from pretrained weights.

        Args:
            model_path: HuggingFace model ID or local path.
                Defaults to "Qwen/Qwen3-ASR-0.6B".

        Raises:
            ModelLoadError: If the model cannot be loaded for any reason.
        """
        self._model_path = model_path or "Qwen/Qwen3-ASR-0.6B"
        self._model: Any | None = None
        try:
            from qwen_asr import Qwen3ASRModel as _Qwen3ASRModel

            self._model = _Qwen3ASRModel.from_pretrained(
                self._model_path,
                dtype=torch.bfloat16,
                device_map="cuda:0",
                max_inference_batch_size=4,
                max_new_tokens=256,
            )
            logger.info("Loaded QwenASR model from %s", self._model_path)
        except Exception as exc:
            raise ModelLoadError(f"Failed to load ASR model: {exc}") from exc

    def transcribe(self, audio: np.ndarray, sample_rate: int = 16000) -> str:
        """Transcribe a Japanese audio segment.

        Args:
            audio: 1-D float32 NumPy array of audio samples.
            sample_rate: Sample rate of the audio in Hz. Defaults to 16000.

        Returns:
            Transcribed text with leading/trailing whitespace stripped, or an
            empty string if the audio is too short (< 0.1 s at 16 kHz).

        Raises:
            ASRError: If the model is not loaded or transcription fails.
        """
        if self._model is None:
            raise ASRError("ASR model not loaded")
        if len(audio) < 1600:  # < 0.1s at 16kHz
            return ""
        try:
            results = self._model.transcribe(audio=(audio, sample_rate), language="Japanese")
            return str(results[0].text).strip()
        except Exception as exc:
            raise ASRError(f"Transcription failed: {exc}") from exc

    def transcribe_batch(self, segments: list[SpeechSegment]) -> list[ASRResult]:
        """Transcribe a batch of speech segments and return non-blank results.

        Runs all segments through the ASR model in a single inference call using
        ``torch.inference_mode()``.  After transcription, morphological analysis
        is performed via fugashi and logged at DEBUG level.  Segments whose
        transcription is empty or whitespace-only are filtered out.

        Args:
            segments: List of ``SpeechSegment`` objects to transcribe.

        Returns:
            List of ``ASRResult`` objects, one per non-blank transcription.
            Ordering matches the input order with blank entries removed.

        Raises:
            ASRError: If the model is not loaded or batch transcription fails.
        """
        if self._model is None:
            raise ASRError("ASR model not loaded")
        if not segments:
            return []

        audio_inputs = [(seg.audio, seg.sample_rate) for seg in segments]
        t0 = time.perf_counter_ns()
        try:
            with torch.inference_mode():
                raw_results = self._model.transcribe(audio=audio_inputs, language="Japanese")
        except Exception as exc:
            raise ASRError(f"Batch transcription failed: {exc}") from exc
        elapsed_ms = (time.perf_counter_ns() - t0) / 1_000_000

        per_segment_ms = elapsed_ms / max(len(segments), 1)
        results: list[ASRResult] = []
        for seg, raw in zip(segments, raw_results):
            text = str(raw.text).strip()
            if not text:
                logger.debug("Filtered blank transcription for segment %s", seg.segment_id)
                continue
            morphemes = [w.surface for w in _tagger(text)]
            logger.debug(
                "Segment %s → %d morphemes: %s",
                seg.segment_id,
                len(morphemes),
                morphemes,
            )
            results.append(
                ASRResult(
                    text=text,
                    segment_id=seg.segment_id,
                    elapsed_ms=per_segment_ms,
                )
            )
        return results

    def unload(self) -> None:
        """Release the model and free GPU memory.

        Safe to call even if the model was never loaded.
        """
        if self._model is not None:
            # Qwen3ASRModel wraps the torch model in .model attribute
            if hasattr(self._model, "model"):
                self._model.model.cpu()
            del self._model
            self._model = None
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.synchronize()
                torch.cuda.empty_cache()
            logger.info("QwenASR model unloaded")
