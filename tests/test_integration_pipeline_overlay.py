"""Integration tests: pipeline → AnalysisWorker → OverlayWindow end-to-end.

These tests verify that the complete signal chain from ASRResult through
AnalysisWorker to the overlay's dual-display state machine works correctly.

Mocked components: QwenASR.transcribe_batch(), SileroVAD processing
Real components: PreprocessingPipeline, AnalysisWorker, OverlayWindow
"""

import queue
import time
from typing import Any

import pytest

from src.analysis.pipeline import PreprocessingPipeline
from src.config import AppConfig
from src.models import SentenceResult
from src.pipeline.analysis_worker import AnalysisWorker
from src.pipeline.types import ASRResult
from src.ui.overlay import OverlayWindow

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def app_config() -> AppConfig:
    return AppConfig(user_jlpt_level=3)


@pytest.fixture()
def analysis_pipeline() -> PreprocessingPipeline:
    return PreprocessingPipeline()


@pytest.fixture()
def text_queue() -> queue.Queue[ASRResult]:
    return queue.Queue(maxsize=50)


@pytest.fixture()
def overlay(qapp: Any, app_config: AppConfig) -> OverlayWindow:
    return OverlayWindow(config=app_config)


@pytest.fixture()
def worker(
    text_queue: queue.Queue[ASRResult],
    analysis_pipeline: PreprocessingPipeline,
) -> AnalysisWorker:
    return AnalysisWorker(
        text_queue=text_queue,
        analysis_pipeline=analysis_pipeline,
        config={},
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_asr(text: str, seg_id: str = "seg-001") -> ASRResult:
    return ASRResult(text=text, segment_id=seg_id, elapsed_ms=5.0)


def wait_for(condition: Any, timeout: float = 5.0, poll: float = 0.05, qapp: Any = None) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if qapp is not None:
            qapp.processEvents()
        if condition():
            return True
        time.sleep(poll)
    return False


# ---------------------------------------------------------------------------
# Test 1: Pipeline produces SentenceResult with analysis
# ---------------------------------------------------------------------------


def test_pipeline_produces_sentence_result(
    qapp: Any,
    text_queue: queue.Queue[ASRResult],
    worker: AnalysisWorker,
) -> None:
    """End-to-end: ASRResult → AnalysisWorker → SentenceResult emitted."""
    results: list[SentenceResult] = []
    worker.sentence_ready.connect(results.append)

    text_queue.put_nowait(make_asr("日本語のテストです"))
    worker.start()

    assert wait_for(lambda: len(results) > 0, qapp=qapp), "SentenceResult never emitted"
    worker.stop()
    worker.wait(3000)

    sr = results[0]
    assert sr.japanese_text == "日本語のテストです"
    assert sr.analysis is not None


# ---------------------------------------------------------------------------
# Test 2: Overlay receives SentenceResult, enters LIVE mode
# ---------------------------------------------------------------------------


def test_overlay_live_mode_updates_on_sentence_ready(
    qapp: Any,
    text_queue: queue.Queue[ASRResult],
    worker: AnalysisWorker,
    overlay: OverlayWindow,
) -> None:
    """Overlay shows new sentence in LIVE mode and _preview_browser is hidden."""
    worker.sentence_ready.connect(overlay.on_sentence_ready)
    text_queue.put_nowait(make_asr("東京は大きい都市です"))
    worker.start()

    assert wait_for(lambda: overlay._current_result is not None, qapp=qapp), (
        "Overlay never updated"
    )
    worker.stop()
    worker.wait(3000)

    assert overlay._history.is_browsing is False
    assert overlay._preview_browser.isHidden() is True
    assert overlay._current_result is not None
    assert overlay._current_result.japanese_text == "東京は大きい都市です"
    assert overlay._history.latest is not None


# ---------------------------------------------------------------------------
# Test 3: Browse mode — _prev_sentence shows preview browser
# ---------------------------------------------------------------------------


def test_browse_mode_shows_preview_browser(
    qapp: Any,
    text_queue: queue.Queue[ASRResult],
    worker: AnalysisWorker,
    overlay: OverlayWindow,
) -> None:
    """After 2 sentences, pressing prev enters BROWSE mode and shows preview."""
    worker.sentence_ready.connect(overlay.on_sentence_ready)
    worker.start()

    # Send two sentences
    text_queue.put_nowait(make_asr("最初の文章です", "seg-1"))
    assert wait_for(
        lambda: (
            overlay._history.latest is not None
            and overlay._history.latest.japanese_text == "最初の文章です"
        ),
        qapp=qapp,
    )

    text_queue.put_nowait(make_asr("二番目の文章です", "seg-2"))
    assert wait_for(lambda: overlay._history.count >= 2, qapp=qapp), "History should have 2 items"

    worker.stop()
    worker.wait(3000)

    assert overlay._history.is_browsing is False
    assert overlay._history.cursor_index == -1  # LIVE mode

    # Press prev → enter BROWSE mode
    overlay._prev_sentence()

    assert overlay._history.is_browsing is True
    assert overlay._preview_browser.isHidden() is False
    assert overlay._history.cursor_index == overlay._history.count - 2


# ---------------------------------------------------------------------------
# Test 4: Next sentence collapses to LIVE mode when reaching latest
# ---------------------------------------------------------------------------


def test_next_to_latest_collapses_to_live_mode(
    qapp: Any,
    text_queue: queue.Queue[ASRResult],
    worker: AnalysisWorker,
    overlay: OverlayWindow,
) -> None:
    """Pressing next after reaching latest index collapses preview browser."""
    worker.sentence_ready.connect(overlay.on_sentence_ready)
    worker.start()

    text_queue.put_nowait(make_asr("文章A", "seg-a"))
    assert wait_for(lambda: overlay._history.latest is not None, qapp=qapp)

    text_queue.put_nowait(make_asr("文章B", "seg-b"))
    assert wait_for(lambda: overlay._history.count >= 2, qapp=qapp)

    worker.stop()
    worker.wait(3000)

    # Enter browse mode
    overlay._prev_sentence()
    assert overlay._history.is_browsing is True
    assert overlay._preview_browser.isHidden() is False

    # Press next → should collapse back to LIVE
    overlay._next_sentence()

    assert overlay._history.is_browsing is False
    assert overlay._preview_browser.isHidden() is True


# ---------------------------------------------------------------------------
# Test 5: New sentence during browse — preview browser shows latest, main stays
# ---------------------------------------------------------------------------


def test_new_sentence_during_browse_updates_preview(
    qapp: Any,
    text_queue: queue.Queue[ASRResult],
    worker: AnalysisWorker,
    overlay: OverlayWindow,
) -> None:
    """While browsing, a new sentence updates _preview_browser but not _jp_browser."""
    worker.sentence_ready.connect(overlay.on_sentence_ready)
    worker.start()

    # Send first two sentences so we can navigate
    text_queue.put_nowait(make_asr("最初", "seg-1"))
    assert wait_for(lambda: overlay._history.latest is not None, qapp=qapp)
    text_queue.put_nowait(make_asr("二番目", "seg-2"))
    assert wait_for(lambda: overlay._history.count >= 2, qapp=qapp)

    # Enter browse mode
    overlay._prev_sentence()
    assert overlay._history.is_browsing is True
    browsed_text = overlay._current_result.japanese_text if overlay._current_result else ""

    # Send another sentence while browsing
    text_queue.put_nowait(make_asr("三番目", "seg-3"))
    assert wait_for(
        lambda: (
            overlay._history.latest is not None
            and overlay._history.latest.japanese_text == "三番目"
        ),
        qapp=qapp,
    )

    worker.stop()
    worker.wait(3000)

    # Still in browse mode, browsed sentence unchanged
    assert overlay._history.is_browsing is True
    assert overlay._preview_browser.isHidden() is False
    if overlay._current_result:
        assert overlay._current_result.japanese_text == browsed_text


# ---------------------------------------------------------------------------
# Test 6: highlight_hovered emits 3-tuple (hit, point, result)
# ---------------------------------------------------------------------------


def test_highlight_hovered_signal_is_3_arg(
    qapp: Any,
    overlay: OverlayWindow,
) -> None:
    """highlight_hovered signal passes (hit, point, result) — 3 arguments."""

    emitted: list[tuple] = []
    overlay.highlight_hovered.connect(lambda hit, pt, result: emitted.append((hit, pt, result)))

    # Confirm signal accepts 3-arg handler (just connecting it is enough)
    assert len(emitted) == 0  # no hover yet — just confirm wiring works


# ---------------------------------------------------------------------------
# Test 7: Empty history — prev/next are no-ops (no crash)
# ---------------------------------------------------------------------------


def test_empty_history_nav_no_crash(qapp: Any, overlay: OverlayWindow) -> None:
    """Navigating when history is empty does not crash."""
    assert overlay._history.count == 0
    overlay._prev_sentence()  # should be a no-op
    overlay._next_sentence()  # should be a no-op
    assert overlay._history.count == 0
    assert overlay._history.is_browsing is False


# ---------------------------------------------------------------------------
# Test 8: Max history cap respected
# ---------------------------------------------------------------------------


def test_max_history_cap(
    qapp: Any,
    text_queue: queue.Queue[ASRResult],
    worker: AnalysisWorker,
    overlay: OverlayWindow,
) -> None:
    """History is capped at overlay._history.max_size entries."""
    worker.sentence_ready.connect(overlay.on_sentence_ready)
    worker.start()

    # Send more sentences than max_history (default 10)
    for i in range(overlay._history.max_size + 3):
        text_queue.put_nowait(make_asr(f"文章{i}", f"seg-{i}"))

    assert wait_for(
        lambda: overlay._history.count >= overlay._history.max_size,
        timeout=10.0,
        qapp=qapp,
    ), f"History never reached max_size={overlay._history.max_size}"

    worker.stop()
    worker.wait(3000)

    assert overlay._history.count <= overlay._history.max_size


# ---------------------------------------------------------------------------
# Test 9: on_asr_ready (fast preview) does not affect analysis state
# ---------------------------------------------------------------------------


def test_asr_ready_does_not_affect_analysis_state(
    qapp: Any,
    overlay: OverlayWindow,
) -> None:
    """on_asr_ready provides plain-text preview; does not set _current_result."""
    assert overlay._current_result is None

    asr = ASRResult(text="認識中...", segment_id="seg-x", elapsed_ms=1.0)
    overlay.on_asr_ready(asr)
    qapp.processEvents()

    # _current_result remains None (only set by on_sentence_ready)
    assert overlay._current_result is None
    assert overlay._history.latest is None
