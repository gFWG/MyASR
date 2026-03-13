"""Application configuration for MyASR."""

import dataclasses
import json
import logging
from pathlib import Path
from typing import Any

from src.profiling.config import ProfilingConfig

logger = logging.getLogger(__name__)

DEFAULT_JLPT_COLORS: dict[str, str] = {
    "n5_vocab": "#E8F5E9",
    "n5_grammar": "#81C784",
    "n4_vocab": "#C8E6C9",
    "n4_grammar": "#4CAF50",
    "n3_vocab": "#BBDEFB",
    "n3_grammar": "#1976D2",
    "n2_vocab": "#FFF9C4",
    "n2_grammar": "#F9A825",
    "n1_vocab": "#FFCDD2",
    "n1_grammar": "#D32F2F",
}


@dataclasses.dataclass
class AppConfig:
    """Application configuration with sensible defaults."""

    user_jlpt_level: int = 3
    sample_rate: int = 16000
    vad_threshold: float = 0.5
    vad_min_silence_ms: int = 300
    vad_min_speech_ms: int = 400
    overlay_opacity: float = 0.78
    overlay_width: int = 800
    overlay_height: int = 120
    overlay_font_size_jp: int = 16
    enable_vocab_highlight: bool = True
    enable_grammar_highlight: bool = True
    max_history: int = 10
    jlpt_colors: dict[str, str] = dataclasses.field(
        default_factory=lambda: dict(DEFAULT_JLPT_COLORS)
    )
    profiling: ProfilingConfig = dataclasses.field(default_factory=ProfilingConfig)


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
            loaded: dict[str, Any] = json.load(f)
    except (json.JSONDecodeError, OSError):
        logger.warning("Failed to parse config file %s, using defaults", path)
        return AppConfig()
    defaults: dict[str, Any] = dataclasses.asdict(AppConfig())
    defaults = _deep_update(defaults, loaded)
    known = {f.name for f in dataclasses.fields(AppConfig)}
    filtered: dict[str, Any] = {k: v for k, v in defaults.items() if k in known}
    # Handle nested ProfilingConfig
    if "profiling" in filtered and isinstance(filtered["profiling"], dict):
        filtered["profiling"] = ProfilingConfig(**filtered["profiling"])
    return AppConfig(**filtered)


def _deep_update(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively update a dictionary, preserving nested structures.

    Args:
        base: Base dictionary to update.
        override: Dictionary with override values.

    Returns:
        Updated dictionary with nested merging.
    """
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_update(result[key], value)
        else:
            result[key] = value
    return result


def jlpt_colors_to_renderer_format(flat: dict[str, str]) -> dict[int, dict[str, str]]:
    """Convert flat JLPT color config to HighlightRenderer format.

    Args:
        flat: Keys like "n4_vocab", "n3_grammar", etc. with hex color values.

    Returns:
        Nested dict keyed by level (1–4) with "vocab"/"grammar" sub-keys.
    """
    result: dict[int, dict[str, str]] = {}
    for key, color in flat.items():
        parts = key.split("_", 1)
        if len(parts) != 2:
            continue
        level_str, kind = parts
        if not level_str.startswith("n") or kind not in ("vocab", "grammar"):
            continue
        try:
            level = int(level_str[1:])
        except ValueError:
            continue
        if level not in result:
            result[level] = {}
        result[level][kind] = color
    return result


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
