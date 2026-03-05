# PyAudioWPatch Integration Guide

This guide describes how to integrate `PyAudioWPatch` as the Windows audio backend for MyASR. While `sounddevice` is used for cross-platform microphone capture, `PyAudioWPatch` is required on Windows to capture system audio loopback (WASAPI) without needing virtual audio cables.

## Overview

On Windows 11, capturing what you hear (system audio) requires using the Windows Audio Session API (WASAPI) in loopback mode. Standard `sounddevice` implementations often struggle with loopback device enumeration and stable capture on Windows. `PyAudioWPatch` provides a specialized fork of PyAudio that simplifies finding and opening these loopback devices.

## Key Differences from sounddevice

| Feature | sounddevice | PyAudioWPatch |
|---------|-------------|---------------|
| Callback Input | `np.ndarray` (float32) | `bytes` (raw buffer) |
| Callback Return | `None` | `(None, pyaudio.paContinue)` |
| Sample Rate | Direct (e.g., 16000Hz) | Inherited from OS (typically 44.1k/48k) |
| Channels | Mono (requested) | Typically Stereo (downmix needed) |
| Status Flags | `CallbackFlags` object | Integer bitmask |
| Format Constant | `"float32"` string | `pyaudio.paFloat32` |

## Installation

Add `pyaudiowpatch` to your environment. Note that this is a Windows-only dependency for the loopback feature.

```bash
pip install pyaudiowpatch
```

In `requirements.txt`, use an environment marker:
```text
pyaudiowpatch; platform_system=="Windows"
```

## Recommended Architecture

Following the project convention of avoiding abstract base classes (ABCs), use a simple factory function to instantiate the correct backend based on the operating system.

```python
import sys
from src.config import AppConfig
from src.audio.capture import AudioCapture
# from src.audio.backends import WasapiLoopbackCapture (suggested location)

def create_audio_capture(config: AppConfig) -> AudioCapture:
    """Factory to create the appropriate audio capture backend.
    
    Args:
        config: Application configuration.
        
    Returns:
        An instance compatible with the AudioCapture interface.
    """
    if sys.platform == "win32":
        # Fallback to AudioCapture if specifically requested, 
        # but default to WASAPI for Windows system audio.
        return WasapiLoopbackCapture(sample_rate=config.sample_rate)
    return AudioCapture(sample_rate=config.sample_rate)
```

## WasapiLoopbackCapture Implementation

The following skeleton implements the `WasapiLoopbackCapture` class. It handles device discovery, resampling from the hardware rate to the target rate, and mono downmixing.

```python
import logging
import wave
from collections.abc import Callable
from typing import Any

import numpy as np
from src.exceptions import AudioCaptureError

logger = logging.getLogger(__name__)

class WasapiLoopbackCapture:
    """Windows-specific audio capture for system loopback using PyAudioWPatch."""

    def __init__(self, sample_rate: int = 16000) -> None:
        self._target_rate = sample_rate
        self._p: Any = None
        self._stream: Any = None
        self._user_callback: Callable[[np.ndarray], None] | None = None
        self._device_info: dict[str, Any] | None = None

    def _get_loopback_device(self, p: Any) -> dict[str, Any]:
        try:
            return p.get_default_wasapi_loopback()
        except OSError as exc:
            raise AudioCaptureError("No WASAPI loopback device found") from exc

    def start(self, callback: Callable[[np.ndarray], None]) -> None:
        """Starts the WASAPI loopback stream."""
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

    def _pa_callback(self, in_data: bytes, frame_count: int, time_info: dict, status: int) -> tuple:
        """Internal callback handling conversion and resampling."""
        import pyaudiowpatch as pyaudio  # noqa: PLC0415
        
        if status:
            logger.warning("PyAudio status: %d", status)

        if self._user_callback and in_data:
            # 1. Convert bytes to float32 numpy array
            audio_data = np.frombuffer(in_data, dtype=np.float32)
            
            # 2. Reshape to (frames, channels)
            channels = self._device_info["maxInputChannels"]
            audio_data = audio_data.reshape(-1, channels)
            
            # 3. Downmix to mono (average channels)
            if channels > 1:
                audio_data = np.mean(audio_data, axis=1)
            else:
                audio_data = audio_data.flatten()

            # 4. Resample to target rate (16kHz)
            # Use scipy.signal.resample for better quality if available
            native_rate = int(self._device_info["defaultSampleRate"])
            if native_rate != self._target_rate:
                num_samples = int(len(audio_data) * self._target_rate / native_rate)
                from scipy.signal import resample  # noqa: PLC0415
                audio_data = resample(audio_data, num_samples).astype(np.float32)

            self._user_callback(audio_data)

        return (None, pyaudio.paContinue)

    def stop(self) -> None:
        """Stops and cleans up the PyAudio resources."""
        if self._stream:
            self._stream.stop_stream()
            self._stream.close()
            self._stream = None
        
        if self._p:
            self._p.terminate()
            self._p = None
        
        self._user_callback = None

    @classmethod
    def list_devices(cls) -> list[dict[str, Any]]:
        """Lists available WASAPI devices."""
        import pyaudiowpatch as pyaudio  # noqa: PLC0415
        p = pyaudio.PyAudio()
        devices = []
        try:
            for i in range(p.get_device_count()):
                devices.append(p.get_device_info_by_index(i))
        finally:
            p.terminate()
        return devices
```

## Critical Gotchas

1. **Callback Mode Only**: Standard WASAPI loopback can block the entire thread if the system is silent when using blocking reads. Always use the `stream_callback` approach as shown above.
2. **Dynamic Sample Rate**: Never hardcode the input sample rate for WASAPI loopback. You must query `device['defaultSampleRate']` from the device dictionary, or the stream will fail to open.
3. **Channel Count**: Loopback devices usually match the output configuration (e.g., 2 channels for stereo, 6 or 8 for surround). Use `device['maxInputChannels']` to correctly reshape the buffer before downmixing.
4. **Resampling overhead**: Resampling in the callback adds CPU load. Ensure the block size (`frames_per_buffer`) is large enough to handle the computation but small enough for low latency.

## Pipeline Integration

Update `src/pipeline.py` (or your main entry point) to use the factory function instead of hardcoding `AudioCapture`.

```python
# In src/pipeline.py
from src.audio.capture import create_audio_capture # Using the factory

class Pipeline:
    def __init__(self, config: AppConfig):
        self.config = config
        # Use the factory to get the right backend for the OS
        self.audio = create_audio_capture(config)
        
    def start(self):
        self.audio.start(self._on_audio)
        
    def _on_audio(self, data: np.ndarray):
        # Data is already mono float32 16kHz
        self.vad.process(data)
```

## Testing Strategy

### Windows Testing
Test on a physical Windows machine with active audio playback (e.g., YouTube or Spotify). Verify that `WasapiLoopbackCapture` correctly captures system audio even when no microphone is connected.

### WSL2 / Linux Development
Since WASAPI is not available on Linux/WSL, you must mock the backend:

```python
def test_pipeline_with_mock_audio():
    class MockAudio:
        def start(self, cb): self.cb = cb
        def stop(self): pass
        
    pipeline = Pipeline(config)
    pipeline.audio = MockAudio()
    # Manually trigger callback with synthetic data
    pipeline.audio.cb(np.zeros(1600, dtype=np.float32))
```

Ensure that CI/CD pipelines skip Windows-specific tests or use a conditional decorator:
```python
import pytest
import sys

@pytest.mark.skipif(sys.platform != "win32", reason="Windows only test")
def test_wasapi_initialization():
    capture = WasapiLoopbackCapture()
    # ...
```
