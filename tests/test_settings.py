"""Tests for src.ui.settings.SettingsDialog."""

from __future__ import annotations

import unittest.mock as mock

import pytest
from PySide6.QtWidgets import QApplication

from src.config import DEFAULT_EXPLANATION_TEMPLATE, DEFAULT_TRANSLATION_TEMPLATE, AppConfig
from src.ui.settings import SettingsDialog


@pytest.fixture()
def default_config() -> AppConfig:
    return AppConfig()


@pytest.fixture()
def dialog(qapp: QApplication, default_config: AppConfig) -> SettingsDialog:
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
        ollama_api_key="sk-test",
        llm_temperature=0.7,
        llm_top_p=0.8,
        llm_max_tokens=500,
        llm_streaming=False,
        llm_thinking=True,
        llm_prefill="Sure,",
        llm_extra_args='{"seed": 42}',
        vad_threshold=0.6,
        vad_min_silence_ms=400,
        vad_min_speech_ms=500,
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
    assert d._ollama_model_combo.currentText() == "mymodel:7b"
    assert d._ollama_timeout_spin.value() == 60.0
    assert d._ollama_api_key_edit.text() == "sk-test"
    assert d._llm_temperature_spin.value() == 0.7
    assert d._llm_top_p_spin.value() == 0.8
    assert d._llm_max_tokens_spin.value() == 500
    assert d._llm_streaming_check.isChecked() is False
    assert d._llm_thinking_check.isChecked() is True
    assert d._llm_prefill_edit.text() == "Sure,"
    assert d._llm_extra_args_edit.text() == '{"seed": 42}'
    assert d._vad_threshold_spin.value() == 0.6
    assert d._vad_min_silence_spin.value() == 400
    assert d._vad_min_speech_spin.value() == 500
    assert d._translation_template_edit.toPlainText() == "trans: {japanese_text}"
    assert d._explanation_template_edit.toPlainText() == "expl: {japanese_text}"


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


def test_ollama_url_populated(dialog: SettingsDialog) -> None:
    assert dialog._ollama_url_edit.text() == "http://localhost:11434"


def test_template_fields_populated(dialog: SettingsDialog) -> None:
    assert dialog._translation_template_edit.toPlainText() == DEFAULT_TRANSLATION_TEMPLATE
    assert dialog._explanation_template_edit.toPlainText() == DEFAULT_EXPLANATION_TEMPLATE


def test_model_combo_is_editable(dialog: SettingsDialog) -> None:
    assert dialog._ollama_model_combo.isEditable() is True


def test_vad_threshold_spinbox_range(dialog: SettingsDialog) -> None:
    assert dialog._vad_threshold_spin.minimum() == 0.1
    assert dialog._vad_threshold_spin.maximum() == 0.95


def test_vad_min_silence_spinbox_range(dialog: SettingsDialog) -> None:
    assert dialog._vad_min_silence_spin.minimum() == 100
    assert dialog._vad_min_silence_spin.maximum() == 2000


def test_vad_min_speech_spinbox_range(dialog: SettingsDialog) -> None:
    assert dialog._vad_min_speech_spin.minimum() == 100
    assert dialog._vad_min_speech_spin.maximum() == 2000


def test_llm_temperature_spinbox_range(dialog: SettingsDialog) -> None:
    assert dialog._llm_temperature_spin.minimum() == 0.0
    assert dialog._llm_temperature_spin.maximum() == 2.0


def test_llm_top_p_spinbox_range(dialog: SettingsDialog) -> None:
    assert dialog._llm_top_p_spin.minimum() == 0.0
    assert dialog._llm_top_p_spin.maximum() == 1.0


def test_llm_max_tokens_spinbox_range(dialog: SettingsDialog) -> None:
    assert dialog._llm_max_tokens_spin.minimum() == 1
    assert dialog._llm_max_tokens_spin.maximum() == 4096


def test_collect_config_returns_appconfig(dialog: SettingsDialog) -> None:
    config = dialog._collect_config()
    assert isinstance(config, AppConfig)
    assert config.ollama_url == "http://localhost:11434"
    assert config.llm_streaming is True


def test_collect_config_preserves_non_ui_fields(qapp: QApplication) -> None:
    config = AppConfig(db_path="/custom/path.db", audio_device_id=5)
    d = SettingsDialog(config)
    collected = d._collect_config()
    assert collected.db_path == "/custom/path.db"
    assert collected.audio_device_id == 5


def test_api_key_field_uses_password_mode(dialog: SettingsDialog) -> None:
    from PySide6.QtWidgets import QLineEdit

    assert dialog._ollama_api_key_edit.echoMode() == QLineEdit.EchoMode.Password


def test_parse_format_field_populated(qapp: QApplication) -> None:
    config = AppConfig(llm_parse_format="<tr>(.*?)</tr>")
    d = SettingsDialog(config)
    assert d._llm_parse_format_edit.text() == "<tr>(.*?)</tr>"


def test_display_mode_combo_populated(qapp: QApplication) -> None:
    config = AppConfig(overlay_display_mode="single")
    d = SettingsDialog(config)
    assert d._display_mode_combo.currentText() == "single"


def test_shortcut_fields_populated(qapp: QApplication) -> None:
    config = AppConfig(
        shortcut_prev_sentence="Alt+Left",
        shortcut_next_sentence="Alt+Right",
        shortcut_toggle_display="Ctrl+D",
    )
    d = SettingsDialog(config)
    assert d._shortcut_prev_edit.text() == "Alt+Left"
    assert d._shortcut_next_edit.text() == "Alt+Right"
    assert d._shortcut_toggle_edit.text() == "Ctrl+D"


def test_collect_config_includes_parse_format(dialog: SettingsDialog) -> None:
    dialog._llm_parse_format_edit.setText("<output>(.*?)</output>")
    collected = dialog._collect_config()
    assert collected.llm_parse_format == "<output>(.*?)</output>"


def test_collect_config_includes_display_mode(dialog: SettingsDialog) -> None:
    dialog._display_mode_combo.setCurrentText("single")
    collected = dialog._collect_config()
    assert collected.overlay_display_mode == "single"


def test_collect_config_includes_shortcuts(dialog: SettingsDialog) -> None:
    dialog._shortcut_prev_edit.setText("Ctrl+Up")
    dialog._shortcut_next_edit.setText("Ctrl+Down")
    dialog._shortcut_toggle_edit.setText("Ctrl+M")
    collected = dialog._collect_config()
    assert collected.shortcut_prev_sentence == "Ctrl+Up"
    assert collected.shortcut_next_sentence == "Ctrl+Down"
    assert collected.shortcut_toggle_display == "Ctrl+M"
