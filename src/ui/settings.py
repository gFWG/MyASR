"""Settings dialog for MyASR application configuration."""

from __future__ import annotations

import logging
from collections.abc import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTextEdit,
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
        self._build_resource_tab()

        button_bar = QHBoxLayout()
        self._reset_btn = QPushButton("Reset")
        self._reset_btn.setObjectName("resetButton")
        self._save_btn = QPushButton("Save")
        self._cancel_btn = QPushButton("Cancel")
        button_bar.addWidget(self._reset_btn)
        button_bar.addStretch()
        button_bar.addWidget(self._save_btn)
        button_bar.addWidget(self._cancel_btn)
        main_layout.addLayout(button_bar)

        # Windows 11 style for reset button (red accent, theme-aware)
        self._reset_btn.setStyleSheet(
            "QPushButton#resetButton {"
            "  background-color: palette(highlight);"
            "  color: palette(highlighted-text);"
            "  border: 1px solid transparent;"
            "  border-radius: 4px;"
            "  padding: 6px 16px;"
            "  min-width: 80px;"
            "}"
            "QPushButton#resetButton:hover {"
            "  background-color: #D42B1C;"
            "  color: white;"
            "}"
            "QPushButton#resetButton:pressed {"
            "  background-color: #A8261A;"
            "  color: white;"
            "}"
        )

        self._reset_btn.clicked.connect(self._on_reset)
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

    def _build_resource_tab(self) -> None:
        """Build the Resource tab with ASR Model selection and availability check."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # ASR Model selection row
        model_row = QHBoxLayout()
        model_label = QLabel("ASR Model")
        self._asr_model_combo = QComboBox()
        self._asr_model_combo.addItem("Qwen-ASR-0.6B", "Qwen/Qwen3-ASR-0.6B")
        self._asr_model_combo.addItem("Qwen-ASR-1.7B", "Qwen/Qwen3-ASR-1.7B")
        self._asr_model_combo.setMinimumWidth(200)
        model_row.addWidget(model_label)
        model_row.addWidget(self._asr_model_combo)

        # Restart needed warning label
        self._restart_label = QLabel("Restart Required!")
        self._restart_label.setStyleSheet("color: #D32F2F; font-weight: bold;")
        model_row.addWidget(self._restart_label)

        # Refresh button
        model_row.addStretch()
        self._refresh_model_btn = QPushButton("Refresh")
        self._refresh_model_btn.clicked.connect(self._on_refresh_model)
        model_row.addWidget(self._refresh_model_btn)

        layout.addLayout(model_row)

        # Result text box for model availability status
        self._model_status_text = QTextEdit()
        self._model_status_text.setReadOnly(True)
        self._model_status_text.setMaximumHeight(150)
        self._model_status_text.setPlaceholderText("Click 'Refresh' to check model availability...")
        layout.addWidget(self._model_status_text)

        layout.addStretch()

        self._tabs.addTab(widget, "Resource")

    def _on_refresh_model(self) -> None:
        """Check if the selected ASR model is available and display the result."""
        model_name = self._asr_model_combo.currentData()
        model_display = self._asr_model_combo.currentText()
        self._model_status_text.clear()

        # Try to check model availability
        try:
            import os

            import torch

            # Check CUDA availability
            if not torch.cuda.is_available():
                self._append_status(
                    f"❌ CUDA not available - GPU required for ASR model", is_error=True
                )
                return

            # Check if model path exists locally
            # Check common HuggingFace cache locations
            hf_cache = os.environ.get("HF_HOME", os.path.expanduser("~/.cache/huggingface"))
            hub_cache = os.environ.get("HUGGINGFACE_HUB_CACHE", os.path.join(hf_cache, "hub"))

            # Normalize model name for cache path
            model_folder_name = "models--" + model_name.replace("/", "--")
            cache_path = os.path.join(hub_cache, model_folder_name)

            if os.path.exists(cache_path):
                self._append_status(f"✅ Model found in cache: {cache_path}", is_error=False)
                # Check for model files
                snapshots_path = os.path.join(cache_path, "snapshots")
                if os.path.exists(snapshots_path):
                    snapshots = os.listdir(snapshots_path)
                    if snapshots:
                        self._append_status(f"   Snapshot: {snapshots[0]}", is_error=False)
            else:
                self._append_status(
                    f"⚠️ Model not found in cache: {model_display}", is_error=True
                )
                self._append_status(f"   Expected path: {cache_path}", is_error=False)
                self._append_status(
                    "   Please download the model or ensure offline mode has the model.",
                    is_error=False,
                )
                return

            # Check VRAM (rough estimate)
            if torch.cuda.is_available():
                gpu_name = torch.cuda.get_device_name(0)
                total_vram = torch.cuda.get_device_properties(0).total_memory / (1024**3)
                self._append_status(f"✅ GPU: {gpu_name}", is_error=False)
                self._append_status(f"   VRAM: {total_vram:.1f} GB", is_error=False)

                # Model size estimates (approximate)
                model_vram_req = 1.5 if "0.6B" in model_display else 4.0
                if total_vram < model_vram_req:
                    self._append_status(
                        f"⚠️ VRAM may be insufficient (need ~{model_vram_req:.1f} GB)",
                        is_error=True,
                    )
                else:
                    self._append_status(
                        f"✅ VRAM sufficient for {model_display}", is_error=False
                    )

            self._append_status(f"\n✅ {model_display} is available", is_error=False)

        except ImportError as e:
            self._append_status(f"❌ Import error: {e}", is_error=True)
        except Exception as e:
            self._append_status(f"❌ Error checking model: {e}", is_error=True)

    def _append_status(self, text: str, is_error: bool = False) -> None:
        """Append text to the status area with optional red highlighting for errors."""
        cursor = self._model_status_text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        format = QTextCharFormat()
        if is_error:
            format.setForeground(QColor("#D32F2F"))  # Red color for errors
            format.setFontWeight(700)  # Bold

        cursor.insertText(text + "\n", format)
        self._model_status_text.setTextCursor(cursor)
        self._model_status_text.ensureCursorVisible()

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

        # Set ASR model combo box
        asr_model = config.asr_model
        for i in range(self._asr_model_combo.count()):
            if self._asr_model_combo.itemData(i) == asr_model:
                self._asr_model_combo.setCurrentIndex(i)
                break

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
            asr_model=self._asr_model_combo.currentData(),
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

    def _on_reset(self) -> None:
        """Reset all settings to default values after confirmation."""
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Reset Settings")
        msg_box.setText("Are you sure you want to reset all settings to default values?")
        msg_box.setInformativeText("This action cannot be undone.")
        msg_box.setIcon(QMessageBox.Icon.Warning)
        msg_box.setStandardButtons(
            QMessageBox.StandardButton.Reset | QMessageBox.StandardButton.Cancel
        )
        msg_box.setDefaultButton(QMessageBox.StandardButton.Cancel)

        # Style the message box buttons for Windows 11 consistency (theme-aware)
        msg_box.setStyleSheet(
            "QMessageBox {"
            "  font-family: 'Segoe UI', sans-serif;"
            "}"
            "QPushButton {"
            "  min-width: 80px;"
            "  padding: 6px 16px;"
            "  border-radius: 4px;"
            "  border: 1px solid palette(mid);"
            "  background-color: palette(button);"
            "  color: palette(button-text);"
            "}"
            "QPushButton:hover {"
            "  background-color: palette(highlight);"
            "  color: palette(highlighted-text);"
            "  border-color: palette(highlight);"
            "}"
            "QPushButton:pressed {"
            "  background-color: palette(dark);"
            "  color: palette(button-text);"
            "}"
        )

        result = msg_box.exec()
        if result == QMessageBox.StandardButton.Reset:
            default_config = AppConfig()
            self._populate_from_config(default_config)
            logger.info("SettingsDialog: settings reset to defaults")
