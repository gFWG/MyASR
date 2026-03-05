"""Ollama LLM client for Japanese-to-Chinese translation."""

import logging

import requests

from src.config import AppConfig
from src.db.models import AnalysisResult, GrammarHit, VocabHit
from src.exceptions import LLMError, LLMTimeoutError, LLMUnavailableError  # noqa: F401

logger = logging.getLogger(__name__)

_SIMPLE_TEMPLATE = (
    "あなたは日本語の翻訳者です。次の日本語を中国語に翻訳してください。"
    "翻訳のみを出力し、他の内容は出力しないでください。\n\n"
    "日本語：{japanese_text}"
)

_COMPLEX_TEMPLATE = (
    "あなたは日本語教師です。次の日本語を中国語に翻訳し、学習者向けの考点解析を提供してください。\n\n"
    "日本語：{japanese_text}\n\n"
    "前処理結果：\n"
    "- 超纲词汇：{vocab_hits_formatted}\n"
    "- 命中语法：{grammar_hits_formatted}\n\n"
    "以下の形式で回答してください：\n"
    "翻訳：<中国語翻訳>\n"
    "解析：<考点解析（超纲词汇・語法の説明を含む）>"
)


class OllamaClient:
    """Client for translating Japanese text via Ollama LLM.

    Handles prompt construction, HTTP communication, and response parsing.
    All errors are caught internally; methods never raise on network failures.
    """

    def __init__(self, config: AppConfig) -> None:
        self._url = config.ollama_url
        self._model = config.ollama_model
        self._timeout = config.ollama_timeout_sec

    def translate(
        self,
        japanese_text: str,
        analysis: AnalysisResult,
    ) -> tuple[str | None, str | None]:
        """Translate Japanese text to Chinese, with optional study-point analysis.

        Args:
            japanese_text: The Japanese sentence to translate.
            analysis: Preprocessing result containing vocab/grammar hits and complexity flag.

        Returns:
            A tuple of (translation, explanation). Both are None on failure.
            explanation is None for simple sentences or when parsing finds no analysis section.
        """
        prompt = self._build_prompt(japanese_text, analysis)
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
            return self._parse_response(text, analysis.is_complex)
        except requests.exceptions.Timeout:
            logger.warning("Ollama timeout after %ss", self._timeout)
            return (None, None)
        except requests.exceptions.ConnectionError as exc:
            logger.warning("Ollama unavailable: %s", exc)
            return (None, None)
        except Exception as exc:  # noqa: BLE001
            logger.error("Ollama request failed: %s", exc)
            return (None, None)

    def _build_prompt(self, japanese_text: str, analysis: AnalysisResult) -> str:
        if not analysis.is_complex:
            return _SIMPLE_TEMPLATE.format(japanese_text=japanese_text)

        vocab_hits_formatted = _format_vocab_hits(analysis.vocab_hits)
        grammar_hits_formatted = _format_grammar_hits(analysis.grammar_hits)
        return _COMPLEX_TEMPLATE.format(
            japanese_text=japanese_text,
            vocab_hits_formatted=vocab_hits_formatted,
            grammar_hits_formatted=grammar_hits_formatted,
        )

    def _parse_response(
        self,
        response_text: str,
        is_complex: bool,
    ) -> tuple[str, str | None]:
        if not is_complex:
            return (response_text.strip(), None)

        if not response_text.strip():
            return ("", None)

        translation_marker = "翻訳："
        explanation_marker = "解析："

        trans_idx = response_text.find(translation_marker)
        expl_idx = response_text.find(explanation_marker)

        if trans_idx != -1 and expl_idx != -1:
            translation = response_text[trans_idx + len(translation_marker) : expl_idx].strip()
            explanation = response_text[expl_idx + len(explanation_marker) :].strip()
            return (translation, explanation)

        if trans_idx != -1:
            translation = response_text[trans_idx + len(translation_marker) :].strip()
            return (translation, None)

        return (response_text.strip(), None)

    def health_check(self) -> bool:
        """Check whether the Ollama service is reachable.

        Returns:
            True if the service responds with HTTP 200, False otherwise.
        """
        try:
            response = requests.get(f"{self._url}/api/tags", timeout=5)
            return response.status_code == 200
        except Exception:  # noqa: BLE001
            return False


def _format_vocab_hits(vocab_hits: list[VocabHit]) -> str:
    if not vocab_hits:
        return "なし"
    return "、".join(f"{vh.surface}({vh.lemma}, N{vh.jlpt_level})" for vh in vocab_hits)


def _format_grammar_hits(grammar_hits: list[GrammarHit]) -> str:
    if not grammar_hits:
        return "なし"
    return "、".join(
        f"{gh.matched_text}(N{gh.jlpt_level}, {gh.description})" for gh in grammar_hits
    )
