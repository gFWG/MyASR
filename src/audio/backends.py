"""Windows-specific audio backends for MyASR."""

import logging
from collections.abc import Callable
from typing import Any

import numpy as np

try:
    import soxr as _soxr

    _HAVE_SOXR = True
except ImportError:
    _soxr = None  # optional: scipy fallback used instead
    _HAVE_SOXR = False

from src.exceptions import AudioCaptureError

logger = logging.getLogger(__name__)


def resample_audio(audio: np.ndarray, in_rate: int, out_rate: int) -> np.ndarray:
    """Resample a mono float32 audio array from in_rate to out_rate.

    Uses soxr for high-quality, low-latency rational resampling when available.
    Falls back to ``scipy.signal.resample_poly`` if soxr is not installed.

    Args:
        audio: 1-D float32 array of audio samples.
        in_rate: Source sample rate in Hz.
        out_rate: Target sample rate in Hz.

    Returns:
        Resampled 1-D float32 array.
    """
    if in_rate == out_rate:
        return audio
    if _HAVE_SOXR:
        resampled: np.ndarray = _soxr.resample(audio, in_rate, out_rate, quality="HQ")
    else:
        from math import gcd

        from scipy.signal import resample_poly

        divisor = gcd(in_rate, out_rate)
        resampled = resample_poly(audio, out_rate // divisor, in_rate // divisor)
    return resampled.astype(np.float32)


class WasapiLoopbackCapture:
    """Windows-specific audio capture for system loopback using PyAudioWPatch.

    Captures system audio (what you hear) via WASAPI loopback mode.
    Handles device discovery, resampling from hardware rate to target rate,
    and mono downmixing.

    Args:
        sample_rate: Target sample rate in Hz. Defaults to 16000 for VAD/ASR compatibility.
    """

    def __init__(self, sample_rate: int = 16000) -> None:
        self._target_rate = sample_rate
        self._p: Any = None
        self._stream: Any = None
        self._user_callback: Callable[[np.ndarray], None] | None = None
        self._device_info: dict[str, Any] | None = None

    def _get_loopback_device(self, p: Any) -> dict[str, Any]:
        """Get the default WASAPI loopback device.

        Args:
            p: PyAudio instance.

        Returns:
            Device info dictionary.

        Raises:
            AudioCaptureError: If no loopback device is found.
        """
        try:
            device_info: dict[str, Any] = p.get_default_wasapi_loopback()
            return device_info
        except OSError as exc:
            raise AudioCaptureError("No WASAPI loopback device found") from exc

    def start(self, callback: Callable[[np.ndarray], None]) -> None:
        """Start the WASAPI loopback stream.

        Args:
            callback: Called with a mono float32 numpy array (shape: [blocksize])
                for each captured audio block, resampled to target rate.

        Raises:
            AudioCaptureError: If already running, or if stream fails to open.
        """
        if self._stream is not None:
            raise AudioCaptureError("already running")

        import pyaudiowpatch as pyaudio  # noqa: PLC0415

        self._p = pyaudio.PyAudio()
        self._device_info = self._get_loopback_device(self._p)
        self._user_callback = callback

        # WASAPI loopback requires matching the default device settings
        native_rate = int(self._device_info["defaultSampleRate"])
        channels = self._device_info["maxInputChannels"]

        try:
            self._stream = self._p.open(
                format=pyaudio.paFloat32,
                channels=channels,
                rate=native_rate,
                input=True,
                frames_per_buffer=1024,
                input_device_index=self._device_info["index"],
                stream_callback=self._pa_callback,
            )
        except Exception as exc:
            self.stop()
            raise AudioCaptureError(f"Failed to open WASAPI stream: {exc}") from exc

    def _pa_callback(
        self, in_data: bytes, frame_count: int, time_info: dict[str, Any], status: int
    ) -> tuple[None, int]:
        """Internal callback handling conversion and resampling.

        Args:
            in_data: Raw audio bytes from PyAudio.
            frame_count: Number of frames in the buffer.
            time_info: Timing information from PyAudio (unused).
            status: Status flags from PyAudio.

        Returns:
            Tuple of (None, paContinue) to keep the stream running.
        """
        import pyaudiowpatch as pyaudio  # noqa: PLC0415

        if status:
            logger.warning("PyAudio status: %d", status)

        if self._user_callback and in_data:
            # 1. Convert bytes to float32 numpy array
            audio_data = np.frombuffer(in_data, dtype=np.float32)

            # 2. Reshape to (frames, channels)
            # _device_info is guaranteed non-None when stream is open
            assert self._device_info is not None
            channels = self._device_info["maxInputChannels"]
            audio_data = audio_data.reshape(-1, channels)

            # 3. Downmix to mono (average channels)
            if channels > 1:
                audio_data = np.mean(audio_data, axis=1)
            else:
                audio_data = audio_data.flatten()

            # 4. Resample to target rate (16kHz)
            native_rate = int(self._device_info["defaultSampleRate"])
            audio_data = resample_audio(audio_data, native_rate, self._target_rate)

            self._user_callback(audio_data)

        return (None, pyaudio.paContinue)

    def stop(self) -> None:
        """Stop and clean up PyAudio resources.

        Safe to call even if capture is not running; logs and returns silently.
        """
        if self._stream is not None:
            try:
                self._stream.stop_stream()
                self._stream.close()
            except Exception as exc:
                logger.warning("Error closing PyAudio stream: %s", exc)
            finally:
                self._stream = None

        if self._p is not None:
            try:
                self._p.terminate()
            except Exception as exc:
                logger.warning("Error terminating PyAudio: %s", exc)
            finally:
                self._p = None

        self._user_callback = None

    @classmethod
    def list_devices(cls) -> list[dict[str, Any]]:
        """List available WASAPI devices.

        Returns:
            List of device info dictionaries.

        Raises:
            AudioCaptureError: If PyAudio raises an error while querying devices.
        """
        import pyaudiowpatch as pyaudio  # noqa: PLC0415

        p = pyaudio.PyAudio()
        devices = []
        try:
            for i in range(p.get_device_count()):
                devices.append(p.get_device_info_by_index(i))
        except Exception as exc:
            raise AudioCaptureError(f"Failed to list WASAPI devices: {exc}") from exc
        finally:
            p.terminate()
        return devices
