"""Tests for SileroVAD wrapper."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.models import AudioSegment

SAMPLE_RATE = 16000
CHUNK_SAMPLES = 512


def make_audio(n_samples: int = CHUNK_SAMPLES) -> np.ndarray:
    return np.zeros(n_samples, dtype=np.float32)


@pytest.fixture
def mock_silero(
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[tuple[MagicMock, MagicMock, MagicMock], None, None]:
    mock_model = MagicMock()
    mock_iterator = MagicMock()
    mock_iterator.return_value = None
    with (
        patch("src.vad.silero.load_silero_vad", return_value=mock_model) as mock_load,
        patch("src.vad.silero.VADIterator", return_value=mock_iterator) as mock_vad_iter,
    ):
        yield mock_load, mock_vad_iter, mock_iterator


def test_process_chunk_silence_returns_none(
    mock_silero: tuple[MagicMock, MagicMock, MagicMock],
) -> None:
    from src.vad.silero import SileroVAD

    _, _, mock_iterator = mock_silero
    mock_iterator.return_value = None

    vad = SileroVAD()
    result = vad.process_chunk(make_audio())

    assert result is None


def test_process_chunk_speech_start_sets_flag(
    mock_silero: tuple[MagicMock, MagicMock, MagicMock],
) -> None:
    from src.vad.silero import SileroVAD

    _, _, mock_iterator = mock_silero
    mock_iterator.return_value = {"start": 0}

    vad = SileroVAD()
    result = vad.process_chunk(make_audio())

    assert result is None
    assert vad._is_speech is True


def test_process_chunk_speech_end_creates_segment(
    mock_silero: tuple[MagicMock, MagicMock, MagicMock],
) -> None:
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


def test_process_chunk_short_speech_filtered(
    mock_silero: tuple[MagicMock, MagicMock, MagicMock],
) -> None:
    from src.vad.silero import SileroVAD

    _, _, mock_iterator = mock_silero

    vad = SileroVAD(min_speech_ms=250, sample_rate=SAMPLE_RATE)

    mock_iterator.return_value = {"start": 0}
    vad.process_chunk(make_audio(512))

    mock_iterator.return_value = {"end": 512}
    result = vad.process_chunk(make_audio(512))

    assert result is None
    assert not vad._is_speech


def test_process_chunk_force_cut_at_30s(
    mock_silero: tuple[MagicMock, MagicMock, MagicMock],
) -> None:
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


def test_reset_clears_state(mock_silero: tuple[MagicMock, MagicMock, MagicMock]) -> None:
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
    assert len(vad._pre_buffer) == 0
    assert vad._total_samples == 0
    assert vad._speech_start_sample == 0
    mock_iterator.reset_states.assert_called_once()


def test_pre_buffer_prepends_audio_to_speech(
    mock_silero: tuple[MagicMock, MagicMock, MagicMock],
) -> None:
    """Pre-buffer captures silence chunks and prepends them on speech start."""
    from src.vad.silero import SileroVAD

    _, _, mock_iterator = mock_silero
    vad = SileroVAD()

    # Send 3 silence chunks → they go into the ring pre-buffer
    silence = make_audio()
    mock_iterator.return_value = None
    for _ in range(3):
        vad.process_chunk(silence)

    assert len(vad._pre_buffer) == 3
    assert vad._is_speech is False

    # Speech start → pre-buffer copied into audio_buffer, then current chunk appended
    speech = make_audio()
    mock_iterator.return_value = {"start": 0}
    vad.process_chunk(speech)

    assert vad._is_speech is True
    assert len(vad._pre_buffer) == 0
    # audio_buffer = 3 pre-buffer chunks + 1 speech chunk = 4
    assert len(vad._audio_buffer) == 4

    # Send 5 more speech chunks to exceed min_speech_ms=250
    # Need total >= 8 chunks (8 * 512 / 16000 = 0.256s > 0.250s)
    mock_iterator.return_value = None
    for _ in range(5):
        vad.process_chunk(make_audio())

    # Speech end → segment contains all chunks
    mock_iterator.return_value = {"end": CHUNK_SAMPLES}
    result = vad.process_chunk(make_audio())

    assert result is not None
    assert len(result) == 1
    # 3 pre-buffer + 1 start + 5 continued + 1 end = 10 chunks total
    assert result[0].samples.shape[0] == CHUNK_SAMPLES * 10


# ── Chunk buffering tests (Bug 1: "Input audio chunk is too short") ──


def test_short_chunk_accumulates_before_processing(
    mock_silero: tuple[MagicMock, MagicMock, MagicMock],
) -> None:
    """Chunks shorter than 512 samples must be buffered, not passed to VADIterator."""
    from src.vad.silero import SileroVAD

    _, _, mock_iterator = mock_silero
    mock_iterator.return_value = None

    vad = SileroVAD()

    # Send a 200-sample chunk — too short for VADIterator
    short_chunk = make_audio(200)
    result = vad.process_chunk(short_chunk)

    assert result is None
    # VADIterator should NOT have been called (chunk buffered, not processed)
    mock_iterator.assert_not_called()
    # Pending buffer should hold the 200 samples
    assert vad._pending_size == 200


def test_short_chunks_accumulate_until_512(
    mock_silero: tuple[MagicMock, MagicMock, MagicMock],
) -> None:
    """Multiple short chunks accumulate until >= 512 samples, then process."""
    from src.vad.silero import SileroVAD

    _, _, mock_iterator = mock_silero
    mock_iterator.return_value = None

    vad = SileroVAD()

    # Send 341-sample chunks (simulating WASAPI 48kHz→16kHz resample)
    chunk_341 = make_audio(341)
    vad.process_chunk(chunk_341)
    assert mock_iterator.call_count == 0
    assert vad._pending_size == 341

    # Second chunk: 341 + 341 = 682 → one 512-block processed, 170 left over
    vad.process_chunk(chunk_341)
    assert mock_iterator.call_count == 1
    assert vad._pending_size == 170

    # Third chunk: 170 + 341 = 511 → still not enough
    vad.process_chunk(chunk_341)
    assert mock_iterator.call_count == 1
    assert vad._pending_size == 511

    # Fourth chunk: 511 + 341 = 852 → one more 512-block, 340 left
    vad.process_chunk(chunk_341)
    assert mock_iterator.call_count == 2
    assert vad._pending_size == 340


def test_exact_512_chunk_processed_immediately(
    mock_silero: tuple[MagicMock, MagicMock, MagicMock],
) -> None:
    """An exact 512-sample chunk should be processed immediately with no leftover."""
    from src.vad.silero import SileroVAD

    _, _, mock_iterator = mock_silero
    mock_iterator.return_value = None

    vad = SileroVAD()

    chunk_512 = make_audio(512)
    vad.process_chunk(chunk_512)

    assert mock_iterator.call_count == 1
    assert len(vad._pending) == 0


def test_large_chunk_split_into_multiple_blocks(
    mock_silero: tuple[MagicMock, MagicMock, MagicMock],
) -> None:
    """A chunk larger than 512 should be split into multiple 512-sample blocks."""
    from src.vad.silero import SileroVAD

    _, _, mock_iterator = mock_silero
    mock_iterator.return_value = None

    vad = SileroVAD()

    # 2000 samples → 3 full blocks (1536 samples) + 464 leftover
    chunk_2000 = make_audio(2000)
    vad.process_chunk(chunk_2000)

    assert mock_iterator.call_count == 3
    assert len(vad._pending) == 2000 - 512 * 3  # 464


def test_reset_clears_pending_buffer(
    mock_silero: tuple[MagicMock, MagicMock, MagicMock],
) -> None:
    """Reset must clear the pending accumulation buffer."""
    from src.vad.silero import SileroVAD

    _, _, mock_iterator = mock_silero
    mock_iterator.return_value = None

    vad = SileroVAD()

    # Accumulate a short chunk
    vad.process_chunk(make_audio(200))
    assert vad._pending_size == 200

    vad.reset()
    assert vad._pending_size == 0


def test_short_chunks_speech_detection_works(
    mock_silero: tuple[MagicMock, MagicMock, MagicMock],
) -> None:
    """Speech detection works correctly with sub-512 incoming chunks."""
    from src.vad.silero import SileroVAD

    _, _, mock_iterator = mock_silero

    vad = SileroVAD(min_speech_ms=0)
    call_count = [0]

    def side_effect(*args: object, **kwargs: object) -> dict[str, int] | None:
        call_count[0] += 1
        if call_count[0] == 1:
            return {"start": 0}
        if call_count[0] == 2:
            return {"end": CHUNK_SAMPLES}
        return None

    mock_iterator.side_effect = side_effect

    # Feed 4 × 300-sample chunks = 1200 samples → 2 × 512-sample blocks processed
    # Block 1: speech start, Block 2: speech end
    result = None
    for _ in range(4):
        result = vad.process_chunk(make_audio(300))

    # Should have a completed segment
    assert result is not None
    assert len(result) == 1
    assert isinstance(result[0], AudioSegment)


# ── Performance tests ──────────────────────────────────────────────────────────


def test_process_chunk_performance(
    mock_silero: tuple[MagicMock, MagicMock, MagicMock],
) -> None:
    """process_chunk must handle 1000 chunks with mean latency < 5 ms each.

    This guards against O(n²) accumulation hotspots (e.g. np.concatenate on
    _pending every call) that would degrade at 31 chunks/sec sustained input.
    """
    import time

    from src.vad.silero import SileroVAD

    _, _, mock_iterator = mock_silero
    mock_iterator.return_value = None

    vad = SileroVAD()

    # 512-sample chunks at 16 kHz ≈ 31 chunks/sec (real-time audio rate)
    chunk = make_audio(512)
    n_chunks = 1000

    start = time.perf_counter()
    for _ in range(n_chunks):
        vad.process_chunk(chunk)
    elapsed = time.perf_counter() - start

    mean_ms = (elapsed / n_chunks) * 1000
    assert mean_ms < 5.0, (
        f"process_chunk too slow: mean {mean_ms:.3f} ms/chunk (limit 5 ms). "
        "Check for O(n²) accumulation in _pending ring buffer."
    )


def test_process_chunk_performance_short_chunks(
    mock_silero: tuple[MagicMock, MagicMock, MagicMock],
) -> None:
    """Ring buffer must also be fast with sub-512 chunks (WASAPI resampled input)."""
    import time

    from src.vad.silero import SileroVAD

    _, _, mock_iterator = mock_silero
    mock_iterator.return_value = None

    vad = SileroVAD()

    # 341-sample chunks simulate 48 kHz → 16 kHz resampled WASAPI loopback
    chunk = make_audio(341)
    n_chunks = 1000

    start = time.perf_counter()
    for _ in range(n_chunks):
        vad.process_chunk(chunk)
    elapsed = time.perf_counter() - start

    mean_ms = (elapsed / n_chunks) * 1000
    assert mean_ms < 5.0, (
        f"process_chunk (short chunks) too slow: mean {mean_ms:.3f} ms/chunk (limit 5 ms)."
    )


# ── update_params() tests ────────────────────────────────────────────────────────


def test_update_params_sets_threshold(
    mock_silero: tuple[MagicMock, MagicMock, MagicMock],
) -> None:
    """update_params() should update VADIterator.threshold."""
    from src.vad.silero import SileroVAD

    _, _, mock_iterator = mock_silero
    mock_iterator.return_value = None
    # Set up mock with real attribute values
    mock_iterator.threshold = 0.5

    vad = SileroVAD(threshold=0.5)
    assert vad._vad_iterator.threshold == 0.5

    vad.update_params(threshold=0.7)
    assert vad._vad_iterator.threshold == 0.7


def test_update_params_sets_min_silence_ms(
    mock_silero: tuple[MagicMock, MagicMock, MagicMock],
) -> None:
    """update_params() should update VADIterator.min_silence_duration_ms."""
    from src.vad.silero import SileroVAD

    _, _, mock_iterator = mock_silero
    mock_iterator.return_value = None
    # Set up mock with real attribute values
    mock_iterator.min_silence_duration_ms = 300

    vad = SileroVAD(min_silence_ms=300)
    assert vad._vad_iterator.min_silence_duration_ms == 300

    vad.update_params(min_silence_ms=600)
    assert vad._vad_iterator.min_silence_duration_ms == 600


def test_update_params_sets_min_speech_ms(
    mock_silero: tuple[MagicMock, MagicMock, MagicMock],
) -> None:
    """update_params() should update _min_speech_samples."""
    from src.vad.silero import SileroVAD

    _, _, mock_iterator = mock_silero
    mock_iterator.return_value = None

    vad = SileroVAD(min_speech_ms=250, sample_rate=16000)
    # 250ms at 16kHz = 4000 samples
    assert vad._min_speech_samples == 4000

    vad.update_params(min_speech_ms=500)
    # 500ms at 16kHz = 8000 samples
    assert vad._min_speech_samples == 8000


def test_update_params_none_unchanged(
    mock_silero: tuple[MagicMock, MagicMock, MagicMock],
) -> None:
    """update_params() with None should leave values unchanged."""
    from src.vad.silero import SileroVAD

    _, _, mock_iterator = mock_silero
    mock_iterator.return_value = None
    # Set up mock with real attribute values
    mock_iterator.threshold = 0.5
    mock_iterator.min_silence_duration_ms = 300

    vad = SileroVAD(threshold=0.5, min_silence_ms=300, min_speech_ms=250)
    vad.update_params()  # All None

    assert vad._vad_iterator.threshold == 0.5
    assert vad._vad_iterator.min_silence_duration_ms == 300
    assert vad._min_speech_samples == 4000  # 250ms at 16kHz
