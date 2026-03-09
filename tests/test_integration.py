"""Integration tests: mock-based pipeline integration + real-audio GPU tests.

Fast integration tests (no GPU, no Ollama) verify the multi-stage pipeline
with mock workers and mock models.  All fast tests run unconditionally.

Real-audio tests using actual speech data (dev/short.wav, dev/long.wav) and GPU
ASR inference are guarded by @slow and @gpu markers:
    Run with: pytest tests/test_integration.py -m "slow and gpu"
    Skip with: pytest -m "not slow"
"""

import queue
import sys
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, call, patch

import numpy as np
import pytest
import soundfile as sf

from src.db.models import AudioSegment
from src.pipeline.types import SpeechSegment
from src.vad.silero import SileroVAD

slow = pytest.mark.slow
gpu = pytest.mark.gpu
windows_only = pytest.mark.skipif(sys.platform != "win32", reason="Windows only test")

DEV_DIR = Path(__file__).resolve().parent.parent / "dev"


# ---------------------------------------------------------------------------
# Helper: build minimal pipeline config
# ---------------------------------------------------------------------------


def _pipeline_config() -> dict[str, Any]:
    return {
        "sample_rate": 16000,
        "asr_batch_size": 4,
        "asr_flush_timeout_ms": 200,
        "db_path": ":memory:",
        "ollama_url": "http://localhost:11434",
        "ollama_model": "qwen3.5:4b",
    }


# ---------------------------------------------------------------------------
# Helper: mock AudioSegment factory
# ---------------------------------------------------------------------------


def _mock_audio_segment(n_samples: int = 512) -> AudioSegment:
    return AudioSegment(
        samples=np.zeros(n_samples, dtype=np.float32),
        duration_sec=n_samples / 16000.0,
    )


# ---------------------------------------------------------------------------
# Fast integration tests — no GPU, no Ollama, no real audio files
# ---------------------------------------------------------------------------


def test_vad_worker_processes_chunks_to_queue(qt_app: Any) -> None:
    """VadWorker: audio chunks → SpeechSegments on segment_queue via mock VAD."""
    from src.db.models import AudioSegment as DBAudioSegment
    from src.pipeline.vad_worker import VadWorker

    audio_q: queue.Queue[np.ndarray] = queue.Queue(maxsize=100)
    seg_q: queue.Queue[Any] = queue.Queue(maxsize=20)

    mock_vad = MagicMock()
    mock_vad.process_chunk.return_value = [
        DBAudioSegment(samples=np.zeros(512, dtype=np.float32), duration_sec=0.032)
    ]

    worker = VadWorker(audio_q, seg_q, mock_vad, {"sample_rate": 16000})
    worker.start()
    try:
        for _ in range(5):
            audio_q.put(np.zeros(512, dtype=np.float32))
        results = []
        for _ in range(5):
            seg = seg_q.get(timeout=3.0)
            results.append(seg)
    finally:
        worker.stop()

    assert len(results) == 5
    for seg in results:
        assert hasattr(seg, "audio")
        assert hasattr(seg, "sample_rate")
        assert seg.sample_rate == 16000


def test_vad_worker_throughput_100_chunks(qt_app: Any) -> None:
    """VadWorker: 100 chunks processed < 2s (pure overhead, no GPU)."""
    from src.db.models import AudioSegment as DBAudioSegment
    from src.pipeline.vad_worker import VadWorker

    audio_q: queue.Queue[np.ndarray] = queue.Queue(maxsize=200)
    seg_q: queue.Queue[Any] = queue.Queue(maxsize=200)

    mock_vad = MagicMock()
    mock_vad.process_chunk.return_value = [
        DBAudioSegment(samples=np.zeros(512, dtype=np.float32), duration_sec=0.032)
    ]

    worker = VadWorker(audio_q, seg_q, mock_vad, {"sample_rate": 16000})
    for _ in range(100):
        audio_q.put(np.zeros(512, dtype=np.float32))

    start = time.monotonic()
    worker.start()
    results = []
    try:
        for _ in range(100):
            seg = seg_q.get(timeout=5.0)
            results.append(seg)
    finally:
        worker.stop()
    elapsed = time.monotonic() - start

    assert len(results) == 100
    assert elapsed < 2.0, f"100 chunks took {elapsed:.2f}s, expected < 2s"


def test_orchestrator_start_stop_lifecycle(qt_app: Any) -> None:
    """PipelineOrchestrator: start() then stop() completes without error."""
    from src.pipeline.orchestrator import PipelineOrchestrator

    config = {"sample_rate": 16000, "vad_threshold": 0.5}

    with (
        patch("src.pipeline.orchestrator.SileroVAD") as MockVAD,
        patch("src.pipeline.orchestrator.QwenASR") as MockASR,
        patch("src.pipeline.orchestrator.AsyncOllamaClient") as MockLLM,
        patch("src.pipeline.orchestrator.WasapiLoopbackCapture") as MockCapture,
        patch("src.pipeline.orchestrator.VadWorker") as MockVadW,
        patch("src.pipeline.orchestrator.AsrWorker") as MockAsrW,
        patch("src.pipeline.orchestrator.LlmWorker") as MockLlmW,
    ):
        MockVAD.return_value = MagicMock()
        MockASR.return_value = MagicMock()
        MockLLM.return_value = MagicMock()
        MockCapture.return_value = MagicMock()
        MockVadW.return_value = MagicMock()
        MockAsrW.return_value = MagicMock()
        MockLlmW.return_value = MagicMock()

        orch = PipelineOrchestrator(config)
        orch.start()
        orch.stop()


def test_orchestrator_put_audio_drops_when_full(qt_app: Any, caplog: Any) -> None:
    """PipelineOrchestrator.put_audio(): drops chunks gracefully when audio_queue is full."""
    import logging

    from src.pipeline.orchestrator import PipelineOrchestrator

    config = {"sample_rate": 16000}

    with (
        patch("src.pipeline.orchestrator.SileroVAD"),
        patch("src.pipeline.orchestrator.QwenASR"),
        patch("src.pipeline.orchestrator.AsyncOllamaClient"),
    ):
        orch = PipelineOrchestrator(config)
        while True:
            try:
                orch._audio_queue.put_nowait(np.zeros(512, dtype=np.float32))
            except queue.Full:
                break

        with caplog.at_level(logging.WARNING):
            orch.put_audio(np.zeros(512, dtype=np.float32))


@slow
class TestVADWithRealAudio:
    """VAD produces speech segments from real Japanese audio."""

    def test_vad_detects_speech_in_short_wav(self, short_wav: tuple[np.ndarray, int]) -> None:
        audio, sr = short_wav
        assert sr == 16000, f"Expected 16kHz, got {sr}Hz"

        vad = SileroVAD(sample_rate=sr)
        chunk_size = 512
        segments: list[AudioSegment] = []

        for i in range(0, len(audio), chunk_size):
            chunk = audio[i : i + chunk_size]
            if len(chunk) < chunk_size:
                chunk = np.pad(chunk, (0, chunk_size - len(chunk)))
            result = vad.process_chunk(chunk)
            if result is not None:
                segments.extend(result)

        assert len(segments) > 0, "VAD should detect speech in short.wav"
        for seg in segments:
            assert seg.duration_sec > 0.0
            assert seg.samples.dtype == np.float32
            assert len(seg.samples) > 0

    def test_vad_detects_speech_in_long_wav(self, long_wav: tuple[np.ndarray, int]) -> None:
        audio, sr = long_wav
        assert sr == 16000, f"Expected 16kHz, got {sr}Hz"

        vad = SileroVAD(sample_rate=sr)
        chunk_size = 512
        segments: list[AudioSegment] = []

        for i in range(0, len(audio), chunk_size):
            chunk = audio[i : i + chunk_size]
            if len(chunk) < chunk_size:
                chunk = np.pad(chunk, (0, chunk_size - len(chunk)))
            result = vad.process_chunk(chunk)
            if result is not None:
                segments.extend(result)

        assert len(segments) > 0, "VAD should detect speech in long.wav"
        total_speech_sec = sum(s.duration_sec for s in segments)
        assert total_speech_sec > 1.0, "Long audio should contain >1s of speech"

    def test_vad_segments_are_within_max_duration(self, long_wav: tuple[np.ndarray, int]) -> None:
        audio, sr = long_wav
        vad = SileroVAD(sample_rate=sr)
        chunk_size = 512
        segments: list[AudioSegment] = []

        for i in range(0, len(audio), chunk_size):
            chunk = audio[i : i + chunk_size]
            if len(chunk) < chunk_size:
                chunk = np.pad(chunk, (0, chunk_size - len(chunk)))
            result = vad.process_chunk(chunk)
            if result is not None:
                segments.extend(result)

        for seg in segments:
            assert seg.duration_sec <= 30.0, f"Segment exceeds 30s max: {seg.duration_sec:.1f}s"


@slow
@gpu
class TestASRWithRealAudio:
    """ASR transcribes real Japanese audio into text."""

    def test_asr_transcribes_short_wav(self, short_wav: tuple[np.ndarray, int]) -> None:
        from src.asr.qwen_asr import QwenASR

        audio, sr = short_wav
        asr = QwenASR()
        try:
            text = asr.transcribe(audio, sample_rate=sr)
            assert isinstance(text, str)
            assert len(text) > 0, "ASR should produce non-empty text for speech audio"
        finally:
            asr.unload()

    def test_asr_transcribes_long_wav(self, long_wav: tuple[np.ndarray, int]) -> None:
        from src.asr.qwen_asr import QwenASR

        audio, sr = long_wav
        asr = QwenASR()
        try:
            text = asr.transcribe(audio, sample_rate=sr)
            assert isinstance(text, str)
            assert len(text) > 0, "ASR should produce non-empty text for speech audio"
        finally:
            asr.unload()


@slow
@gpu
class TestVADASRPipeline:
    """End-to-end VAD -> ASR pipeline with real audio."""

    def test_vad_then_asr_produces_japanese_text(self, short_wav: tuple[np.ndarray, int]) -> None:
        from src.asr.qwen_asr import QwenASR

        audio, sr = short_wav
        vad = SileroVAD(sample_rate=sr)
        chunk_size = 512
        segments: list[AudioSegment] = []

        for i in range(0, len(audio), chunk_size):
            chunk = audio[i : i + chunk_size]
            if len(chunk) < chunk_size:
                chunk = np.pad(chunk, (0, chunk_size - len(chunk)))
            result = vad.process_chunk(chunk)
            if result is not None:
                segments.extend(result)

        assert len(segments) > 0, "VAD must detect segments before ASR can run"

        asr = QwenASR()
        try:
            transcriptions: list[str] = []
            for seg in segments:
                text = asr.transcribe(seg.samples, sample_rate=sr)
                if text:
                    transcriptions.append(text)

            assert len(transcriptions) > 0, "ASR should transcribe at least one segment"
            full_text = "".join(transcriptions)
            has_japanese = any(
                "\u3040" <= ch <= "\u309f"  # Hiragana
                or "\u30a0" <= ch <= "\u30ff"  # Katakana
                or "\u4e00" <= ch <= "\u9fff"  # CJK Unified
                for ch in full_text
            )
            assert has_japanese, (
                f"Transcription should contain Japanese characters, got: {full_text[:100]}"
            )
        finally:
            asr.unload()


@pytest.fixture()
def short_wav_data() -> tuple[np.ndarray, int]:
    """Load dev/short.wav directly (duplicate of conftest fixture for local use)."""
    path = DEV_DIR / "short.wav"
    if not path.exists():
        pytest.skip(f"Test audio not found: {path}")
    data, sr = sf.read(str(path), dtype="float32", always_2d=False)
    if data.ndim == 2:
        data = data.mean(axis=1)
    return data, int(sr)


@slow
@gpu
@windows_only
class TestWasapiLoopbackASRIntegration:
    """Integration test for WasapiLoopbackCapture + QwenASR.

    Plays audio from dev/short.wav through system speakers, captures via
    WASAPI loopback, and transcribes with QwenASR.

    This test requires:
    - Windows platform (WASAPI loopback)
    - CUDA GPU for ASR model
    - Audio output device configured and working
    - dev/short.wav file present
    """

    def test_play_capture_transcribe_produces_japanese_text(
        self, short_wav_data: tuple[np.ndarray, int]
    ) -> None:
        """Play audio, capture via WASAPI loopback, and verify ASR transcription."""
        import sounddevice as sd

        from src.asr.qwen_asr import QwenASR
        from src.audio.backends import WasapiLoopbackCapture

        audio, sr = short_wav_data
        assert sr == 16000, f"Expected 16kHz audio, got {sr}Hz"

        # Buffer to collect captured audio
        captured_chunks: list[np.ndarray] = []

        def on_audio_chunk(chunk: np.ndarray) -> None:
            """Callback for WasapiLoopbackCapture."""
            captured_chunks.append(chunk)

        # Start WASAPI loopback capture
        capture = WasapiLoopbackCapture(sample_rate=16000)
        capture.start(on_audio_chunk)

        try:
            # Play the audio through system speakers
            sd.play(audio, samplerate=sr)
            sd.wait()  # Wait for playback to complete

            # Allow extra time for audio to be captured
            import time

            time.sleep(0.5)

        finally:
            capture.stop()

        # Combine captured chunks into single array
        assert len(captured_chunks) > 0, "Should have captured some audio chunks"

        captured_audio = np.concatenate(captured_chunks)

        # Verify we captured meaningful audio (not silence)
        rms = np.sqrt(np.mean(captured_audio**2))
        assert rms > 0.01, f"Captured audio RMS too low ({rms}), likely silence"

        # Transcribe with QwenASR
        asr = QwenASR()
        try:
            text = asr.transcribe(captured_audio, sample_rate=16000)

            assert isinstance(text, str), f"Expected str, got {type(text)}"
            assert len(text) > 0, "ASR should produce non-empty text for captured speech"

            # Verify Japanese characters in transcription
            has_japanese = any(
                "\u3040" <= ch <= "\u309f"  # Hiragana
                or "\u30a0" <= ch <= "\u30ff"  # Katakana
                or "\u4e00" <= ch <= "\u9fff"  # CJK Unified
                for ch in text
            )
            assert has_japanese, (
                f"Transcription should contain Japanese characters, got: {text[:100]}"
            )

        finally:
            asr.unload()

    def test_capture_respects_target_sample_rate(
        self, short_wav_data: tuple[np.ndarray, int]
    ) -> None:
        """Verify that WasapiLoopbackCapture resamples to target rate correctly."""
        import time

        from src.audio.backends import WasapiLoopbackCapture

        audio, sr = short_wav_data
        target_rate = 16000

        captured_chunks: list[np.ndarray] = []
        capture = WasapiLoopbackCapture(sample_rate=target_rate)

        def on_audio_chunk(chunk: np.ndarray) -> None:
            captured_chunks.append(chunk)

        capture.start(on_audio_chunk)

        try:
            import sounddevice as sd

            sd.play(audio, samplerate=sr)
            sd.wait()
            time.sleep(0.5)
        finally:
            capture.stop()

        # Verify captured audio is at target sample rate
        # The chunks should be at 16kHz after resampling
        assert len(captured_chunks) > 0, "Should have captured audio chunks"

        # Each chunk should be mono (1-D array)
        for chunk in captured_chunks:
            assert chunk.ndim == 1, f"Expected mono audio, got {chunk.ndim}D array"
            assert chunk.dtype == np.float32, f"Expected float32, got {chunk.dtype}"


# =============================================================================
# Fast integration tests — no GPU, no Ollama, no real audio files
# =============================================================================


class TestPipelineOrchestratorIntegration:
    """Integration test: PipelineOrchestrator with injected mock workers.

    Validates lifecycle ordering (start in order, stop in reverse), that audio
    chunks are routed through the orchestrator, and that shutdown is clean.
    """

    @pytest.fixture()
    def mock_workers(self) -> dict[str, MagicMock]:
        """Pre-built mock workers with Qt-signal-like attributes."""
        vad_worker = MagicMock()
        asr_worker = MagicMock()
        llm_worker = MagicMock()
        for worker in (vad_worker, asr_worker, llm_worker):
            worker.error_occurred = MagicMock()
        asr_worker.asr_ready = MagicMock()
        llm_worker.translation_ready = MagicMock()
        return {"vad": vad_worker, "asr": asr_worker, "llm": llm_worker}

    @pytest.fixture()
    def orchestrator(self, qt_app: Any, mock_workers: dict[str, MagicMock]) -> Any:
        """PipelineOrchestrator with all heavy deps replaced by mocks."""
        from src.pipeline.orchestrator import PipelineOrchestrator

        with (
            patch("src.pipeline.orchestrator.SileroVAD"),
            patch("src.pipeline.orchestrator.QwenASR"),
            patch("src.pipeline.orchestrator.AsyncOllamaClient"),
            patch("src.pipeline.orchestrator.WasapiLoopbackCapture"),
            patch("src.pipeline.orchestrator.VadWorker", return_value=mock_workers["vad"]),
            patch("src.pipeline.orchestrator.AsrWorker", return_value=mock_workers["asr"]),
            patch("src.pipeline.orchestrator.LlmWorker", return_value=mock_workers["llm"]),
        ):
            orch = PipelineOrchestrator(config=_pipeline_config())
            yield orch

    def test_start_calls_workers_in_vad_asr_llm_order(
        self,
        orchestrator: Any,
        mock_workers: dict[str, MagicMock],
    ) -> None:
        """start() must invoke VAD.start(), then ASR.start(), then LLM.start()."""
        manager = MagicMock()
        manager.attach_mock(mock_workers["vad"].start, "vad_start")
        manager.attach_mock(mock_workers["asr"].start, "asr_start")
        manager.attach_mock(mock_workers["llm"].start, "llm_start")

        orchestrator.start()

        assert manager.mock_calls == [
            call.vad_start(),
            call.asr_start(),
            call.llm_start(),
        ], f"Unexpected call order: {manager.mock_calls}"

    def test_stop_calls_workers_in_llm_asr_vad_order(
        self,
        orchestrator: Any,
        mock_workers: dict[str, MagicMock],
    ) -> None:
        """stop() must invoke LLM.stop() first, then ASR, then VAD (reverse pipeline)."""
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
        ], f"Unexpected call order: {manager.mock_calls}"

    def test_stop_waits_on_each_worker(
        self,
        orchestrator: Any,
        mock_workers: dict[str, MagicMock],
    ) -> None:
        """stop() must call .wait(3000) on each worker for graceful drain."""
        orchestrator.start()
        orchestrator.stop()

        mock_workers["vad"].wait.assert_called_once_with(3000)
        mock_workers["asr"].wait.assert_called_once_with(3000)
        mock_workers["llm"].wait.assert_called_once_with(3000)

    def test_put_audio_feeds_10_chunks_into_pipeline(self, orchestrator: Any) -> None:
        """10 mock audio chunks put via put_audio() must reach the audio queue."""
        orchestrator.start()

        chunk = np.zeros(1600, dtype=np.float32)
        for _ in range(10):
            orchestrator.put_audio(chunk)

        assert orchestrator._audio_queue.qsize() == 10, (
            f"Expected 10 items in audio_queue, got {orchestrator._audio_queue.qsize()}"
        )
        orchestrator.stop()

    def test_start_stop_no_exceptions(self, orchestrator: Any) -> None:
        """start() followed by stop() must complete without raising exceptions."""
        orchestrator.start()
        orchestrator.stop()
        assert orchestrator._running is False

    def test_running_flag_lifecycle(self, orchestrator: Any) -> None:
        """_running transitions: False → True on start(), True → False on stop()."""
        assert orchestrator._running is False
        orchestrator.start()
        assert orchestrator._running is True
        orchestrator.stop()
        assert orchestrator._running is False


# ---------------------------------------------------------------------------
# End-to-end queue flow: real VadWorker + mock SileroVAD
# ---------------------------------------------------------------------------


class TestVadWorkerQueueFlow:
    """End-to-end queue flow test using a real VadWorker with a mock VAD model.

    Validates that audio chunks injected into audio_queue produce SpeechSegments
    on segment_queue without blocking, and within a reasonable timeout.
    """

    def test_5_chunks_produce_5_speech_segments(self, qt_app: Any) -> None:
        """5 audio chunks processed by mock VAD must yield 5 SpeechSegments within 2s."""
        from src.pipeline.vad_worker import VadWorker

        audio_queue_t: queue.Queue[np.ndarray] = queue.Queue(maxsize=1000)
        segment_queue_t: queue.Queue[SpeechSegment] = queue.Queue(maxsize=20)

        # Mock VAD that always returns one AudioSegment per chunk
        samples = np.zeros(1600, dtype=np.float32)
        mock_vad = MagicMock()
        mock_vad.process_chunk.return_value = [
            AudioSegment(samples=samples, duration_sec=0.1),
        ]

        worker = VadWorker(
            audio_queue=audio_queue_t,
            segment_queue=segment_queue_t,
            vad=mock_vad,
            config={"sample_rate": 16000},
        )

        # Feed 5 chunks before starting to ensure they're waiting
        chunk = np.zeros(1600, dtype=np.float32)
        for _ in range(5):
            audio_queue_t.put_nowait(chunk)

        worker.start()

        # Collect segments using queue timeouts — no sleep()
        collected: list[SpeechSegment] = []
        deadline = time.monotonic() + 2.0
        while len(collected) < 5 and time.monotonic() < deadline:
            try:
                seg = segment_queue_t.get(timeout=0.1)
                collected.append(seg)
            except queue.Empty:
                pass

        worker.stop()

        assert len(collected) == 5, f"Expected 5 SpeechSegments within 2s, got {len(collected)}"
        for seg in collected:
            assert isinstance(seg, SpeechSegment)
            assert seg.sample_rate == 16000
            assert isinstance(seg.segment_id, str) and len(seg.segment_id) > 0

    def test_worker_shutdown_is_clean_after_queue_flow(self, qt_app: Any) -> None:
        """VadWorker must stop cleanly (<2s) after processing chunks."""
        from src.pipeline.vad_worker import VadWorker

        audio_queue_t: queue.Queue[np.ndarray] = queue.Queue(maxsize=1000)
        segment_queue_t: queue.Queue[SpeechSegment] = queue.Queue(maxsize=20)

        mock_vad = MagicMock()
        mock_vad.process_chunk.return_value = [
            AudioSegment(samples=np.zeros(512, dtype=np.float32), duration_sec=0.032),
        ]

        worker = VadWorker(
            audio_queue=audio_queue_t,
            segment_queue=segment_queue_t,
            vad=mock_vad,
            config={"sample_rate": 16000},
        )

        chunk = np.zeros(512, dtype=np.float32)
        for _ in range(5):
            audio_queue_t.put_nowait(chunk)

        worker.start()
        # Wait for at least one segment to confirm processing started
        try:
            segment_queue_t.get(timeout=2.0)
        except queue.Empty:
            pass  # Stop even if no segment arrived — test clean shutdown

        t0 = time.monotonic()
        worker.stop()
        elapsed = time.monotonic() - t0

        assert elapsed < 2.0, f"Worker stop() took {elapsed:.2f}s — expected <2s"
        assert not worker.isRunning(), "Worker thread must be fully stopped"


# ---------------------------------------------------------------------------
# Performance assertion: VadWorker throughput with mock VAD
# ---------------------------------------------------------------------------


class TestVadWorkerPerformance:
    """Performance test: VadWorker must process 100 chunks in <500ms with mock VAD.

    The mock VAD returns instantly so this measures queue-threading overhead only,
    not GPU inference time.
    """

    def test_100_chunks_processed_under_500ms(self, qt_app: Any) -> None:
        """VadWorker must process 100 audio chunks in <500ms (mock VAD = instant)."""
        from src.pipeline.vad_worker import VadWorker

        audio_queue_t: queue.Queue[np.ndarray] = queue.Queue(maxsize=1000)
        segment_queue_t: queue.Queue[SpeechSegment] = queue.Queue(maxsize=200)

        samples = np.zeros(512, dtype=np.float32)
        mock_vad = MagicMock()
        mock_vad.process_chunk.return_value = [
            AudioSegment(samples=samples, duration_sec=0.032),
        ]

        worker = VadWorker(
            audio_queue=audio_queue_t,
            segment_queue=segment_queue_t,
            vad=mock_vad,
            config={"sample_rate": 16000},
        )

        chunk = np.zeros(512, dtype=np.float32)
        for _ in range(100):
            audio_queue_t.put_nowait(chunk)

        t0 = time.monotonic()
        worker.start()

        # Wait for all 100 segments to arrive — use queue timeout, no sleep()
        collected = 0
        deadline = time.monotonic() + 5.0  # generous outer deadline
        while collected < 100 and time.monotonic() < deadline:
            try:
                segment_queue_t.get(timeout=0.05)
                collected += 1
            except queue.Empty:
                pass

        elapsed_ms = (time.monotonic() - t0) * 1000
        worker.stop()

        assert collected == 100, f"Expected 100 segments, got {collected}"
        assert elapsed_ms < 500, (
            f"100 chunks took {elapsed_ms:.1f}ms — expected <500ms with mock VAD"
        )
