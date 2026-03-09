"""Tests for src.ui.settings.SettingsDialog."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from src.config import DEFAULT_EXPLANATION_TEMPLATE, DEFAULT_TRANSLATION_TEMPLATE, AppConfig
from src.ui.settings import SettingsDialog


@pytest.fixture()
def default_config() -> AppConfig:
    """Default AppConfig for dialog construction."""
    return AppConfig()


@pytest.fixture()
def dialog(qapp: QApplication, default_config: AppConfig) -> SettingsDialog:
    """SettingsDialog constructed with default config, not shown."""
    return SettingsDialog(default_config)


def test_settings_dialog_has_four_tabs(dialog: SettingsDialog) -> None:
    assert dialog._tabs.count() == 4


def test_widgets_populate_from_config(qapp: QApplication) -> None:
    config = AppConfig(
        user_jlpt_level=2,
        overlay_opacity=0.50,
        overlay_font_size_jp=20,
        overlay_font_size_cn=18,
        enable_vocab_highlight=False,
        enable_grammar_highlight=False,
        ollama_url="http://remote:11434",
        ollama_model="mymodel:7b",
        ollama_timeout_sec=60.0,
        translation_template="trans: {japanese_text}",
        explanation_template="expl: {japanese_text}",
    )
    d = SettingsDialog(config)
    assert d._jlpt_level_spin.value() == 2
    assert d._opacity_slider.value() == 50
    assert d._font_size_jp_spin.value() == 20
    assert d._font_size_cn_spin.value() == 18
    assert d._vocab_highlight_check.isChecked() is False
    assert d._grammar_highlight_check.isChecked() is False
    assert d._ollama_url_edit.text() == "http://remote:11434"
    assert d._ollama_model_edit.text() == "mymodel:7b"
    assert d._ollama_timeout_spin.value() == 60.0
    assert d._translation_template_edit.toPlainText() == "trans: {japanese_text}"
    assert d._explanation_template_edit.toPlainText() == "expl: {japanese_text}"


def test_save_emits_config_changed(qapp: QApplication, tmp_path: object) -> None:
    import unittest.mock as mock

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


def test_ollama_url_populated(dialog: SettingsDialog) -> None:
    assert dialog._ollama_url_edit.text() == "http://localhost:11434"


def test_template_fields_populated(dialog: SettingsDialog) -> None:
    assert dialog._translation_template_edit.toPlainText() == DEFAULT_TRANSLATION_TEMPLATE
    assert dialog._explanation_template_edit.toPlainText() == DEFAULT_EXPLANATION_TEMPLATE
