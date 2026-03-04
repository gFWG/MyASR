"""Tests for src.analysis.pipeline."""

import time

import pytest

from src.analysis.pipeline import PreprocessingPipeline
from src.config import AppConfig
from src.db.models import AnalysisResult


@pytest.fixture(scope="module")
def pipeline() -> PreprocessingPipeline:
    return PreprocessingPipeline(AppConfig())


def test_pipeline_returns_analysis_result(pipeline: PreprocessingPipeline) -> None:
    result = pipeline.process("これは猫です")
    assert isinstance(result, AnalysisResult)
    assert len(result.tokens) > 0


def test_pipeline_empty_text(pipeline: PreprocessingPipeline) -> None:
    result = pipeline.process("")
    assert isinstance(result, AnalysisResult)
    assert result.tokens == []
    assert result.vocab_hits == []
    assert result.grammar_hits == []


def test_pipeline_shares_tagger(pipeline: PreprocessingPipeline) -> None:
    assert pipeline._scorer._tagger is pipeline._tokenizer.tagger


def test_pipeline_complex_sentence_flagged(pipeline: PreprocessingPipeline) -> None:
    result = pipeline.process("経済の概念を理解することは社会発展に影響を与えざるを得ない")
    assert isinstance(result.complexity_score, float)
    assert isinstance(result.is_complex, bool)


def test_pipeline_latency(pipeline: PreprocessingPipeline) -> None:
    sentence = "昨日友達と映画を見に行きました"
    # Warm-up run (first call loads models/caches)
    pipeline.process(sentence)
    times: list[float] = []
    for _ in range(5):
        start = time.perf_counter()
        pipeline.process(sentence)
        times.append((time.perf_counter() - start) * 1000)
    avg_ms = sum(times) / len(times)
    assert avg_ms < 50.0, f"Average latency {avg_ms:.1f}ms exceeds 50ms"


def test_pipeline_vocab_hits_populated(pipeline: PreprocessingPipeline) -> None:
    # 概念 is N1 (level=1), which is < user_jlpt_level=3 → beyond level
    result = pipeline.process("概念を理解する")
    lemmas = [h.lemma for h in result.vocab_hits]
    assert "概念" in lemmas
