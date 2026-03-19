"""Tests for src.ui.settings.SettingsDialog."""

from __future__ import annotations

import unittest.mock as mock
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from src.asr.model_resources import get_model_spec
from src.config import DEFAULT_JLPT_COLORS, AppConfig
from src.exceptions import ModelResourceError
from src.ui.settings import SettingsDialog


@pytest.fixture()
def default_config() -> AppConfig:
    return AppConfig()


@pytest.fixture()
def dialog(qapp: QApplication, default_config: AppConfig) -> SettingsDialog:
    return SettingsDialog(default_config)


def _create_model_directory(repo_id: str, directory: Path) -> Path:
    spec = get_model_spec(repo_id)
    directory.mkdir(parents=True, exist_ok=True)
    for file_name in spec.required_files:
        (directory / file_name).write_bytes(b"ready")
    return directory


def test_settings_dialog_has_three_tabs(dialog: SettingsDialog) -> None:
    assert dialog._tabs.count() == 3


def test_resource_tab_has_analysis_replace_buttons(dialog: SettingsDialog) -> None:
    assert dialog._replace_vocab_btn.text() == "Replace Vocabulary (CSV)"
    assert dialog._replace_grammar_btn.text() == "Replace Grammar (JSON)"


def test_widgets_populate_from_config(qapp: QApplication, tmp_path: Path) -> None:
    config = AppConfig(
        user_jlpt_level=2,
        overlay_opacity=0.50,
        overlay_font_size_jp=20,
        enable_vocab_highlight=False,
        enable_grammar_highlight=False,
        vad_threshold=0.6,
        vad_min_silence_ms=400,
        vad_min_speech_ms=500,
        asr_model="Qwen/Qwen3-ASR-1.7B",
        asr_model_local_path=str(tmp_path / "local-model"),
    )
    d = SettingsDialog(config)
    assert d._jlpt_level.value() == 2
    assert d._opacity.value() == 50
    assert d._font_size_jp.value() == 20
    assert d._vocab_highlight_check.isChecked() is False
    assert d._grammar_highlight_check.isChecked() is False
    assert d._vad_threshold.value() == pytest.approx(0.6)
    assert d._vad_min_silence.value() == 400
    assert d._vad_min_speech.value() == 500
    assert d._asr_model_combo.currentData() == "Qwen/Qwen3-ASR-1.7B"
    assert d._model_path_edit.text() == str(tmp_path / "local-model")


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


def test_jlpt_level_selector_range(dialog: SettingsDialog) -> None:
    """JlptLevelSelector should accept values 1-5 (N1-N5)."""
    # Test all valid values
    for level in [1, 2, 3, 4, 5]:
        dialog._jlpt_level.setValue(level)
        assert dialog._jlpt_level.value() == level


def test_opacity_range(dialog: SettingsDialog) -> None:
    assert dialog._opacity._slider.minimum() == 10
    assert dialog._opacity._slider.maximum() == 100


def test_vad_threshold_range(dialog: SettingsDialog) -> None:
    assert dialog._vad_threshold._spinbox.minimum() == pytest.approx(0.1)
    assert dialog._vad_threshold._spinbox.maximum() == pytest.approx(0.95)


def test_vad_min_silence_range(dialog: SettingsDialog) -> None:
    assert dialog._vad_min_silence._slider.minimum() == 100
    assert dialog._vad_min_silence._slider.maximum() == 2000


def test_vad_min_speech_range(dialog: SettingsDialog) -> None:
    assert dialog._vad_min_speech._slider.minimum() == 100
    assert dialog._vad_min_speech._slider.maximum() == 2000


def test_collect_config_returns_appconfig(dialog: SettingsDialog) -> None:
    dialog._model_path_edit.setText("/tmp/my-model")
    config = dialog._collect_config()
    assert isinstance(config, AppConfig)
    assert config.asr_model_local_path == "/tmp/my-model"


def test_collect_config_preserves_sample_rate(qapp: QApplication) -> None:
    """Test that non-UI fields like sample_rate are preserved in _collect_config."""
    config = AppConfig(sample_rate=48000)
    d = SettingsDialog(config)
    collected = d._collect_config()
    assert collected.sample_rate == 48000


def test_on_save_does_not_close_dialog(qapp: QApplication) -> None:
    config = AppConfig()
    d = SettingsDialog(config)
    d.show()
    with mock.patch("src.ui.settings.save_config"):
        d._on_save()
    assert d.isVisible()


def test_on_save_keeps_restart_label_visible_for_resource_change(
    qapp: QApplication, tmp_path: Path
) -> None:
    config = AppConfig()
    d = SettingsDialog(config, runtime_config=config)
    model_dir = _create_model_directory(config.asr_model, tmp_path / "model")
    d._model_path_edit.setText(str(model_dir))

    with mock.patch("src.ui.settings.save_config"):
        d._on_save()

    assert d._restart_label.isHidden() is False


def test_on_save_blocks_invalid_custom_model_directory(qapp: QApplication, tmp_path: Path) -> None:
    config = AppConfig()
    d = SettingsDialog(config)
    d._model_path_edit.setText(str(tmp_path / "missing-model"))

    with (
        mock.patch("src.ui.settings.save_config") as mock_save,
        mock.patch.object(d, "_show_resource_message") as mock_message,
    ):
        d._on_save()

    mock_save.assert_not_called()
    mock_message.assert_called_once()


def test_on_save_blocks_model_resource_error(qapp: QApplication) -> None:
    config = AppConfig()
    d = SettingsDialog(config)
    d._model_path_edit.setText("/tmp/bad-model")

    with (
        mock.patch(
            "src.ui.settings.validate_model_directory",
            side_effect=ModelResourceError("broken model directory"),
        ),
        mock.patch("src.ui.settings.save_config") as mock_save,
        mock.patch.object(d, "_show_resource_message") as mock_message,
    ):
        d._on_save()

    mock_save.assert_not_called()
    mock_message.assert_called_once()


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


# ── Composite widget integration tests ──


def test_vad_threshold_slider_spinbox_sync(qapp: QApplication) -> None:
    """Test that moving the slider syncs with the spinbox for VAD threshold."""
    config = AppConfig(vad_threshold=0.5)
    d = SettingsDialog(config)
    # Move slider - slider uses integer scale (0.5 * 100 = 50)
    d._vad_threshold._slider.setValue(70)  # Should become 0.70
    assert d._vad_threshold.value() == pytest.approx(0.70)


def test_opacity_slider_spinbox_sync(qapp: QApplication) -> None:
    """Test that opacity slider and spinbox stay synchronized."""
    config = AppConfig(overlay_opacity=0.78)
    d = SettingsDialog(config)
    # Move slider
    d._opacity._slider.setValue(60)
    assert d._opacity.value() == 60
    assert d._opacity._spinbox.value() == 60


def test_max_history_slider_spinbox_sync(qapp: QApplication) -> None:
    """Test that max history slider and spinbox stay synchronized."""
    config = AppConfig(max_history=10)
    d = SettingsDialog(config)
    # Change via spinbox
    d._max_history._spinbox.setValue(25)
    assert d._max_history._slider.value() == 25
    assert d._max_history.value() == 25


def test_replace_vocab_success(
    dialog: SettingsDialog, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_csv = tmp_path / "source_vocab.csv"
    source_csv.write_text("id,pronBase,lemma,definition,level\n1,ア,あ,ah,N5")

    monkeypatch.setattr(
        "src.ui.settings.QFileDialog.getOpenFileName",
        lambda *args, **kwargs: (str(source_csv), ""),
    )

    replace_calls = []

    def mock_atomic_replace(source: Path, target: Path) -> None:
        replace_calls.append((source, target))

    monkeypatch.setattr(dialog, "_atomic_replace_file", mock_atomic_replace)

    dialog._on_replace_vocab()

    assert len(replace_calls) == 1
    assert replace_calls[0][0] == source_csv
    assert replace_calls[0][1] == Path("data/vocabulary.csv")
    assert dialog._resource_state_requires_restart is True
    assert dialog._restart_label.isHidden() is False
    assert "Replaced vocabulary list" in dialog._model_status_text.toPlainText()


def test_replace_grammar_success(
    dialog: SettingsDialog, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_json = tmp_path / "source_grammar.json"
    source_json.write_text(
        (
            '[{"id": "test_1", "word": "grammar", '
            '"re": "^test", "level": "N5", "description": "test"}]'
        )
    )

    monkeypatch.setattr(
        "src.ui.settings.QFileDialog.getOpenFileName",
        lambda *args, **kwargs: (str(source_json), ""),
    )

    replace_calls = []

    def mock_atomic_replace(source: Path, target: Path) -> None:
        replace_calls.append((source, target))

    monkeypatch.setattr(dialog, "_atomic_replace_file", mock_atomic_replace)

    dialog._on_replace_grammar()

    assert len(replace_calls) == 1
    assert replace_calls[0][0] == source_json
    assert replace_calls[0][1] == Path("data/grammar.json")
    assert dialog._resource_state_requires_restart is True
    assert dialog._restart_label.isHidden() is False
    assert "Replaced grammar rules" in dialog._model_status_text.toPlainText()


def test_replace_vocab_cancel_is_noop(
    dialog: SettingsDialog, monkeypatch: pytest.MonkeyPatch
) -> None:
    original_status = dialog._model_status_text.toPlainText()

    monkeypatch.setattr(
        "src.ui.settings.QFileDialog.getOpenFileName",
        lambda *args, **kwargs: ("", ""),
    )

    replace_called = False

    def mock_atomic_replace(source: Path, target: Path) -> None:
        nonlocal replace_called
        replace_called = True

    monkeypatch.setattr(dialog, "_atomic_replace_file", mock_atomic_replace)

    dialog._on_replace_vocab()

    assert replace_called is False
    assert dialog._resource_state_requires_restart is False
    assert dialog._model_status_text.toPlainText() == original_status


def test_replace_grammar_cancel_is_noop(
    dialog: SettingsDialog, monkeypatch: pytest.MonkeyPatch
) -> None:
    original_status = dialog._model_status_text.toPlainText()

    monkeypatch.setattr(
        "src.ui.settings.QFileDialog.getOpenFileName",
        lambda *args, **kwargs: ("", ""),
    )

    replace_called = False

    def mock_atomic_replace(source: Path, target: Path) -> None:
        nonlocal replace_called
        replace_called = True

    monkeypatch.setattr(dialog, "_atomic_replace_file", mock_atomic_replace)

    dialog._on_replace_grammar()

    assert replace_called is False
    assert dialog._resource_state_requires_restart is False
    assert dialog._model_status_text.toPlainText() == original_status


def test_replace_vocab_validation_failure(
    dialog: SettingsDialog, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_csv = tmp_path / "bad_vocab.csv"
    source_csv.write_text("wrong,format\n1,2")

    monkeypatch.setattr(
        "src.ui.settings.QFileDialog.getOpenFileName",
        lambda *args, **kwargs: (str(source_csv), ""),
    )

    replace_called = False

    def mock_atomic_replace(source: Path, target: Path) -> None:
        nonlocal replace_called
        replace_called = True

    monkeypatch.setattr(dialog, "_atomic_replace_file", mock_atomic_replace)
    show_calls: list[tuple[str, str, str, object]] = []

    def mock_show_resource_message(
        title: str, text: str, informative_text: str, icon: object
    ) -> None:
        show_calls.append((title, text, informative_text, icon))

    monkeypatch.setattr(dialog, "_show_resource_message", mock_show_resource_message)

    dialog._on_replace_vocab()

    assert not replace_called
    assert len(show_calls) == 1
    assert show_calls[0][0] == "Replace Failed"
    assert "could not replace the vocabulary list" in show_calls[0][1]
    assert "Failed to replace vocabulary list" in dialog._model_status_text.toPlainText()


def test_replace_grammar_validation_failure(
    dialog: SettingsDialog, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_json = tmp_path / "bad_grammar.json"
    source_json.write_text('{"not_an_array": true}')

    monkeypatch.setattr(
        "src.ui.settings.QFileDialog.getOpenFileName",
        lambda *args, **kwargs: (str(source_json), ""),
    )

    replace_called = False

    def mock_atomic_replace(source: Path, target: Path) -> None:
        nonlocal replace_called
        replace_called = True

    monkeypatch.setattr(dialog, "_atomic_replace_file", mock_atomic_replace)
    show_calls: list[tuple[str, str, str, object]] = []

    def mock_show_resource_message(
        title: str, text: str, informative_text: str, icon: object
    ) -> None:
        show_calls.append((title, text, informative_text, icon))

    monkeypatch.setattr(dialog, "_show_resource_message", mock_show_resource_message)

    dialog._on_replace_grammar()

    assert not replace_called
    assert len(show_calls) == 1
    assert show_calls[0][0] == "Replace Failed"
    assert "could not replace the grammar rules" in show_calls[0][1]
    assert "Failed to replace grammar rules" in dialog._model_status_text.toPlainText()
