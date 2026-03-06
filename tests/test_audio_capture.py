"""Tests for AudioCapture."""

from collections.abc import Callable, Generator
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.exceptions import AudioCaptureError


@pytest.fixture
def mock_sd() -> Generator[tuple[MagicMock, MagicMock], None, None]:
    mock = MagicMock()
    mock_stream = MagicMock()
    mock.InputStream.return_value = mock_stream
    with patch.dict("sys.modules", {"sounddevice": mock}):
        yield mock, mock_stream


def test_start_begins_stream(mock_sd: tuple[MagicMock, MagicMock]) -> None:
    mock, mock_stream = mock_sd
    from src.audio.capture import AudioCapture

    cap = AudioCapture(device_id=0, sample_rate=16000)
    callback: Callable[[np.ndarray], None] = MagicMock()
    cap.start(callback)

    mock.InputStream.assert_called_once_with(
        samplerate=16000,
        blocksize=512,
        device=0,
        channels=1,
        dtype="float32",
        callback=cap._audio_callback,
    )
    mock_stream.start.assert_called_once()


def test_stop_closes_stream(mock_sd: tuple[MagicMock, MagicMock]) -> None:
    mock, mock_stream = mock_sd
    from src.audio.capture import AudioCapture

    cap = AudioCapture()
    cap.start(MagicMock())
    cap.stop()

    mock_stream.stop.assert_called_once()
    mock_stream.close.assert_called_once()
    assert cap._stream is None


def test_callback_passes_mono_audio(mock_sd: tuple[MagicMock, MagicMock]) -> None:
    _mock, _mock_stream = mock_sd
    from src.audio.capture import AudioCapture

    cap = AudioCapture()
    received: list[np.ndarray] = []
    cap.start(received.append)

    # Simulate sounddevice callback with stereo-shaped block (channels=1)
    indata = np.ones((512, 1), dtype="float32") * 0.5
    cap._audio_callback(indata, 512, None, None)

    assert len(received) == 1
    assert received[0].shape == (512,)
    np.testing.assert_array_equal(received[0], indata[:, 0])


def test_double_start_raises(mock_sd: tuple[MagicMock, MagicMock]) -> None:
    _mock, _mock_stream = mock_sd
    from src.audio.capture import AudioCapture

    cap = AudioCapture()
    cap.start(MagicMock())

    with pytest.raises(AudioCaptureError, match="already running"):
        cap.start(MagicMock())


def test_stop_when_not_started_does_not_raise(mock_sd: tuple[MagicMock, MagicMock]) -> None:
    _mock, _mock_stream = mock_sd
    from src.audio.capture import AudioCapture

    cap = AudioCapture()
    cap.stop()


def test_list_devices_returns_list(mock_sd: tuple[MagicMock, MagicMock]) -> None:
    mock, _mock_stream = mock_sd
    mock.query_devices.return_value = [
        {"name": "Mic", "max_input_channels": 2},
        {"name": "Speakers", "max_input_channels": 0},
    ]
    from src.audio.capture import AudioCapture

    devices = AudioCapture.list_devices()
    assert isinstance(devices, list)
    assert len(devices) == 2
    assert devices[0]["name"] == "Mic"


def test_invalid_device_raises_audio_capture_error(mock_sd: tuple[MagicMock, MagicMock]) -> None:
    mock, _mock_stream = mock_sd
    mock.InputStream.side_effect = Exception("Invalid device")
    from src.audio.capture import AudioCapture

    cap = AudioCapture(device_id=999)
    with pytest.raises(AudioCaptureError, match="Failed to start audio capture"):
        cap.start(MagicMock())

    # Stream must be cleaned up after failure
    assert cap._stream is None
