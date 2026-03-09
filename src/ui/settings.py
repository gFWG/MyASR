"""Settings dialog for MyASR application configuration."""

from __future__ import annotations

import asyncio
import logging
import re

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSlider,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from PySide6.QtGui import QKeySequence

from src.config import AppConfig, save_config
from src.llm.ollama_client import OllamaClient

logger = logging.getLogger(__name__)


class SettingsDialog(QDialog):
    """Non-modal settings dialog for configuring MyASR application.

    Presents configuration options across five tabs: General, Appearance,
    Model, Shortcuts, and Templates. Emits config_changed when the user saves.

    Args:
        config: Current application configuration to populate widgets from.
        parent: Optional parent widget.

    Signals:
        config_changed: Emitted with the new AppConfig when settings are saved.
    """

    config_changed = Signal(object)

    def __init__(self, config: AppConfig, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = config

        self.setWindowTitle("Settings")
        self.setMinimumSize(480, 400)

        main_layout = QVBoxLayout(self)

        self._tabs = QTabWidget()
        main_layout.addWidget(self._tabs)

        self._build_general_tab()
        self._build_appearance_tab()
        self._build_model_tab()
        self._build_shortcuts_tab()
        self._build_templates_tab()

        button_bar = QHBoxLayout()
        self._save_btn = QPushButton("Save")
        self._cancel_btn = QPushButton("Cancel")
        button_bar.addStretch()
        button_bar.addWidget(self._save_btn)
        button_bar.addWidget(self._cancel_btn)
        main_layout.addLayout(button_bar)

        self._save_btn.clicked.connect(self._on_save)
        self._cancel_btn.clicked.connect(self.close)

        self._populate_from_config(config)

        logger.debug("SettingsDialog initialized")

    def _build_general_tab(self) -> None:
        widget = QWidget()
        layout = QFormLayout(widget)

        self._jlpt_level_spin = QSpinBox()
        self._jlpt_level_spin.setRange(1, 5)
        layout.addRow("JLPT Level", self._jlpt_level_spin)

        self._llm_mode_value: str = "translation"
        llm_mode_row = QHBoxLayout()
        self._llm_mode_btn_translation = QPushButton("translation")
        self._llm_mode_btn_translation.setCheckable(True)
        self._llm_mode_btn_explanation = QPushButton("explanation")
        self._llm_mode_btn_explanation.setCheckable(True)
        llm_mode_row.addWidget(self._llm_mode_btn_translation)
        llm_mode_row.addWidget(self._llm_mode_btn_explanation)
        llm_mode_row.addStretch()
        self._llm_mode_btn_translation.clicked.connect(
            lambda: self._select_llm_mode("translation")
        )
        self._llm_mode_btn_explanation.clicked.connect(
            lambda: self._select_llm_mode("explanation")
        )
        layout.addRow("LLM Mode", llm_mode_row)

        self._vad_threshold_spin = QDoubleSpinBox()
        self._vad_threshold_spin.setRange(0.1, 0.95)
        self._vad_threshold_spin.setSingleStep(0.05)
        self._vad_threshold_spin.setDecimals(2)
        layout.addRow("VAD Threshold", self._vad_threshold_spin)

        self._vad_min_silence_spin = QSpinBox()
        self._vad_min_silence_spin.setRange(100, 2000)
        self._vad_min_silence_spin.setSingleStep(50)
        self._vad_min_silence_spin.setSuffix(" ms")
        layout.addRow("VAD Min Silence", self._vad_min_silence_spin)

        self._vad_min_speech_spin = QSpinBox()
        self._vad_min_speech_spin.setRange(100, 2000)
        self._vad_min_speech_spin.setSingleStep(50)
        self._vad_min_speech_spin.setSuffix(" ms")
        layout.addRow("VAD Min Speech", self._vad_min_speech_spin)

        self._tabs.addTab(widget, "General")

    def _build_appearance_tab(self) -> None:
        widget = QWidget()
        layout = QFormLayout(widget)

        opacity_row = QHBoxLayout()
        self._opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self._opacity_slider.setRange(10, 100)
        self._opacity_label = QLabel("78%")
        opacity_row.addWidget(self._opacity_slider)
        opacity_row.addWidget(self._opacity_label)
        self._opacity_slider.valueChanged.connect(lambda v: self._opacity_label.setText(f"{v}%"))
        layout.addRow("Overlay Opacity", opacity_row)

        self._font_size_jp_spin = QSpinBox()
        self._font_size_jp_spin.setRange(8, 48)
        layout.addRow("Japanese Font Size", self._font_size_jp_spin)

        self._font_size_cn_spin = QSpinBox()
        self._font_size_cn_spin.setRange(8, 48)
        layout.addRow("Chinese Font Size", self._font_size_cn_spin)

        self._vocab_highlight_check = QCheckBox("Show vocabulary highlights")
        layout.addRow("", self._vocab_highlight_check)

        self._grammar_highlight_check = QCheckBox("Show grammar highlights")
        layout.addRow("", self._grammar_highlight_check)

        self._display_mode_value: str = "both"
        display_mode_row = QHBoxLayout()
        self._display_mode_btn_both = QPushButton("both")
        self._display_mode_btn_both.setCheckable(True)
        self._display_mode_btn_single = QPushButton("single")
        self._display_mode_btn_single.setCheckable(True)
        display_mode_row.addWidget(self._display_mode_btn_both)
        display_mode_row.addWidget(self._display_mode_btn_single)
        display_mode_row.addStretch()
        self._display_mode_btn_both.clicked.connect(lambda: self._select_display_mode("both"))
        self._display_mode_btn_single.clicked.connect(lambda: self._select_display_mode("single"))
        layout.addRow("Display Mode", display_mode_row)

        self._tabs.addTab(widget, "Appearance")

    def _build_model_tab(self) -> None:
        widget = QWidget()
        layout = QFormLayout(widget)

        self._ollama_url_edit = QLineEdit()
        self._ollama_url_edit.setPlaceholderText("http://localhost:11434")
        layout.addRow("Provider URL", self._ollama_url_edit)

        self._ollama_api_key_edit = QLineEdit()
        self._ollama_api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._ollama_api_key_edit.setPlaceholderText("Optional — required for LM Studio / remote")
        layout.addRow("API Key", self._ollama_api_key_edit)

        model_row = QHBoxLayout()
        self._ollama_model_combo = QComboBox()
        self._ollama_model_combo.setEditable(True)
        self._ollama_model_combo.setMinimumWidth(200)
        self._refresh_models_btn = QPushButton("⟳")
        self._refresh_models_btn.setFixedWidth(32)
        self._refresh_models_btn.setToolTip("Refresh model list from provider")
        model_row.addWidget(self._ollama_model_combo)
        model_row.addWidget(self._refresh_models_btn)
        layout.addRow("Model", model_row)

        self._ollama_timeout_spin = QDoubleSpinBox()
        self._ollama_timeout_spin.setRange(5.0, 120.0)
        self._ollama_timeout_spin.setSingleStep(5.0)
        layout.addRow("Timeout (s)", self._ollama_timeout_spin)

        self._llm_streaming_check = QCheckBox("Enable streaming")
        layout.addRow("", self._llm_streaming_check)

        self._llm_temperature_spin = QDoubleSpinBox()
        self._llm_temperature_spin.setRange(0.0, 2.0)
        self._llm_temperature_spin.setSingleStep(0.1)
        self._llm_temperature_spin.setDecimals(2)
        layout.addRow("Temperature", self._llm_temperature_spin)

        self._llm_top_p_spin = QDoubleSpinBox()
        self._llm_top_p_spin.setRange(0.0, 1.0)
        self._llm_top_p_spin.setSingleStep(0.05)
        self._llm_top_p_spin.setDecimals(2)
        layout.addRow("Top P", self._llm_top_p_spin)

        self._llm_max_tokens_spin = QSpinBox()
        self._llm_max_tokens_spin.setRange(1, 4096)
        self._llm_max_tokens_spin.setSingleStep(50)
        layout.addRow("Max Tokens", self._llm_max_tokens_spin)

        self._llm_thinking_check = QCheckBox("Enable thinking/reasoning")
        layout.addRow("", self._llm_thinking_check)

        self._llm_prefill_edit = QLineEdit()
        self._llm_prefill_edit.setPlaceholderText("Assistant message prefix (optional)")
        layout.addRow("Prefill", self._llm_prefill_edit)

        self._llm_extra_args_edit = QLineEdit()
        self._llm_extra_args_edit.setPlaceholderText('{"key": "value"}')
        layout.addRow("Extra Args (JSON)", self._llm_extra_args_edit)

        self._llm_parse_format_edit = QLineEdit()
        self._llm_parse_format_edit.setPlaceholderText(
            "e.g. <tr>(.*?)</tr>  — empty = full output"
        )
        layout.addRow("Parse Format (regex)", self._llm_parse_format_edit)

        self._regex_error_label = QLabel("")
        self._regex_error_label.setStyleSheet("color: red;")
        layout.addRow("", self._regex_error_label)

        test_row = QHBoxLayout()
        self._test_conn_btn = QPushButton("Test Connection")
        self._test_conn_label = QLabel("")
        test_row.addWidget(self._test_conn_btn)
        test_row.addWidget(self._test_conn_label)
        test_row.addStretch()
        layout.addRow("", test_row)

        self._test_conn_btn.clicked.connect(self._on_test_connection)
        self._refresh_models_btn.clicked.connect(self._on_refresh_models)

        self._tabs.addTab(widget, "Model")

    def _build_shortcuts_tab(self) -> None:
        widget = QWidget()
        layout = QFormLayout(widget)

        self._shortcut_prev_edit = QLineEdit()
        self._shortcut_prev_edit.setPlaceholderText("e.g. Ctrl+Left")
        layout.addRow("Shortcut: Prev Sentence", self._shortcut_prev_edit)

        self._shortcut_next_edit = QLineEdit()
        self._shortcut_next_edit.setPlaceholderText("e.g. Ctrl+Right")
        layout.addRow("Shortcut: Next Sentence", self._shortcut_next_edit)

        self._shortcut_toggle_edit = QLineEdit()
        self._shortcut_toggle_edit.setPlaceholderText("e.g. Ctrl+T")
        layout.addRow("Shortcut: Toggle Display", self._shortcut_toggle_edit)

        self._tabs.addTab(widget, "Shortcuts")

    def _build_templates_tab(self) -> None:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        layout.addWidget(QLabel("Translation template"))
        self._translation_template_edit = QPlainTextEdit()
        layout.addWidget(self._translation_template_edit)

        layout.addWidget(QLabel("Explanation template"))
        self._explanation_template_edit = QPlainTextEdit()
        layout.addWidget(self._explanation_template_edit)

        layout.addWidget(QLabel("Use {japanese_text} as placeholder"))

        self._tabs.addTab(widget, "Templates")

    def _select_llm_mode(self, mode: str) -> None:
        self._llm_mode_value = mode
        self._llm_mode_btn_translation.setChecked(mode == "translation")
        self._llm_mode_btn_explanation.setChecked(mode == "explanation")

    def _select_display_mode(self, mode: str) -> None:
        self._display_mode_value = mode
        self._display_mode_btn_both.setChecked(mode == "both")
        self._display_mode_btn_single.setChecked(mode == "single")

    def _populate_from_config(self, config: AppConfig) -> None:
        self._jlpt_level_spin.setValue(config.user_jlpt_level)
        self._select_llm_mode(config.llm_mode)

        self._vad_threshold_spin.setValue(config.vad_threshold)
        self._vad_min_silence_spin.setValue(config.vad_min_silence_ms)
        self._vad_min_speech_spin.setValue(config.vad_min_speech_ms)

        opacity_pct = round(config.overlay_opacity * 100)
        self._opacity_slider.setValue(max(10, min(100, opacity_pct)))
        self._font_size_jp_spin.setValue(config.overlay_font_size_jp)
        self._font_size_cn_spin.setValue(config.overlay_font_size_cn)
        self._vocab_highlight_check.setChecked(config.enable_vocab_highlight)
        self._grammar_highlight_check.setChecked(config.enable_grammar_highlight)

        self._ollama_url_edit.setText(config.ollama_url)
        self._ollama_api_key_edit.setText(config.ollama_api_key)
        self._ollama_model_combo.setCurrentText(config.ollama_model)
        self._ollama_timeout_spin.setValue(config.ollama_timeout_sec)
        self._llm_streaming_check.setChecked(config.llm_streaming)
        self._llm_temperature_spin.setValue(config.llm_temperature)
        self._llm_top_p_spin.setValue(config.llm_top_p)
        self._llm_max_tokens_spin.setValue(config.llm_max_tokens)
        self._llm_thinking_check.setChecked(config.llm_thinking)
        self._llm_prefill_edit.setText(config.llm_prefill)
        self._llm_extra_args_edit.setText(config.llm_extra_args)
        self._llm_parse_format_edit.setText(config.llm_parse_format)

        self._select_display_mode(config.overlay_display_mode)
        self._shortcut_prev_edit.setText(config.shortcut_prev_sentence)
        self._shortcut_next_edit.setText(config.shortcut_next_sentence)
        self._shortcut_toggle_edit.setText(config.shortcut_toggle_display)

        self._translation_template_edit.setPlainText(config.translation_template)
        self._explanation_template_edit.setPlainText(config.explanation_template)

        logger.debug("SettingsDialog: widgets populated from config")

    def _collect_config(self) -> AppConfig:
        return AppConfig(
            user_jlpt_level=self._jlpt_level_spin.value(),
            llm_mode=self._llm_mode_value,  # type: ignore[arg-type]
            vad_threshold=self._vad_threshold_spin.value(),
            vad_min_silence_ms=self._vad_min_silence_spin.value(),
            vad_min_speech_ms=self._vad_min_speech_spin.value(),
            overlay_opacity=self._opacity_slider.value() / 100.0,
            overlay_font_size_jp=self._font_size_jp_spin.value(),
            overlay_font_size_cn=self._font_size_cn_spin.value(),
            enable_vocab_highlight=self._vocab_highlight_check.isChecked(),
            enable_grammar_highlight=self._grammar_highlight_check.isChecked(),
            ollama_url=self._ollama_url_edit.text(),
            ollama_api_key=self._ollama_api_key_edit.text(),
            ollama_model=self._ollama_model_combo.currentText(),
            ollama_timeout_sec=self._ollama_timeout_spin.value(),
            llm_streaming=self._llm_streaming_check.isChecked(),
            llm_temperature=self._llm_temperature_spin.value(),
            llm_top_p=self._llm_top_p_spin.value(),
            llm_max_tokens=self._llm_max_tokens_spin.value(),
            llm_thinking=self._llm_thinking_check.isChecked(),
            llm_prefill=self._llm_prefill_edit.text(),
            llm_extra_args=self._llm_extra_args_edit.text(),
            llm_parse_format=self._llm_parse_format_edit.text(),
            translation_template=self._translation_template_edit.toPlainText(),
            explanation_template=self._explanation_template_edit.toPlainText(),
            sample_rate=self._config.sample_rate,
            db_path=self._config.db_path,
            overlay_width=self._config.overlay_width,
            overlay_height=self._config.overlay_height,
            audio_device_id=self._config.audio_device_id,
            overlay_display_mode=self._display_mode_value,  # type: ignore[arg-type]
            shortcut_prev_sentence=self._shortcut_prev_edit.text(),
            shortcut_next_sentence=self._shortcut_next_edit.text(),
            shortcut_toggle_display=self._shortcut_toggle_edit.text(),
        )

    def _on_save(self) -> None:
        parse_format = self._llm_parse_format_edit.text()
        if parse_format:
            try:
                re.compile(parse_format)
            except re.error as e:
                self._regex_error_label.setText(f"Invalid regex: {e}")
                return
        self._regex_error_label.setText("")
        new_config = self._collect_config()
        save_config(new_config)
        self.config_changed.emit(new_config)
        logger.info("SettingsDialog: config saved and signal emitted")

    def _on_test_connection(self) -> None:
        test_config = AppConfig(
            ollama_url=self._ollama_url_edit.text(),
            ollama_model=self._ollama_model_combo.currentText(),
            ollama_timeout_sec=self._ollama_timeout_spin.value(),
            ollama_api_key=self._ollama_api_key_edit.text(),
        )
        client = OllamaClient(test_config)
        ok = asyncio.run(client.health_check_async())
        if ok:
            self._test_conn_label.setText("Connected ✓")
            logger.info("SettingsDialog: LLM connection successful")
        else:
            self._test_conn_label.setText("Failed ✗")
            logger.warning("SettingsDialog: LLM connection failed")

    def _on_refresh_models(self) -> None:
        test_config = AppConfig(
            ollama_url=self._ollama_url_edit.text(),
            ollama_api_key=self._ollama_api_key_edit.text(),
        )
        client = OllamaClient(test_config)
        models = asyncio.run(client.list_models_async())
        if models:
            current = self._ollama_model_combo.currentText()
            self._ollama_model_combo.clear()
            self._ollama_model_combo.addItems(models)
            if current:
                idx = self._ollama_model_combo.findText(current)
                if idx >= 0:
                    self._ollama_model_combo.setCurrentIndex(idx)
                else:
                    self._ollama_model_combo.setCurrentText(current)
            self._test_conn_label.setText(f"{len(models)} models loaded")
            logger.info("SettingsDialog: loaded %d models", len(models))
        else:
            self._test_conn_label.setText("No models found")
            logger.warning("SettingsDialog: model list empty or fetch failed")
