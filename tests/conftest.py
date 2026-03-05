"""Shared fixtures for the test suite."""

from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

DEV_DIR = Path(__file__).resolve().parent.parent / "dev"


@pytest.fixture()
def short_wav() -> tuple[np.ndarray, int]:
    """Load dev/short.wav as mono float32 numpy array + sample rate."""
    path = DEV_DIR / "short.wav"
    if not path.exists():
        pytest.skip(f"Test audio not found: {path}")
    data, sr = sf.read(str(path), dtype="float32", always_2d=False)
    if data.ndim == 2:
        data = data.mean(axis=1)
    return data, int(sr)


@pytest.fixture()
def long_wav() -> tuple[np.ndarray, int]:
    """Load dev/long.wav as mono float32 numpy array + sample rate."""
    path = DEV_DIR / "long.wav"
    if not path.exists():
        pytest.skip(f"Test audio not found: {path}")
    data, sr = sf.read(str(path), dtype="float32", always_2d=False)
    if data.ndim == 2:
        data = data.mean(axis=1)
    return data, int(sr)
