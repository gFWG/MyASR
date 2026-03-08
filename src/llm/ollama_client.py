"""Ollama LLM client — async httpx implementation with LRU cache."""

import asyncio
import json
import logging
from functools import lru_cache

import httpx

from src.config import AppConfig
from src.exceptions import LLMTimeoutError, LLMUnavailableError

logger = logging.getLogger(__name__)

_REQUEST_TIMEOUT = 15.0
_NUM_PREDICT = 200
_LRU_MAXSIZE = 256


class AsyncOllamaClient:
    """Async Ollama client for Japanese-to-Chinese translation via httpx streaming.

    Supports async context manager protocol for lifecycle management.
    An LRU cache (maxsize=256) prevents duplicate HTTP calls for identical inputs.

    Args:
        config: Application configuration containing Ollama connection details.
    """

    def __init__(self, config: AppConfig) -> None:
        self._url = config.ollama_url
        self._model = config.ollama_model
        self._mode = config.llm_mode
        self._translation_template = config.translation_template
        self._explanation_template = config.explanation_template
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
            LLMTimeoutError: If the Ollama request times out.
            LLMUnavailableError: If the Ollama service is unreachable.
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
            LLMTimeoutError: If the Ollama request times out.
            LLMUnavailableError: If the Ollama service is unreachable.
        """
        return asyncio.run(self.translate_async(japanese_text, ""))

    async def _fetch(self, text: str, context: str) -> tuple[str | None, str | None]:
        prompt = self._build_prompt(text)
        payload: dict[str, object] = {
            "model": self._model,
            "prompt": prompt,
            "stream": True,
            "options": {
                "temperature": 0.3,
                "num_predict": _NUM_PREDICT,
            },
        }
        collected: list[str] = []
        try:
            async with self._http.stream(
                "POST",
                f"{self._url}/api/generate",
                json=payload,
                timeout=_REQUEST_TIMEOUT,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    try:
                        data: dict[str, object] = json.loads(line)
                    except json.JSONDecodeError:
                        logger.warning("Unexpected non-JSON line from Ollama: %s", line)
                        continue
                    chunk = data.get("response", "")
                    if isinstance(chunk, str):
                        collected.append(chunk)
                    if data.get("done"):
                        break
        except httpx.TimeoutException as exc:
            logger.warning("Ollama timeout after %ss: %s", _REQUEST_TIMEOUT, exc)
            raise LLMTimeoutError(f"Ollama request timed out after {_REQUEST_TIMEOUT}s") from exc
        except httpx.ConnectError as exc:
            logger.warning("Ollama unavailable: %s", exc)
            raise LLMUnavailableError(f"Cannot connect to Ollama: {exc}") from exc

        full_text = "".join(collected)
        return self._parse_response(full_text)

    def _build_prompt(self, japanese_text: str) -> str:
        if self._mode == "translation":
            return self._translation_template.format(japanese_text=japanese_text)
        return self._explanation_template.format(japanese_text=japanese_text)

    def _parse_response(self, response_text: str) -> tuple[str | None, str | None]:
        if self._mode == "translation":
            stripped = response_text.strip()
            return (stripped, None)

        stripped = response_text.strip()
        if not stripped:
            return (None, None)
        return (None, stripped)

    async def health_check_async(self) -> bool:
        """Check if Ollama is reachable.

        Returns:
            True if the /api/tags endpoint responds with HTTP 200.
        """
        try:
            response = await self._http.get(f"{self._url}/api/tags", timeout=5.0)
            return bool(response.status_code == 200)
        except Exception:  # noqa: BLE001
            return False


OllamaClient = AsyncOllamaClient
