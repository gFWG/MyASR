"""Application configuration for MyASR."""

import dataclasses
import json
import logging
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)

DEFAULT_TRANSLATION_TEMPLATE = (
    "你是一名日语翻译专家。请将以下<src></src>之间的文本翻译为中文。"
    "注意只需要输出翻译后的结果，不要额外解释。输出格式为：<tr>...</tr>\n\n"
    "<src>{japanese_text}</src>"
)

DEFAULT_EXPLANATION_TEMPLATE = (
    "あなたは日本語教師です。次の日本語文について、中国語学習者向けに"
    "文法・語彙の解析を中国語で提供してください。翻訳は不要です。\n\n"
    "日本語：{japanese_text}\n\n"
    "解析のみ出力してください（翻訳は含めないこと）："
)


@dataclasses.dataclass
class AppConfig:
    """Application configuration with sensible defaults."""

    user_jlpt_level: int = 3
    llm_mode: Literal["translation", "explanation"] = "translation"
    translation_template: str = DEFAULT_TRANSLATION_TEMPLATE
    explanation_template: str = DEFAULT_EXPLANATION_TEMPLATE
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3.5:4b"
    ollama_timeout_sec: float = 30.0
    sample_rate: int = 16000
    db_path: str = "data/myasr.db"


def load_config(path: str = "data/config.json") -> AppConfig:
    """Load configuration from a JSON file, falling back to defaults.

    Args:
        path: Path to the JSON config file.

    Returns:
        AppConfig populated from file, merged with defaults.
        Returns defaults if file doesn't exist or JSON is malformed.
    """
    config_path = Path(path)
    if not config_path.exists():
        return AppConfig()
    try:
        with config_path.open(encoding="utf-8") as f:
            loaded: dict[str, object] = json.load(f)
    except (json.JSONDecodeError, OSError):
        logger.warning("Failed to parse config file %s, using defaults", path)
        return AppConfig()
    defaults = dataclasses.asdict(AppConfig())
    defaults.update(loaded)
    return AppConfig(**defaults)


def save_config(config: AppConfig, path: str = "data/config.json") -> None:
    """Save configuration to a JSON file.

    Args:
        config: AppConfig instance to save.
        path: Path to write the JSON config file.
    """
    config_path = Path(path)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with config_path.open("w", encoding="utf-8") as f:
        json.dump(dataclasses.asdict(config), f, indent=2, ensure_ascii=False)
