"""Tests for OllamaClient."""

from unittest.mock import MagicMock, patch

import requests

from src.config import AppConfig
from src.llm.ollama_client import OllamaClient


def _make_config(
    llm_mode: str = "translation",
) -> AppConfig:
    return AppConfig(llm_mode=llm_mode)  # type: ignore[arg-type]


def _make_explanation_config() -> AppConfig:
    return AppConfig(llm_mode="explanation")


# ---------------------------------------------------------------------------
# translate() — translation mode
# ---------------------------------------------------------------------------


def test_translate_translation_mode_returns_translation_only() -> None:
    client = OllamaClient(_make_config("translation"))
    mock_response = MagicMock()
    mock_response.json.return_value = {"response": "这是测试翻译"}
    mock_response.raise_for_status.return_value = None

    with patch("src.llm.ollama_client.requests.post", return_value=mock_response):
        result = client.translate("テストです")

    assert result == ("这是测试翻译", None)


def test_translate_explanation_mode_returns_explanation_only() -> None:
    client = OllamaClient(_make_explanation_config())
    mock_response = MagicMock()
    mock_response.json.return_value = {"response": "这里使用了N1语法的被动态..."}
    mock_response.raise_for_status.return_value = None

    with patch("src.llm.ollama_client.requests.post", return_value=mock_response):
        result = client.translate("複雑な文です")

    assert result == (None, "这里使用了N1语法的被动态...")


def test_translate_returns_none_tuple_on_timeout() -> None:
    client = OllamaClient(_make_config())

    with patch(
        "src.llm.ollama_client.requests.post",
        side_effect=requests.exceptions.Timeout,
    ):
        result = client.translate("テスト")

    assert result == (None, None)


def test_translate_returns_none_tuple_on_connection_error() -> None:
    client = OllamaClient(_make_config())

    with patch(
        "src.llm.ollama_client.requests.post",
        side_effect=requests.exceptions.ConnectionError,
    ):
        result = client.translate("テスト")

    assert result == (None, None)


# ---------------------------------------------------------------------------
# _build_prompt()
# ---------------------------------------------------------------------------


def test_build_prompt_translation_mode_uses_translation_template() -> None:
    client = OllamaClient(_make_config("translation"))
    prompt = client._build_prompt("テストです")

    assert "テストです" in prompt
    assert "翻译" in prompt or "翻訳" in prompt


def test_build_prompt_explanation_mode_uses_explanation_template() -> None:
    client = OllamaClient(_make_explanation_config())
    prompt = client._build_prompt("テストです")

    assert "テストです" in prompt
    assert "解析" in prompt or "解説" in prompt or "説明" in prompt


def test_build_prompt_custom_translation_template() -> None:
    config = AppConfig(
        llm_mode="translation",
        translation_template="Translate: {japanese_text}",
    )
    client = OllamaClient(config)
    prompt = client._build_prompt("テスト")

    assert prompt == "Translate: テスト"


def test_build_prompt_custom_explanation_template() -> None:
    config = AppConfig(
        llm_mode="explanation",
        explanation_template="Explain: {japanese_text}",
    )
    client = OllamaClient(config)
    prompt = client._build_prompt("テスト")

    assert prompt == "Explain: テスト"


# ---------------------------------------------------------------------------
# _parse_response()
# ---------------------------------------------------------------------------


def test_parse_response_translation_mode_strips_whitespace() -> None:
    client = OllamaClient(_make_config("translation"))
    result = client._parse_response("  翻译结果  ")

    assert result == ("翻译结果", None)


def test_parse_response_explanation_returns_explanation_only() -> None:
    client = OllamaClient(_make_explanation_config())
    result = client._parse_response("语法解析内容")

    assert result == (None, "语法解析内容")


def test_parse_response_explanation_strips_whitespace() -> None:
    client = OllamaClient(_make_explanation_config())
    result = client._parse_response("  语法解析内容  ")

    assert result == (None, "语法解析内容")


def test_parse_response_explanation_empty_string() -> None:
    client = OllamaClient(_make_explanation_config())
    result = client._parse_response("")

    assert result == (None, None)


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
