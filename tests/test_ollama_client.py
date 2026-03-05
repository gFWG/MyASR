"""Tests for OllamaClient."""

from unittest.mock import MagicMock, patch

import requests

from src.config import AppConfig
from src.db.models import AnalysisResult, GrammarHit, VocabHit
from src.llm.ollama_client import OllamaClient


def _make_config() -> AppConfig:
    return AppConfig()


def _simple_analysis() -> AnalysisResult:
    return AnalysisResult(
        tokens=[],
        vocab_hits=[],
        grammar_hits=[],
        complexity_score=0.0,
        is_complex=False,
    )


def _complex_analysis(
    vocab_hits: list[VocabHit] | None = None,
    grammar_hits: list[GrammarHit] | None = None,
) -> AnalysisResult:
    return AnalysisResult(
        tokens=[],
        vocab_hits=vocab_hits or [],
        grammar_hits=grammar_hits or [],
        complexity_score=5.0,
        is_complex=True,
    )


# ---------------------------------------------------------------------------
# translate()
# ---------------------------------------------------------------------------


def test_translate_simple_returns_translation_only() -> None:
    client = OllamaClient(_make_config())
    mock_response = MagicMock()
    mock_response.json.return_value = {"response": "这是测试翻译"}
    mock_response.raise_for_status.return_value = None

    with patch("src.llm.ollama_client.requests.post", return_value=mock_response):
        result = client.translate("テストです", _simple_analysis())

    assert result == ("这是测试翻译", None)


def test_translate_complex_returns_translation_and_explanation() -> None:
    client = OllamaClient(_make_config())
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "response": "翻訳：复杂句子的翻译\n解析：这里使用了N1语法..."
    }
    mock_response.raise_for_status.return_value = None

    with patch("src.llm.ollama_client.requests.post", return_value=mock_response):
        result = client.translate("複雑な文です", _complex_analysis())

    assert result == ("复杂句子的翻译", "这里使用了N1语法...")


def test_translate_returns_none_tuple_on_timeout() -> None:
    client = OllamaClient(_make_config())

    with patch(
        "src.llm.ollama_client.requests.post",
        side_effect=requests.exceptions.Timeout,
    ):
        result = client.translate("テスト", _simple_analysis())

    assert result == (None, None)


def test_translate_returns_none_tuple_on_connection_error() -> None:
    client = OllamaClient(_make_config())

    with patch(
        "src.llm.ollama_client.requests.post",
        side_effect=requests.exceptions.ConnectionError,
    ):
        result = client.translate("テスト", _simple_analysis())

    assert result == (None, None)


# ---------------------------------------------------------------------------
# _build_prompt()
# ---------------------------------------------------------------------------


def test_build_prompt_simple_uses_simple_template() -> None:
    client = OllamaClient(_make_config())
    prompt = client._build_prompt("テストです", _simple_analysis())

    assert "翻訳のみを出力" in prompt
    assert "テストです" in prompt


def test_build_prompt_complex_includes_formatted_hits() -> None:
    client = OllamaClient(_make_config())

    vocab_hit = VocabHit(
        surface="概念",
        lemma="がいねん",
        pos="名詞",
        jlpt_level=1,
        user_level=3,
    )
    grammar_hit = GrammarHit(
        rule_id="r1",
        matched_text="～にとって",
        jlpt_level=2,
        confidence_type="high",
        description="に関して",
    )
    analysis = _complex_analysis(vocab_hits=[vocab_hit], grammar_hits=[grammar_hit])
    prompt = client._build_prompt("テスト", analysis)

    assert "概念(がいねん, N1)" in prompt
    assert "～にとって(N2, に関して)" in prompt


# ---------------------------------------------------------------------------
# _parse_response()
# ---------------------------------------------------------------------------


def test_parse_response_complex_with_both_markers() -> None:
    client = OllamaClient(_make_config())
    result = client._parse_response("翻訳：翻译结果\n解析：语法解析", is_complex=True)

    assert result == ("翻译结果", "语法解析")


def test_parse_response_complex_with_only_translation_marker() -> None:
    client = OllamaClient(_make_config())
    result = client._parse_response("翻訳：只有翻译没有解析", is_complex=True)

    assert result == ("只有翻译没有解析", None)


def test_parse_response_complex_without_markers_fallback() -> None:
    client = OllamaClient(_make_config())
    result = client._parse_response("直接的翻译文本", is_complex=True)

    assert result == ("直接的翻译文本", None)


def test_parse_response_empty_string() -> None:
    client = OllamaClient(_make_config())
    result = client._parse_response("", is_complex=True)

    assert result == ("", None)


# ---------------------------------------------------------------------------
# health_check()
# ---------------------------------------------------------------------------


def test_health_check_true_when_reachable() -> None:
    client = OllamaClient(_make_config())
    mock_response = MagicMock()
    mock_response.status_code = 200

    with patch("src.llm.ollama_client.requests.get", return_value=mock_response):
        assert client.health_check() is True


def test_health_check_false_when_unreachable() -> None:
    client = OllamaClient(_make_config())

    with patch(
        "src.llm.ollama_client.requests.get",
        side_effect=requests.exceptions.ConnectionError,
    ):
        assert client.health_check() is False
