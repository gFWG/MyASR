"""Tests for PipelineOrchestrator.

Tests cover:
- Constructor creates queues with correct maxsizes
- Constructor instantiates workers with correct queue wiring
- start() calls .start() on capture, VAD, ASR workers in that order
- stop() calls .stop() on ASR, VAD workers in reverse order and .wait(3000)
- put_audio() routes chunk to audio_queue
- put_audio() drops chunk and logs warning when audio_queue is full
- connect_signals() wires asr_ready signal
- Property accessors asr_ready, error_occurred exist
- _running flag updated on start/stop
"""

from typing import Any
from unittest.mock import MagicMock, call, patch

import numpy as np
import pytest

from src.pipeline.orchestrator import PipelineOrchestrator

# ---------------------------------------------------------------------------
# Helper: build config dict
# ---------------------------------------------------------------------------


def _config() -> dict[str, Any]:
    return {
        "sample_rate": 16000,
        "asr_batch_size": 4,
        "asr_flush_timeout_ms": 500,
        "db_path": ":memory:",
    }


# ---------------------------------------------------------------------------
# Fixture: orchestrator with all heavy deps mocked
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_workers() -> dict[str, MagicMock]:
    """Pre-built mock workers (VAD / ASR)."""
    vad_worker = MagicMock()
    asr_worker = MagicMock()
    for worker in (vad_worker, asr_worker):
        worker.error_occurred = MagicMock()
    asr_worker.asr_ready = MagicMock()
    return {"vad": vad_worker, "asr": asr_worker}


@pytest.fixture()
def orchestrator(
    qt_app: Any,
    mock_workers: dict[str, MagicMock],
) -> PipelineOrchestrator:
    """PipelineOrchestrator with all GPU models and workers replaced by mocks."""
    mock_vad_model = MagicMock()
    mock_asr_model = MagicMock()
    mock_capture = MagicMock()

    with (
        patch("src.pipeline.orchestrator.SileroVAD", return_value=mock_vad_model),
        patch("src.pipeline.orchestrator.QwenASR", return_value=mock_asr_model),
        patch(
            "src.pipeline.orchestrator.WasapiLoopbackCapture",
            return_value=mock_capture,
        ),
        patch(
            "src.pipeline.orchestrator.VadWorker",
            return_value=mock_workers["vad"],
        ),
        patch(
            "src.pipeline.orchestrator.AsrWorker",
            return_value=mock_workers["asr"],
        ),
    ):
        orch = PipelineOrchestrator(config=_config())
    return orch


# ---------------------------------------------------------------------------
# Constructor: queue creation
# ---------------------------------------------------------------------------


def test_orchestrator_creates_audio_queue_with_maxsize_1000(
    orchestrator: PipelineOrchestrator,
) -> None:
    """audio_queue must have maxsize=1000."""
    assert orchestrator._audio_queue.maxsize == 1000


def test_orchestrator_creates_segment_queue_with_maxsize_20(
    orchestrator: PipelineOrchestrator,
) -> None:
    """segment_queue must have maxsize=20."""
    assert orchestrator._segment_queue.maxsize == 20


def test_orchestrator_creates_text_queue_with_maxsize_50(
    orchestrator: PipelineOrchestrator,
) -> None:
    """text_queue must have maxsize=50."""
    assert orchestrator._text_queue.maxsize == 50


# ---------------------------------------------------------------------------
# Constructor: worker instantiation
# ---------------------------------------------------------------------------


def test_orchestrator_instantiates_workers(
    qt_app: Any,
) -> None:
    """Constructor calls VadWorker, AsrWorker with expected queues."""
    with (
        patch("src.pipeline.orchestrator.SileroVAD"),
        patch("src.pipeline.orchestrator.QwenASR"),
        patch("src.pipeline.orchestrator.WasapiLoopbackCapture"),
        patch(
            "src.pipeline.orchestrator.VadWorker",
        ) as MockVadWorker,
        patch(
            "src.pipeline.orchestrator.AsrWorker",
        ) as MockAsrWorker,
    ):
        for MockWorker in (MockVadWorker, MockAsrWorker):
            instance = MagicMock()
            instance.error_occurred = MagicMock()
            instance.asr_ready = MagicMock()
            MockWorker.return_value = instance

        orch = PipelineOrchestrator(config=_config())

        # VadWorker receives audio_queue + segment_queue
        vad_call = MockVadWorker.call_args
        assert vad_call.kwargs["audio_queue"] is orch._audio_queue or (
            vad_call.args and vad_call.args[0] is orch._audio_queue
        )

        # AsrWorker receives segment_queue + text_queue
        asr_call = MockAsrWorker.call_args
        assert asr_call.kwargs.get("segment_queue") is orch._segment_queue or (
            asr_call.args and asr_call.args[0] is orch._segment_queue
        )


# ---------------------------------------------------------------------------
# start() ordering
# ---------------------------------------------------------------------------


def test_start_calls_workers_in_order(
    orchestrator: PipelineOrchestrator,
    mock_workers: dict[str, MagicMock],
) -> None:
    """start() must call VAD.start() first, then ASR."""
    manager = MagicMock()
    manager.attach_mock(mock_workers["vad"].start, "vad_start")
    manager.attach_mock(mock_workers["asr"].start, "asr_start")

    orchestrator.start()

    assert manager.mock_calls == [
        call.vad_start(),
        call.asr_start(),
    ]


def test_start_sets_running_flag(
    orchestrator: PipelineOrchestrator,
) -> None:
    """start() must set _running to True."""
    orchestrator.start()
    assert orchestrator._running is True


# ---------------------------------------------------------------------------
# stop() ordering
# ---------------------------------------------------------------------------


def test_stop_calls_workers_in_reverse_order(
    orchestrator: PipelineOrchestrator,
    mock_workers: dict[str, MagicMock],
) -> None:
    """stop() must call ASR.stop() first, then VAD."""
    orchestrator.start()

    manager = MagicMock()
    manager.attach_mock(mock_workers["vad"].stop, "vad_stop")
    manager.attach_mock(mock_workers["asr"].stop, "asr_stop")

    orchestrator.stop()

    assert manager.mock_calls == [
        call.asr_stop(),
        call.vad_stop(),
    ]


def test_stop_calls_wait_on_each_worker(
    orchestrator: PipelineOrchestrator,
    mock_workers: dict[str, MagicMock],
) -> None:
    """stop() must call .wait(3000) on each worker."""
    orchestrator.start()
    orchestrator.stop()

    mock_workers["vad"].wait.assert_called_once_with(3000)
    mock_workers["asr"].wait.assert_called_once_with(3000)


def test_stop_clears_running_flag(
    orchestrator: PipelineOrchestrator,
) -> None:
    """stop() must set _running to False."""
    orchestrator.start()
    orchestrator.stop()
    assert orchestrator._running is False


# ---------------------------------------------------------------------------
# put_audio()
# ---------------------------------------------------------------------------


def test_put_audio_routes_chunk_to_audio_queue(
    orchestrator: PipelineOrchestrator,
) -> None:
    """put_audio() places the chunk into audio_queue."""
    chunk = np.zeros(512, dtype=np.float32)
    orchestrator.put_audio(chunk)
    assert not orchestrator._audio_queue.empty()
    retrieved = orchestrator._audio_queue.get_nowait()
    np.testing.assert_array_equal(retrieved, chunk)


def test_put_audio_drops_chunk_when_queue_full(
    orchestrator: PipelineOrchestrator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """put_audio() drops chunk and logs warning when audio_queue is full."""
    import logging

    # Fill the queue to capacity
    chunk = np.zeros(512, dtype=np.float32)
    for _ in range(orchestrator._audio_queue.maxsize):
        orchestrator._audio_queue.put_nowait(chunk)

    assert orchestrator._audio_queue.full()

    with caplog.at_level(logging.WARNING, logger="src.pipeline.orchestrator"):
        orchestrator.put_audio(chunk)  # Should NOT raise, should warn

    # Queue remains full (chunk was dropped, not enqueued)
    assert orchestrator._audio_queue.full()
    assert orchestrator._audio_queue.qsize() == orchestrator._audio_queue.maxsize

    warning_texts = [r.message for r in caplog.records if r.levelno == logging.WARNING]
    assert any("drop" in str(t).lower() or "full" in str(t).lower() for t in warning_texts), (
        f"Expected drop/full warning, got: {warning_texts}"
    )


# ---------------------------------------------------------------------------
# connect_signals()
# ---------------------------------------------------------------------------


def test_connect_signals_connects_asr_ready(
    orchestrator: PipelineOrchestrator,
    mock_workers: dict[str, MagicMock],
) -> None:
    """connect_signals() calls connect on asr_worker.asr_ready."""
    on_asr = MagicMock()
    orchestrator.connect_signals(on_asr_ready=on_asr)
    mock_workers["asr"].asr_ready.connect.assert_called_once_with(on_asr)


# ---------------------------------------------------------------------------
# Signal property accessors
# ---------------------------------------------------------------------------


def test_asr_ready_property_returns_worker_signal(
    orchestrator: PipelineOrchestrator,
    mock_workers: dict[str, MagicMock],
) -> None:
    """asr_ready property must return the asr_worker.asr_ready signal."""
    assert orchestrator.asr_ready is mock_workers["asr"].asr_ready


def test_error_occurred_property_accessible(
    orchestrator: PipelineOrchestrator,
) -> None:
    """error_occurred property must be accessible (list of worker signals)."""
    err = orchestrator.error_occurred
    assert isinstance(err, list)
    assert len(err) == 2


def test_on_config_changed_calls_vad_worker_update(
    orchestrator: PipelineOrchestrator,
    mock_workers: dict[str, MagicMock],
) -> None:
    """on_config_changed() should call VadWorker.update_vad_params with config values."""
    from src.config import AppConfig

    config = AppConfig(
        vad_threshold=0.7,
        vad_min_silence_ms=500,
        vad_min_speech_ms=300,
    )

    orchestrator.on_config_changed(config)

    mock_workers["vad"].update_vad_params.assert_called_once_with(
        threshold=0.7,
        min_silence_ms=500,
        min_speech_ms=300,
    )
