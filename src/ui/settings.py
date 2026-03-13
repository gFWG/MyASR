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
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.config import DEFAULT_JLPT_COLORS, AppConfig, save_config
from src.ui.widgets import JlptLevelSelector, SliderDoubleSpinBox, SliderSpinBox

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
        self.setMinimumSize(560, 400)

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

        # JLPT Level - segmented control (N1-N5)
        self._jlpt_level = JlptLevelSelector()
        layout.addRow("JLPT Level", self._jlpt_level)

        # VAD Threshold - float slider + spinbox
        self._vad_threshold = SliderDoubleSpinBox(decimals=2)
        self._vad_threshold.setRange(0.1, 0.95)
        self._vad_threshold.setSingleStep(0.05)
        layout.addRow("VAD Threshold", self._vad_threshold)

        # VAD Min Silence - integer slider + spinbox
        self._vad_min_silence = SliderSpinBox()
        self._vad_min_silence.setRange(100, 2000)
        self._vad_min_silence.setSingleStep(50)
        self._vad_min_silence.setSuffix(" ms")
        layout.addRow("VAD Min Silence", self._vad_min_silence)

        # VAD Min Speech - integer slider + spinbox
        self._vad_min_speech = SliderSpinBox()
        self._vad_min_speech.setRange(100, 2000)
        self._vad_min_speech.setSingleStep(50)
        self._vad_min_speech.setSuffix(" ms")
        layout.addRow("VAD Min Speech", self._vad_min_speech)

        # Max Sentence History - integer slider + spinbox
        self._max_history = SliderSpinBox()
        self._max_history.setRange(1, 50)
        self._max_history.setSingleStep(1)
        layout.addRow("Max Sentence History", self._max_history)

        self._tabs.addTab(widget, "General")

    def _build_appearance_tab(self) -> None:
        widget = QWidget()
        layout = QFormLayout(widget)

        # Overlay Opacity - integer slider + spinbox (percentage)
        self._opacity = SliderSpinBox()
        self._opacity.setRange(10, 100)
        self._opacity.setSingleStep(1)
        self._opacity.setSuffix("%")
        layout.addRow("Overlay Opacity", self._opacity)

        # Japanese Font Size - integer slider + spinbox
        self._font_size_jp = SliderSpinBox()
        self._font_size_jp.setRange(8, 48)
        self._font_size_jp.setSingleStep(1)
        layout.addRow("Japanese Font Size", self._font_size_jp)

        self._vocab_highlight_check = QCheckBox("Show vocabulary highlights")
        layout.addRow("", self._vocab_highlight_check)

        self._grammar_highlight_check = QCheckBox("Show grammar highlights")
        layout.addRow("", self._grammar_highlight_check)

        # JLPT color table: 3 rows x 6 columns grid
        # Row 0: Header (JLPT, N1, N2, N3, N4, N5)
        # Row 1: Grammar color buttons
        # Row 2: Vocab color buttons
        color_grid = QGridLayout()
        color_grid.setSpacing(8)

        # Header row
        headers = ["JLPT", "N1", "N2", "N3", "N4", "N5"]
        for col, text in enumerate(headers):
            label = QLabel(text)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            color_grid.addWidget(label, 0, col)

        # Row labels
        grammar_label = QLabel("Grammar")
        grammar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        color_grid.addWidget(grammar_label, 1, 0)

        vocab_label = QLabel("Vocab")
        vocab_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        color_grid.addWidget(vocab_label, 2, 0)

        # Color buttons (square)
        self._jlpt_color_buttons: dict[str, QPushButton] = {}
        button_size = 32
        levels = ["n1", "n2", "n3", "n4", "n5"]

        for col, level in enumerate(levels, start=1):
            # Grammar button
            g_key = f"{level}_grammar"
            g_btn = QPushButton()
            g_btn.setFixedSize(button_size, button_size)
            g_btn.clicked.connect(self._make_color_callback(g_key))
            self._jlpt_color_buttons[g_key] = g_btn
            color_grid.addWidget(g_btn, 1, col, Qt.AlignmentFlag.AlignCenter)

            # Vocab button
            v_key = f"{level}_vocab"
            v_btn = QPushButton()
            v_btn.setFixedSize(button_size, button_size)
            v_btn.clicked.connect(self._make_color_callback(v_key))
            self._jlpt_color_buttons[v_key] = v_btn
            color_grid.addWidget(v_btn, 2, col, Qt.AlignmentFlag.AlignCenter)

        # Add label and grid on separate rows
        layout.addRow("", QLabel(""))
        layout.addRow(color_grid)

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
        self._jlpt_level.setValue(config.user_jlpt_level)

        self._vad_threshold.setValue(config.vad_threshold)
        self._vad_min_silence.setValue(config.vad_min_silence_ms)
        self._vad_min_speech.setValue(config.vad_min_speech_ms)
        self._max_history.setValue(config.max_history)

        opacity_pct = round(config.overlay_opacity * 100)
        self._opacity.setValue(max(10, min(100, opacity_pct)))
        self._font_size_jp.setValue(config.overlay_font_size_jp)
        self._vocab_highlight_check.setChecked(config.enable_vocab_highlight)
        self._grammar_highlight_check.setChecked(config.enable_grammar_highlight)

        for key, btn in self._jlpt_color_buttons.items():
            hex_color = config.jlpt_colors.get(key, DEFAULT_JLPT_COLORS.get(key, "#FFFFFF"))
            btn.setProperty("hex_color", hex_color)
            self._update_color_button_style(btn, hex_color)

        logger.debug("SettingsDialog: widgets populated from config")

    def _collect_config(self) -> AppConfig:
        return AppConfig(
            user_jlpt_level=self._jlpt_level.value(),
            vad_threshold=self._vad_threshold.value(),
            vad_min_silence_ms=self._vad_min_silence.value(),
            vad_min_speech_ms=self._vad_min_speech.value(),
            max_history=self._max_history.value(),
            overlay_opacity=self._opacity.value() / 100.0,
            overlay_font_size_jp=self._font_size_jp.value(),
            enable_vocab_highlight=self._vocab_highlight_check.isChecked(),
            enable_grammar_highlight=self._grammar_highlight_check.isChecked(),
            sample_rate=self._config.sample_rate,
            overlay_width=self._config.overlay_width,
            overlay_height=self._config.overlay_height,
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
