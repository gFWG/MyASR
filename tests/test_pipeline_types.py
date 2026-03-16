"""Tests for pipeline data types."""

from dataclasses import FrozenInstanceError

import numpy as np
import pytest

from src.pipeline.types import ASRResult, SpeechSegment


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
