"""Qwen3-ASR-0.6B speech recognition wrapper."""

import logging
from typing import Any

import numpy as np
import torch

from src.exceptions import ASRError, ModelLoadError

logger = logging.getLogger(__name__)


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
                max_inference_batch_size=32,
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

    def unload(self) -> None:
        """Release the model and free GPU memory.

        Safe to call even if the model was never loaded.
        """
        if self._model is not None:
            del self._model
            self._model = None
            torch.cuda.empty_cache()
            logger.info("QwenASR model unloaded")
