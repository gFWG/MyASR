"""Tests for pipeline data types."""

from dataclasses import FrozenInstanceError

import numpy as np
import pytest

from src.pipeline.types import ASRResult, LLMResult, PipelineStageMetrics, SpeechSegment


class TestSpeechSegment:
    """Tests for SpeechSegment dataclass."""

    def test_construct_with_valid_data(self) -> None:
        """Test constructing SpeechSegment with valid data."""
        audio = np.array([0.1, 0.2, 0.3], dtype=np.float32)
        segment = SpeechSegment(
            audio=audio,
            sample_rate=16000,
            timestamp=123.456,
            segment_id="abc-123",
        )

        assert np.array_equal(segment.audio, audio)
        assert segment.sample_rate == 16000
        assert segment.timestamp == 123.456
        assert segment.segment_id == "abc-123"

    def test_fields_are_immutable(self) -> None:
        """Test that SpeechSegment fields cannot be modified (frozen)."""
        audio = np.array([0.1, 0.2, 0.3], dtype=np.float32)
        segment = SpeechSegment(
            audio=audio,
            sample_rate=16000,
            timestamp=123.456,
            segment_id="abc-123",
        )

        with pytest.raises(FrozenInstanceError):
            segment.segment_id = "new-id"  # type: ignore[misc]


class TestASRResult:
    """Tests for ASRResult dataclass."""

    def test_construct_with_valid_data(self) -> None:
        """Test constructing ASRResult with valid data."""
        result = ASRResult(
            text="こんにちは",
            segment_id="seg-001",
            elapsed_ms=45.2,
        )

        assert result.text == "こんにちは"
        assert result.segment_id == "seg-001"
        assert result.elapsed_ms == 45.2

    def test_fields_are_immutable(self) -> None:
        """Test that ASRResult fields cannot be modified (frozen)."""
        result = ASRResult(
            text="こんにちは",
            segment_id="seg-001",
            elapsed_ms=45.2,
        )

        with pytest.raises(FrozenInstanceError):
            result.text = "modified"  # type: ignore[misc]


class TestTranslationResult:
    """Tests for TranslationResult dataclass."""

    def test_construct_with_valid_data(self) -> None:
        """Test constructing TranslationResult with valid data."""
        result = LLMResult(
            translation="你好",
            explanation="Greeting used in Japanese",
            segment_id="seg-002",
            elapsed_ms=120.5,
        )

        assert result.translation == "你好"
        assert result.explanation == "Greeting used in Japanese"
        assert result.segment_id == "seg-002"
        assert result.elapsed_ms == 120.5

    def test_construct_with_none_values(self) -> None:
        """Test constructing TranslationResult with None values."""
        result = LLMResult(
            translation=None,
            explanation=None,
            segment_id="seg-003",
            elapsed_ms=50.0,
        )

        assert result.translation is None
        assert result.explanation is None
        assert result.segment_id == "seg-003"

    def test_fields_are_immutable(self) -> None:
        """Test that TranslationResult fields cannot be modified (frozen)."""
        result = LLMResult(
            translation="你好",
            explanation="Greeting",
            segment_id="seg-002",
            elapsed_ms=120.5,
        )

        with pytest.raises(FrozenInstanceError):
            result.translation = "modified"  # type: ignore[misc]


class TestPipelineStageMetrics:
    """Tests for PipelineStageMetrics dataclass."""

    def test_construct_with_valid_data(self) -> None:
        """Test constructing PipelineStageMetrics with valid data."""
        metrics = PipelineStageMetrics(
            stage="vad",
            start_time=100.0,
            end_time=100.5,
            elapsed_ms=500.0,
        )

        assert metrics.stage == "vad"
        assert metrics.start_time == 100.0
        assert metrics.end_time == 100.5
        assert metrics.elapsed_ms == 500.0

    def test_fields_are_immutable(self) -> None:
        """Test that PipelineStageMetrics fields cannot be modified (frozen)."""
        metrics = PipelineStageMetrics(
            stage="asr",
            start_time=200.0,
            end_time=201.0,
            elapsed_ms=1000.0,
        )

        with pytest.raises(FrozenInstanceError):
            metrics.stage = "modified"  # type: ignore[misc]
