"""Tests for AsyncOllamaClient (httpx-based async client with LRU cache)."""

import json
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.config import AppConfig
from src.exceptions import LLMTimeoutError, LLMUnavailableError
from src.llm.ollama_client import AsyncOllamaClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(llm_mode: str = "translation") -> AppConfig:
    return AppConfig(llm_mode=llm_mode)  # type: ignore[arg-type]


def _make_streaming_response(response_text: str) -> list[bytes]:
    """Build list of NDJSON byte chunks as Ollama streams them."""
    chunks = []
    for char in response_text:
        chunk = json.dumps({"response": char, "done": False}) + "\n"
        chunks.append(chunk.encode())
    done_chunk = json.dumps({"response": "", "done": True}) + "\n"
    chunks.append(done_chunk.encode())
    return chunks


def _mock_httpx_stream(response_text: str) -> MagicMock:
    """Return an async context manager mock that yields NDJSON lines."""
    chunks = _make_streaming_response(response_text)

    async def _aiter_lines() -> AsyncGenerator[str, None]:
        for chunk in chunks:
            yield chunk.decode()

    mock_response = MagicMock()
    mock_response.aiter_lines = _aiter_lines
    mock_response.raise_for_status = MagicMock()

    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=mock_response)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


# ---------------------------------------------------------------------------
# translate_async() — translation mode
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# LRU cache — same (text, context) input must not trigger duplicate HTTP calls
# ---------------------------------------------------------------------------


async def test_translate_async_lru_cache_prevents_duplicate_http_calls() -> None:
    client = AsyncOllamaClient(_make_config("translation"))
    # Clear cache between tests
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
    assert call_count == 1  # second call must hit cache


async def test_translate_async_cache_keyed_by_text_and_context() -> None:
    """Different context strings must produce separate HTTP calls."""
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


# ---------------------------------------------------------------------------
# sync translate() wrapper — backward compat
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# async context manager lifecycle
# ---------------------------------------------------------------------------


async def test_async_context_manager_closes_client() -> None:
    """__aexit__ must close the underlying httpx client."""
    config = _make_config()
    async with AsyncOllamaClient(config) as client:
        assert not client._http.is_closed
    assert client._http.is_closed


# ---------------------------------------------------------------------------
# _build_prompt() — prompt template rendering
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# health_check()
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# num_predict / timeout spec compliance
# ---------------------------------------------------------------------------


async def test_payload_uses_reduced_num_predict() -> None:
    """Payload must use num_predict=200 (down from 512)."""
    client = AsyncOllamaClient(_make_config("translation"))
    client.translate_cached.cache_clear()
    captured_payload: dict[str, object] = {}

    stream_cm = _mock_httpx_stream("ok")

    def capture_stream(method: str, url: str, json: dict[str, object], **kwargs: object) -> object:  # noqa: A002
        nonlocal captured_payload
        captured_payload = json
        return stream_cm

    with patch.object(client._http, "stream", side_effect=capture_stream):
        await client.translate_async("テスト", "")

    options = captured_payload.get("options", {})
    assert isinstance(options, dict)
    assert options.get("num_predict") == 200


async def test_request_timeout_is_15_seconds() -> None:
    """Timeout kwarg passed to httpx.stream must be 15.0."""
    client = AsyncOllamaClient(_make_config("translation"))
    client.translate_cached.cache_clear()
    captured_kwargs: dict[str, object] = {}

    stream_cm = _mock_httpx_stream("ok")

    def capture_stream(method: str, url: str, **kwargs: object) -> object:
        nonlocal captured_kwargs
        captured_kwargs = dict(kwargs)
        return stream_cm

    with patch.object(client._http, "stream", side_effect=capture_stream):
        await client.translate_async("テスト", "")

    assert captured_kwargs.get("timeout") == 15.0
