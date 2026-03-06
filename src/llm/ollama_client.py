"""Ollama LLM client for Japanese-to-Chinese translation."""

import logging

import requests

from src.config import AppConfig
from src.exceptions import LLMError, LLMTimeoutError, LLMUnavailableError  # noqa: F401

logger = logging.getLogger(__name__)


class OllamaClient:
    """Client for translating Japanese text via Ollama LLM.

    Handles prompt construction, HTTP communication, and response parsing.
    All errors are caught internally; methods never raise on network failures.
    """

    def __init__(self, config: AppConfig) -> None:
        self._url = config.ollama_url
        self._model = config.ollama_model
        self._timeout = config.ollama_timeout_sec
        self._mode = config.llm_mode
        self._translation_template = config.translation_template
        self._explanation_template = config.explanation_template

    def translate(self, japanese_text: str) -> tuple[str | None, str | None]:
        """Translate or explain Japanese text based on configured LLM mode.

        Args:
            japanese_text: The Japanese sentence to process.

        Returns:
            A tuple of (translation, explanation). Both are None on failure.
            In "translation" mode, returns (translation, None).
            In "explanation" mode, returns (None, explanation).
        """
        prompt = self._build_prompt(japanese_text)
        payload = {
            "model": self._model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.3,
                "num_predict": 512,
            },
        }
        try:
            response = requests.post(
                f"{self._url}/api/generate",
                json=payload,
                timeout=self._timeout,
            )
            response.raise_for_status()
            text = response.json()["response"]
            return self._parse_response(text)
        except requests.exceptions.Timeout:
            logger.warning("Ollama timeout after %ss", self._timeout)
            return (None, None)
        except requests.exceptions.ConnectionError as exc:
            logger.warning("Ollama unavailable: %s", exc)
            return (None, None)
        except Exception as exc:  # noqa: BLE001
            logger.error("Ollama request failed: %s", exc)
            return (None, None)

    def _build_prompt(self, japanese_text: str) -> str:
        if self._mode == "translation":
            return self._translation_template.format(japanese_text=japanese_text)
        return self._explanation_template.format(japanese_text=japanese_text)

    def _parse_response(self, response_text: str) -> tuple[str | None, str | None]:
        if self._mode == "translation":
            return (response_text.strip(), None)

        # Explanation mode: return (None, explanation)
        stripped = response_text.strip()
        if not stripped:
            return (None, None)
        return (None, stripped)

    def health_check(self) -> bool:
        try:
            response = requests.get(f"{self._url}/api/tags", timeout=5)
            return bool(response.status_code == 200)
        except Exception:  # noqa: BLE001
            return False
