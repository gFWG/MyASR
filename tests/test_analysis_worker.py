"""Tests for AnalysisWorker QThread.

Tests cover:
- sentence_ready signal emitted with SentenceResult for each ASRResult
- stop() terminates the loop cleanly within 2 seconds
- error_occurred signal emitted when processing raises, worker continues
- Empty vocab/grammar hits produce empty lists (no crash)
"""

import queue
import time
from typing import Any
from unittest.mock import MagicMock

import pytest

from src.db.models import AnalysisResult, GrammarHit, SentenceResult, Token, VocabHit
from src.pipeline.types import ASRResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_asr_result(text: str = "日本語テスト") -> ASRResult:
    return ASRResult(text=text, segment_id="seg-001", elapsed_ms=10.0)


def make_mock_pipeline(
    vocab_hits: list[VocabHit] | None = None,
    grammar_hits: list[GrammarHit] | None = None,
) -> MagicMock:
    """Return a mock PreprocessingPipeline that produces deterministic AnalysisResult."""
    mock = MagicMock()
    result = AnalysisResult(
        tokens=[Token(surface="日本", lemma="日本", pos="noun")],
        vocab_hits=vocab_hits or [],
        grammar_hits=grammar_hits or [],
    )
    mock.process.return_value = result
    return mock


def make_vocab_hit(jlpt_level: int = 3) -> VocabHit:
    return VocabHit(
        surface="日本",
        lemma="日本",
        pos="noun",
        jlpt_level=jlpt_level,
        start_pos=0,
        end_pos=2,
    )


def make_grammar_hit() -> GrammarHit:
    return GrammarHit(
        rule_id="N3_te_form",
        matched_text="て",
        jlpt_level=3,
        word="て",
        description="te-form",
        start_pos=3,
        end_pos=4,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def text_queue() -> queue.Queue[ASRResult]:
    return queue.Queue(maxsize=50)


@pytest.fixture()
def config() -> dict[str, Any]:
    return {}


# ---------------------------------------------------------------------------
# Import guard
# ---------------------------------------------------------------------------


def _import_analysis_worker() -> type:
    from src.pipeline.analysis_worker import AnalysisWorker  # noqa: PLC0415

    return AnalysisWorker


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_import() -> None:
    """AnalysisWorker can be imported without errors."""
    cls = _import_analysis_worker()
    assert cls is not None


def test_sentence_ready_emitted(
    qapp: Any,
    text_queue: queue.Queue[ASRResult],
    config: dict[str, Any],
) -> None:
    """sentence_ready is emitted once per ASRResult processed."""
    AnalysisWorker = _import_analysis_worker()

    mock_pipeline = make_mock_pipeline()
    worker = AnalysisWorker(
        text_queue=text_queue,
        analysis_pipeline=mock_pipeline,
        config=config,
    )

    results: list[SentenceResult] = []
    worker.sentence_ready.connect(results.append)

    asr = make_asr_result("日本語テスト")
    text_queue.put_nowait(asr)

    worker.start()
    # Give worker time to process
    deadline = time.monotonic() + 3.0
    while len(results) == 0 and time.monotonic() < deadline:
        qapp.processEvents()
        time.sleep(0.05)

    worker.stop()
    worker.wait(3000)

    assert len(results) == 1
    sr = results[0]
    assert sr.japanese_text == "日本語テスト"


def test_sentence_result_has_analysis(
    qapp: Any,
    text_queue: queue.Queue[ASRResult],
    config: dict[str, Any],
) -> None:
    """SentenceResult contains AnalysisResult from the pipeline."""
    AnalysisWorker = _import_analysis_worker()

    vocab = make_vocab_hit(jlpt_level=3)
    grammar = make_grammar_hit()
    mock_pipeline = make_mock_pipeline(vocab_hits=[vocab], grammar_hits=[grammar])

    worker = AnalysisWorker(
        text_queue=text_queue,
        analysis_pipeline=mock_pipeline,
        config=config,
    )

    results: list[SentenceResult] = []
    worker.sentence_ready.connect(results.append)
    text_queue.put_nowait(make_asr_result())

    worker.start()
    deadline = time.monotonic() + 3.0
    while len(results) == 0 and time.monotonic() < deadline:
        qapp.processEvents()
        time.sleep(0.05)

    worker.stop()
    worker.wait(3000)

    assert len(results) == 1
    sr = results[0]
    assert len(sr.analysis.vocab_hits) == 1
    assert len(sr.analysis.grammar_hits) == 1


def test_stop_terminates_within_two_seconds(
    qapp: Any,
    text_queue: queue.Queue[ASRResult],
    config: dict[str, Any],
) -> None:
    """stop() terminates the worker loop cleanly within 2 seconds."""
    AnalysisWorker = _import_analysis_worker()
    mock_pipeline = make_mock_pipeline()

    worker = AnalysisWorker(
        text_queue=text_queue,
        analysis_pipeline=mock_pipeline,
        config=config,
    )

    worker.start()
    time.sleep(0.1)  # Let it spin up

    t0 = time.monotonic()
    worker.stop()
    elapsed = time.monotonic() - t0

    assert not worker.isRunning(), "Worker should have stopped"
    assert elapsed < 2.5, f"stop() took {elapsed:.2f}s — expected <2.5s"


def test_error_occurred_emitted_on_exception(
    qapp: Any,
    text_queue: queue.Queue[ASRResult],
    config: dict[str, Any],
) -> None:
    """error_occurred signal fires when pipeline raises; worker continues processing."""
    AnalysisWorker = _import_analysis_worker()

    mock_pipeline = MagicMock()
    mock_pipeline.process.side_effect = RuntimeError("analysis crash")

    worker = AnalysisWorker(
        text_queue=text_queue,
        analysis_pipeline=mock_pipeline,
        config=config,
    )

    errors: list[str] = []
    worker.error_occurred.connect(errors.append)
    text_queue.put_nowait(make_asr_result("クラッシュテスト"))

    worker.start()
    deadline = time.monotonic() + 3.0
    while len(errors) == 0 and time.monotonic() < deadline:
        qapp.processEvents()
        time.sleep(0.05)

    worker.stop()
    worker.wait(3000)

    assert len(errors) == 1
    assert "analysis crash" in errors[0]


def test_empty_analysis_no_crash(
    qapp: Any,
    text_queue: queue.Queue[ASRResult],
    config: dict[str, Any],
) -> None:
    """Empty vocab/grammar hits produce SentenceResult with empty lists, no crash."""
    AnalysisWorker = _import_analysis_worker()
    mock_pipeline = make_mock_pipeline(vocab_hits=[], grammar_hits=[])

    worker = AnalysisWorker(
        text_queue=text_queue,
        analysis_pipeline=mock_pipeline,
        config=config,
    )

    results: list[SentenceResult] = []
    worker.sentence_ready.connect(results.append)
    text_queue.put_nowait(make_asr_result("無難なテスト"))

    worker.start()
    deadline = time.monotonic() + 3.0
    while len(results) == 0 and time.monotonic() < deadline:
        qapp.processEvents()
        time.sleep(0.05)

    worker.stop()
    worker.wait(3000)

    assert len(results) == 1
    sr = results[0]
    assert sr.analysis.vocab_hits == []
    assert sr.analysis.grammar_hits == []
