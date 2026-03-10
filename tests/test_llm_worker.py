"""Tests for LlmWorker QThread.

Tests cover:
- Full translate flow: ASRResult in → TranslationResult with text/translation/explanation out
- LLMTimeoutError → emit TranslationResult with translation=None, continue processing
- LLMUnavailableError → emit TranslationResult with translation=None, continue processing
- DB update_translation called with correct segment_id
- translation_ready signal emitted per result
- result_queue.put_nowait() used — drop + warn when full (no deadlock)
- Clean shutdown in <2s via stop()
"""

import queue
import time
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from PySide6.QtCore import Qt

from src.exceptions import LLMTimeoutError, LLMUnavailableError
from src.pipeline.types import ASRResult, LLMResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_asr_result(text: str = "日本語テスト", db_row_id: int | None = None) -> ASRResult:
    """Create a dummy ASRResult."""
    return ASRResult(
        text=text,
        segment_id=str(uuid.uuid4()),
        elapsed_ms=10.0,
        db_row_id=db_row_id,
    )


def make_mock_llm_client(
    return_value: tuple[str | None, str | None] = ("翻訳結果", None),
    side_effect: BaseException | None = None,
) -> MagicMock:
    """Create a mock AsyncOllamaClient."""
    mock_client = MagicMock()
    if side_effect is not None:
        mock_client.translate_async = AsyncMock(side_effect=side_effect)
    else:
        mock_client.translate_async = AsyncMock(return_value=return_value)
    return mock_client


def make_mock_db_repo() -> MagicMock:
    """Create a mock LearningRepository."""
    mock_repo = MagicMock()
    mock_repo.update_translation = MagicMock(return_value=True)
    return mock_repo


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def text_queue() -> queue.Queue[ASRResult]:
    return queue.Queue(maxsize=50)


@pytest.fixture()
def result_queue() -> queue.Queue[LLMResult]:
    return queue.Queue(maxsize=50)


@pytest.fixture()
def config() -> dict[str, Any]:
    return {}


# ---------------------------------------------------------------------------
# Import guard
# ---------------------------------------------------------------------------


def _import_llm_worker() -> type:
    """Import LlmWorker, raising ImportError if not yet implemented."""
    from src.pipeline.llm_worker import LlmWorker

    return LlmWorker


# ---------------------------------------------------------------------------
# Constructor / attribute tests
# ---------------------------------------------------------------------------


def test_llm_worker_init_stores_attributes(
    qt_app: Any,
    text_queue: queue.Queue[ASRResult],
    result_queue: queue.Queue[LLMResult],
    config: dict[str, Any],
) -> None:
    """LlmWorker stores queues, llm_client, db_path, and config on construction."""
    LlmWorker = _import_llm_worker()
    mock_client = make_mock_llm_client()

    w = LlmWorker(
        text_queue=text_queue,
        result_queue=result_queue,
        llm_client=mock_client,
        db_path=None,
        config=config,
    )

    assert w._text_queue is text_queue
    assert w._result_queue is result_queue
    assert w._llm_client is mock_client
    assert w._db_path is None
    assert w._db_repo is None
    assert w._config is config
    assert w._running is False


def test_llm_worker_has_signals(
    qt_app: Any,
    text_queue: queue.Queue[ASRResult],
    result_queue: queue.Queue[LLMResult],
    config: dict[str, Any],
) -> None:
    """LlmWorker must expose error_occurred and translation_ready signals."""
    LlmWorker = _import_llm_worker()
    mock_client = make_mock_llm_client()

    w = LlmWorker(
        text_queue=text_queue,
        result_queue=result_queue,
        llm_client=mock_client,
        db_path=None,
        config=config,
    )

    assert hasattr(w, "error_occurred")
    assert hasattr(w, "translation_ready")


# ---------------------------------------------------------------------------
# Full translate flow tests
# ---------------------------------------------------------------------------


def test_llm_worker_full_translate_flow_produces_result(
    qt_app: Any,
    result_queue: queue.Queue[LLMResult],
    config: dict[str, Any],
) -> None:
    """A single ASRResult → TranslationResult with translation in result_queue."""
    LlmWorker = _import_llm_worker()
    mock_client = make_mock_llm_client(return_value=("これは翻訳です", None))

    text_q: queue.Queue[ASRResult] = queue.Queue(maxsize=50)
    asr_result = make_asr_result("今日は天気がいいですね")
    text_q.put(asr_result)

    w = LlmWorker(
        text_queue=text_q,
        result_queue=result_queue,
        llm_client=mock_client,
        db_path=None,
        config=config,
    )

    w.start()
    deadline = time.monotonic() + 3.0
    result: LLMResult | None = None
    while time.monotonic() < deadline:
        try:
            result = result_queue.get(timeout=0.1)
            break
        except queue.Empty:
            pass

    w.stop()

    assert result is not None, "Expected a TranslationResult in result_queue"
    assert isinstance(result, LLMResult)
    assert result.translation == "これは翻訳です"
    assert result.segment_id == asr_result.segment_id
    assert result.elapsed_ms >= 0.0


def test_llm_worker_translate_flow_emits_signal(
    qt_app: Any,
    result_queue: queue.Queue[LLMResult],
    config: dict[str, Any],
) -> None:
    """translation_ready signal emitted with correct TranslationResult."""
    LlmWorker = _import_llm_worker()
    mock_client = make_mock_llm_client(return_value=("翻訳テスト", None))

    text_q: queue.Queue[ASRResult] = queue.Queue(maxsize=50)
    asr_result = make_asr_result("テスト文章")
    text_q.put(asr_result)

    w = LlmWorker(
        text_queue=text_q,
        result_queue=result_queue,
        llm_client=mock_client,
        db_path=None,
        config=config,
    )

    emitted: list[LLMResult] = []
    w.translation_ready.connect(emitted.append, Qt.ConnectionType.DirectConnection)

    w.start()
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline and not emitted:
        time.sleep(0.05)

    w.stop()

    assert len(emitted) >= 1, "Expected translation_ready to be emitted"
    assert emitted[0].segment_id == asr_result.segment_id
    assert emitted[0].translation == "翻訳テスト"


def test_llm_worker_calls_db_update_translation(
    qt_app: Any,
    result_queue: queue.Queue[LLMResult],
    config: dict[str, Any],
) -> None:
    """db_repo.update_translation is called with db_row_id after successful translation."""
    from unittest.mock import patch as _patch

    LlmWorker = _import_llm_worker()
    mock_client = make_mock_llm_client(return_value=("DB更新テスト", None))
    mock_repo = make_mock_db_repo()

    text_q: queue.Queue[ASRResult] = queue.Queue(maxsize=50)
    asr_result = make_asr_result("DB更新テスト文章", db_row_id=42)
    text_q.put(asr_result)

    with _patch("src.pipeline.llm_worker.LearningRepository", return_value=mock_repo):
        w = LlmWorker(
            text_queue=text_q,
            result_queue=result_queue,
            llm_client=mock_client,
            db_path=":memory:",
            config=config,
        )

        w.start()
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            try:
                result_queue.get(timeout=0.1)
                break
            except queue.Empty:
                pass

        w.stop()

    assert mock_repo.update_translation.called, "Expected update_translation to be called"
    call_args = mock_repo.update_translation.call_args
    assert call_args is not None
    assert call_args.args[0] == 42, "Expected row_id=42 as first arg"


# ---------------------------------------------------------------------------
# LLMTimeoutError tests
# ---------------------------------------------------------------------------


def test_llm_worker_timeout_error_emits_with_none_translation(
    qt_app: Any,
    result_queue: queue.Queue[LLMResult],
    config: dict[str, Any],
) -> None:
    """LLMTimeoutError → translation_ready emitted with translation=None."""
    LlmWorker = _import_llm_worker()
    mock_client = make_mock_llm_client(side_effect=LLMTimeoutError("Timeout"))

    text_q: queue.Queue[ASRResult] = queue.Queue(maxsize=50)
    asr_result = make_asr_result("タイムアウトテスト")
    text_q.put(asr_result)

    w = LlmWorker(
        text_queue=text_q,
        result_queue=result_queue,
        llm_client=mock_client,
        db_path=None,
        config=config,
    )

    emitted: list[LLMResult] = []
    w.translation_ready.connect(emitted.append, Qt.ConnectionType.DirectConnection)

    w.start()
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline and not emitted:
        time.sleep(0.05)

    w.stop()

    assert len(emitted) >= 1, "Expected translation_ready to be emitted even on timeout"
    assert emitted[0].translation is None
    assert emitted[0].segment_id == asr_result.segment_id


def test_llm_worker_timeout_error_continues_processing(
    qt_app: Any,
    result_queue: queue.Queue[LLMResult],
    config: dict[str, Any],
) -> None:
    """After LLMTimeoutError, worker continues to process subsequent ASRResults."""
    LlmWorker = _import_llm_worker()

    call_count = 0

    async def _side_effect(text: str, context: str) -> tuple[str | None, str | None]:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise LLMTimeoutError("First call times out")
        return ("成功翻訳", None)

    mock_client = MagicMock()
    mock_client.translate_async = _side_effect

    text_q: queue.Queue[ASRResult] = queue.Queue(maxsize=50)
    text_q.put(make_asr_result("一回目タイムアウト"))
    text_q.put(make_asr_result("二回目成功"))

    w = LlmWorker(
        text_queue=text_q,
        result_queue=result_queue,
        llm_client=mock_client,
        db_path=None,
        config=config,
    )

    w.start()
    deadline = time.monotonic() + 4.0
    collected: list[LLMResult] = []
    while time.monotonic() < deadline and len(collected) < 2:
        try:
            collected.append(result_queue.get(timeout=0.1))
        except queue.Empty:
            pass

    w.stop()

    assert len(collected) == 2, "Worker should have processed both items"
    # First has None translation, second has successful translation
    assert collected[0].translation is None
    assert collected[1].translation == "成功翻訳"


# ---------------------------------------------------------------------------
# LLMUnavailableError tests
# ---------------------------------------------------------------------------


def test_llm_worker_unavailable_error_emits_with_none_translation(
    qt_app: Any,
    result_queue: queue.Queue[LLMResult],
    config: dict[str, Any],
) -> None:
    """LLMUnavailableError → translation_ready emitted with translation=None."""
    LlmWorker = _import_llm_worker()
    mock_client = make_mock_llm_client(side_effect=LLMUnavailableError("Connection refused"))

    text_q: queue.Queue[ASRResult] = queue.Queue(maxsize=50)
    asr_result = make_asr_result("接続エラーテスト")
    text_q.put(asr_result)

    w = LlmWorker(
        text_queue=text_q,
        result_queue=result_queue,
        llm_client=mock_client,
        db_path=None,
        config=config,
    )

    emitted: list[LLMResult] = []
    w.translation_ready.connect(emitted.append, Qt.ConnectionType.DirectConnection)

    w.start()
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline and not emitted:
        time.sleep(0.05)

    w.stop()

    assert len(emitted) >= 1, "Expected translation_ready to be emitted even when unavailable"
    assert emitted[0].translation is None
    assert emitted[0].explanation is None
    assert emitted[0].segment_id == asr_result.segment_id


def test_llm_worker_unavailable_error_continues_processing(
    qt_app: Any,
    result_queue: queue.Queue[LLMResult],
    config: dict[str, Any],
) -> None:
    """After LLMUnavailableError, worker continues to process subsequent items."""
    LlmWorker = _import_llm_worker()

    call_count = 0

    async def _side_effect(text: str, context: str) -> tuple[str | None, str | None]:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise LLMUnavailableError("Ollama not running")
        return ("回復翻訳", None)

    mock_client = MagicMock()
    mock_client.translate_async = _side_effect

    text_q: queue.Queue[ASRResult] = queue.Queue(maxsize=50)
    text_q.put(make_asr_result("接続なし"))
    text_q.put(make_asr_result("回復後"))

    w = LlmWorker(
        text_queue=text_q,
        result_queue=result_queue,
        llm_client=mock_client,
        db_path=None,
        config=config,
    )

    w.start()
    deadline = time.monotonic() + 4.0
    collected: list[LLMResult] = []
    while time.monotonic() < deadline and len(collected) < 2:
        try:
            collected.append(result_queue.get(timeout=0.1))
        except queue.Empty:
            pass

    w.stop()

    assert len(collected) == 2, "Worker should continue after LLMUnavailableError"
    assert collected[0].translation is None
    assert collected[1].translation == "回復翻訳"


# ---------------------------------------------------------------------------
# Shutdown tests
# ---------------------------------------------------------------------------


def test_llm_worker_stop_completes_within_2s(
    qt_app: Any,
    text_queue: queue.Queue[ASRResult],
    result_queue: queue.Queue[LLMResult],
    config: dict[str, Any],
) -> None:
    """stop() must complete within 2 seconds."""
    LlmWorker = _import_llm_worker()
    mock_client = make_mock_llm_client()

    w = LlmWorker(
        text_queue=text_queue,
        result_queue=result_queue,
        llm_client=mock_client,
        db_path=None,
        config=config,
    )

    w.start()
    time.sleep(0.1)

    t0 = time.monotonic()
    w.stop()
    elapsed = time.monotonic() - t0

    assert elapsed < 2.0, f"stop() took {elapsed:.2f}s — expected < 2s"
    assert not w.isRunning(), "Worker thread should have stopped"


def test_llm_worker_running_flag_false_after_stop(
    qt_app: Any,
    text_queue: queue.Queue[ASRResult],
    result_queue: queue.Queue[LLMResult],
    config: dict[str, Any],
) -> None:
    """_running should be False after stop() is called."""
    LlmWorker = _import_llm_worker()
    mock_client = make_mock_llm_client()

    w = LlmWorker(
        text_queue=text_queue,
        result_queue=result_queue,
        llm_client=mock_client,
        db_path=None,
        config=config,
    )

    w.start()
    time.sleep(0.05)
    w.stop()

    assert w._running is False


# ---------------------------------------------------------------------------
# Queue full / drop tests
# ---------------------------------------------------------------------------


def test_llm_worker_drops_result_when_result_queue_full(
    qt_app: Any,
    config: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """When result_queue is full, results are dropped with a warning (no deadlock)."""
    LlmWorker = _import_llm_worker()
    mock_client = make_mock_llm_client(return_value=("テスト", None))

    # Full result queue (maxsize=1, already filled)
    full_result_queue: queue.Queue[LLMResult] = queue.Queue(maxsize=1)
    dummy = LLMResult(
        translation="dummy",
        explanation=None,
        segment_id=str(uuid.uuid4()),
        elapsed_ms=0.0,
    )
    full_result_queue.put_nowait(dummy)
    assert full_result_queue.full()

    text_q: queue.Queue[ASRResult] = queue.Queue(maxsize=50)
    text_q.put(make_asr_result("キュー満杯テスト"))

    w = LlmWorker(
        text_queue=text_q,
        result_queue=full_result_queue,
        llm_client=mock_client,
        db_path=None,
        config=config,
    )

    import logging

    with caplog.at_level(logging.WARNING, logger="src.pipeline.llm_worker"):
        w.start()
        time.sleep(0.5)
        w.stop()

    # Queue should remain at maxsize=1 (dropped, not blocked)
    assert full_result_queue.full(), "Queue should remain full; result was dropped not blocked"

    warning_msgs = [r.message for r in caplog.records if r.levelno == logging.WARNING]
    assert any("full" in str(m).lower() or "drop" in str(m).lower() for m in warning_msgs), (
        "Expected a queue-full warning"
    )


def test_llm_worker_no_deadlock_on_full_result_queue(
    qt_app: Any,
    config: dict[str, Any],
) -> None:
    """Worker must not deadlock when result_queue is full — stop() finishes in <2s."""
    LlmWorker = _import_llm_worker()
    mock_client = make_mock_llm_client(return_value=("テスト", None))

    full_result_queue: queue.Queue[LLMResult] = queue.Queue(maxsize=1)
    dummy = LLMResult(
        translation="dummy",
        explanation=None,
        segment_id=str(uuid.uuid4()),
        elapsed_ms=0.0,
    )
    full_result_queue.put_nowait(dummy)

    text_q: queue.Queue[ASRResult] = queue.Queue(maxsize=50)
    for _ in range(5):
        try:
            text_q.put_nowait(make_asr_result("テスト"))
        except queue.Full:
            break

    w = LlmWorker(
        text_queue=text_q,
        result_queue=full_result_queue,
        llm_client=mock_client,
        db_path=None,
        config=config,
    )

    w.start()
    time.sleep(0.3)

    t0 = time.monotonic()
    w.stop()
    elapsed = time.monotonic() - t0

    assert elapsed < 2.0, f"stop() took {elapsed:.2f}s — potential deadlock on full result_queue"


def test_llm_worker_update_client(
    qt_app: Any,
    config: dict[str, Any],
) -> None:
    LlmWorker = _import_llm_worker()
    old_client = make_mock_llm_client(return_value=("old", None))
    new_client = make_mock_llm_client(return_value=("new", None))

    text_q: queue.Queue[ASRResult] = queue.Queue(maxsize=50)
    result_q: queue.Queue[LLMResult] = queue.Queue(maxsize=50)

    w = LlmWorker(
        text_queue=text_q,
        result_queue=result_q,
        llm_client=old_client,
        db_path=None,
        config=config,
    )

    assert w._llm_client is old_client
    w.update_client(new_client)
    assert w._llm_client is new_client


def test_cleanup_closes_db_repo_and_llm_client(
    qt_app: Any,
    config: dict[str, Any],
) -> None:
    from unittest.mock import AsyncMock
    from unittest.mock import patch as _patch

    LlmWorker = _import_llm_worker()
    mock_client = make_mock_llm_client(return_value=("翻訳", None))
    mock_client.close = AsyncMock()
    mock_repo = make_mock_db_repo()

    text_q: queue.Queue[ASRResult] = queue.Queue(maxsize=50)
    result_q: queue.Queue[LLMResult] = queue.Queue(maxsize=50)

    with _patch("src.pipeline.llm_worker.LearningRepository", return_value=mock_repo):
        w = LlmWorker(
            text_queue=text_q,
            result_queue=result_q,
            llm_client=mock_client,
            db_path=":memory:",
            config=config,
        )
        w.start()
        time.sleep(0.1)
        w.stop()

    mock_repo.close.assert_called_once()
    mock_client.close.assert_awaited_once()
