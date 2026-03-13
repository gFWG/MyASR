"""Tests for src.config module."""

import json
from pathlib import Path

from src.config import (
    AppConfig,
    load_config,
    save_config,
)


def test_appconfig_defaults() -> None:
    c = AppConfig()
    assert c.user_jlpt_level == 3
    assert c.sample_rate == 16000
    assert c.vad_threshold == 0.5
    assert c.vad_min_silence_ms == 300
    assert c.vad_min_speech_ms == 400


def test_load_config_missing_file(tmp_path: Path) -> None:
    nonexistent = str(tmp_path / "no_such_config.json")
    c = load_config(nonexistent)
    assert c.user_jlpt_level == 3


def test_load_config_malformed_json(tmp_path: Path) -> None:
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("{ this is not valid json }", encoding="utf-8")
    c = load_config(str(bad_file))
    assert c.user_jlpt_level == 3


def test_save_and_load_roundtrip(tmp_path: Path) -> None:
    path = str(tmp_path / "config.json")
    original = AppConfig(user_jlpt_level=1)
    save_config(original, path)
    loaded = load_config(path)
    assert loaded.user_jlpt_level == 1
    assert loaded.sample_rate == 16000


def test_load_config_partial_json(tmp_path: Path) -> None:
    partial_file = tmp_path / "partial.json"
    partial_file.write_text(json.dumps({"user_jlpt_level": 2}), encoding="utf-8")
    c = load_config(str(partial_file))
    assert c.user_jlpt_level == 2
    assert c.sample_rate == 16000


def test_save_config_creates_parent_dirs(tmp_path: Path) -> None:
    nested_path = str(tmp_path / "nested" / "dir" / "config.json")
    save_config(AppConfig(), nested_path)
    loaded = load_config(nested_path)
    assert loaded.user_jlpt_level == 3


def test_config_new_fields_have_defaults() -> None:
    c = AppConfig()
    assert c.overlay_opacity == 0.78
    assert c.overlay_width == 800
    assert c.overlay_height == 120
    assert c.overlay_font_size_jp == 16
    assert c.overlay_font_size_cn == 14
    assert c.enable_vocab_highlight is True
    assert c.enable_grammar_highlight is True
    assert c.audio_device_id is None


def test_config_backward_compat_unknown_keys_filtered(tmp_path: Path) -> None:
    import json as _json

    config_file = tmp_path / "config.json"
    config_file.write_text(
        _json.dumps({"user_jlpt_level": 4, "unknown_future_key": "ignored"}),
        encoding="utf-8",
    )
    c = load_config(str(config_file))
    assert c.user_jlpt_level == 4
    assert not hasattr(c, "unknown_future_key")


def test_defaults_new_config_fields() -> None:
    AppConfig()  # simply verify construction succeeds


def test_save_load_roundtrip_new_fields(tmp_path: Path) -> None:
    config = AppConfig()
    path = str(tmp_path / "config.json")
    save_config(config, path)
    load_config(path)  # verify round-trip does not raise
