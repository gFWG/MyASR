"""Tests for src.config module."""

import json
from pathlib import Path

from src.config import AppConfig, load_config, save_config


def test_appconfig_defaults() -> None:
    """AppConfig fields match documented defaults."""
    c = AppConfig()
    assert c.user_jlpt_level == 3
    assert c.complexity_vocab_threshold == 2
    assert c.complexity_n1_grammar_threshold == 1
    assert c.complexity_readability_threshold == 3.0
    assert c.complexity_ambiguous_grammar_threshold == 1
    assert c.ollama_url == "http://localhost:11434"
    assert c.ollama_model == "qwen3.5:4b"
    assert c.ollama_timeout_sec == 30.0
    assert c.sample_rate == 16000
    assert c.db_path == "data/myasr.db"


def test_load_config_missing_file(tmp_path: Path) -> None:
    """load_config returns defaults when the file does not exist."""
    nonexistent = str(tmp_path / "no_such_config.json")
    c = load_config(nonexistent)
    assert c.user_jlpt_level == 3
    assert c.ollama_model == "qwen3.5:4b"


def test_load_config_malformed_json(tmp_path: Path) -> None:
    """load_config returns defaults when the JSON is malformed."""
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("{ this is not valid json }", encoding="utf-8")
    c = load_config(str(bad_file))
    assert c.user_jlpt_level == 3


def test_save_and_load_roundtrip(tmp_path: Path) -> None:
    """save_config then load_config recovers the same values."""
    path = str(tmp_path / "config.json")
    original = AppConfig(user_jlpt_level=1, ollama_model="test-model")
    save_config(original, path)
    loaded = load_config(path)
    assert loaded.user_jlpt_level == 1
    assert loaded.ollama_model == "test-model"
    assert loaded.sample_rate == 16000  # default preserved


def test_load_config_partial_json(tmp_path: Path) -> None:
    """load_config merges partial JSON with defaults."""
    partial_file = tmp_path / "partial.json"
    partial_file.write_text(json.dumps({"user_jlpt_level": 2}), encoding="utf-8")
    c = load_config(str(partial_file))
    assert c.user_jlpt_level == 2
    assert c.ollama_model == "qwen3.5:4b"  # default preserved
    assert c.sample_rate == 16000  # default preserved


def test_save_config_creates_parent_dirs(tmp_path: Path) -> None:
    """save_config creates parent directories if they don't exist."""
    nested_path = str(tmp_path / "nested" / "dir" / "config.json")
    save_config(AppConfig(), nested_path)
    loaded = load_config(nested_path)
    assert loaded.user_jlpt_level == 3
