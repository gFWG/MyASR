"""Tests for SileroVAD wrapper."""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.db.models import AudioSegment

SAMPLE_RATE = 16000
CHUNK_SAMPLES = 512


def make_audio(n_samples: int = CHUNK_SAMPLES) -> np.ndarray:
    return np.zeros(n_samples, dtype=np.float32)


@pytest.fixture
def mock_silero(monkeypatch):
    mock_model = MagicMock()
    mock_iterator = MagicMock()
    mock_iterator.return_value = None
    with (
        patch("src.vad.silero.load_silero_vad", return_value=mock_model) as mock_load,
        patch("src.vad.silero.VADIterator", return_value=mock_iterator) as mock_vad_iter,
    ):
        yield mock_load, mock_vad_iter, mock_iterator


def test_process_chunk_silence_returns_none(mock_silero):
    from src.vad.silero import SileroVAD

    _, _, mock_iterator = mock_silero
    mock_iterator.return_value = None

    vad = SileroVAD()
    result = vad.process_chunk(make_audio())

    assert result is None


def test_process_chunk_speech_start_sets_flag(mock_silero):
    from src.vad.silero import SileroVAD

    _, _, mock_iterator = mock_silero
    mock_iterator.return_value = {"start": 0}

    vad = SileroVAD()
    result = vad.process_chunk(make_audio())

    assert result is None
    assert vad._is_speech is True


def test_process_chunk_speech_end_creates_segment(mock_silero):
    from src.vad.silero import SileroVAD

    _, _, mock_iterator = mock_silero

    vad = SileroVAD(min_speech_ms=0)

    mock_iterator.return_value = {"start": 0}
    vad.process_chunk(make_audio())

    mock_iterator.return_value = {"end": CHUNK_SAMPLES}
    result = vad.process_chunk(make_audio())

    assert result is not None
    assert len(result) == 1
    assert isinstance(result[0], AudioSegment)
    assert result[0].samples.shape[0] == CHUNK_SAMPLES * 2
    assert result[0].duration_sec == pytest.approx(CHUNK_SAMPLES * 2 / SAMPLE_RATE)
    assert vad._is_speech is False
    assert vad._audio_buffer == []


def test_process_chunk_short_speech_filtered(mock_silero):
    from src.vad.silero import SileroVAD

    _, _, mock_iterator = mock_silero

    vad = SileroVAD(min_speech_ms=250, sample_rate=SAMPLE_RATE)

    mock_iterator.return_value = {"start": 0}
    vad.process_chunk(make_audio(512))

    mock_iterator.return_value = {"end": 512}
    result = vad.process_chunk(make_audio(512))

    assert result is None
    assert not vad._is_speech


def test_process_chunk_force_cut_at_30s(mock_silero):
    from src.vad.silero import SileroVAD

    _, _, mock_iterator = mock_silero

    vad = SileroVAD(min_speech_ms=0, sample_rate=SAMPLE_RATE)

    mock_iterator.return_value = {"start": 0}
    vad.process_chunk(make_audio(512))

    mock_iterator.return_value = None
    max_samples = 30 * SAMPLE_RATE
    chunk_size = 4096
    total = 512
    while total < max_samples:
        n = min(chunk_size, max_samples - total + chunk_size)
        vad.process_chunk(make_audio(n))
        total += n
        if not vad._is_speech:
            break

    assert not vad._is_speech
    assert vad._audio_buffer == []
    mock_iterator.reset_states.assert_called()


def test_reset_clears_state(mock_silero):
    from src.vad.silero import SileroVAD

    _, _, mock_iterator = mock_silero

    vad = SileroVAD()

    mock_iterator.return_value = {"start": 0}
    vad.process_chunk(make_audio())

    assert vad._is_speech is True
    assert len(vad._audio_buffer) > 0

    vad.reset()

    assert vad._is_speech is False
    assert vad._audio_buffer == []
    assert vad._total_samples == 0
    assert vad._speech_start_sample == 0
    mock_iterator.reset_states.assert_called_once()
