"""Settings dialog for MyASR application configuration."""

from __future__ import annotations

import logging

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

from src.config import AppConfig, save_config
from src.llm.ollama_client import OllamaClient

logger = logging.getLogger(__name__)


class SettingsDialog(QDialog):
    """Non-modal settings dialog for configuring MyASR application.

    Presents configuration options across four tabs: General, Appearance,
    Model, and Templates. Emits config_changed when the user saves.

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

        self._llm_mode_combo = QComboBox()
        self._llm_mode_combo.addItems(["translation", "explanation"])
        layout.addRow("LLM Mode", self._llm_mode_combo)

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

        self._tabs.addTab(widget, "Appearance")

    def _build_model_tab(self) -> None:
        widget = QWidget()
        layout = QFormLayout(widget)

        self._ollama_url_edit = QLineEdit()
        layout.addRow("Ollama URL", self._ollama_url_edit)

        self._ollama_model_edit = QLineEdit()
        layout.addRow("Model name", self._ollama_model_edit)

        self._ollama_timeout_spin = QDoubleSpinBox()
        self._ollama_timeout_spin.setRange(5.0, 120.0)
        self._ollama_timeout_spin.setSingleStep(5.0)
        layout.addRow("Timeout (s)", self._ollama_timeout_spin)

        test_row = QHBoxLayout()
        self._test_conn_btn = QPushButton("Test Connection")
        self._test_conn_label = QLabel("")
        test_row.addWidget(self._test_conn_btn)
        test_row.addWidget(self._test_conn_label)
        test_row.addStretch()
        layout.addRow("", test_row)

        self._test_conn_btn.clicked.connect(self._on_test_connection)

        self._tabs.addTab(widget, "Model")

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

    def _populate_from_config(self, config: AppConfig) -> None:
        self._jlpt_level_spin.setValue(config.user_jlpt_level)
        idx = self._llm_mode_combo.findText(config.llm_mode)
        if idx >= 0:
            self._llm_mode_combo.setCurrentIndex(idx)

        opacity_pct = round(config.overlay_opacity * 100)
        self._opacity_slider.setValue(max(10, min(100, opacity_pct)))
        self._font_size_jp_spin.setValue(config.overlay_font_size_jp)
        self._font_size_cn_spin.setValue(config.overlay_font_size_cn)
        self._vocab_highlight_check.setChecked(config.enable_vocab_highlight)
        self._grammar_highlight_check.setChecked(config.enable_grammar_highlight)

        self._ollama_url_edit.setText(config.ollama_url)
        self._ollama_model_edit.setText(config.ollama_model)
        self._ollama_timeout_spin.setValue(config.ollama_timeout_sec)

        self._translation_template_edit.setPlainText(config.translation_template)
        self._explanation_template_edit.setPlainText(config.explanation_template)

        logger.debug("SettingsDialog: widgets populated from config")

    def _collect_config(self) -> AppConfig:
        return AppConfig(
            user_jlpt_level=self._jlpt_level_spin.value(),
            llm_mode=self._llm_mode_combo.currentText(),  # type: ignore[arg-type]  # QComboBox returns str; AppConfig.llm_mode is a Literal — safe at runtime
            overlay_opacity=self._opacity_slider.value() / 100.0,
            overlay_font_size_jp=self._font_size_jp_spin.value(),
            overlay_font_size_cn=self._font_size_cn_spin.value(),
            enable_vocab_highlight=self._vocab_highlight_check.isChecked(),
            enable_grammar_highlight=self._grammar_highlight_check.isChecked(),
            ollama_url=self._ollama_url_edit.text(),
            ollama_model=self._ollama_model_edit.text(),
            ollama_timeout_sec=self._ollama_timeout_spin.value(),
            translation_template=self._translation_template_edit.toPlainText(),
            explanation_template=self._explanation_template_edit.toPlainText(),
            sample_rate=self._config.sample_rate,
            db_path=self._config.db_path,
            overlay_width=self._config.overlay_width,
            overlay_height=self._config.overlay_height,
            audio_device_id=self._config.audio_device_id,
        )

    def _on_save(self) -> None:
        new_config = self._collect_config()
        save_config(new_config)
        self.config_changed.emit(new_config)
        logger.info("SettingsDialog: config saved and signal emitted")
        self.close()

    def _on_test_connection(self) -> None:
        import asyncio

        test_config = AppConfig(
            ollama_url=self._ollama_url_edit.text(),
            ollama_model=self._ollama_model_edit.text(),
            ollama_timeout_sec=self._ollama_timeout_spin.value(),
        )
        client = OllamaClient(test_config)
        ok = asyncio.run(client.health_check_async())
        if ok:
            self._test_conn_label.setText("Connected ✓")
            logger.info("SettingsDialog: Ollama connection successful")
        else:
            self._test_conn_label.setText("Failed ✗")
            logger.warning("SettingsDialog: Ollama connection failed")
