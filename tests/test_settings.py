"""Tests for src.ui.settings.SettingsDialog."""

from __future__ import annotations

import unittest.mock as mock

import pytest
from PySide6.QtWidgets import QApplication

from src.config import DEFAULT_JLPT_COLORS, AppConfig
from src.ui.settings import SettingsDialog


@pytest.fixture()
def default_config() -> AppConfig:
    return AppConfig()


@pytest.fixture()
def dialog(qapp: QApplication, default_config: AppConfig) -> SettingsDialog:
    return SettingsDialog(default_config)


def test_settings_dialog_has_two_tabs(dialog: SettingsDialog) -> None:
    assert dialog._tabs.count() == 2


def test_widgets_populate_from_config(qapp: QApplication) -> None:
    config = AppConfig(
        user_jlpt_level=2,
        overlay_opacity=0.50,
        overlay_font_size_jp=20,
        enable_vocab_highlight=False,
        enable_grammar_highlight=False,
        vad_threshold=0.6,
        vad_min_silence_ms=400,
        vad_min_speech_ms=500,
    )
    d = SettingsDialog(config)
    assert d._jlpt_level_spin.value() == 2
    assert d._opacity_slider.value() == 50
    assert d._font_size_jp_spin.value() == 20
    assert d._vocab_highlight_check.isChecked() is False
    assert d._grammar_highlight_check.isChecked() is False
    assert d._vad_threshold_spin.value() == 0.6
    assert d._vad_min_silence_spin.value() == 400
    assert d._vad_min_speech_spin.value() == 500


def test_save_emits_config_changed(qapp: QApplication, tmp_path: object) -> None:
    config = AppConfig()
    d = SettingsDialog(config)
    received: list[AppConfig] = []
    d.config_changed.connect(received.append)

    with mock.patch("src.ui.settings.save_config"):
        d._on_save()

    assert len(received) == 1
    assert isinstance(received[0], AppConfig)


def test_cancel_does_not_emit_signal(dialog: SettingsDialog) -> None:
    received: list[AppConfig] = []
    dialog.config_changed.connect(received.append)
    dialog.close()
    assert len(received) == 0


def test_jlpt_level_spinbox_range(dialog: SettingsDialog) -> None:
    assert dialog._jlpt_level_spin.minimum() == 1
    assert dialog._jlpt_level_spin.maximum() == 5


def test_opacity_slider_range(dialog: SettingsDialog) -> None:
    assert dialog._opacity_slider.minimum() == 10
    assert dialog._opacity_slider.maximum() == 100


def test_vad_threshold_spinbox_range(dialog: SettingsDialog) -> None:
    assert dialog._vad_threshold_spin.minimum() == 0.1
    assert dialog._vad_threshold_spin.maximum() == 0.95


def test_vad_min_silence_spinbox_range(dialog: SettingsDialog) -> None:
    assert dialog._vad_min_silence_spin.minimum() == 100
    assert dialog._vad_min_silence_spin.maximum() == 2000


def test_vad_min_speech_spinbox_range(dialog: SettingsDialog) -> None:
    assert dialog._vad_min_speech_spin.minimum() == 100
    assert dialog._vad_min_speech_spin.maximum() == 2000


def test_collect_config_returns_appconfig(dialog: SettingsDialog) -> None:
    config = dialog._collect_config()
    assert isinstance(config, AppConfig)


def test_collect_config_preserves_non_ui_fields(qapp: QApplication) -> None:
    config = AppConfig(db_path="/custom/path.db", audio_device_id=5)
    d = SettingsDialog(config)
    collected = d._collect_config()
    assert collected.db_path == "/custom/path.db"
    assert collected.audio_device_id == 5


def test_on_save_does_not_close_dialog(qapp: QApplication) -> None:
    config = AppConfig()
    d = SettingsDialog(config)
    d.show()
    with mock.patch("src.ui.settings.save_config"):
        d._on_save()
    assert d.isVisible()


# ── JLPT color picker tests ──


def test_jlpt_color_buttons_exist(dialog: SettingsDialog) -> None:
    assert len(dialog._jlpt_color_buttons) == 10
    expected_keys = {
        "n5_vocab",
        "n5_grammar",
        "n4_vocab",
        "n4_grammar",
        "n3_vocab",
        "n3_grammar",
        "n2_vocab",
        "n2_grammar",
        "n1_vocab",
        "n1_grammar",
    }
    assert set(dialog._jlpt_color_buttons.keys()) == expected_keys


def test_jlpt_color_buttons_populated_from_config(qapp: QApplication) -> None:
    custom_colors = dict(DEFAULT_JLPT_COLORS)
    custom_colors["n4_vocab"] = "#FF0000"
    config = AppConfig(jlpt_colors=custom_colors)
    d = SettingsDialog(config)
    assert d._jlpt_color_buttons["n4_vocab"].property("hex_color") == "#FF0000"


def test_jlpt_color_buttons_default_colors(dialog: SettingsDialog) -> None:
    for key, expected_color in DEFAULT_JLPT_COLORS.items():
        btn = dialog._jlpt_color_buttons[key]
        assert btn.property("hex_color") == expected_color


def test_collect_config_includes_jlpt_colors(dialog: SettingsDialog) -> None:
    dialog._jlpt_color_buttons["n4_vocab"].setProperty("hex_color", "#123456")
    collected = dialog._collect_config()
    assert collected.jlpt_colors["n4_vocab"] == "#123456"
