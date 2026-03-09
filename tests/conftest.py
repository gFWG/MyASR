"""Shared fixtures for the test suite."""

import sys
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf
from PySide6.QtWidgets import QApplication

DEV_DIR = Path(__file__).resolve().parent.parent / "dev"


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    """Shared QApplication for all tests (session scope).

    Both worker tests (QThread) and widget tests (QWidget) need a Qt event
    loop.  QApplication is a superset of QCoreApplication, so it satisfies
    both.  Using session scope ensures only one instance exists per process.
    """
    app = QApplication.instance()
    if not isinstance(app, QApplication):
        app = QApplication(sys.argv)
    return app


@pytest.fixture(scope="session")
def qt_app(qapp: QApplication) -> QApplication:
    """Alias for ``qapp`` — used by worker / pipeline tests."""
    return qapp


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
