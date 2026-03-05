import os
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from PySide6.QtWidgets import QApplication

from src.db.models import AnalysisResult, AudioSegment, SentenceResult
from src.exceptions import ASRError, AudioCaptureError

os.environ["QT_QPA_PLATFORM"] = "offscreen"


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance() or QApplication([])
    yield app  # type: ignore[misc]


def _make_config() -> MagicMock:
    cfg = MagicMock()
    cfg.sample_rate = 16000
    return cfg


def _make_analysis_result() -> AnalysisResult:
    return AnalysisResult(
        tokens=[],
        vocab_hits=[],
        grammar_hits=[],
        complexity_score=0.0,
        is_complex=False,
    )


def _make_audio_segment() -> AudioSegment:
    return AudioSegment(samples=np.zeros(16000, dtype=np.float32), duration_sec=1.0)


@patch("src.pipeline.PreprocessingPipeline")
@patch("src.pipeline.QwenASR")
@patch("src.pipeline.SileroVAD")
@patch("src.pipeline.AudioCapture")
def test_pipeline_emits_sentence_ready_on_valid_segment(
    mock_audio_cls: MagicMock,
    mock_vad_cls: MagicMock,
    mock_asr_cls: MagicMock,
    mock_prep_cls: MagicMock,
    qapp: QApplication,
) -> None:
    segment = _make_audio_segment()
    analysis = _make_analysis_result()

    mock_audio = mock_audio_cls.return_value
    mock_vad = mock_vad_cls.return_value
    mock_asr = mock_asr_cls.return_value
    mock_prep = mock_prep_cls.return_value

    mock_vad.process_chunk.return_value = [segment]
    mock_asr.transcribe.return_value = "テスト"
    mock_prep.process.return_value = analysis

    captured_callback: list = []

    def fake_start(callback):
        captured_callback.append(callback)

    mock_audio.start.side_effect = fake_start

    from src.pipeline import PipelineWorker

    worker = PipelineWorker(_make_config())

    results: list[SentenceResult] = []
    worker.sentence_ready.connect(results.append)

    worker._running = True

    worker._audio_capture.start(callback=lambda chunk: worker._audio_queue.put(chunk))
    captured_callback[0](np.zeros(512, dtype=np.float32))

    chunk = worker._audio_queue.get(timeout=1.0)
    segments = worker._vad.process_chunk(chunk)
    assert segments is not None
    for seg in segments:
        text = worker._asr.transcribe(seg.samples, sample_rate=worker._config.sample_rate)
        if not text:
            continue
        result_analysis = worker._preprocessing.process(text)
        result = SentenceResult(
            japanese_text=text,
            chinese_translation=None,
            explanation=None,
            analysis=result_analysis,
        )
        worker.sentence_ready.emit(result)

    assert len(results) == 1
    assert results[0].japanese_text == "テスト"
    assert results[0].chinese_translation is None
    assert results[0].analysis is analysis


@patch("src.pipeline.PreprocessingPipeline")
@patch("src.pipeline.QwenASR")
@patch("src.pipeline.SileroVAD")
@patch("src.pipeline.AudioCapture")
def test_pipeline_skips_empty_asr_result(
    mock_audio_cls: MagicMock,
    mock_vad_cls: MagicMock,
    mock_asr_cls: MagicMock,
    mock_prep_cls: MagicMock,
    qapp: QApplication,
) -> None:
    segment = _make_audio_segment()

    mock_vad = mock_vad_cls.return_value
    mock_asr = mock_asr_cls.return_value

    mock_vad.process_chunk.return_value = [segment]
    mock_asr.transcribe.return_value = ""

    from src.pipeline import PipelineWorker

    worker = PipelineWorker(_make_config())

    results: list[SentenceResult] = []
    errors: list[str] = []
    worker.sentence_ready.connect(results.append)
    worker.error_occurred.connect(errors.append)

    chunk = np.zeros(512, dtype=np.float32)
    worker._audio_queue.put(chunk)

    segments_out = worker._vad.process_chunk(chunk)
    assert segments_out is not None
    for seg in segments_out:
        text = worker._asr.transcribe(seg.samples, sample_rate=worker._config.sample_rate)
        if not text:
            continue
        result_analysis = worker._preprocessing.process(text)
        result = SentenceResult(
            japanese_text=text,
            chinese_translation=None,
            explanation=None,
            analysis=result_analysis,
        )
        worker.sentence_ready.emit(result)

    assert len(results) == 0
    assert len(errors) == 0


@patch("src.pipeline.PreprocessingPipeline")
@patch("src.pipeline.QwenASR")
@patch("src.pipeline.SileroVAD")
@patch("src.pipeline.AudioCapture")
def test_pipeline_handles_asr_error_gracefully(
    mock_audio_cls: MagicMock,
    mock_vad_cls: MagicMock,
    mock_asr_cls: MagicMock,
    mock_prep_cls: MagicMock,
    qapp: QApplication,
) -> None:
    segment = _make_audio_segment()

    mock_vad = mock_vad_cls.return_value
    mock_asr = mock_asr_cls.return_value

    mock_vad.process_chunk.return_value = [segment]
    mock_asr.transcribe.side_effect = ASRError("model failed")

    from src.pipeline import PipelineWorker

    worker = PipelineWorker(_make_config())

    results: list[SentenceResult] = []
    errors: list[str] = []
    worker.sentence_ready.connect(results.append)
    worker.error_occurred.connect(errors.append)

    chunk = np.zeros(512, dtype=np.float32)
    segments_out = worker._vad.process_chunk(chunk)
    assert segments_out is not None
    for seg in segments_out:
        try:
            text = worker._asr.transcribe(seg.samples, sample_rate=worker._config.sample_rate)
        except ASRError:
            continue
        if not text:
            continue
        result_analysis = worker._preprocessing.process(text)
        result = SentenceResult(
            japanese_text=text,
            chinese_translation=None,
            explanation=None,
            analysis=result_analysis,
        )
        worker.sentence_ready.emit(result)

    assert len(results) == 0
    assert len(errors) == 0


@patch("src.pipeline.PreprocessingPipeline")
@patch("src.pipeline.QwenASR")
@patch("src.pipeline.SileroVAD")
@patch("src.pipeline.AudioCapture")
def test_pipeline_emits_error_on_audio_capture_failure(
    mock_audio_cls: MagicMock,
    mock_vad_cls: MagicMock,
    mock_asr_cls: MagicMock,
    mock_prep_cls: MagicMock,
    qapp: QApplication,
) -> None:
    mock_audio = mock_audio_cls.return_value
    mock_audio.start.side_effect = AudioCaptureError("no device")

    from src.pipeline import PipelineWorker

    worker = PipelineWorker(_make_config())

    errors: list[str] = []
    results: list[SentenceResult] = []
    worker.error_occurred.connect(errors.append)
    worker.sentence_ready.connect(results.append)

    worker.run()

    assert len(errors) == 1
    assert "no device" in errors[0]
    assert len(results) == 0
    assert worker._running is False


@patch("src.pipeline.PreprocessingPipeline")
@patch("src.pipeline.QwenASR")
@patch("src.pipeline.SileroVAD")
@patch("src.pipeline.AudioCapture")
def test_stop_calls_cleanup(
    mock_audio_cls: MagicMock,
    mock_vad_cls: MagicMock,
    mock_asr_cls: MagicMock,
    mock_prep_cls: MagicMock,
    qapp: QApplication,
) -> None:
    mock_audio = mock_audio_cls.return_value
    mock_vad = mock_vad_cls.return_value
    mock_asr = mock_asr_cls.return_value

    from src.pipeline import PipelineWorker

    worker = PipelineWorker(_make_config())

    worker._running = False
    worker._cleanup()

    mock_audio.stop.assert_called_once()
    mock_vad.reset.assert_called_once()
    mock_asr.unload.assert_called_once()
