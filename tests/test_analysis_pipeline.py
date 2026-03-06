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


def test_pipeline_latency(pipeline: PreprocessingPipeline) -> None:
    sentence = "昨日友達と映画を見に行きました"
    pipeline.process(sentence)
    times: list[float] = []
    for _ in range(5):
        start = time.perf_counter()
        pipeline.process(sentence)
        times.append((time.perf_counter() - start) * 1000)
    avg_ms = sum(times) / len(times)
    assert avg_ms < 50.0, f"Average latency {avg_ms:.1f}ms exceeds 50ms"


def test_pipeline_vocab_hits_populated(pipeline: PreprocessingPipeline) -> None:
    result = pipeline.process("概念を理解する")
    lemmas = [h.lemma for h in result.vocab_hits]
    assert "概念" in lemmas

    # Assert position fields are populated
    for vocab_hit in result.vocab_hits:
        assert vocab_hit.start_pos >= 0
        assert vocab_hit.end_pos > vocab_hit.start_pos


def test_pipeline_grammar_hits_have_positions(pipeline: PreprocessingPipeline) -> None:
    result = pipeline.process("食べている")

    for grammar_hit in result.grammar_hits:
        assert grammar_hit.start_pos >= 0
        assert grammar_hit.end_pos > grammar_hit.start_pos
