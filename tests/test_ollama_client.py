"""Tests for AsyncOllamaClient (OpenAI-compatible /v1/chat/completions)."""

import json
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.config import AppConfig
from src.exceptions import LLMTimeoutError, LLMUnavailableError
from src.llm.ollama_client import AsyncOllamaClient


def _make_config(
    llm_mode: str = "translation",
    **kwargs: object,
) -> AppConfig:
    return AppConfig(llm_mode=llm_mode, **kwargs)  # type: ignore[arg-type]


def _make_sse_lines(text: str) -> list[str]:
    lines: list[str] = []
    for char in text:
        chunk = {
            "id": "chatcmpl-1",
            "object": "chat.completion.chunk",
            "choices": [{"index": 0, "delta": {"content": char}, "finish_reason": None}],
        }
        lines.append(f"data: {json.dumps(chunk)}")
    lines.append("data: [DONE]")
    return lines


def _mock_httpx_stream(text: str) -> MagicMock:
    sse_lines = _make_sse_lines(text)

    async def _aiter_lines() -> AsyncGenerator[str, None]:
        for line in sse_lines:
            yield line

    mock_response = MagicMock()
    mock_response.aiter_lines = _aiter_lines
    mock_response.raise_for_status = MagicMock()

    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=mock_response)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


def _mock_non_streaming_response(text: str) -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "id": "chatcmpl-1",
        "object": "chat.completion",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": text}}],
    }
    return mock_resp


async def test_translate_async_translation_mode_returns_translation() -> None:
    client = AsyncOllamaClient(_make_config("translation"))
    stream_cm = _mock_httpx_stream("翻訳結果テキスト")

    with patch.object(client._http, "stream", return_value=stream_cm):
        result = await client.translate_async("テストです", "")

    assert result == ("翻訳結果テキスト", None)


async def test_translate_async_explanation_mode_returns_explanation() -> None:
    client = AsyncOllamaClient(_make_config("explanation"))
    stream_cm = _mock_httpx_stream("语法解析内容")

    with patch.object(client._http, "stream", return_value=stream_cm):
        result = await client.translate_async("テストです", "")

    assert result == (None, "语法解析内容")


async def test_translate_async_strips_whitespace() -> None:
    client = AsyncOllamaClient(_make_config("translation"))
    stream_cm = _mock_httpx_stream("  翻訳  ")

    with patch.object(client._http, "stream", return_value=stream_cm):
        result = await client.translate_async("テスト", "")

    assert result == ("翻訳", None)


async def test_translate_async_extracts_tr_tags() -> None:
    client = AsyncOllamaClient(_make_config("translation"))
    stream_cm = _mock_httpx_stream("Some preamble\n<tr>实际翻译</tr>\nExtra")

    with patch.object(client._http, "stream", return_value=stream_cm):
        result = await client.translate_async("テスト", "")

    assert result == ("实际翻译", None)


async def test_translate_async_no_tr_tags_uses_raw_text() -> None:
    client = AsyncOllamaClient(_make_config("translation"))
    stream_cm = _mock_httpx_stream("直接翻译")

    with patch.object(client._http, "stream", return_value=stream_cm):
        result = await client.translate_async("テスト", "")

    assert result == ("直接翻译", None)


async def test_translate_async_empty_response_returns_none() -> None:
    client = AsyncOllamaClient(_make_config("translation"))
    stream_cm = _mock_httpx_stream("   ")

    with patch.object(client._http, "stream", return_value=stream_cm):
        result = await client.translate_async("テスト", "")

    assert result == (None, None)


async def test_translate_async_raises_llm_timeout_error() -> None:
    client = AsyncOllamaClient(_make_config())

    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
    cm.__aexit__ = AsyncMock(return_value=False)

    with patch.object(client._http, "stream", return_value=cm):
        with pytest.raises(LLMTimeoutError):
            await client.translate_async("テスト", "")


async def test_translate_async_raises_llm_unavailable_error() -> None:
    client = AsyncOllamaClient(_make_config())

    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(side_effect=httpx.ConnectError("refused"))
    cm.__aexit__ = AsyncMock(return_value=False)

    with patch.object(client._http, "stream", return_value=cm):
        with pytest.raises(LLMUnavailableError):
            await client.translate_async("テスト", "")


async def test_translate_async_lru_cache_prevents_duplicate_http_calls() -> None:
    client = AsyncOllamaClient(_make_config("translation"))
    client.translate_cached.cache_clear()

    stream_cm = _mock_httpx_stream("キャッシュ結果")
    call_count = 0

    def counting_stream(*args: object, **kwargs: object) -> object:
        nonlocal call_count
        call_count += 1
        return stream_cm

    with patch.object(client._http, "stream", side_effect=counting_stream):
        result1 = await client.translate_async("同じテキスト", "")
        result2 = await client.translate_async("同じテキスト", "")

    assert result1 == result2
    assert call_count == 1


async def test_translate_async_cache_keyed_by_text_and_context() -> None:
    client = AsyncOllamaClient(_make_config("translation"))
    client.translate_cached.cache_clear()

    call_count = 0

    def counting_stream(*args: object, **kwargs: object) -> object:
        nonlocal call_count
        call_count += 1
        return _mock_httpx_stream(f"result{call_count}")

    with patch.object(client._http, "stream", side_effect=counting_stream):
        await client.translate_async("テキスト", "context_a")
        await client.translate_async("テキスト", "context_b")

    assert call_count == 2


def test_translate_sync_wrapper_returns_tuple() -> None:
    client = AsyncOllamaClient(_make_config("translation"))
    client.translate_cached.cache_clear()
    stream_cm = _mock_httpx_stream("同期翻訳")

    with patch.object(client._http, "stream", return_value=stream_cm):
        result = client.translate("テスト")

    assert result == ("同期翻訳", None)


def test_translate_sync_wrapper_raises_on_timeout() -> None:
    client = AsyncOllamaClient(_make_config())
    client.translate_cached.cache_clear()

    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
    cm.__aexit__ = AsyncMock(return_value=False)

    with patch.object(client._http, "stream", return_value=cm):
        with pytest.raises(LLMTimeoutError):
            client.translate("テスト")


def test_translate_sync_wrapper_raises_on_connection_error() -> None:
    client = AsyncOllamaClient(_make_config())
    client.translate_cached.cache_clear()

    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(side_effect=httpx.ConnectError("refused"))
    cm.__aexit__ = AsyncMock(return_value=False)

    with patch.object(client._http, "stream", return_value=cm):
        with pytest.raises(LLMUnavailableError):
            client.translate("テスト")


async def test_async_context_manager_closes_client() -> None:
    config = _make_config()
    async with AsyncOllamaClient(config) as client:
        assert not client._http.is_closed
    assert client._http.is_closed


def test_build_prompt_translation_mode_contains_text() -> None:
    client = AsyncOllamaClient(_make_config("translation"))
    prompt = client._build_prompt("テストです")

    assert "テストです" in prompt
    assert "翻译" in prompt or "翻訳" in prompt


def test_build_prompt_explanation_mode_contains_text() -> None:
    client = AsyncOllamaClient(_make_config("explanation"))
    prompt = client._build_prompt("テストです")

    assert "テストです" in prompt
    assert "解析" in prompt or "解説" in prompt or "説明" in prompt


def test_build_prompt_custom_template() -> None:
    config = AppConfig(
        llm_mode="translation",
        translation_template="Translate: {japanese_text}",
    )
    client = AsyncOllamaClient(config)
    assert client._build_prompt("テスト") == "Translate: テスト"


async def test_health_check_true_when_reachable() -> None:
    client = AsyncOllamaClient(_make_config())
    mock_response = MagicMock()
    mock_response.status_code = 200

    async def fake_get(url: str, **kwargs: object) -> MagicMock:
        return mock_response

    with patch.object(client._http, "get", side_effect=fake_get):
        result = await client.health_check_async()

    assert result is True


async def test_health_check_false_when_unreachable() -> None:
    client = AsyncOllamaClient(_make_config())

    async def fake_get(url: str, **kwargs: object) -> None:
        raise httpx.ConnectError("refused")

    with patch.object(client._http, "get", side_effect=fake_get):
        result = await client.health_check_async()

    assert result is False


async def test_payload_uses_openai_chat_completions_format() -> None:
    client = AsyncOllamaClient(_make_config("translation"))
    client.translate_cached.cache_clear()
    captured_payload: dict[str, object] = {}

    stream_cm = _mock_httpx_stream("ok")

    def capture_stream(method: str, url: str, json: dict[str, object], **kwargs: object) -> object:
        nonlocal captured_payload
        captured_payload = json
        return stream_cm

    with patch.object(client._http, "stream", side_effect=capture_stream):
        await client.translate_async("テスト", "")

    assert "messages" in captured_payload
    assert "model" in captured_payload
    assert captured_payload.get("max_tokens") == 200
    assert captured_payload.get("temperature") == 0.3
    assert captured_payload.get("top_p") == 0.9
    assert captured_payload.get("stream") is True


async def test_request_timeout_uses_config_value() -> None:
    client = AsyncOllamaClient(_make_config("translation", ollama_timeout_sec=45.0))
    client.translate_cached.cache_clear()
    captured_kwargs: dict[str, object] = {}

    stream_cm = _mock_httpx_stream("ok")

    def capture_stream(method: str, url: str, **kwargs: object) -> object:
        nonlocal captured_kwargs
        captured_kwargs = dict(kwargs)
        return stream_cm

    with patch.object(client._http, "stream", side_effect=capture_stream):
        await client.translate_async("テスト", "")

    assert captured_kwargs.get("timeout") == 45.0


async def test_api_key_sent_in_authorization_header() -> None:
    client = AsyncOllamaClient(_make_config("translation", ollama_api_key="sk-test-key"))
    client.translate_cached.cache_clear()
    captured_kwargs: dict[str, object] = {}

    stream_cm = _mock_httpx_stream("ok")

    def capture_stream(method: str, url: str, **kwargs: object) -> object:
        nonlocal captured_kwargs
        captured_kwargs = dict(kwargs)
        return stream_cm

    with patch.object(client._http, "stream", side_effect=capture_stream):
        await client.translate_async("テスト", "")

    headers = captured_kwargs.get("headers", {})
    assert isinstance(headers, dict)
    assert headers.get("Authorization") == "Bearer sk-test-key"


async def test_no_api_key_omits_authorization_header() -> None:
    client = AsyncOllamaClient(_make_config("translation", ollama_api_key=""))
    headers = client._headers()
    assert "Authorization" not in headers


async def test_thinking_enabled_adds_reasoning_payload() -> None:
    client = AsyncOllamaClient(_make_config("translation", llm_thinking=True))
    client.translate_cached.cache_clear()
    captured_payload: dict[str, object] = {}

    stream_cm = _mock_httpx_stream("ok")

    def capture_stream(method: str, url: str, json: dict[str, object], **kwargs: object) -> object:
        nonlocal captured_payload
        captured_payload = json
        return stream_cm

    with patch.object(client._http, "stream", side_effect=capture_stream):
        await client.translate_async("テスト", "")

    assert captured_payload.get("reasoning") == {"effort": "low"}


async def test_prefill_adds_assistant_message() -> None:
    client = AsyncOllamaClient(_make_config("translation", llm_prefill="<tr>"))
    messages = client._build_messages("テスト")
    assert len(messages) == 2
    assert messages[1]["role"] == "assistant"
    assert messages[1]["content"] == "<tr>"


async def test_no_prefill_single_user_message() -> None:
    client = AsyncOllamaClient(_make_config("translation", llm_prefill=""))
    messages = client._build_messages("テスト")
    assert len(messages) == 1
    assert messages[0]["role"] == "user"


async def test_extra_args_merged_into_payload() -> None:
    client = AsyncOllamaClient(
        _make_config("translation", llm_extra_args='{"seed": 42, "stop": ["\\n"]}')
    )
    client.translate_cached.cache_clear()
    captured_payload: dict[str, object] = {}

    stream_cm = _mock_httpx_stream("ok")

    def capture_stream(method: str, url: str, json: dict[str, object], **kwargs: object) -> object:
        nonlocal captured_payload
        captured_payload = json
        return stream_cm

    with patch.object(client._http, "stream", side_effect=capture_stream):
        await client.translate_async("テスト", "")

    assert captured_payload.get("seed") == 42
    assert captured_payload.get("stop") == ["\n"]


async def test_invalid_extra_args_ignored() -> None:
    client = AsyncOllamaClient(_make_config("translation", llm_extra_args="not valid json"))
    client.translate_cached.cache_clear()
    stream_cm = _mock_httpx_stream("ok")

    with patch.object(client._http, "stream", return_value=stream_cm):
        result = await client.translate_async("テスト", "")

    assert result == ("ok", None)


async def test_non_streaming_mode() -> None:
    client = AsyncOllamaClient(_make_config("translation", llm_streaming=False))
    client.translate_cached.cache_clear()
    mock_resp = _mock_non_streaming_response("非ストリーミング翻訳")

    async def fake_post(url: str, **kwargs: object) -> MagicMock:
        return mock_resp

    with patch.object(client._http, "post", side_effect=fake_post):
        result = await client.translate_async("テスト", "")

    assert result == ("非ストリーミング翻訳", None)


async def test_list_models_returns_sorted_list() -> None:
    client = AsyncOllamaClient(_make_config())
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "object": "list",
        "data": [
            {"id": "qwen3.5:4b", "object": "model"},
            {"id": "llama3:8b", "object": "model"},
            {"id": "gemma2:2b", "object": "model"},
        ],
    }

    async def fake_get(url: str, **kwargs: object) -> MagicMock:
        return mock_resp

    with patch.object(client._http, "get", side_effect=fake_get):
        models = await client.list_models_async()

    assert models == ["gemma2:2b", "llama3:8b", "qwen3.5:4b"]


async def test_list_models_returns_empty_on_error() -> None:
    client = AsyncOllamaClient(_make_config())

    async def fake_get(url: str, **kwargs: object) -> None:
        raise httpx.ConnectError("refused")

    with patch.object(client._http, "get", side_effect=fake_get):
        models = await client.list_models_async()

    assert models == []


async def test_url_trailing_slash_stripped() -> None:
    client = AsyncOllamaClient(_make_config(ollama_url="http://localhost:11434/"))
    assert client._url == "http://localhost:11434"
