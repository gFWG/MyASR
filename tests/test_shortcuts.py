from unittest.mock import MagicMock

import pytest
from pynput import keyboard
from PySide6.QtWidgets import QApplication

from src.config import AppConfig
from src.ui.shortcuts import (
    GlobalShortcutManager,
    _normalise_key,
    _parse_shortcut,
)

# --- _parse_shortcut tests ---


def test_parse_shortcut_ctrl_left() -> None:
    result = _parse_shortcut("Ctrl+Left")
    assert result == frozenset({keyboard.Key.ctrl, keyboard.Key.left})


def test_parse_shortcut_ctrl_t() -> None:
    result = _parse_shortcut("Ctrl+T")
    assert result == frozenset({keyboard.Key.ctrl, keyboard.KeyCode.from_char("t")})


def test_parse_shortcut_ctrl_right() -> None:
    result = _parse_shortcut("Ctrl+Right")
    assert result == frozenset({keyboard.Key.ctrl, keyboard.Key.right})


def test_parse_shortcut_f5() -> None:
    result = _parse_shortcut("F5")
    assert result == frozenset({keyboard.Key.f5})


def test_parse_shortcut_shift_alt_x() -> None:
    result = _parse_shortcut("Shift+Alt+x")
    assert result == frozenset(
        {keyboard.Key.shift, keyboard.Key.alt, keyboard.KeyCode.from_char("x")}
    )


def test_parse_shortcut_invalid_raises() -> None:
    with pytest.raises(ValueError, match="Unrecognised"):
        _parse_shortcut("Ctrl+Bogus")


# --- _normalise_key tests ---


def test_normalise_key_folds_ctrl_l_to_ctrl() -> None:
    assert _normalise_key(keyboard.Key.ctrl_l) == keyboard.Key.ctrl


def test_normalise_key_folds_ctrl_r_to_ctrl() -> None:
    assert _normalise_key(keyboard.Key.ctrl_r) == keyboard.Key.ctrl


def test_normalise_key_folds_shift_l_to_shift() -> None:
    assert _normalise_key(keyboard.Key.shift_l) == keyboard.Key.shift


def test_normalise_key_preserves_arrow_keys() -> None:
    assert _normalise_key(keyboard.Key.left) == keyboard.Key.left
    assert _normalise_key(keyboard.Key.right) == keyboard.Key.right


def test_normalise_key_lowercases_char() -> None:
    upper_t = keyboard.KeyCode.from_char("T")
    lower_t = keyboard.KeyCode.from_char("t")
    assert _normalise_key(upper_t) == lower_t


# --- GlobalShortcutManager tests ---


def test_signals_defined(qapp: QApplication) -> None:
    config = AppConfig()
    manager = GlobalShortcutManager(config)
    manager.toggle_display_triggered.connect(lambda: None)
    manager.prev_sentence_triggered.connect(lambda: None)
    manager.next_sentence_triggered.connect(lambda: None)


def test_lifecycle_start_stop(qapp: QApplication, mocker: MagicMock) -> None:
    mock_listener_instance = MagicMock()
    mock_cls = mocker.patch(
        "src.ui.shortcuts.keyboard.Listener", return_value=mock_listener_instance
    )

    config = AppConfig()
    manager = GlobalShortcutManager(config)
    manager.start()

    mock_cls.assert_called_once()
    mock_listener_instance.start.assert_called_once()

    manager.stop()
    mock_listener_instance.stop.assert_called_once()
    mock_listener_instance.join.assert_called_once()


def test_lifecycle_start_idempotent(qapp: QApplication, mocker: MagicMock) -> None:
    mock_listener_instance = MagicMock()
    mocker.patch("src.ui.shortcuts.keyboard.Listener", return_value=mock_listener_instance)

    config = AppConfig()
    manager = GlobalShortcutManager(config)
    manager.start()
    manager.start()

    assert mock_listener_instance.start.call_count == 1


def test_update_shortcuts_restarts_listener(qapp: QApplication, mocker: MagicMock) -> None:
    mock_instance_1 = MagicMock()
    mock_instance_2 = MagicMock()
    mock_cls = mocker.patch(
        "src.ui.shortcuts.keyboard.Listener",
        side_effect=[mock_instance_1, mock_instance_2],
    )

    config = AppConfig()
    manager = GlobalShortcutManager(config)
    manager.start()

    new_config = AppConfig(
        shortcut_prev_sentence="Ctrl+Up",
        shortcut_next_sentence="Ctrl+Down",
        shortcut_toggle_display="Ctrl+H",
    )
    manager.update_shortcuts(new_config)

    mock_instance_1.stop.assert_called_once()
    mock_instance_1.join.assert_called_once()
    assert mock_cls.call_count == 2
    mock_instance_2.start.assert_called_once()


def test_make_callback_uses_qtimer(qapp: QApplication, mocker: MagicMock) -> None:
    """The _make_callback method should use QTimer.singleShot for thread-safe dispatch."""
    mock_timer = mocker.patch("src.ui.shortcuts.QTimer")
    config = AppConfig()
    manager = GlobalShortcutManager(config)

    cb = manager._make_callback("_emit_toggle_display")
    cb()

    mock_timer.singleShot.assert_called_once_with(0, manager._emit_toggle_display)


def test_on_press_tracks_keys_and_triggers_hotkey(qapp: QApplication, mocker: MagicMock) -> None:
    """Pressing the correct key combination should trigger the hotkey callback."""
    mocker.patch("src.ui.shortcuts.keyboard.Listener", return_value=MagicMock())
    mock_timer = mocker.patch("src.ui.shortcuts.QTimer")

    config = AppConfig(shortcut_toggle_display="Ctrl+T")
    manager = GlobalShortcutManager(config)

    # Simulate Ctrl+T press
    manager._on_press(keyboard.Key.ctrl_l)
    manager._on_press(keyboard.KeyCode.from_char("t"))

    # Should have triggered the toggle callback via QTimer
    mock_timer.singleShot.assert_called_once()


def test_on_press_arrow_key_hotkey(qapp: QApplication, mocker: MagicMock) -> None:
    """Arrow key shortcuts (e.g. Ctrl+Left) should trigger correctly."""
    mocker.patch("src.ui.shortcuts.keyboard.Listener", return_value=MagicMock())
    mock_timer = mocker.patch("src.ui.shortcuts.QTimer")

    config = AppConfig(shortcut_prev_sentence="Ctrl+Left")
    manager = GlobalShortcutManager(config)

    # Simulate Ctrl+Left press
    manager._on_press(keyboard.Key.ctrl_l)
    manager._on_press(keyboard.Key.left)

    # Should have triggered the prev callback via QTimer
    assert mock_timer.singleShot.call_count >= 1


def test_on_release_removes_from_pressed(qapp: QApplication, mocker: MagicMock) -> None:
    """Key release should remove key from pressed set."""
    mocker.patch("src.ui.shortcuts.keyboard.Listener", return_value=MagicMock())

    config = AppConfig()
    manager = GlobalShortcutManager(config)

    manager._on_press(keyboard.Key.ctrl_l)
    assert keyboard.Key.ctrl in manager._pressed

    manager._on_release(keyboard.Key.ctrl_l)
    assert keyboard.Key.ctrl not in manager._pressed


def test_on_press_none_key_is_noop(qapp: QApplication, mocker: MagicMock) -> None:
    """Pressing None should be silently ignored."""
    mocker.patch("src.ui.shortcuts.keyboard.Listener", return_value=MagicMock())

    config = AppConfig()
    manager = GlobalShortcutManager(config)
    manager._on_press(None)

    assert len(manager._pressed) == 0


def test_builds_correct_number_of_hotkeys(qapp: QApplication) -> None:
    """Manager should build exactly 3 hotkeys (toggle, prev, next)."""
    config = AppConfig()
    manager = GlobalShortcutManager(config)
    assert len(manager._hotkeys) == 3


def test_hotkey_with_invalid_shortcut_skipped(qapp: QApplication) -> None:
    """An invalid shortcut string should be skipped without crashing."""
    config = AppConfig(shortcut_toggle_display="Ctrl+Bogus")
    manager = GlobalShortcutManager(config)
    # Only 2 valid hotkeys should remain (prev + next)
    assert len(manager._hotkeys) == 2


def test_partial_combo_does_not_trigger(qapp: QApplication, mocker: MagicMock) -> None:
    """Pressing only part of a combo should not trigger."""
    mocker.patch("src.ui.shortcuts.keyboard.Listener", return_value=MagicMock())
    mock_timer = mocker.patch("src.ui.shortcuts.QTimer")

    config = AppConfig(shortcut_toggle_display="Ctrl+T")
    manager = GlobalShortcutManager(config)

    # Only press Ctrl — should not trigger
    manager._on_press(keyboard.Key.ctrl_l)
    mock_timer.singleShot.assert_not_called()


def test_extra_keys_prevent_trigger(qapp: QApplication, mocker: MagicMock) -> None:
    """Pressing extra keys beyond the combo should not trigger."""
    mocker.patch("src.ui.shortcuts.keyboard.Listener", return_value=MagicMock())
    mock_timer = mocker.patch("src.ui.shortcuts.QTimer")

    config = AppConfig(shortcut_toggle_display="Ctrl+T")
    manager = GlobalShortcutManager(config)

    # Press Ctrl+Shift+T — should not trigger Ctrl+T
    manager._on_press(keyboard.Key.ctrl_l)
    manager._on_press(keyboard.Key.shift_l)
    manager._on_press(keyboard.KeyCode.from_char("t"))
    mock_timer.singleShot.assert_not_called()
