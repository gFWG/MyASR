"""Settings dialog for MyASR application configuration."""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QCloseEvent, QColor, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.asr.model_resources import (
    default_model_directory,
    delete_model_artifacts,
    download_model_snapshot,
    find_hf_cache_snapshot,
    get_model_spec,
    resolve_model_directory,
    validate_model_directory,
)
from src.config import DEFAULT_JLPT_COLORS, AppConfig, save_config
from src.exceptions import ModelResourceError
from src.ui.widgets import JlptLevelSelector, SliderDoubleSpinBox, SliderSpinBox

logger = logging.getLogger(__name__)

_MESSAGE_BOX_STYLESHEET = (
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


class _DownloadWorker(QThread):
    progress = Signal(str)
    finished_ok = Signal(str, str)
    finished_err = Signal(str)
    finished_cancelled = Signal()

    def __init__(self, repo_id: str, target_directory: str) -> None:
        super().__init__()
        self._repo_id = repo_id
        self._target_directory = target_directory

    def run(self) -> None:
        try:
            download_model_snapshot(
                repo_id=self._repo_id,
                target_directory=self._target_directory,
                progress_callback=self.progress.emit,
                check_cancelled=self.isInterruptionRequested,
            )
        except ModelResourceError as exc:
            if self.isInterruptionRequested() or "cancelled" in str(exc).lower():
                self.finished_cancelled.emit()
                return
            self.finished_err.emit(str(exc))
            return
        except Exception as exc:
            if self.isInterruptionRequested():
                self.finished_cancelled.emit()
                return
            logger.exception("Unexpected download failure for %s", self._repo_id)
            self.finished_err.emit(f"Unexpected download failure: {exc}")
            return

        self.finished_ok.emit(self._repo_id, self._target_directory)


class SettingsDialog(QDialog):
    config_changed = Signal(object)

    def __init__(
        self,
        config: AppConfig,
        parent: QWidget | None = None,
        runtime_config: AppConfig | None = None,
        active_model_directory: str = "",
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._runtime_config = runtime_config or config
        self._active_model_directory = self._normalize_path_for_compare(active_model_directory)
        self._download_worker: _DownloadWorker | None = None
        self._resource_state_requires_restart = False

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

    def select_tab(self, index: int) -> None:
        """Switch to the tab at *index* (0=General, 1=Appearance, 2=Resource)."""
        if 0 <= index < self._tabs.count():
            self._tabs.setCurrentIndex(index)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._download_worker is not None and self._download_worker.isRunning():
            if not self._download_worker.isInterruptionRequested():
                msg_box = QMessageBox(self)
                msg_box.setWindowTitle("Download In Progress")
                msg_box.setText("An ASR model download is still running.")
                msg_box.setInformativeText("Cancel the download and close Settings?")
                msg_box.setIcon(QMessageBox.Icon.Warning)
                msg_box.setStandardButtons(
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                msg_box.setDefaultButton(QMessageBox.StandardButton.No)
                msg_box.setStyleSheet(_MESSAGE_BOX_STYLESHEET)
                if msg_box.exec() != QMessageBox.StandardButton.Yes:
                    event.ignore()
                    return
                self._on_cancel_download()
            # Download was cancelled but thread hasn't exited yet — let it finish in background
            event.ignore()
            return

        super().closeEvent(event)

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

        # Pre-buffer - integer slider + spinbox
        self._pre_buffer = SliderSpinBox()
        self._pre_buffer.setRange(0, 1000)
        self._pre_buffer.setSingleStep(50)
        self._pre_buffer.setSuffix(" ms")
        layout.addRow("Pre-buffer", self._pre_buffer)

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
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)

        description = QLabel(
            "Manage the local Qwen ASR files used for startup, downloads, and cleanup. "
            "Leave the path blank to use MyASR's default model directory."
        )
        description.setWordWrap(True)
        description.setStyleSheet("color: palette(mid);")
        layout.addWidget(description)

        model_row = QHBoxLayout()
        model_label = QLabel("ASR Model")
        self._asr_model_combo = QComboBox()
        self._asr_model_combo.addItem("Qwen-ASR-0.6B", "Qwen/Qwen3-ASR-0.6B")
        self._asr_model_combo.addItem("Qwen-ASR-1.7B", "Qwen/Qwen3-ASR-1.7B")
        self._asr_model_combo.setMinimumWidth(220)
        model_row.addWidget(model_label)
        model_row.addWidget(self._asr_model_combo, 1)
        layout.addLayout(model_row)

        self._restart_label = QLabel("Restart required to apply ASR resource changes.")
        self._restart_label.setStyleSheet("color: #D32F2F; font-weight: 600;")
        self._restart_label.hide()
        layout.addWidget(self._restart_label)

        path_row = QHBoxLayout()
        path_label = QLabel("Model Directory")
        self._model_path_edit = QLineEdit()
        self._model_path_edit.setClearButtonEnabled(True)
        self._model_path_edit.setMinimumWidth(320)
        self._select_path_btn = QPushButton("Select File Path")
        self._select_path_btn.clicked.connect(self._on_select_file_path)
        path_row.addWidget(path_label)
        path_row.addWidget(self._model_path_edit, 1)
        path_row.addWidget(self._select_path_btn)
        layout.addLayout(path_row)

        self._default_path_label = QLabel()
        self._default_path_label.setWordWrap(True)
        self._default_path_label.setStyleSheet("color: palette(mid);")
        layout.addWidget(self._default_path_label)

        action_row = QHBoxLayout()
        action_row.addStretch()
        self._download_model_btn = QPushButton("Download")
        self._cancel_download_btn = QPushButton("Cancel Download")
        self._cancel_download_btn.hide()
        self._delete_model_btn = QPushButton("Delete")
        self._refresh_model_btn = QPushButton("Refresh")
        self._download_model_btn.clicked.connect(self._on_download_model)
        self._cancel_download_btn.clicked.connect(self._on_cancel_download)
        self._delete_model_btn.clicked.connect(self._on_delete_model)
        self._refresh_model_btn.clicked.connect(self._on_refresh_model)
        action_row.addWidget(self._download_model_btn)
        action_row.addWidget(self._cancel_download_btn)
        action_row.addWidget(self._delete_model_btn)
        action_row.addWidget(self._refresh_model_btn)
        layout.addLayout(action_row)

        self._model_status_text = QTextEdit()
        self._model_status_text.setReadOnly(True)
        self._model_status_text.setMaximumHeight(180)
        self._model_status_text.setPlaceholderText(
            "Use Refresh to inspect the selected model directory."
        )
        layout.addWidget(self._model_status_text)

        layout.addStretch()

        self._resource_tab = widget
        self._asr_model_combo.currentIndexChanged.connect(self._on_resource_inputs_changed)
        self._model_path_edit.textChanged.connect(self._on_resource_inputs_changed)
        self._tabs.addTab(widget, "Resource")

    def _on_resource_inputs_changed(self, _value: object | None = None) -> None:
        self._update_resource_path_placeholder()
        self._update_restart_label()
        self._model_status_text.clear()

    def _current_model_repo_id(self) -> str:
        repo_id = self._asr_model_combo.currentData()
        if not isinstance(repo_id, str):
            raise ModelResourceError("No ASR model is currently selected.")
        return repo_id

    def _current_custom_model_path(self) -> str:
        return self._model_path_edit.text().strip()

    def _current_target_directory(self) -> Path:
        return (
            resolve_model_directory(
                self._current_model_repo_id(),
                self._current_custom_model_path(),
            )
            .expanduser()
            .resolve(strict=False)
        )

    def _update_resource_path_placeholder(self) -> None:
        default_path = default_model_directory(self._current_model_repo_id()).resolve(strict=False)
        self._model_path_edit.setPlaceholderText(str(default_path))
        self._default_path_label.setText(f"Default directory: {default_path}")

    def _normalize_path_for_compare(self, path_value: str) -> str:
        stripped_value = path_value.strip()
        if not stripped_value:
            return ""

        normalized_path = Path(stripped_value).expanduser()
        try:
            normalized_path = normalized_path.resolve(strict=False)
        except OSError:
            pass
        return str(normalized_path).casefold()

    def _update_restart_label(self) -> None:
        model_changed = self._current_model_repo_id() != self._runtime_config.asr_model
        path_changed = self._normalize_path_for_compare(
            self._current_custom_model_path()
        ) != self._normalize_path_for_compare(self._runtime_config.asr_model_local_path)
        self._restart_label.setVisible(
            model_changed or path_changed or self._resource_state_requires_restart
        )

    def _set_resource_controls_enabled(self, enabled: bool) -> None:
        self._asr_model_combo.setEnabled(enabled)
        self._model_path_edit.setEnabled(enabled)
        self._select_path_btn.setEnabled(enabled)
        self._download_model_btn.setEnabled(enabled)
        self._delete_model_btn.setEnabled(enabled)
        self._refresh_model_btn.setEnabled(enabled)
        self._reset_btn.setEnabled(enabled)
        self._save_btn.setEnabled(enabled)
        self._cancel_btn.setEnabled(enabled)

    def _show_resource_message(
        self,
        title: str,
        text: str,
        informative_text: str,
        icon: QMessageBox.Icon,
    ) -> None:
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle(title)
        msg_box.setText(text)
        if informative_text:
            msg_box.setInformativeText(informative_text)
        msg_box.setIcon(icon)
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg_box.setStyleSheet(_MESSAGE_BOX_STYLESHEET)
        msg_box.exec()

    def _confirm_delete_model(self, target_directory: Path) -> bool:
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Delete Model")
        msg_box.setText(f"Delete the selected ASR model files from {target_directory}?")
        msg_box.setInformativeText(
            "MyASR only removes files it manages for Qwen ASR. Other files in this "
            "directory will be left untouched."
        )
        msg_box.setIcon(QMessageBox.Icon.Warning)
        msg_box.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel
        )
        msg_box.setDefaultButton(QMessageBox.StandardButton.Cancel)
        msg_box.setStyleSheet(_MESSAGE_BOX_STYLESHEET)
        return msg_box.exec() == QMessageBox.StandardButton.Yes

    def _is_active_model_directory(self, directory: Path) -> bool:
        if not self._active_model_directory:
            return False
        return self._normalize_path_for_compare(str(directory)) == self._active_model_directory

    def _append_resource_status(
        self,
        repo_id: str,
        target_directory: Path,
        custom_path_selected: bool,
    ) -> None:
        model_display = self._asr_model_combo.currentText()
        location_label = "Custom directory" if custom_path_selected else "Default directory"
        self._append_status(f"Model: {model_display}")
        self._append_status(f"{location_label}: {target_directory}")

        if target_directory.exists():
            try:
                validate_model_directory(repo_id, target_directory)
            except ModelResourceError as exc:
                self._append_status(str(exc), is_error=True)
                if custom_path_selected:
                    self._append_status(
                        "Download the selected model into this directory, or clear the field "
                        "to use the default location."
                    )
                else:
                    self._append_status(
                        "Delete the incomplete files or download the model again into the "
                        "default directory."
                    )
                return

            self._append_status(f"{model_display} is ready in {target_directory}.")
            return

        if custom_path_selected:
            self._append_status(
                f"Custom model directory does not exist yet: {target_directory}",
                is_error=True,
            )
            self._append_status(
                "Download the selected model into this path before saving it for startup use."
            )
            return

        self._append_status(
            f"No managed local copy was found in the default directory: {target_directory}",
            is_error=True,
        )
        cache_snapshot = find_hf_cache_snapshot(repo_id)
        if cache_snapshot is None:
            self._append_status("Click Download to save a local copy into the default directory.")
            return

        try:
            validate_model_directory(repo_id, cache_snapshot)
        except ModelResourceError as exc:
            self._append_status(
                f"A Hugging Face cache snapshot was found but it is incomplete: {cache_snapshot}",
                is_error=True,
            )
            self._append_status(str(exc), is_error=True)
            return

        self._append_status(f"Cached Hugging Face snapshot detected: {cache_snapshot}")
        self._append_status(
            "Startup can still use the cached model until you download a managed local copy."
        )

    def _on_select_file_path(self) -> None:
        start_directory = self._current_target_directory()
        if not start_directory.exists():
            start_directory = (
                start_directory.parent if start_directory.parent.exists() else Path.cwd()
            )

        selected_directory = QFileDialog.getExistingDirectory(
            self,
            "Select ASR Model Directory",
            str(start_directory),
        )
        if selected_directory:
            self._model_path_edit.setText(selected_directory)

    def _on_download_model(self) -> None:
        if self._download_worker is not None and self._download_worker.isRunning():
            return

        target_directory = self._current_target_directory()
        if target_directory.exists() and not target_directory.is_dir():
            message = f"Model path must be a directory, not a file: {target_directory}"
            self._append_status(message, is_error=True)
            self._show_resource_message(
                title="Invalid Model Path",
                text="MyASR can only download ASR models into a directory.",
                informative_text=message,
                icon=QMessageBox.Icon.Critical,
            )
            return

        self._model_status_text.clear()
        repo_id = self._current_model_repo_id()
        spec = get_model_spec(repo_id)
        size_gb = spec.download_size_mb / 1000
        self._append_status(
            f"Preparing download of {spec.display_name} (~{size_gb:.1f} GB) "
            f"into {target_directory}..."
        )
        self._set_resource_controls_enabled(False)
        self._cancel_download_btn.show()

        self._download_worker = _DownloadWorker(
            self._current_model_repo_id(),
            str(target_directory),
        )
        self._download_worker.progress.connect(self._append_status)
        self._download_worker.finished_ok.connect(self._on_download_finished)
        self._download_worker.finished_err.connect(self._on_download_failed)
        self._download_worker.finished_cancelled.connect(self._on_download_cancelled)
        self._download_worker.finished.connect(self._on_download_complete_cleanup)
        self._download_worker.start()

    def _on_cancel_download(self) -> None:
        if self._download_worker is None or not self._download_worker.isRunning():
            return
        self._download_worker.requestInterruption()
        self._cancel_download_btn.setEnabled(False)
        self._append_status("Cancellation requested — waiting for download to stop...")

    def _on_download_finished(self, repo_id: str, target_directory: str) -> None:
        self._resource_state_requires_restart = True
        self._update_restart_label()
        self._model_status_text.clear()
        self._append_status(f"Download complete: {target_directory}")
        self._append_resource_status(
            repo_id=repo_id,
            target_directory=Path(target_directory),
            custom_path_selected=bool(self._current_custom_model_path()),
        )

    def _on_download_failed(self, message: str) -> None:
        self._append_status(message, is_error=True)
        self._show_resource_message(
            title="Download Failed",
            text="MyASR could not download the selected ASR model.",
            informative_text=message,
            icon=QMessageBox.Icon.Critical,
        )

    def _on_download_cancelled(self) -> None:
        self._append_status("Download cancelled.")

    def _on_download_complete_cleanup(self) -> None:
        self._set_resource_controls_enabled(True)
        self._cancel_download_btn.hide()
        self._cancel_download_btn.setEnabled(True)
        if self._download_worker is None:
            return

        self._download_worker.wait()
        self._download_worker.deleteLater()
        self._download_worker = None

    def _on_delete_model(self) -> None:
        target_directory = self._current_target_directory()
        if self._is_active_model_directory(target_directory):
            message = (
                "The selected model directory is currently in use. Restart MyASR before "
                "deleting these files."
            )
            self._append_status(message, is_error=True)
            self._show_resource_message(
                title="Model In Use",
                text="MyASR cannot delete the model files that are currently loaded.",
                informative_text=message,
                icon=QMessageBox.Icon.Warning,
            )
            return

        if not self._confirm_delete_model(target_directory):
            return

        try:
            report = delete_model_artifacts(target_directory)
        except ModelResourceError as exc:
            self._append_status(str(exc), is_error=True)
            self._show_resource_message(
                title="Delete Failed",
                text="MyASR could not remove the selected ASR model files.",
                informative_text=str(exc),
                icon=QMessageBox.Icon.Critical,
            )
            return

        self._model_status_text.clear()
        if report.removed_entries:
            self._append_status(
                f"Removed {len(report.removed_entries)} managed model entries from "
                f"{target_directory}."
            )
            if report.remaining_entries:
                self._append_status(
                    f"Preserved other files: {', '.join(report.remaining_entries)}"
                )
            elif report.removed_directory:
                self._append_status("Removed the now-empty model directory.")
            self._resource_state_requires_restart = True
            self._update_restart_label()
        else:
            self._append_status(f"No MyASR-managed model files were found in {target_directory}.")

        self._append_resource_status(
            repo_id=self._current_model_repo_id(),
            target_directory=target_directory,
            custom_path_selected=bool(self._current_custom_model_path()),
        )

    def _on_refresh_model(self) -> None:
        self._model_status_text.clear()
        self._append_resource_status(
            repo_id=self._current_model_repo_id(),
            target_directory=self._current_target_directory(),
            custom_path_selected=bool(self._current_custom_model_path()),
        )

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
        self._pre_buffer.setValue(config.pre_buffer_ms)
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

        self._model_path_edit.setText(config.asr_model_local_path)
        self._update_resource_path_placeholder()
        self._update_restart_label()
        self._on_refresh_model()

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
            pre_buffer_ms=self._pre_buffer.value(),
            max_history=self._max_history.value(),
            overlay_opacity=self._opacity.value() / 100.0,
            overlay_font_size_jp=self._font_size_jp.value(),
            enable_vocab_highlight=self._vocab_highlight_check.isChecked(),
            enable_grammar_highlight=self._grammar_highlight_check.isChecked(),
            asr_model=self._current_model_repo_id(),
            asr_model_local_path=self._current_custom_model_path(),
            sample_rate=self._config.sample_rate,
            overlay_width=self._config.overlay_width,
            overlay_height=self._config.overlay_height,
            jlpt_colors={
                key: btn.property("hex_color") or DEFAULT_JLPT_COLORS.get(key, "#FFFFFF")
                for key, btn in self._jlpt_color_buttons.items()
            },
            profiling=self._config.profiling,
        )

    def _on_save(self) -> None:
        repo_id = self._current_model_repo_id()
        custom_model_path = self._current_custom_model_path()
        if custom_model_path:
            try:
                validate_model_directory(repo_id, custom_model_path)
            except ModelResourceError as exc:
                self._append_status(str(exc), is_error=True)
                self._show_resource_message(
                    title="Model Directory Not Ready",
                    text="Download the selected ASR model before saving a custom directory.",
                    informative_text=str(exc),
                    icon=QMessageBox.Icon.Warning,
                )
                return
        else:
            default_dir = default_model_directory(repo_id).expanduser().resolve(strict=False)
            if not default_dir.exists():
                cache_snapshot = find_hf_cache_snapshot(repo_id)
                if cache_snapshot is None:
                    self._append_status(
                        f"No model files found at {default_dir} and no HF cache available.",
                        is_error=True,
                    )
                    self._show_resource_message(
                        title="No Model Available",
                        text=(
                            "No local model files were found for the selected ASR model. "
                            "Download the model first, or set a custom directory."
                        ),
                        informative_text=str(default_dir),
                        icon=QMessageBox.Icon.Warning,
                    )
                    return

        new_config = self._collect_config()
        save_config(new_config)
        self._config = new_config
        self._update_restart_label()
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

        msg_box.setStyleSheet(_MESSAGE_BOX_STYLESHEET)

        result = msg_box.exec()
        if result == QMessageBox.StandardButton.Reset:
            default_config = AppConfig()
            self._populate_from_config(default_config)
            logger.info("SettingsDialog: settings reset to defaults")
