from unittest.mock import MagicMock

import pytest
from PySide6.QtWidgets import QApplication

from src.config import AppConfig
from src.ui.shortcuts import GlobalShortcutManager, _qt_key_to_pynput


def test_key_conversion_ctrl_left() -> None:
    assert _qt_key_to_pynput("Ctrl+Left") == "<ctrl>+<left>"


def test_key_conversion_ctrl_t() -> None:
    assert _qt_key_to_pynput("Ctrl+T") == "<ctrl>+t"


def test_key_conversion_ctrl_right() -> None:
    assert _qt_key_to_pynput("Ctrl+Right") == "<ctrl>+<right>"


def test_key_conversion_f5() -> None:
    assert _qt_key_to_pynput("F5") == "<f5>"


def test_key_conversion_shift_alt_x() -> None:
    assert _qt_key_to_pynput("Shift+Alt+x") == "<shift>+<alt>+x"


def test_key_conversion_invalid_raises() -> None:
    with pytest.raises(ValueError, match="Unrecognized"):
        _qt_key_to_pynput("Ctrl+Bogus")


def test_signals_defined(qapp: QApplication) -> None:
    config = AppConfig()
    manager = GlobalShortcutManager(config)
    manager.toggle_display_triggered.connect(lambda: None)
    manager.prev_sentence_triggered.connect(lambda: None)
    manager.next_sentence_triggered.connect(lambda: None)


def test_lifecycle_start_stop(qapp: QApplication, mocker: MagicMock) -> None:
    mock_hotkeys_instance = MagicMock()
    mock_cls = mocker.patch(
        "src.ui.shortcuts.keyboard.GlobalHotKeys", return_value=mock_hotkeys_instance
    )

    config = AppConfig()
    manager = GlobalShortcutManager(config)
    manager.start()

    mock_cls.assert_called_once()
    mock_hotkeys_instance.start.assert_called_once()

    manager.stop()
    mock_hotkeys_instance.stop.assert_called_once()
    mock_hotkeys_instance.join.assert_called_once()


def test_lifecycle_start_idempotent(qapp: QApplication, mocker: MagicMock) -> None:
    mock_hotkeys_instance = MagicMock()
    mocker.patch("src.ui.shortcuts.keyboard.GlobalHotKeys", return_value=mock_hotkeys_instance)

    config = AppConfig()
    manager = GlobalShortcutManager(config)
    manager.start()
    manager.start()

    assert mock_hotkeys_instance.start.call_count == 1


def test_update_shortcuts_restarts_listener(qapp: QApplication, mocker: MagicMock) -> None:
    mock_instance_1 = MagicMock()
    mock_instance_2 = MagicMock()
    mock_cls = mocker.patch(
        "src.ui.shortcuts.keyboard.GlobalHotKeys",
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
