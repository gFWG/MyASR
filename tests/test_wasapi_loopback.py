"""Tests for WasapiLoopbackCapture (Windows-only)."""

import sys
from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.exceptions import AudioCaptureError


@pytest.fixture
def mock_pyaudiowpatch() -> Generator[dict[str, MagicMock], None, None]:
    """Mock pyaudiowpatch module for testing."""
    mock_pyaudio = MagicMock()
    mock_pyaudio.paFloat32 = 1
    mock_pyaudio.paContinue = 0

    mock_instance = MagicMock()
    mock_pyaudio.PyAudio.return_value = mock_instance

    # Mock device info
    mock_device: dict[str, Any] = {
        "index": 0,
        "defaultSampleRate": 48000.0,
        "maxInputChannels": 2,
        "name": "Speakers (Loopback)",
    }
    mock_instance.get_default_wasapi_loopback.return_value = mock_device

    # Mock stream
    mock_stream = MagicMock()
    mock_instance.open.return_value = mock_stream

    with patch.dict("sys.modules", {"pyaudiowpatch": mock_pyaudio}):
        yield {
            "module": mock_pyaudio,
            "instance": mock_instance,
            "stream": mock_stream,
            "device": mock_device,
        }


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only test")
def test_wasapi_start_opens_stream(mock_pyaudiowpatch: dict[str, MagicMock]) -> None:
    """Test that start() opens a WASAPI loopback stream with correct parameters."""
    from src.audio.backends import WasapiLoopbackCapture

    capture = WasapiLoopbackCapture(sample_rate=16000)
    callback = MagicMock()

    capture.start(callback)

    mock_pyaudiowpatch["instance"].get_default_wasapi_loopback.assert_called_once()
    mock_pyaudiowpatch["instance"].open.assert_called_once_with(
        format=mock_pyaudiowpatch["module"].paFloat32,
        channels=2,  # from mock device
        rate=48000,  # from mock device sample rate
        input=True,
        frames_per_buffer=1024,
        input_device_index=0,
        stream_callback=capture._pa_callback,
    )

    capture.stop()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only test")
def test_wasapi_stop_closes_resources(mock_pyaudiowpatch: dict[str, MagicMock]) -> None:
    """Test that stop() closes stream and terminates PyAudio."""
    from src.audio.backends import WasapiLoopbackCapture

    capture = WasapiLoopbackCapture(sample_rate=16000)
    capture.start(MagicMock())
    capture.stop()

    mock_pyaudiowpatch["stream"].stop_stream.assert_called_once()
    mock_pyaudiowpatch["stream"].close.assert_called_once()
    mock_pyaudiowpatch["instance"].terminate.assert_called_once()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only test")
def test_wasapi_start_twice_raises_error(mock_pyaudiowpatch: dict[str, MagicMock]) -> None:
    """Test that starting an already-running capture raises an error."""
    from src.audio.backends import WasapiLoopbackCapture

    capture = WasapiLoopbackCapture(sample_rate=16000)
    capture.start(MagicMock())

    with pytest.raises(AudioCaptureError, match="already running"):
        capture.start(MagicMock())

    capture.stop()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only test")
def test_wasapi_callback_downmixes_and_resamples(mock_pyaudiowpatch: dict[str, MagicMock]) -> None:
    """Test that the callback correctly downmixes stereo to mono and resamples."""

    from src.audio.backends import WasapiLoopbackCapture

    capture = WasapiLoopbackCapture(sample_rate=16000)
    user_callback = MagicMock()
    capture.start(user_callback)

    # Create stereo test data: 1024 frames, 2 channels
    # Shape: (1024, 2) in interleaved format = 2048 samples
    stereo_data = np.random.rand(2048).astype(np.float32)
    in_data = stereo_data.tobytes()

    # Mock scipy.signal.resample to avoid dependency on resampling quality
    with patch("scipy.signal.resample") as mock_resample:
        # resample returns same number of samples in this mock
        mock_resample.return_value = np.zeros(341, dtype=np.float32)

        result = capture._pa_callback(in_data, 1024, {}, 0)

        # Check return value
        assert result == (None, mock_pyaudiowpatch["module"].paContinue)

        # Check that resample was called (48kHz -> 16kHz = 1/3 samples)
        mock_resample.assert_called_once()

        # User callback should be called with resampled mono data
        user_callback.assert_called_once()

    capture.stop()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only test")
def test_wasapi_no_loopback_device_raises_error(mock_pyaudiowpatch: dict[str, MagicMock]) -> None:
    """Test that missing loopback device raises AudioCaptureError."""
    from src.audio.backends import WasapiLoopbackCapture

    mock_pyaudiowpatch["instance"].get_default_wasapi_loopback.side_effect = OSError(
        "No loopback device"
    )

    capture = WasapiLoopbackCapture(sample_rate=16000)

    with pytest.raises(AudioCaptureError, match="No WASAPI loopback device found"):
        capture.start(MagicMock())


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only test")
def test_wasapi_list_devices(mock_pyaudiowpatch: dict[str, MagicMock]) -> None:
    """Test that list_devices returns device list."""
    from src.audio.backends import WasapiLoopbackCapture

    mock_pyaudiowpatch["instance"].get_device_count.return_value = 2
    mock_pyaudiowpatch["instance"].get_device_info_by_index.side_effect = [
        {"index": 0, "name": "Device 1"},
        {"index": 1, "name": "Device 2"},
    ]

    devices = WasapiLoopbackCapture.list_devices()

    assert len(devices) == 2
    assert devices[0]["name"] == "Device 1"
    assert devices[1]["name"] == "Device 2"


def test_create_audio_capture_factory_on_linux() -> None:
    """Test that factory returns AudioCapture on non-Windows platforms."""
    with patch("sys.platform", "linux"):
        # Force re-import to pick up mocked platform
        import importlib

        from src.audio import capture

        importlib.reload(capture)

        from src.config import AppConfig

        config = AppConfig()
        backend = capture.create_audio_capture(config)

        # Should be AudioCapture (sounddevice-based)
        assert hasattr(backend, "_device_id")
        assert hasattr(backend, "_sample_rate")


def test_create_audio_capture_factory_on_windows() -> None:
    """Test that factory returns WasapiLoopbackCapture on Windows."""
    with patch("sys.platform", "win32"):
        import importlib

        from src.audio import capture

        importlib.reload(capture)

        from src.config import AppConfig

        config = AppConfig()

        # Mock the WasapiLoopbackCapture import
        with patch("src.audio.backends.WasapiLoopbackCapture") as mock_wasapi:
            mock_instance = MagicMock()
            mock_wasapi.return_value = mock_instance

            backend = capture.create_audio_capture(config)

            mock_wasapi.assert_called_once_with(sample_rate=16000)
            assert backend == mock_instance
