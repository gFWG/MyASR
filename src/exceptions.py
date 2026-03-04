"""MyASR exception hierarchy."""


class MyASRError(Exception):
    """Base exception for all MyASR errors."""


class AudioCaptureError(MyASRError):
    """Error during audio capture."""


class VADError(MyASRError):
    """Error during voice activity detection."""


class ASRError(MyASRError):
    """Error during automatic speech recognition."""


class ModelLoadError(ASRError):
    """Failed to load a model (ASR, VAD, etc.)."""


class PreprocessingError(MyASRError):
    """Error during text preprocessing/analysis."""


class LLMError(MyASRError):
    """Error communicating with the LLM service."""


class LLMTimeoutError(LLMError):
    """LLM request timed out."""


class LLMUnavailableError(LLMError):
    """LLM service is not reachable."""


class DatabaseError(MyASRError):
    """Error during database operations."""
