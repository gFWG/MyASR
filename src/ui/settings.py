"""Settings dialog for MyASR application configuration."""

from __future__ import annotations

import logging
from collections.abc import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.config import DEFAULT_JLPT_COLORS, AppConfig, save_config

logger = logging.getLogger(__name__)


class SettingsDialog(QDialog):
    """Non-modal settings dialog for configuring MyASR application.

    Presents configuration options across two tabs: General and Appearance.
    Emits config_changed when the user saves.

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

        self._max_history_spin = QSpinBox()
        self._max_history_spin.setRange(1, 100)
        self._max_history_spin.setSingleStep(1)
        layout.addRow("Max Sentence History", self._max_history_spin)

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

        self._vocab_highlight_check = QCheckBox("Show vocabulary highlights")
        layout.addRow("", self._vocab_highlight_check)

        self._grammar_highlight_check = QCheckBox("Show grammar highlights")
        layout.addRow("", self._grammar_highlight_check)

        self._jlpt_color_buttons: dict[str, QPushButton] = {}
        jlpt_labels = {
            "n5_vocab": "N5 Vocab",
            "n5_grammar": "N5 Grammar",
            "n4_vocab": "N4 Vocab",
            "n4_grammar": "N4 Grammar",
            "n3_vocab": "N3 Vocab",
            "n3_grammar": "N3 Grammar",
            "n2_vocab": "N2 Vocab",
            "n2_grammar": "N2 Grammar",
            "n1_vocab": "N1 Vocab",
            "n1_grammar": "N1 Grammar",
        }
        for key, label in jlpt_labels.items():
            btn = QPushButton()
            btn.setFixedSize(60, 24)
            btn.clicked.connect(self._make_color_callback(key))
            self._jlpt_color_buttons[key] = btn
            layout.addRow(label, btn)

        self._tabs.addTab(widget, "Appearance")

    def _make_color_callback(self, key: str) -> Callable[[], None]:
        """Create a callback that opens a color dialog for the given JLPT color key."""

        def _pick_color() -> None:
            btn = self._jlpt_color_buttons[key]
            current = btn.property("hex_color") or DEFAULT_JLPT_COLORS.get(key, "#FFFFFF")
            color = QColorDialog.getColor(QColor(current), self, f"Pick color for {key}")
            if color.isValid():
                hex_color = color.name()
                btn.setProperty("hex_color", hex_color)
                self._update_color_button_style(btn, hex_color)

        return _pick_color

    def _update_color_button_style(self, btn: QPushButton, hex_color: str) -> None:
        """Set the button background to the given hex color."""
        btn.setStyleSheet(
            f"background-color: {hex_color}; border: 1px solid #888; border-radius: 3px;"
        )

    def _populate_from_config(self, config: AppConfig) -> None:
        self._jlpt_level_spin.setValue(config.user_jlpt_level)

        self._vad_threshold_spin.setValue(config.vad_threshold)
        self._vad_min_silence_spin.setValue(config.vad_min_silence_ms)
        self._vad_min_speech_spin.setValue(config.vad_min_speech_ms)
        self._max_history_spin.setValue(config.max_history)

        opacity_pct = round(config.overlay_opacity * 100)
        self._opacity_slider.setValue(max(10, min(100, opacity_pct)))
        self._font_size_jp_spin.setValue(config.overlay_font_size_jp)
        self._vocab_highlight_check.setChecked(config.enable_vocab_highlight)
        self._grammar_highlight_check.setChecked(config.enable_grammar_highlight)

        for key, btn in self._jlpt_color_buttons.items():
            hex_color = config.jlpt_colors.get(key, DEFAULT_JLPT_COLORS.get(key, "#FFFFFF"))
            btn.setProperty("hex_color", hex_color)
            self._update_color_button_style(btn, hex_color)

        logger.debug("SettingsDialog: widgets populated from config")

    def _collect_config(self) -> AppConfig:
        return AppConfig(
            user_jlpt_level=self._jlpt_level_spin.value(),
            vad_threshold=self._vad_threshold_spin.value(),
            vad_min_silence_ms=self._vad_min_silence_spin.value(),
            vad_min_speech_ms=self._vad_min_speech_spin.value(),
            max_history=self._max_history_spin.value(),
            overlay_opacity=self._opacity_slider.value() / 100.0,
            overlay_font_size_jp=self._font_size_jp_spin.value(),
            enable_vocab_highlight=self._vocab_highlight_check.isChecked(),
            enable_grammar_highlight=self._grammar_highlight_check.isChecked(),
            sample_rate=self._config.sample_rate,
            db_path=self._config.db_path,
            overlay_width=self._config.overlay_width,
            overlay_height=self._config.overlay_height,
            audio_device_id=self._config.audio_device_id,
            jlpt_colors={
                key: btn.property("hex_color") or DEFAULT_JLPT_COLORS.get(key, "#FFFFFF")
                for key, btn in self._jlpt_color_buttons.items()
            },
        )

    def _on_save(self) -> None:
        new_config = self._collect_config()
        save_config(new_config)
        self.config_changed.emit(new_config)
        logger.info("SettingsDialog: config saved and signal emitted")
