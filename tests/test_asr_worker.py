"""Tests for AsrWorker QThread.

Tests cover:
- batch of 4 → 4 ASRResult objects produced
- flush on 500ms timeout even with partial batch
- blank transcriptions (empty after strip()) are filtered out
- clean shutdown in <2s via stop()
- error_occurred signal emitted on ASR exception (worker continues)
- text_queue.put_nowait() used — drop + warn when full (no deadlock)
- asr_ready signal emitted per result
"""

import queue
import time
import uuid
from typing import Any
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from PySide6.QtCore import Qt

from src.pipeline.types import ASRResult, SpeechSegment

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_segment(text_hint: str = "テスト", duration_samples: int = 16000) -> SpeechSegment:
    """Create a dummy SpeechSegment."""
    return SpeechSegment(
        audio=np.zeros(duration_samples, dtype=np.float32),
        sample_rate=16000,
        timestamp=time.monotonic(),
        segment_id=str(uuid.uuid4()),
    )


def make_mock_asr(results: list[str]) -> MagicMock:
    mock_asr = MagicMock()

    def _transcribe_batch(segments: list[SpeechSegment]) -> list[ASRResult]:
        out: list[ASRResult] = []
        for seg, text in zip(segments, results):
            if text.strip():
                out.append(ASRResult(text=text, segment_id=seg.segment_id, elapsed_ms=1.0))
        return out

    mock_asr.transcribe_batch.side_effect = _transcribe_batch
    return mock_asr


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def segment_queue() -> queue.Queue[SpeechSegment]:
    return queue.Queue(maxsize=20)


@pytest.fixture()
def text_queue() -> queue.Queue[ASRResult]:
    return queue.Queue(maxsize=50)


@pytest.fixture()
def config() -> dict[str, Any]:
    return {"asr_batch_size": 4, "asr_flush_timeout_ms": 500}


# ---------------------------------------------------------------------------
# Import guard (module doesn't exist yet — tests should fail to import until
# implementation is done, which is the TDD "red" phase)
# ---------------------------------------------------------------------------


def _import_asr_worker() -> type:
    """Import AsrWorker, raising ImportError if not yet implemented."""
    from src.pipeline.asr_worker import AsrWorker

    return AsrWorker


# ---------------------------------------------------------------------------
# Constructor / attribute tests
# ---------------------------------------------------------------------------


def test_asr_worker_init_stores_attributes(
    qt_app: Any,
    segment_queue: queue.Queue[SpeechSegment],
    text_queue: queue.Queue[ASRResult],
    config: dict[str, Any],
) -> None:
    """AsrWorker stores queues, asr, and config on construction."""
    AsrWorker = _import_asr_worker()
    mock_asr = make_mock_asr([])

    w = AsrWorker(
        segment_queue=segment_queue,
        text_queue=text_queue,
        asr=mock_asr,
        config=config,
    )

    assert w._segment_queue is segment_queue
    assert w._text_queue is text_queue
    assert w._asr is mock_asr
    assert w._config is config
    assert w._running is False


def test_asr_worker_has_signals(
    qt_app: Any,
    segment_queue: queue.Queue[SpeechSegment],
    text_queue: queue.Queue[ASRResult],
    config: dict[str, Any],
) -> None:
    """AsrWorker must expose error_occurred and asr_ready signals."""
    AsrWorker = _import_asr_worker()
    mock_asr = make_mock_asr([])

    w = AsrWorker(
        segment_queue=segment_queue,
        text_queue=text_queue,
        asr=mock_asr,
        config=config,
    )

    assert hasattr(w, "error_occurred")
    assert hasattr(w, "asr_ready")


# ---------------------------------------------------------------------------
# Batch processing tests
# ---------------------------------------------------------------------------


def test_asr_worker_batch_of_4_produces_4_results(
    qt_app: Any,
    text_queue: queue.Queue[ASRResult],
    config: dict[str, Any],
) -> None:
    """When 4 segments fill the batch, transcribe_batch is called and 4 results appear."""
    AsrWorker = _import_asr_worker()

    texts = ["日本語テスト一", "日本語テスト二", "日本語テスト三", "日本語テスト四"]
    mock_asr = make_mock_asr(texts)

    seg_q: queue.Queue[SpeechSegment] = queue.Queue(maxsize=20)
    w = AsrWorker(
        segment_queue=seg_q,
        text_queue=text_queue,
        asr=mock_asr,
        config=config,
    )

    # Put exactly 4 segments (fills batch)
    for _ in texts:
        seg_q.put(make_segment())

    w.start()
    # Wait for results to appear (up to 3s)
    deadline = time.monotonic() + 3.0
    collected: list[ASRResult] = []
    while time.monotonic() < deadline and len(collected) < 4:
        try:
            collected.append(text_queue.get(timeout=0.05))
        except queue.Empty:
            pass

    w.stop()

    assert len(collected) == 4, f"Expected 4 ASRResults, got {len(collected)}"
    for r in collected:
        assert isinstance(r, ASRResult)
        assert r.text.strip() != ""


def test_asr_worker_flush_on_timeout_partial_batch(
    qt_app: Any,
    text_queue: queue.Queue[ASRResult],
    config: dict[str, Any],
) -> None:
    """Partial batch (< batch_size) is flushed after 500ms timeout."""
    AsrWorker = _import_asr_worker()

    # config with longer timeout to prevent premature flush; we'll use short one
    flush_config = {"asr_batch_size": 4, "asr_flush_timeout_ms": 300}
    mock_asr = make_mock_asr(["日本語テスト"])

    seg_q: queue.Queue[SpeechSegment] = queue.Queue(maxsize=20)
    w = AsrWorker(
        segment_queue=seg_q,
        text_queue=text_queue,
        asr=mock_asr,
        config=flush_config,
    )

    # Only 1 segment — batch of 4 never fills
    seg_q.put(make_segment())

    w.start()
    # Wait up to 2s — flush should happen in ~300ms
    deadline = time.monotonic() + 2.0
    collected: list[ASRResult] = []
    while time.monotonic() < deadline and not collected:
        try:
            collected.append(text_queue.get(timeout=0.05))
        except queue.Empty:
            pass

    w.stop()

    assert len(collected) >= 1, "Expected partial batch to be flushed after timeout"


def test_asr_worker_filters_blank_transcriptions(
    qt_app: Any,
    text_queue: queue.Queue[ASRResult],
    config: dict[str, Any],
) -> None:
    """Blank transcriptions (empty string after strip()) are NOT put into text_queue."""
    AsrWorker = _import_asr_worker()

    # 4 segments but mock returns blank for first two, valid for last two
    mock_asr = MagicMock()

    def _transcribe_batch_blanks(segments: list[SpeechSegment]) -> list[ASRResult]:
        results = []
        texts = ["", "  ", "有効テスト一", "有効テスト二"]
        for seg, text in zip(segments, texts):
            # Only include non-blank (mirroring what transcribe_batch should do)
            if text.strip():
                results.append(ASRResult(text=text, segment_id=seg.segment_id, elapsed_ms=1.0))
        return results

    mock_asr.transcribe_batch.side_effect = _transcribe_batch_blanks

    seg_q: queue.Queue[SpeechSegment] = queue.Queue(maxsize=20)
    flush_config = {"asr_batch_size": 4, "asr_flush_timeout_ms": 300}
    w = AsrWorker(
        segment_queue=seg_q,
        text_queue=text_queue,
        asr=mock_asr,
        config=flush_config,
    )

    for _ in range(4):
        seg_q.put(make_segment())

    w.start()
    deadline = time.monotonic() + 3.0
    collected: list[ASRResult] = []
    while time.monotonic() < deadline and len(collected) < 2:
        try:
            collected.append(text_queue.get(timeout=0.05))
        except queue.Empty:
            pass
    # Give it a moment to process any extra
    time.sleep(0.2)
    # Drain remaining
    while not text_queue.empty():
        try:
            collected.append(text_queue.get_nowait())
        except queue.Empty:
            break

    w.stop()

    assert len(collected) == 2, f"Expected 2 non-blank results, got {len(collected)}"
    for r in collected:
        assert r.text.strip() != ""


# ---------------------------------------------------------------------------
# Shutdown tests
# ---------------------------------------------------------------------------


def test_asr_worker_stop_completes_within_2s(
    qt_app: Any,
    segment_queue: queue.Queue[SpeechSegment],
    text_queue: queue.Queue[ASRResult],
    config: dict[str, Any],
) -> None:
    """stop() must complete within 2 seconds."""
    AsrWorker = _import_asr_worker()
    mock_asr = make_mock_asr([])

    w = AsrWorker(
        segment_queue=segment_queue,
        text_queue=text_queue,
        asr=mock_asr,
        config=config,
    )

    w.start()
    time.sleep(0.1)

    t0 = time.monotonic()
    w.stop()
    elapsed = time.monotonic() - t0

    assert elapsed < 2.0, f"stop() took {elapsed:.2f}s — expected < 2s"
    assert not w.isRunning(), "Worker thread should have stopped"


def test_asr_worker_running_flag_false_after_stop(
    qt_app: Any,
    segment_queue: queue.Queue[SpeechSegment],
    text_queue: queue.Queue[ASRResult],
    config: dict[str, Any],
) -> None:
    """_running should be False after stop() is called."""
    AsrWorker = _import_asr_worker()
    mock_asr = make_mock_asr([])

    w = AsrWorker(
        segment_queue=segment_queue,
        text_queue=text_queue,
        asr=mock_asr,
        config=config,
    )

    w.start()
    time.sleep(0.05)
    w.stop()

    assert w._running is False


# ---------------------------------------------------------------------------
# Error handling tests
# ---------------------------------------------------------------------------


def test_asr_worker_emits_error_on_asr_exception(
    qt_app: Any,
    text_queue: queue.Queue[ASRResult],
    config: dict[str, Any],
) -> None:
    """When transcribe_batch raises, error_occurred is emitted and worker continues."""
    AsrWorker = _import_asr_worker()

    mock_asr = MagicMock()
    mock_asr.transcribe_batch.side_effect = RuntimeError("GPU exploded")

    seg_q: queue.Queue[SpeechSegment] = queue.Queue(maxsize=20)
    flush_config = {"asr_batch_size": 1, "asr_flush_timeout_ms": 100}
    w = AsrWorker(
        segment_queue=seg_q,
        text_queue=text_queue,
        asr=mock_asr,
        config=flush_config,
    )

    emitted_errors: list[str] = []
    w.error_occurred.connect(emitted_errors.append, Qt.ConnectionType.DirectConnection)

    seg_q.put(make_segment())

    w.start()
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline and not emitted_errors:
        time.sleep(0.05)

    w.stop()

    assert len(emitted_errors) >= 1, "Expected error_occurred to be emitted"
    assert "GPU exploded" in emitted_errors[0]


def test_asr_worker_continues_after_exception(
    qt_app: Any,
    text_queue: queue.Queue[ASRResult],
    config: dict[str, Any],
) -> None:
    """After an exception on one batch, worker processes subsequent batches."""
    AsrWorker = _import_asr_worker()

    call_count = 0

    def _side_effect(segments: list[SpeechSegment]) -> list[ASRResult]:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("First batch fails")
        return [
            ASRResult(text="継続テスト", segment_id=seg.segment_id, elapsed_ms=1.0)
            for seg in segments
        ]

    mock_asr = MagicMock()
    mock_asr.transcribe_batch.side_effect = _side_effect

    seg_q: queue.Queue[SpeechSegment] = queue.Queue(maxsize=20)
    flush_config = {"asr_batch_size": 1, "asr_flush_timeout_ms": 100}
    w = AsrWorker(
        segment_queue=seg_q,
        text_queue=text_queue,
        asr=mock_asr,
        config=flush_config,
    )

    seg_q.put(make_segment())
    seg_q.put(make_segment())

    w.start()
    deadline = time.monotonic() + 3.0
    got_result = False
    while time.monotonic() < deadline:
        try:
            text_queue.get(timeout=0.05)
            got_result = True
            break
        except queue.Empty:
            pass

    w.stop()

    assert got_result, "Worker should continue processing after exception"


# ---------------------------------------------------------------------------
# Signal tests
# ---------------------------------------------------------------------------


def test_asr_worker_emits_asr_ready_per_result(
    qt_app: Any,
    text_queue: queue.Queue[ASRResult],
    config: dict[str, Any],
) -> None:
    """asr_ready signal is emitted once per ASRResult."""
    AsrWorker = _import_asr_worker()

    texts = ["テスト一", "テスト二"]
    mock_asr = make_mock_asr(texts)

    seg_q: queue.Queue[SpeechSegment] = queue.Queue(maxsize=20)
    flush_config = {"asr_batch_size": 2, "asr_flush_timeout_ms": 300}
    w = AsrWorker(
        segment_queue=seg_q,
        text_queue=text_queue,
        asr=mock_asr,
        config=flush_config,
    )

    emitted_results: list[ASRResult] = []
    w.asr_ready.connect(emitted_results.append, Qt.ConnectionType.DirectConnection)

    for _ in texts:
        seg_q.put(make_segment())

    w.start()
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline and len(emitted_results) < 2:
        time.sleep(0.05)

    w.stop()

    assert len(emitted_results) == 2, f"Expected 2 asr_ready signals, got {len(emitted_results)}"


# ---------------------------------------------------------------------------
# Queue full / drop tests
# ---------------------------------------------------------------------------


def test_asr_worker_drops_result_when_text_queue_full(
    qt_app: Any,
    segment_queue: queue.Queue[SpeechSegment],
    config: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """When text_queue is full, results are dropped with a warning (no deadlock)."""
    AsrWorker = _import_asr_worker()

    mock_asr = make_mock_asr(["テスト"])

    # Full text queue (maxsize=1, already filled)
    full_text_queue: queue.Queue[ASRResult] = queue.Queue(maxsize=1)
    dummy_result = ASRResult(text="dummy", segment_id=str(uuid.uuid4()), elapsed_ms=0.0)
    full_text_queue.put_nowait(dummy_result)
    assert full_text_queue.full()

    seg_q: queue.Queue[SpeechSegment] = queue.Queue(maxsize=20)
    flush_config = {"asr_batch_size": 1, "asr_flush_timeout_ms": 100}
    w = AsrWorker(
        segment_queue=seg_q,
        text_queue=full_text_queue,
        asr=mock_asr,
        config=flush_config,
    )

    seg_q.put(make_segment())

    import logging

    with caplog.at_level(logging.WARNING, logger="src.pipeline.asr_worker"):
        w.start()
        time.sleep(0.5)
        w.stop()

    # Queue should remain at maxsize=1 (dropped, not blocked)
    assert full_text_queue.full(), "Queue should remain full; result was dropped not blocked"
    assert full_text_queue.qsize() == 1

    warning_msgs = [r.message for r in caplog.records if r.levelno == logging.WARNING]
    assert any("full" in str(m).lower() or "drop" in str(m).lower() for m in warning_msgs), (
        "Expected a queue-full warning"
    )


def test_asr_worker_no_deadlock_on_full_text_queue(
    qt_app: Any,
    config: dict[str, Any],
) -> None:
    """Worker must not deadlock when text_queue is full — stop() finishes in <2s."""
    AsrWorker = _import_asr_worker()

    mock_asr = make_mock_asr(["テスト"])

    full_text_queue: queue.Queue[ASRResult] = queue.Queue(maxsize=1)
    dummy_result = ASRResult(text="dummy", segment_id=str(uuid.uuid4()), elapsed_ms=0.0)
    full_text_queue.put_nowait(dummy_result)

    seg_q: queue.Queue[SpeechSegment] = queue.Queue(maxsize=20)
    flush_config = {"asr_batch_size": 1, "asr_flush_timeout_ms": 100}
    w = AsrWorker(
        segment_queue=seg_q,
        text_queue=full_text_queue,
        asr=mock_asr,
        config=flush_config,
    )

    for _ in range(5):
        try:
            seg_q.put_nowait(make_segment())
        except queue.Full:
            break

    w.start()
    time.sleep(0.3)

    t0 = time.monotonic()
    w.stop()
    elapsed = time.monotonic() - t0

    assert elapsed < 2.0, f"stop() took {elapsed:.2f}s — potential deadlock on full text_queue"


# ---------------------------------------------------------------------------
# DB insert_partial wiring tests
# ---------------------------------------------------------------------------


def test_asr_worker_calls_insert_partial_and_sets_db_row_id(
    qt_app: Any,
    text_queue: queue.Queue[ASRResult],
    config: dict[str, Any],
) -> None:
    """When db_repo is provided, insert_partial is called and db_row_id is set on the result."""
    AsrWorker = _import_asr_worker()

    mock_asr = make_mock_asr(["日本語テスト"])
    mock_db_repo = MagicMock()
    mock_db_repo.insert_partial.return_value = 99

    seg_q: queue.Queue[SpeechSegment] = queue.Queue(maxsize=20)
    flush_config = {"asr_batch_size": 1, "asr_flush_timeout_ms": 100}

    with patch("src.pipeline.asr_worker.LearningRepository") as MockLearningRepository:
        MockLearningRepository.return_value = mock_db_repo
        w = AsrWorker(
            segment_queue=seg_q,
            text_queue=text_queue,
            asr=mock_asr,
            config=flush_config,
            db_path=":memory:",
        )

        seg_q.put(make_segment())

        w.start()
        deadline = time.monotonic() + 3.0
        result: ASRResult | None = None
        while time.monotonic() < deadline:
            try:
                result = text_queue.get(timeout=0.1)
                break
            except queue.Empty:
                pass

        w.stop()

    assert result is not None, "Expected an ASRResult in text_queue"
    assert mock_db_repo.insert_partial.called, "Expected insert_partial to be called"
    assert result.db_row_id == 99, f"Expected db_row_id=99, got {result.db_row_id}"


def test_asr_worker_without_db_repo_leaves_db_row_id_none(
    qt_app: Any,
    text_queue: queue.Queue[ASRResult],
    config: dict[str, Any],
) -> None:
    """When db_repo is None (default), db_row_id stays None on the result."""
    AsrWorker = _import_asr_worker()

    mock_asr = make_mock_asr(["日本語テスト"])

    seg_q: queue.Queue[SpeechSegment] = queue.Queue(maxsize=20)
    flush_config = {"asr_batch_size": 1, "asr_flush_timeout_ms": 100}
    w = AsrWorker(
        segment_queue=seg_q,
        text_queue=text_queue,
        asr=mock_asr,
        config=flush_config,
    )

    seg_q.put(make_segment())

    w.start()
    deadline = time.monotonic() + 3.0
    result: ASRResult | None = None
    while time.monotonic() < deadline:
        try:
            result = text_queue.get(timeout=0.1)
            break
        except queue.Empty:
            pass

    w.stop()

    assert result is not None, "Expected an ASRResult in text_queue"
    assert result.db_row_id is None, "Expected db_row_id=None when no db_repo is set"
