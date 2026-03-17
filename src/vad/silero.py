"""Silero VAD wrapper with chunk buffering for speech segment extraction."""

import logging
import math
from collections import deque

import numpy as np
import torch
from silero_vad import VADIterator, load_silero_vad

from src.exceptions import VADError
from src.models import AudioSegment

logger = logging.getLogger(__name__)


class SileroVAD:
    """Voice Activity Detection wrapper using Silero VAD with internal audio buffering.

    Processes audio in fixed-size chunks and accumulates audio until a complete
    speech segment is detected. Returns ``AudioSegment`` objects suitable for ASR.

    Args:
        threshold: Speech probability threshold (0.0–1.0). Higher = less sensitive.
        min_silence_ms: Minimum silence duration in ms to consider speech ended.
        min_speech_ms: Minimum speech duration in ms; shorter segments are discarded.
        sample_rate: Audio sample rate in Hz (must be 16000 or 8000 for Silero).
    """

    # Silero VAD requires chunks of at least sr / 31.25 samples.
    # At 16 kHz that is 512 samples.  Audio backends may deliver shorter
    # chunks (e.g. WASAPI loopback resampled from 48 kHz), so we accumulate
    # incoming audio internally until we have a full 512-sample block.
    _CHUNK_SAMPLES = 512

    def __init__(
        self,
        threshold: float = 0.5,
        min_silence_ms: int = 500,
        min_speech_ms: int = 250,
        sample_rate: int = 16000,
        pre_buffer_ms: int = 300,
    ) -> None:
        try:
            model = load_silero_vad(onnx=False)
            self._vad_iterator = VADIterator(
                model,
                threshold=threshold,
                sampling_rate=sample_rate,
                min_silence_duration_ms=min_silence_ms,
                speech_pad_ms=0,  # Disabled; pre_buffer_ms handles audio padding
            )
        except Exception as exc:
            raise VADError(f"Failed to load Silero VAD model: {exc}") from exc

        self._sample_rate = sample_rate
        self._min_speech_samples = int(min_speech_ms * sample_rate / 1000)
        self._max_speech_samples = 30 * sample_rate
        self._audio_buffer: list[np.ndarray] = []
        self._is_speech: bool = False
        self._speech_start_sample: int = 0
        self._total_samples: int = 0

        # Ring buffer: accumulate incoming chunks without per-call np.concatenate.
        # _intake holds raw float32 arrays; _pending_size tracks total samples.
        # np.concatenate is deferred until we have a full _CHUNK_SAMPLES block to process.
        self._intake: deque[np.ndarray] = deque()
        self._pending_size: int = 0

        # _pending exposes the leftover tail after block extraction (may be empty view).
        self._pending: np.ndarray = np.empty(0, dtype=np.float32)

        pre_buffer_samples = int(pre_buffer_ms * sample_rate / 1000)
        chunk_size = self._CHUNK_SAMPLES
        self._pre_buffer: deque[np.ndarray] = deque(
            maxlen=math.ceil(pre_buffer_samples / chunk_size),
        )

        logger.info(
            "SileroVAD initialised — threshold=%.2f, min_silence_ms=%d, "
            "min_speech_ms=%d, sample_rate=%d, pre_buffer_ms=%d",
            threshold,
            min_silence_ms,
            min_speech_ms,
            sample_rate,
            pre_buffer_ms,
        )

    def process_chunk(self, audio: np.ndarray) -> list[AudioSegment] | None:
        """Process a single audio chunk and return completed speech segments.

        Incoming audio is first accumulated in a deque ring buffer until at least
        ``_CHUNK_SAMPLES`` (512) samples are available, then fed to the
        VADIterator in exact 512-sample blocks.  This prevents the
        "Input audio chunk is too short" error that occurs when backends
        deliver fewer than 512 samples (e.g. WASAPI loopback resampled
        from 48 kHz).

        Args:
            audio: 1-D float32 numpy array of audio samples at ``self._sample_rate``.

        Returns:
            A list of ``AudioSegment`` objects if one or more speech segments
            were completed during this call, or ``None`` if no segment is ready.

        Raises:
            VADError: If the VADIterator raises an unexpected exception.
        """
        self._total_samples += len(audio)

        self._intake.append(audio)
        self._pending_size += len(audio)

        results: list[AudioSegment] = []
        cs = self._CHUNK_SAMPLES

        while self._pending_size >= cs:
            # Build contiguous array from deque, then extract exactly cs samples.
            flat = np.concatenate(list(self._intake))
            block = flat[:cs]
            remainder = flat[cs:]

            self._intake.clear()
            self._pending_size = len(remainder)
            if self._pending_size > 0:
                self._intake.append(remainder)

            # Keep _pending in sync for callers that inspect it (tests).
            self._pending = remainder

            segment = self._process_vad_block(block)
            if segment is not None:
                results.extend(segment)

        # Expose pending for tests/inspection.
        if self._pending_size == 0:
            self._pending = np.empty(0, dtype=np.float32)

        return results if results else None

    def _process_vad_block(self, audio: np.ndarray) -> list[AudioSegment] | None:
        """Feed a single 512-sample block to the VADIterator.

        Args:
            audio: Exactly ``_CHUNK_SAMPLES`` float32 samples.

        Returns:
            A list of completed ``AudioSegment`` objects, or ``None``.
        """
        results: list[AudioSegment] = []
        chunk_tensor = torch.from_numpy(audio)

        try:
            speech_dict = self._vad_iterator(chunk_tensor, return_seconds=False)
        except Exception as exc:
            raise VADError(f"VADIterator failed during chunk processing: {exc}") from exc

        if speech_dict is not None:
            if "start" in speech_dict:
                self._is_speech = True
                self._speech_start_sample = int(speech_dict["start"])
                self._audio_buffer = list(self._pre_buffer)
                self._pre_buffer.clear()
                logger.debug("Speech start detected at sample %d", self._speech_start_sample)

            if "end" in speech_dict and self._is_speech:
                self._audio_buffer.append(audio)
                speech_samples = np.concatenate(self._audio_buffer)
                duration = len(speech_samples) / self._sample_rate
                if len(speech_samples) >= self._min_speech_samples:
                    logger.debug(
                        "Speech segment %.2fs (%d samples)",
                        duration,
                        len(speech_samples),
                    )
                    results.append(AudioSegment(samples=speech_samples, duration_sec=duration))
                else:
                    logger.debug(
                        "Discarding short segment: %d samples < %d min",
                        len(speech_samples),
                        self._min_speech_samples,
                    )
                self._audio_buffer = []
                self._is_speech = False
                return results if results else None

        if self._is_speech:
            self._audio_buffer.append(audio)
            buffered_samples = sum(len(x) for x in self._audio_buffer)
            if buffered_samples >= self._max_speech_samples:
                speech_samples = np.concatenate(self._audio_buffer)
                duration = len(speech_samples) / self._sample_rate
                logger.warning("Force-cutting speech at %.1fs (exceeded 30 s limit)", duration)
                results.append(AudioSegment(samples=speech_samples, duration_sec=duration))
                self._audio_buffer = []
                self._is_speech = False
                self._vad_iterator.reset_states()
        else:
            self._pre_buffer.append(audio)

        return results if results else None

    def reset(self) -> None:
        """Reset VAD state and clear all internal buffers.

        Call this between audio streams or after recovering from an error.
        """
        self._vad_iterator.reset_states()
        self._audio_buffer = []
        self._pre_buffer.clear()
        self._intake.clear()
        self._pending_size = 0
        self._pending = np.empty(0, dtype=np.float32)
        self._is_speech = False
        self._total_samples = 0
        self._speech_start_sample = 0
        logger.debug("SileroVAD state reset")

    def update_params(
        self,
        threshold: float | None = None,
        min_silence_ms: int | None = None,
        min_speech_ms: int | None = None,
        pre_buffer_ms: int | None = None,
    ) -> None:
        """Update VAD parameters dynamically without reloading the model.

        Thread-safe: Can be called while the VAD is processing audio.
        Changes take effect immediately for subsequent audio chunks.

        Args:
            threshold: New speech probability threshold (0.0–1.0). Higher = less sensitive.
            min_silence_ms: New minimum silence duration in ms to consider speech ended.
            min_speech_ms: New minimum speech duration in ms; shorter segments are discarded.
            pre_buffer_ms: New pre-buffer duration in ms to prepend before speech onset.
        """
        if threshold is not None:
            self._vad_iterator.threshold = threshold
            logger.info("VAD threshold updated: %.2f", threshold)

        if min_silence_ms is not None:
            self._vad_iterator.min_silence_duration_ms = min_silence_ms
            logger.info("VAD min_silence_ms updated: %d", min_silence_ms)

        if min_speech_ms is not None:
            self._min_speech_samples = int(min_speech_ms * self._sample_rate / 1000)
            logger.info("VAD min_speech_ms updated: %d", min_speech_ms)

        if pre_buffer_ms is not None:
            pre_buffer_samples = int(pre_buffer_ms * self._sample_rate / 1000)
            chunk_size = self._CHUNK_SAMPLES
            new_maxlen = math.ceil(pre_buffer_samples / chunk_size)
            old_chunks = list(self._pre_buffer)
            self._pre_buffer = deque(old_chunks[-new_maxlen:], maxlen=new_maxlen)
            logger.info("VAD pre_buffer_ms updated: %d", pre_buffer_ms)
