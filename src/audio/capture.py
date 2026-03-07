"""Audio capture module using sounddevice."""

import logging
import sys
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import numpy as np

from src.config import AppConfig
from src.exceptions import AudioCaptureError

if TYPE_CHECKING:
    from src.audio.backends import WasapiLoopbackCapture

logger = logging.getLogger(__name__)


class AudioCapture:
    """Captures audio from an input device using sounddevice.

    Uses lazy import of sounddevice to allow the module to be imported
    even when sounddevice is not installed or an audio device is unavailable.

    Args:
        device_id: Input device index. None uses the system default.
        sample_rate: Sample rate in Hz. Defaults to 16000 for VAD/ASR compatibility.
    """

    def __init__(self, device_id: int | None = None, sample_rate: int = 16000) -> None:
        self._device_id = device_id
        self._sample_rate = sample_rate
        self._stream: Any = None
        self._user_callback: Callable[[np.ndarray], None] | None = None

    def start(self, callback: Callable[[np.ndarray], None]) -> None:
        """Start audio capture and invoke callback on each audio block.

        Args:
            callback: Called with a mono float32 numpy array (shape: [blocksize])
                for each captured audio block.

        Raises:
            AudioCaptureError: If already running, or if sounddevice raises an error.
        """
        if self._stream is not None:
            raise AudioCaptureError("already running")

        import sounddevice as sd  # noqa: PLC0415

        self._user_callback = callback
        try:
            self._stream = sd.InputStream(
                samplerate=self._sample_rate,
                blocksize=512,
                device=self._device_id,
                channels=1,
                dtype="float32",
                callback=self._audio_callback,
            )
            self._stream.start()
        except Exception as exc:
            self._stream = None
            self._user_callback = None
            raise AudioCaptureError(f"Failed to start audio capture: {exc}") from exc

    def _audio_callback(
        self,
        indata: np.ndarray,
        frames: int,
        time: Any,
        status: Any,
    ) -> None:
        """Internal sounddevice callback; forwards mono audio to user callback.

        Args:
            indata: Input audio block, shape (blocksize, channels).
            frames: Number of frames in the block.
            time: Timing information from sounddevice (unused).
            status: Status flags from sounddevice.
        """
        if status:
            logger.warning("Audio status: %s", status)
        if self._user_callback is not None:
            self._user_callback(indata[:, 0].copy())

    def stop(self) -> None:
        """Stop audio capture and release the stream.

        Safe to call even if capture is not running; logs and returns silently.
        """
        if self._stream is None:
            logger.debug("stop() called but stream is not running; no-op")
            return
        self._stream.stop()
        self._stream.close()
        self._stream = None

    @classmethod
    def list_devices(cls) -> list[dict[str, Any]]:
        """List all available audio input/output devices.

        Returns:
            List of device info dicts as returned by sounddevice.query_devices().

        Raises:
            AudioCaptureError: If sounddevice raises an error while querying devices.
        """
        import sounddevice as sd  # noqa: PLC0415

        try:
            return list(sd.query_devices())
        except Exception as exc:
            raise AudioCaptureError(f"Failed to list audio devices: {exc}") from exc


# Type alias for audio capture instances (protocol-like interface)
type AudioCaptureLike = AudioCapture | WasapiLoopbackCapture


def create_audio_capture(config: AppConfig) -> AudioCaptureLike:
    """Factory to create the appropriate audio capture backend.

    On Windows, uses WasapiLoopbackCapture for system audio loopback.
    On other platforms, uses AudioCapture with sounddevice for microphone input.

    Args:
        config: Application configuration.

    Returns:
        An instance compatible with the AudioCapture interface.
    """
    if sys.platform == "win32":
        from src.audio.backends import WasapiLoopbackCapture  # noqa: PLC0415

        return WasapiLoopbackCapture(sample_rate=config.sample_rate)
    return AudioCapture(sample_rate=config.sample_rate)
