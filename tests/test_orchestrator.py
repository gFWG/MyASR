"""Tests for PipelineOrchestrator.

Tests cover:
- Constructor creates all four queues with correct maxsizes
- Constructor instantiates workers with correct queue wiring
- start() calls .start() on VAD, ASR, LLM workers in that order
- stop() calls .stop() on LLM, ASR, VAD workers in reverse order and .wait(3000)
- put_audio() routes chunk to audio_queue
- put_audio() drops chunk and logs warning when audio_queue is full
- connect_signals() wires asr_ready and translation_ready signals
- Property accessors asr_ready, translation_ready, error_occurred exist
- _running flag updated on start/stop
"""

import sys
from typing import Any
from unittest.mock import MagicMock, call, patch

import numpy as np
import pytest
from PySide6.QtCore import QCoreApplication

from src.pipeline.orchestrator import PipelineOrchestrator

# ---------------------------------------------------------------------------
# Qt app fixture (required for QThread subclass workers)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def qt_app() -> QCoreApplication:
    """Create a QCoreApplication for tests that need it."""
    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication(sys.argv)
    return app


# ---------------------------------------------------------------------------
# Helper: build config dict
# ---------------------------------------------------------------------------


def _config() -> dict[str, Any]:
    return {
        "sample_rate": 16000,
        "asr_batch_size": 4,
        "asr_flush_timeout_ms": 500,
        "db_path": ":memory:",
        "ollama_url": "http://localhost:11434",
        "ollama_model": "qwen3.5:4b",
    }


# ---------------------------------------------------------------------------
# Fixture: orchestrator with all heavy deps mocked
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_workers() -> dict[str, MagicMock]:
    """Pre-built mock workers (VAD / ASR / LLM)."""
    vad_worker = MagicMock()
    asr_worker = MagicMock()
    llm_worker = MagicMock()
    # Simulate Qt signals as MagicMock attributes
    for worker in (vad_worker, asr_worker, llm_worker):
        worker.error_occurred = MagicMock()
    asr_worker.asr_ready = MagicMock()
    llm_worker.translation_ready = MagicMock()
    return {"vad": vad_worker, "asr": asr_worker, "llm": llm_worker}


@pytest.fixture()
def orchestrator(
    qt_app: QCoreApplication,
    mock_workers: dict[str, MagicMock],
) -> PipelineOrchestrator:
    """PipelineOrchestrator with all GPU models and workers replaced by mocks."""
    mock_vad_model = MagicMock()
    mock_asr_model = MagicMock()
    mock_llm_client = MagicMock()
    mock_db_repo = MagicMock()

    mock_capture = MagicMock()

    with (
        patch("src.pipeline.orchestrator.SileroVAD", return_value=mock_vad_model),
        patch("src.pipeline.orchestrator.QwenASR", return_value=mock_asr_model),
        patch("src.pipeline.orchestrator.AsyncOllamaClient", return_value=mock_llm_client),
        patch("src.pipeline.orchestrator.LearningRepository", return_value=mock_db_repo),
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
        patch(
            "src.pipeline.orchestrator.LlmWorker",
            return_value=mock_workers["llm"],
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


def test_orchestrator_creates_result_queue_with_maxsize_50(
    orchestrator: PipelineOrchestrator,
) -> None:
    """result_queue must have maxsize=50."""
    assert orchestrator._result_queue.maxsize == 50


# ---------------------------------------------------------------------------
# Constructor: worker instantiation
# ---------------------------------------------------------------------------


def test_orchestrator_instantiates_workers(
    qt_app: QCoreApplication,
) -> None:
    """Constructor calls VadWorker, AsrWorker, LlmWorker with expected queues."""
    with (
        patch("src.pipeline.orchestrator.SileroVAD"),
        patch("src.pipeline.orchestrator.QwenASR"),
        patch("src.pipeline.orchestrator.AsyncOllamaClient"),
        patch("src.pipeline.orchestrator.LearningRepository"),
        patch("src.pipeline.orchestrator.WasapiLoopbackCapture"),
        patch(
            "src.pipeline.orchestrator.VadWorker",
        ) as MockVadWorker,
        patch(
            "src.pipeline.orchestrator.AsrWorker",
        ) as MockAsrWorker,
        patch(
            "src.pipeline.orchestrator.LlmWorker",
        ) as MockLlmWorker,
    ):
        # Provide mock signals on worker instances
        for MockWorker in (MockVadWorker, MockAsrWorker, MockLlmWorker):
            instance = MagicMock()
            instance.error_occurred = MagicMock()
            instance.asr_ready = MagicMock()
            instance.translation_ready = MagicMock()
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

        # LlmWorker receives text_queue + result_queue
        llm_call = MockLlmWorker.call_args
        assert llm_call.kwargs.get("text_queue") is orch._text_queue or (
            llm_call.args and llm_call.args[0] is orch._text_queue
        )


# ---------------------------------------------------------------------------
# start() ordering
# ---------------------------------------------------------------------------


def test_start_calls_workers_in_order(
    orchestrator: PipelineOrchestrator,
    mock_workers: dict[str, MagicMock],
) -> None:
    """start() must call VAD.start() first, then ASR, then LLM."""
    manager = MagicMock()
    manager.attach_mock(mock_workers["vad"].start, "vad_start")
    manager.attach_mock(mock_workers["asr"].start, "asr_start")
    manager.attach_mock(mock_workers["llm"].start, "llm_start")

    orchestrator.start()

    assert manager.mock_calls == [
        call.vad_start(),
        call.asr_start(),
        call.llm_start(),
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
    """stop() must call LLM.stop() first, then ASR, then VAD."""
    orchestrator.start()

    manager = MagicMock()
    manager.attach_mock(mock_workers["vad"].stop, "vad_stop")
    manager.attach_mock(mock_workers["asr"].stop, "asr_stop")
    manager.attach_mock(mock_workers["llm"].stop, "llm_stop")

    orchestrator.stop()

    assert manager.mock_calls == [
        call.llm_stop(),
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
    mock_workers["llm"].wait.assert_called_once_with(3000)


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
    on_trans = MagicMock()
    orchestrator.connect_signals(on_asr_ready=on_asr, on_translation_ready=on_trans)
    mock_workers["asr"].asr_ready.connect.assert_called_once_with(on_asr)


def test_connect_signals_connects_translation_ready(
    orchestrator: PipelineOrchestrator,
    mock_workers: dict[str, MagicMock],
) -> None:
    """connect_signals() calls connect on llm_worker.translation_ready."""
    on_asr = MagicMock()
    on_trans = MagicMock()
    orchestrator.connect_signals(on_asr_ready=on_asr, on_translation_ready=on_trans)
    mock_workers["llm"].translation_ready.connect.assert_called_once_with(on_trans)


# ---------------------------------------------------------------------------
# Signal property accessors
# ---------------------------------------------------------------------------


def test_asr_ready_property_returns_worker_signal(
    orchestrator: PipelineOrchestrator,
    mock_workers: dict[str, MagicMock],
) -> None:
    """asr_ready property must return the asr_worker.asr_ready signal."""
    assert orchestrator.asr_ready is mock_workers["asr"].asr_ready


def test_translation_ready_property_returns_worker_signal(
    orchestrator: PipelineOrchestrator,
    mock_workers: dict[str, MagicMock],
) -> None:
    """translation_ready property must return the llm_worker.translation_ready signal."""
    assert orchestrator.translation_ready is mock_workers["llm"].translation_ready


def test_error_occurred_property_accessible(
    orchestrator: PipelineOrchestrator,
) -> None:
    """error_occurred property must be accessible (list of worker signals)."""
    err = orchestrator.error_occurred
    # error_occurred is a list of signals from all three workers
    assert isinstance(err, list)
    assert len(err) == 3
