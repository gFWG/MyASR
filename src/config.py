"""Application configuration for MyASR."""

import dataclasses
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class AppConfig:
    """Application configuration with sensible defaults."""

    user_jlpt_level: int = 3
    complexity_vocab_threshold: int = 2
    complexity_n1_grammar_threshold: int = 1
    complexity_readability_threshold: float = 3.0
    complexity_ambiguous_grammar_threshold: int = 1
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3-4b-2507"
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
