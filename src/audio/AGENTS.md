# AUDIO CAPTURE KNOWLEDGE BASE

## OVERVIEW

Abstraction layer for platform-specific audio capture. Provides mono float32 audio at 16kHz for VAD and ASR stages. Targets Windows 11 system loopback.

## STRUCTURE

- `capture.py`: Defines `AudioCapture` (sounddevice) and `create_audio_capture` factory.
- `backends.py`: `WasapiLoopbackCapture` (PyAudioWPatch) for Windows system audio.
- `__init__.py`: Package initialization.

## CONVENTIONS

- **Duck Typing**: Backends implement `start(callback)`, `stop()`, and `list_devices()`.
- **Callback Pattern**: `callback` receives a 1D `np.ndarray` (float32, 16kHz).
- **Lazy Imports**: `sounddevice` and `pyaudiowpatch` are imported within methods to prevent crashes in incompatible environments (e.g., WSL2).
- **Resampling**: `backends.resample_audio` uses `soxr` (high quality) with `scipy` fallback.

## ADDING A BACKEND

New backends should follow the `AudioCapture` interface:
1. Implement `start(callback: Callable[[np.ndarray], None])`.
2. Implement `stop()`.
3. Implement class method `list_devices()`.
4. Update `create_audio_capture` factory in `capture.py` to include the new backend.

## NOTES

- **Windows Priority**: `WasapiLoopbackCapture` is the default on Windows to capture what the user hears.
- **Cross-platform**: `sounddevice` serves as a fallback for microphone input on non-Windows systems.
- **Factory Status**: `create_audio_capture` factory exists but orchestrator currently hardwires `WasapiLoopbackCapture` directly.
- **Resampling Requirement**: WASAPI often runs at 44.1/48kHz. Internal resampling to 16kHz is mandatory for the pipeline.
