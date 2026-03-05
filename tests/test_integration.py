"""Integration tests using real Japanese audio files.

These tests exercise the VAD and ASR components with actual speech data
from dev/short.wav and dev/long.wav, validating that the pipeline produces
meaningful transcription results on real audio.

Requires: CUDA GPU for ASR model inference, dev/*.wav files present.
Run with: pytest tests/test_integration.py -m "slow and gpu"
Skip with: pytest -m "not slow"
"""

import numpy as np
import pytest

from src.db.models import AudioSegment
from src.vad.silero import SileroVAD

slow = pytest.mark.slow
gpu = pytest.mark.gpu


@slow
class TestVADWithRealAudio:
    """VAD produces speech segments from real Japanese audio."""

    def test_vad_detects_speech_in_short_wav(self, short_wav: tuple[np.ndarray, int]) -> None:
        audio, sr = short_wav
        assert sr == 16000, f"Expected 16kHz, got {sr}Hz"

        vad = SileroVAD(sample_rate=sr)
        chunk_size = 512
        segments: list[AudioSegment] = []

        for i in range(0, len(audio), chunk_size):
            chunk = audio[i : i + chunk_size]
            if len(chunk) < chunk_size:
                chunk = np.pad(chunk, (0, chunk_size - len(chunk)))
            result = vad.process_chunk(chunk)
            if result is not None:
                segments.extend(result)

        assert len(segments) > 0, "VAD should detect speech in short.wav"
        for seg in segments:
            assert seg.duration_sec > 0.0
            assert seg.samples.dtype == np.float32
            assert len(seg.samples) > 0

    def test_vad_detects_speech_in_long_wav(self, long_wav: tuple[np.ndarray, int]) -> None:
        audio, sr = long_wav
        assert sr == 16000, f"Expected 16kHz, got {sr}Hz"

        vad = SileroVAD(sample_rate=sr)
        chunk_size = 512
        segments: list[AudioSegment] = []

        for i in range(0, len(audio), chunk_size):
            chunk = audio[i : i + chunk_size]
            if len(chunk) < chunk_size:
                chunk = np.pad(chunk, (0, chunk_size - len(chunk)))
            result = vad.process_chunk(chunk)
            if result is not None:
                segments.extend(result)

        assert len(segments) > 0, "VAD should detect speech in long.wav"
        total_speech_sec = sum(s.duration_sec for s in segments)
        assert total_speech_sec > 1.0, "Long audio should contain >1s of speech"

    def test_vad_segments_are_within_max_duration(self, long_wav: tuple[np.ndarray, int]) -> None:
        audio, sr = long_wav
        vad = SileroVAD(sample_rate=sr)
        chunk_size = 512
        segments: list[AudioSegment] = []

        for i in range(0, len(audio), chunk_size):
            chunk = audio[i : i + chunk_size]
            if len(chunk) < chunk_size:
                chunk = np.pad(chunk, (0, chunk_size - len(chunk)))
            result = vad.process_chunk(chunk)
            if result is not None:
                segments.extend(result)

        for seg in segments:
            assert seg.duration_sec <= 30.0, f"Segment exceeds 30s max: {seg.duration_sec:.1f}s"


@slow
@gpu
class TestASRWithRealAudio:
    """ASR transcribes real Japanese audio into text."""

    def test_asr_transcribes_short_wav(self, short_wav: tuple[np.ndarray, int]) -> None:
        from src.asr.qwen_asr import QwenASR

        audio, sr = short_wav
        asr = QwenASR()
        try:
            text = asr.transcribe(audio, sample_rate=sr)
            assert isinstance(text, str)
            assert len(text) > 0, "ASR should produce non-empty text for speech audio"
        finally:
            asr.unload()

    def test_asr_transcribes_long_wav(self, long_wav: tuple[np.ndarray, int]) -> None:
        from src.asr.qwen_asr import QwenASR

        audio, sr = long_wav
        asr = QwenASR()
        try:
            text = asr.transcribe(audio, sample_rate=sr)
            assert isinstance(text, str)
            assert len(text) > 0, "ASR should produce non-empty text for speech audio"
        finally:
            asr.unload()


@slow
@gpu
class TestVADASRPipeline:
    """End-to-end VAD -> ASR pipeline with real audio."""

    def test_vad_then_asr_produces_japanese_text(self, short_wav: tuple[np.ndarray, int]) -> None:
        from src.asr.qwen_asr import QwenASR

        audio, sr = short_wav
        vad = SileroVAD(sample_rate=sr)
        chunk_size = 512
        segments: list[AudioSegment] = []

        for i in range(0, len(audio), chunk_size):
            chunk = audio[i : i + chunk_size]
            if len(chunk) < chunk_size:
                chunk = np.pad(chunk, (0, chunk_size - len(chunk)))
            result = vad.process_chunk(chunk)
            if result is not None:
                segments.extend(result)

        assert len(segments) > 0, "VAD must detect segments before ASR can run"

        asr = QwenASR()
        try:
            transcriptions: list[str] = []
            for seg in segments:
                text = asr.transcribe(seg.samples, sample_rate=sr)
                if text:
                    transcriptions.append(text)

            assert len(transcriptions) > 0, "ASR should transcribe at least one segment"
            full_text = "".join(transcriptions)
            has_japanese = any(
                "\u3040" <= ch <= "\u309f"  # Hiragana
                or "\u30a0" <= ch <= "\u30ff"  # Katakana
                or "\u4e00" <= ch <= "\u9fff"  # CJK Unified
                for ch in full_text
            )
            assert has_japanese, (
                f"Transcription should contain Japanese characters, got: {full_text[:100]}"
            )
        finally:
            asr.unload()
