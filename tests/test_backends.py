import time

import numpy as np

from src.audio.backends import resample_audio


def test_resample_10ms_chunk_under_5ms() -> None:
    chunk = np.random.randn(480).astype(np.float32)  # 10ms at 48kHz mono
    start = time.perf_counter()
    result = resample_audio(chunk, 48000, 16000)
    elapsed_ms = (time.perf_counter() - start) * 1000
    assert result.shape == (160,)
    assert elapsed_ms < 5.0, f"Resampling took {elapsed_ms:.1f}ms, expected <5ms"


def test_resample_passthrough_same_rate() -> None:
    chunk = np.random.randn(480).astype(np.float32)
    result = resample_audio(chunk, 16000, 16000)
    np.testing.assert_array_equal(result, chunk)


def test_resample_output_dtype_is_float32() -> None:
    chunk = np.random.randn(480).astype(np.float32)
    result = resample_audio(chunk, 48000, 16000)
    assert result.dtype == np.float32
