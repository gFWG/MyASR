"""OpenAI-compatible LLM client — async httpx with LRU cache.

Works with Ollama, LM Studio, and any OpenAI-compatible provider
via /v1/chat/completions.
"""

import asyncio
import json
import logging
import re
from functools import lru_cache

import httpx

from src.config import AppConfig
from src.exceptions import LLMTimeoutError, LLMUnavailableError

logger = logging.getLogger(__name__)

_LRU_MAXSIZE = 256
_HEALTH_TIMEOUT = 5.0


class AsyncOllamaClient:
    """Async LLM client using OpenAI-compatible /v1/chat/completions.

    Supports async context manager protocol for lifecycle management.
    An LRU cache (maxsize=256) prevents duplicate HTTP calls for identical inputs.

    Args:
        config: Application configuration containing LLM connection details.
    """

    def __init__(self, config: AppConfig) -> None:
        self._url = config.ollama_url.rstrip("/")
        self._model = config.ollama_model
        self._mode = config.llm_mode
        self._translation_template = config.translation_template
        self._explanation_template = config.explanation_template
        self._timeout = config.ollama_timeout_sec
        self._api_key = config.ollama_api_key
        self._temperature = config.llm_temperature
        self._top_p = config.llm_top_p
        self._max_tokens = config.llm_max_tokens
        self._streaming = config.llm_streaming
        self._thinking = config.llm_thinking
        self._prefill = config.llm_prefill
        self._extra_args = config.llm_extra_args
        self._parse_format = config.llm_parse_format
        self._http = httpx.AsyncClient()
        self._result_cache: dict[tuple[str, str], tuple[str | None, str | None]] = {}

        client_ref = self

        @lru_cache(maxsize=_LRU_MAXSIZE)
        def _cached_sentinel(text: str, context: str) -> bool:
            return True

        original_cache_clear = _cached_sentinel.cache_clear

        def _combined_cache_clear() -> None:
            original_cache_clear()
            client_ref._result_cache.clear()

        _cached_sentinel.cache_clear = _combined_cache_clear  # type: ignore[method-assign]
        self.translate_cached = _cached_sentinel

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    async def __aenter__(self) -> "AsyncOllamaClient":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        await self._http.aclose()

    async def translate_async(self, text: str, context: str) -> tuple[str | None, str | None]:
        """Translate or explain Japanese text, with LRU caching on (text, context).

        Args:
            text: Japanese sentence to process.
            context: Optional context string used as part of the cache key.

        Returns:
            (translation, None) in translation mode.
            (None, explanation) in explanation mode.

        Raises:
            LLMTimeoutError: If the request times out.
            LLMUnavailableError: If the service is unreachable.
        """
        key = (text, context)
        if key in self._result_cache:
            return self._result_cache[key]

        result = await self._fetch(text, context)
        self._result_cache[key] = result
        self.translate_cached(text, context)
        return result

    def translate(self, japanese_text: str) -> tuple[str | None, str | None]:
        """Synchronous wrapper around translate_async for backward compatibility.

        Args:
            japanese_text: The Japanese sentence to process.

        Returns:
            (translation, None) in translation mode.
            (None, explanation) in explanation mode.

        Raises:
            LLMTimeoutError: If the request times out.
            LLMUnavailableError: If the service is unreachable.
        """
        return asyncio.run(self.translate_async(japanese_text, ""))

    def _build_messages(self, japanese_text: str) -> list[dict[str, str]]:
        prompt = self._build_prompt(japanese_text)
        messages: list[dict[str, str]] = [
            {"role": "user", "content": prompt},
        ]
        if self._prefill:
            messages.append({"role": "assistant", "content": self._prefill})
        return messages

    def _build_payload(self, messages: list[dict[str, str]]) -> dict[str, object]:
        payload: dict[str, object] = {
            "model": self._model,
            "messages": messages,
            "stream": self._streaming,
            "temperature": self._temperature,
            "top_p": self._top_p,
            "max_tokens": self._max_tokens,
        }
        if self._thinking:
            payload["reasoning"] = {"effort": "low"}
        if self._extra_args:
            try:
                extra = json.loads(self._extra_args)
                if isinstance(extra, dict):
                    payload.update(extra)
            except json.JSONDecodeError:
                logger.warning("Invalid llm_extra_args JSON, ignoring: %s", self._extra_args)
        return payload

    async def _fetch(self, text: str, context: str) -> tuple[str | None, str | None]:
        messages = self._build_messages(text)
        payload = self._build_payload(messages)
        url = f"{self._url}/v1/chat/completions"

        try:
            if self._streaming:
                full_text = await self._fetch_streaming(url, payload)
            else:
                full_text = await self._fetch_non_streaming(url, payload)
        except httpx.TimeoutException as exc:
            logger.warning("LLM timeout after %ss: %s", self._timeout, exc)
            raise LLMTimeoutError(f"LLM request timed out after {self._timeout}s") from exc
        except httpx.ConnectError as exc:
            logger.warning("LLM unavailable: %s", exc)
            raise LLMUnavailableError(f"Cannot connect to LLM: {exc}") from exc

        return self._parse_response(full_text)

    async def _fetch_streaming(self, url: str, payload: dict[str, object]) -> str:
        collected: list[str] = []
        async with self._http.stream(
            "POST",
            url,
            json=payload,
            headers=self._headers(),
            timeout=self._timeout,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line:
                    continue
                if not line.startswith("data: "):
                    continue
                data_str = line[6:]
                if data_str.strip() == "[DONE]":
                    break
                try:
                    data: dict[str, object] = json.loads(data_str)
                except json.JSONDecodeError:
                    logger.warning("Unexpected non-JSON SSE data: %s", data_str)
                    continue
                choices = data.get("choices", [])
                if not isinstance(choices, list) or not choices:
                    continue
                delta = choices[0].get("delta", {})  # type: ignore[union-attr]
                if isinstance(delta, dict):
                    content = delta.get("content", "")
                    if isinstance(content, str):
                        collected.append(content)
        return "".join(collected)

    async def _fetch_non_streaming(self, url: str, payload: dict[str, object]) -> str:
        response = await self._http.post(
            url,
            json=payload,
            headers=self._headers(),
            timeout=self._timeout,
        )
        response.raise_for_status()
        data = response.json()
        choices = data.get("choices", [])
        if not choices:
            return ""
        message = choices[0].get("message", {})
        return str(message.get("content", ""))

    def _build_prompt(self, japanese_text: str) -> str:
        if self._mode == "translation":
            return self._translation_template.format(japanese_text=japanese_text)
        return self._explanation_template.format(japanese_text=japanese_text)

    def _parse_response(self, response_text: str) -> tuple[str | None, str | None]:
        stripped = response_text.strip()
        if not stripped:
            return (None, None)

        # Apply custom parse format regex if configured
        if self._parse_format:
            try:
                custom_re = re.compile(self._parse_format, re.DOTALL)
                match = custom_re.search(stripped)
                if match:
                    # Use first capture group if present, else full match
                    stripped = (match.group(1) if match.lastindex else match.group(0)).strip()
            except re.error:
                logger.warning(
                    "Invalid llm_parse_format regex, using full output: %s", self._parse_format
                )

        if self._mode == "translation":
            return (stripped or None, None)
        return (None, stripped or None)

    async def health_check_async(self) -> bool:
        """Check if the LLM provider is reachable.

        Returns:
            True if the /v1/models endpoint responds with HTTP 200.
        """
        try:
            response = await self._http.get(
                f"{self._url}/v1/models",
                headers=self._headers(),
                timeout=_HEALTH_TIMEOUT,
            )
            return bool(response.status_code == 200)
        except Exception:  # noqa: BLE001
            return False

    async def list_models_async(self) -> list[str]:
        """Fetch available model names from the provider.

        Returns:
            Sorted list of model ID strings, or empty list on failure.
        """
        try:
            response = await self._http.get(
                f"{self._url}/v1/models",
                headers=self._headers(),
                timeout=_HEALTH_TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()
            models = data.get("data", [])
            return sorted(m.get("id", "") for m in models if isinstance(m, dict) and m.get("id"))
        except Exception:  # noqa: BLE001
            logger.warning("Failed to fetch model list")
            return []


OllamaClient = AsyncOllamaClient
