import os
import sqlite3
from collections.abc import Callable, Generator
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from PySide6.QtWidgets import QApplication

from src.config import AppConfig
from src.db.models import (
    AnalysisResult,
    AudioSegment,
    GrammarHit,
    HighlightGrammar,
    HighlightVocab,
    SentenceRecord,
    SentenceResult,
    VocabHit,
)
from src.db.schema import init_db
from src.exceptions import ASRError, AudioCaptureError

os.environ["QT_QPA_PLATFORM"] = "offscreen"


@pytest.fixture(scope="session")
def qapp() -> Generator[QApplication, None, None]:
    existing = QApplication.instance()
    app: QApplication = existing if isinstance(existing, QApplication) else QApplication([])
    yield app


def _make_config() -> MagicMock:
    cfg = MagicMock(spec=AppConfig)
    cfg.sample_rate = 16000
    cfg.ollama_url = "http://localhost:11434"
    cfg.ollama_model = "qwen3.5:4b"
    cfg.ollama_timeout_sec = 30.0
    cfg.db_path = ":memory:"
    cfg.user_jlpt_level = 3
    return cfg


def _make_analysis_result() -> AnalysisResult:
    return AnalysisResult(
        tokens=[],
        vocab_hits=[],
        grammar_hits=[],
    )


def _make_audio_segment() -> AudioSegment:
    return AudioSegment(samples=np.zeros(16000, dtype=np.float32), duration_sec=1.0)


@patch("src.pipeline.OllamaClient")
@patch("src.pipeline.PreprocessingPipeline")
@patch("src.pipeline.QwenASR")
@patch("src.pipeline.SileroVAD")
@patch("src.pipeline.AudioCapture")
def test_pipeline_emits_sentence_ready_on_valid_segment(
    mock_audio_cls: MagicMock,
    mock_vad_cls: MagicMock,
    mock_asr_cls: MagicMock,
    mock_prep_cls: MagicMock,
    mock_llm_cls: MagicMock,
    qapp: QApplication,
) -> None:
    mock_llm_cls.return_value.translate.return_value = (None, None)
    segment = _make_audio_segment()
    analysis = _make_analysis_result()

    mock_audio = mock_audio_cls.return_value
    mock_vad = mock_vad_cls.return_value
    mock_asr = mock_asr_cls.return_value
    mock_prep = mock_prep_cls.return_value

    mock_vad.process_chunk.return_value = [segment]
    mock_asr.transcribe.return_value = "テスト"
    mock_prep.process.return_value = analysis

    captured_callback: list[Callable[..., None]] = []

    def fake_start(callback: Callable[..., None]) -> None:
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
        translation, explanation = worker._llm.translate(text)
        result = SentenceResult(
            japanese_text=text,
            chinese_translation=translation,
            explanation=explanation,
            analysis=result_analysis,
        )
        worker.sentence_ready.emit(result)

    assert len(results) == 1
    assert results[0].japanese_text == "テスト"
    assert results[0].chinese_translation is None
    assert results[0].analysis is analysis


@patch("src.pipeline.OllamaClient")
@patch("src.pipeline.PreprocessingPipeline")
@patch("src.pipeline.QwenASR")
@patch("src.pipeline.SileroVAD")
@patch("src.pipeline.AudioCapture")
def test_pipeline_skips_empty_asr_result(
    mock_audio_cls: MagicMock,
    mock_vad_cls: MagicMock,
    mock_asr_cls: MagicMock,
    mock_prep_cls: MagicMock,
    mock_llm_cls: MagicMock,
    qapp: QApplication,
) -> None:
    mock_llm_cls.return_value.translate.return_value = (None, None)
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
        translation, explanation = worker._llm.translate(text)
        result = SentenceResult(
            japanese_text=text,
            chinese_translation=translation,
            explanation=explanation,
            analysis=result_analysis,
        )
        worker.sentence_ready.emit(result)

    assert len(results) == 0
    assert len(errors) == 0


@patch("src.pipeline.OllamaClient")
@patch("src.pipeline.PreprocessingPipeline")
@patch("src.pipeline.QwenASR")
@patch("src.pipeline.SileroVAD")
@patch("src.pipeline.AudioCapture")
def test_pipeline_handles_asr_error_gracefully(
    mock_audio_cls: MagicMock,
    mock_vad_cls: MagicMock,
    mock_asr_cls: MagicMock,
    mock_prep_cls: MagicMock,
    mock_llm_cls: MagicMock,
    qapp: QApplication,
) -> None:
    mock_llm_cls.return_value.translate.return_value = (None, None)
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
        translation, explanation = worker._llm.translate(text)
        result = SentenceResult(
            japanese_text=text,
            chinese_translation=translation,
            explanation=explanation,
            analysis=result_analysis,
        )
        worker.sentence_ready.emit(result)

    assert len(results) == 0
    assert len(errors) == 0


@patch("src.pipeline.OllamaClient")
@patch("src.pipeline.PreprocessingPipeline")
@patch("src.pipeline.QwenASR")
@patch("src.pipeline.SileroVAD")
@patch("src.pipeline.AudioCapture")
def test_pipeline_emits_error_on_audio_capture_failure(
    mock_audio_cls: MagicMock,
    mock_vad_cls: MagicMock,
    mock_asr_cls: MagicMock,
    mock_prep_cls: MagicMock,
    mock_llm_cls: MagicMock,
    qapp: QApplication,
) -> None:
    mock_llm_cls.return_value.translate.return_value = (None, None)
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


@patch("src.pipeline.OllamaClient")
@patch("src.pipeline.PreprocessingPipeline")
@patch("src.pipeline.QwenASR")
@patch("src.pipeline.SileroVAD")
@patch("src.pipeline.AudioCapture")
def test_stop_calls_cleanup(
    mock_audio_cls: MagicMock,
    mock_vad_cls: MagicMock,
    mock_asr_cls: MagicMock,
    mock_prep_cls: MagicMock,
    mock_llm_cls: MagicMock,
    qapp: QApplication,
) -> None:
    mock_llm_cls.return_value.translate.return_value = (None, None)
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


# ── New tests ────────────────────────────────────────────────────────────────


@patch("src.pipeline.OllamaClient")
@patch("src.pipeline.PreprocessingPipeline")
@patch("src.pipeline.QwenASR")
@patch("src.pipeline.SileroVAD")
@patch("src.pipeline.AudioCapture")
def test_pipeline_populates_translation_on_llm_success(
    mock_audio_cls: MagicMock,
    mock_vad_cls: MagicMock,
    mock_asr_cls: MagicMock,
    mock_prep_cls: MagicMock,
    mock_llm_cls: MagicMock,
    qapp: QApplication,
) -> None:
    mock_llm_cls.return_value.translate.return_value = ("翻訳文", "解説文")
    analysis = _make_analysis_result()
    mock_prep_cls.return_value.process.return_value = analysis

    from src.pipeline import PipelineWorker

    worker = PipelineWorker(_make_config())

    results: list[SentenceResult] = []
    worker.sentence_ready.connect(results.append)

    text = "テスト文章"
    result_analysis = worker._preprocessing.process(text)
    translation, explanation = worker._llm.translate(text)
    result = SentenceResult(
        japanese_text=text,
        chinese_translation=translation,
        explanation=explanation,
        analysis=result_analysis,
    )
    worker.sentence_ready.emit(result)

    assert len(results) == 1
    assert results[0].chinese_translation == "翻訳文"
    assert results[0].explanation == "解説文"


@patch("src.pipeline.OllamaClient")
@patch("src.pipeline.PreprocessingPipeline")
@patch("src.pipeline.QwenASR")
@patch("src.pipeline.SileroVAD")
@patch("src.pipeline.AudioCapture")
def test_pipeline_emits_with_none_on_llm_failure(
    mock_audio_cls: MagicMock,
    mock_vad_cls: MagicMock,
    mock_asr_cls: MagicMock,
    mock_prep_cls: MagicMock,
    mock_llm_cls: MagicMock,
    qapp: QApplication,
) -> None:
    mock_llm_cls.return_value.translate.side_effect = Exception("timeout")
    analysis = _make_analysis_result()
    mock_prep_cls.return_value.process.return_value = analysis

    from src.pipeline import PipelineWorker

    worker = PipelineWorker(_make_config())

    results: list[SentenceResult] = []
    worker.sentence_ready.connect(results.append)

    text = "テスト文章"
    result_analysis = worker._preprocessing.process(text)
    try:
        translation, explanation = worker._llm.translate(text)
    except Exception:
        translation, explanation = None, None
    result = SentenceResult(
        japanese_text=text,
        chinese_translation=translation,
        explanation=explanation,
        analysis=result_analysis,
    )
    worker.sentence_ready.emit(result)

    assert len(results) == 1
    assert results[0].chinese_translation is None
    assert results[0].explanation is None


@patch("src.pipeline.OllamaClient")
@patch("src.pipeline.PreprocessingPipeline")
@patch("src.pipeline.QwenASR")
@patch("src.pipeline.SileroVAD")
@patch("src.pipeline.AudioCapture")
def test_pipeline_writes_to_db_on_success(
    mock_audio_cls: MagicMock,
    mock_vad_cls: MagicMock,
    mock_asr_cls: MagicMock,
    mock_prep_cls: MagicMock,
    mock_llm_cls: MagicMock,
    qapp: QApplication,
) -> None:
    mock_llm_cls.return_value.translate.return_value = ("中国語訳", None)
    analysis = _make_analysis_result()
    mock_prep_cls.return_value.process.return_value = analysis
    mock_asr_cls.return_value.transcribe.return_value = "テスト"
    mock_vad_cls.return_value.process_chunk.return_value = [_make_audio_segment()]

    db_conn = init_db(":memory:")

    from src.pipeline import PipelineWorker

    worker = PipelineWorker(_make_config(), db_conn=db_conn)

    results: list[SentenceResult] = []
    worker.sentence_ready.connect(results.append)

    text = "テスト"
    result_analysis = worker._preprocessing.process(text)
    translation, explanation = worker._llm.translate(text)
    result = SentenceResult(
        japanese_text=text,
        chinese_translation=translation,
        explanation=explanation,
        analysis=result_analysis,
    )
    worker.sentence_ready.emit(result)

    record, vocab_recs, grammar_recs = worker._to_db_records(result)
    worker._repo.insert_sentence(record, vocab_recs, grammar_recs)  # type: ignore[union-attr]

    cursor = db_conn.execute("SELECT japanese_text, chinese_translation FROM sentence_records")
    rows = cursor.fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "テスト"
    assert rows[0][1] == "中国語訳"


@patch("src.pipeline.LearningRepository")
@patch("src.pipeline.OllamaClient")
@patch("src.pipeline.PreprocessingPipeline")
@patch("src.pipeline.QwenASR")
@patch("src.pipeline.SileroVAD")
@patch("src.pipeline.AudioCapture")
def test_pipeline_still_emits_when_db_write_fails(
    mock_audio_cls: MagicMock,
    mock_vad_cls: MagicMock,
    mock_asr_cls: MagicMock,
    mock_prep_cls: MagicMock,
    mock_llm_cls: MagicMock,
    mock_repo_cls: MagicMock,
    qapp: QApplication,
) -> None:
    mock_llm_cls.return_value.translate.return_value = ("翻訳", None)
    mock_repo_cls.return_value.insert_sentence.side_effect = sqlite3.OperationalError("disk full")
    analysis = _make_analysis_result()
    mock_prep_cls.return_value.process.return_value = analysis

    db_conn = MagicMock(spec=sqlite3.Connection)

    from src.pipeline import PipelineWorker

    worker = PipelineWorker(_make_config(), db_conn=db_conn)

    results: list[SentenceResult] = []
    worker.sentence_ready.connect(results.append)

    text = "テスト文章"
    result_analysis = worker._preprocessing.process(text)
    translation, explanation = worker._llm.translate(text)
    result = SentenceResult(
        japanese_text=text,
        chinese_translation=translation,
        explanation=explanation,
        analysis=result_analysis,
    )
    worker.sentence_ready.emit(result)

    if worker._repo is not None:
        try:
            rec, vocab_recs, grammar_recs = worker._to_db_records(result)
            worker._repo.insert_sentence(rec, vocab_recs, grammar_recs)
        except Exception:
            pass

    assert len(results) == 1
    assert results[0].chinese_translation == "翻訳"


@patch("src.pipeline.OllamaClient")
@patch("src.pipeline.PreprocessingPipeline")
@patch("src.pipeline.QwenASR")
@patch("src.pipeline.SileroVAD")
@patch("src.pipeline.AudioCapture")
def test_to_db_records_converts_correctly(
    mock_audio_cls: MagicMock,
    mock_vad_cls: MagicMock,
    mock_asr_cls: MagicMock,
    mock_prep_cls: MagicMock,
    mock_llm_cls: MagicMock,
    qapp: QApplication,
) -> None:
    mock_llm_cls.return_value.translate.return_value = (None, None)

    from src.pipeline import PipelineWorker

    worker = PipelineWorker(_make_config())

    vocab_hit = VocabHit(
        surface="概念",
        lemma="概念",
        pos="名詞",
        jlpt_level=1,
        user_level=3,
    )
    grammar_hit = GrammarHit(
        rule_id="n1-001",
        matched_text="にもかかわらず",
        jlpt_level=1,
        confidence_type="exact",
        description="despite",
    )
    analysis = AnalysisResult(
        tokens=[],
        vocab_hits=[vocab_hit],
        grammar_hits=[grammar_hit],
    )
    result = SentenceResult(
        japanese_text="概念にもかかわらず",
        chinese_translation="尽管概念如此",
        explanation="N1文法解析",
        analysis=analysis,
    )

    record, vocab_recs, grammar_recs = worker._to_db_records(result)

    assert isinstance(record, SentenceRecord)
    assert record.id is None
    assert record.japanese_text == "概念にもかかわらず"
    assert record.chinese_translation == "尽管概念如此"
    assert record.explanation == "N1文法解析"
    assert record.source_context is None

    assert len(vocab_recs) == 1
    assert isinstance(vocab_recs[0], HighlightVocab)
    assert vocab_recs[0].id is None
    assert vocab_recs[0].sentence_id == 0
    assert vocab_recs[0].surface == "概念"
    assert vocab_recs[0].lemma == "概念"
    assert vocab_recs[0].pos == "名詞"
    assert vocab_recs[0].jlpt_level == 1
    assert vocab_recs[0].is_beyond_level is True
    assert vocab_recs[0].tooltip_shown is False

    assert len(grammar_recs) == 1
    assert isinstance(grammar_recs[0], HighlightGrammar)
    assert grammar_recs[0].id is None
    assert grammar_recs[0].sentence_id == 0
    assert grammar_recs[0].rule_id == "n1-001"
    assert grammar_recs[0].pattern == "にもかかわらず"
    assert grammar_recs[0].jlpt_level == 1
    assert grammar_recs[0].confidence_type == "exact"
    assert grammar_recs[0].description == "despite"
    assert grammar_recs[0].is_beyond_level is True
    assert grammar_recs[0].tooltip_shown is False
