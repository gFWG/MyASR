"""Tests for VadWorker QThread.

Tests cover:
- Processes audio chunks correctly (VAD result → SpeechSegment in segment_queue)
- Clean shutdown in <2s (stop() waits 2000ms)
- Emits error_occurred on exception inside run loop (no crash)
- Full segment_queue → drop+warning (no deadlock)
"""

import queue
import time
import uuid
from typing import Any
from unittest.mock import MagicMock

import numpy as np
import pytest
from PySide6.QtCore import QCoreApplication

from src.db.models import AudioSegment
from src.pipeline.types import SpeechSegment
from src.pipeline.vad_worker import VadWorker


@pytest.fixture(scope="module")
def qt_app() -> QCoreApplication:
    """Create a QCoreApplication for QThread tests."""
    import sys

    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication(sys.argv)
    return app  # type: ignore[return-value]  # QCoreApplication.instance() returns QCoreApplication|None


@pytest.fixture()
def audio_queue() -> queue.Queue[np.ndarray]:
    """Create an audio input queue."""
    return queue.Queue(maxsize=1000)


@pytest.fixture()
def segment_queue() -> queue.Queue[SpeechSegment]:
    """Create a segment output queue."""
    return queue.Queue(maxsize=20)


@pytest.fixture()
def mock_vad() -> MagicMock:
    """Create a mock SileroVAD that returns None by default."""
    vad = MagicMock()
    vad.process_chunk.return_value = None
    return vad


@pytest.fixture()
def config() -> dict[str, Any]:
    """Default config for VadWorker."""
    return {"segment_queue_maxsize": 20, "sample_rate": 16000}


@pytest.fixture()
def worker(
    qt_app: QCoreApplication,
    audio_queue: queue.Queue[np.ndarray],
    segment_queue: queue.Queue[SpeechSegment],
    mock_vad: MagicMock,
    config: dict[str, Any],
) -> VadWorker:
    """Create a VadWorker with mock VAD."""
    return VadWorker(
        audio_queue=audio_queue,
        segment_queue=segment_queue,
        vad=mock_vad,
        config=config,
    )


# ---------------------------------------------------------------------------
# Constructor tests
# ---------------------------------------------------------------------------


def test_vad_worker_init_sets_attributes(
    qt_app: QCoreApplication,
    audio_queue: queue.Queue[np.ndarray],
    segment_queue: queue.Queue[SpeechSegment],
    mock_vad: MagicMock,
    config: dict[str, Any],
) -> None:
    """VadWorker constructor stores queues and vad as attributes."""
    w = VadWorker(
        audio_queue=audio_queue,
        segment_queue=segment_queue,
        vad=mock_vad,
        config=config,
    )
    assert w._audio_queue is audio_queue
    assert w._segment_queue is segment_queue
    assert w._vad is mock_vad
    assert w._config is config
    assert w._running is False


# ---------------------------------------------------------------------------
# Signal tests
# ---------------------------------------------------------------------------


def test_vad_worker_has_error_occurred_signal(worker: VadWorker) -> None:
    """VadWorker must have an error_occurred signal."""
    assert hasattr(worker, "error_occurred")


def test_vad_worker_has_segment_ready_signal(worker: VadWorker) -> None:
    """VadWorker must have a segment_ready signal."""
    assert hasattr(worker, "segment_ready")


# ---------------------------------------------------------------------------
# Audio processing tests
# ---------------------------------------------------------------------------


def test_vad_worker_processes_chunk_and_emits_segment(
    qt_app: QCoreApplication,
    audio_queue: queue.Queue[np.ndarray],
    segment_queue: queue.Queue[SpeechSegment],
    config: dict[str, Any],
) -> None:
    """When VAD returns an AudioSegment, it is converted and placed in segment_queue."""
    samples = np.zeros(512, dtype=np.float32)
    audio_seg = AudioSegment(samples=samples, duration_sec=0.032)

    mock_vad = MagicMock()
    mock_vad.process_chunk.return_value = [audio_seg]

    w = VadWorker(
        audio_queue=audio_queue,
        segment_queue=segment_queue,
        vad=mock_vad,
        config=config,
    )

    # Put one chunk then a sentinel to stop the worker quickly
    chunk = np.zeros(512, dtype=np.float32)
    audio_queue.put(chunk)

    w.start()
    # Wait until segment appears or timeout
    deadline = time.monotonic() + 2.0
    got_segment = False
    while time.monotonic() < deadline:
        try:
            seg = segment_queue.get(timeout=0.05)
            got_segment = True
            break
        except queue.Empty:
            pass

    w.stop()

    assert got_segment, "Expected a SpeechSegment in segment_queue"
    assert isinstance(seg, SpeechSegment)
    np.testing.assert_array_equal(seg.audio, samples)
    assert seg.sample_rate == config.get("sample_rate", 16000)
    assert seg.timestamp > 0.0
    assert isinstance(seg.segment_id, str)
    # Validate it's a UUID
    uuid.UUID(seg.segment_id)


def test_vad_worker_skips_none_vad_result(
    qt_app: QCoreApplication,
    audio_queue: queue.Queue[np.ndarray],
    segment_queue: queue.Queue[SpeechSegment],
    mock_vad: MagicMock,
    config: dict[str, Any],
) -> None:
    """When VAD returns None, nothing is put in segment_queue."""
    mock_vad.process_chunk.return_value = None

    w = VadWorker(
        audio_queue=audio_queue,
        segment_queue=segment_queue,
        vad=mock_vad,
        config=config,
    )

    chunk = np.zeros(512, dtype=np.float32)
    audio_queue.put(chunk)

    w.start()
    time.sleep(0.2)
    w.stop()

    assert segment_queue.empty(), "No segment should be queued when VAD returns None"


def test_vad_worker_processes_multiple_segments_per_chunk(
    qt_app: QCoreApplication,
    audio_queue: queue.Queue[np.ndarray],
    segment_queue: queue.Queue[SpeechSegment],
    config: dict[str, Any],
) -> None:
    """When VAD returns multiple AudioSegments, all are placed in segment_queue."""
    s1 = np.zeros(512, dtype=np.float32)
    s2 = np.ones(512, dtype=np.float32)
    segs = [
        AudioSegment(samples=s1, duration_sec=0.032),
        AudioSegment(samples=s2, duration_sec=0.032),
    ]

    mock_vad = MagicMock()
    mock_vad.process_chunk.return_value = segs

    w = VadWorker(
        audio_queue=audio_queue,
        segment_queue=segment_queue,
        vad=mock_vad,
        config=config,
    )

    chunk = np.zeros(512, dtype=np.float32)
    audio_queue.put(chunk)

    w.start()
    deadline = time.monotonic() + 2.0
    collected: list[SpeechSegment] = []
    while time.monotonic() < deadline and len(collected) < 2:
        try:
            collected.append(segment_queue.get(timeout=0.05))
        except queue.Empty:
            pass

    w.stop()

    assert len(collected) == 2, f"Expected 2 segments, got {len(collected)}"


# ---------------------------------------------------------------------------
# Shutdown tests
# ---------------------------------------------------------------------------


def test_vad_worker_stop_completes_within_2s(
    qt_app: QCoreApplication,
    audio_queue: queue.Queue[np.ndarray],
    segment_queue: queue.Queue[SpeechSegment],
    mock_vad: MagicMock,
    config: dict[str, Any],
) -> None:
    """stop() should complete within 2 seconds."""
    mock_vad.process_chunk.return_value = None

    w = VadWorker(
        audio_queue=audio_queue,
        segment_queue=segment_queue,
        vad=mock_vad,
        config=config,
    )

    w.start()
    time.sleep(0.1)

    t0 = time.monotonic()
    w.stop()
    elapsed = time.monotonic() - t0

    assert elapsed < 2.0, f"stop() took {elapsed:.2f}s — expected < 2s"
    assert not w.isRunning(), "Worker thread should have stopped"


def test_vad_worker_running_flag_false_after_stop(
    qt_app: QCoreApplication,
    worker: VadWorker,
) -> None:
    """_running should be False after stop() is called."""
    worker.start()
    time.sleep(0.05)
    worker.stop()
    assert worker._running is False


# ---------------------------------------------------------------------------
# Error handling tests
# ---------------------------------------------------------------------------


def test_vad_worker_emits_error_on_vad_exception(
    qt_app: QCoreApplication,
    audio_queue: queue.Queue[np.ndarray],
    segment_queue: queue.Queue[SpeechSegment],
    config: dict[str, Any],
) -> None:
    """When VAD raises, error_occurred is emitted and worker continues (no crash)."""
    mock_vad = MagicMock()
    mock_vad.process_chunk.side_effect = RuntimeError("VAD exploded")

    w = VadWorker(
        audio_queue=audio_queue,
        segment_queue=segment_queue,
        vad=mock_vad,
        config=config,
    )

    emitted_errors: list[str] = []
    from PySide6.QtCore import Qt

    w.error_occurred.connect(emitted_errors.append, Qt.ConnectionType.DirectConnection)

    chunk = np.zeros(512, dtype=np.float32)
    audio_queue.put(chunk)

    w.start()
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline and not emitted_errors:
        time.sleep(0.05)

    w.stop()

    assert len(emitted_errors) >= 1, "Expected error_occurred to be emitted"
    assert "VAD exploded" in emitted_errors[0]


def test_vad_worker_continues_after_exception(
    qt_app: QCoreApplication,
    audio_queue: queue.Queue[np.ndarray],
    segment_queue: queue.Queue[SpeechSegment],
    config: dict[str, Any],
) -> None:
    """After an exception, worker continues processing subsequent chunks."""
    samples = np.zeros(512, dtype=np.float32)
    audio_seg = AudioSegment(samples=samples, duration_sec=0.032)

    call_count = 0

    def side_effect(chunk: np.ndarray) -> list[AudioSegment] | None:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("First call fails")
        return [audio_seg]

    mock_vad = MagicMock()
    mock_vad.process_chunk.side_effect = side_effect

    w = VadWorker(
        audio_queue=audio_queue,
        segment_queue=segment_queue,
        vad=mock_vad,
        config=config,
    )

    # Two chunks: first triggers error, second should produce segment
    chunk = np.zeros(512, dtype=np.float32)
    audio_queue.put(chunk)
    audio_queue.put(chunk)

    w.start()
    deadline = time.monotonic() + 2.0
    got_segment = False
    while time.monotonic() < deadline:
        try:
            segment_queue.get(timeout=0.05)
            got_segment = True
            break
        except queue.Empty:
            pass

    w.stop()

    assert got_segment, "Worker should continue processing after exception"


# ---------------------------------------------------------------------------
# Queue full / drop tests
# ---------------------------------------------------------------------------


def test_vad_worker_drops_segment_when_queue_full(
    qt_app: QCoreApplication,
    audio_queue: queue.Queue[np.ndarray],
    config: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """When segment_queue is full, new segments are dropped with a warning (no deadlock)."""
    # Create a full segment_queue (maxsize=1)
    full_segment_queue: queue.Queue[SpeechSegment] = queue.Queue(maxsize=1)
    # Fill it
    dummy_seg = SpeechSegment(
        audio=np.zeros(1, dtype=np.float32),
        sample_rate=16000,
        timestamp=0.0,
        segment_id=str(uuid.uuid4()),
    )
    full_segment_queue.put_nowait(dummy_seg)
    assert full_segment_queue.full()

    samples = np.zeros(512, dtype=np.float32)
    audio_seg = AudioSegment(samples=samples, duration_sec=0.032)

    mock_vad = MagicMock()
    mock_vad.process_chunk.return_value = [audio_seg]

    w = VadWorker(
        audio_queue=audio_queue,
        segment_queue=full_segment_queue,
        vad=mock_vad,
        config=config,
    )

    chunk = np.zeros(512, dtype=np.float32)
    audio_queue.put(chunk)

    import logging

    with caplog.at_level(logging.WARNING, logger="src.pipeline.vad_worker"):
        w.start()
        time.sleep(0.3)
        w.stop()

    # Queue should still be full (dropped, not blocked)
    assert full_segment_queue.full(), "Queue should remain full; segment was dropped not blocked"
    assert full_segment_queue.qsize() == 1, "Queue size should remain 1"

    # Warning should have been logged
    warning_msgs = [r.message for r in caplog.records if r.levelno == logging.WARNING]
    assert any("full" in str(m).lower() or "drop" in str(m).lower() for m in warning_msgs), (
        "Expected a queue-full warning"
    )


def test_vad_worker_no_deadlock_on_full_queue(
    qt_app: QCoreApplication,
    audio_queue: queue.Queue[np.ndarray],
    config: dict[str, Any],
) -> None:
    """Worker must not deadlock when segment_queue is full — must finish in <2s."""
    full_queue: queue.Queue[SpeechSegment] = queue.Queue(maxsize=1)
    dummy_seg = SpeechSegment(
        audio=np.zeros(1, dtype=np.float32),
        sample_rate=16000,
        timestamp=0.0,
        segment_id=str(uuid.uuid4()),
    )
    full_queue.put_nowait(dummy_seg)

    samples = np.zeros(512, dtype=np.float32)
    audio_seg = AudioSegment(samples=samples, duration_sec=0.032)
    mock_vad = MagicMock()
    mock_vad.process_chunk.return_value = [audio_seg]

    w = VadWorker(
        audio_queue=audio_queue,
        segment_queue=full_queue,
        vad=mock_vad,
        config=config,
    )

    # Put many chunks
    for _ in range(10):
        chunk = np.zeros(512, dtype=np.float32)
        try:
            audio_queue.put_nowait(chunk)
        except queue.Full:
            break

    w.start()
    time.sleep(0.2)

    t0 = time.monotonic()
    w.stop()
    elapsed = time.monotonic() - t0

    assert elapsed < 2.0, f"stop() took {elapsed:.2f}s — potential deadlock on full queue"
