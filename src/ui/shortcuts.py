"""Global shortcut manager for system-wide hotkeys using pynput."""

import logging
from typing import Callable

from pynput import keyboard
from PySide6.QtCore import QMetaObject, QObject, Qt, Signal, Slot

from src.config import AppConfig

logger = logging.getLogger(__name__)

_MODIFIER_MAP: dict[str, str] = {
    "ctrl": "<ctrl>",
    "alt": "<alt>",
    "shift": "<shift>",
    "win": "<cmd>",
    "meta": "<cmd>",
    "super": "<cmd>",
}

_SPECIAL_KEY_MAP: dict[str, str] = {
    "left": "<left>",
    "right": "<right>",
    "up": "<up>",
    "down": "<down>",
    "return": "<enter>",
    "enter": "<enter>",
    "space": "<space>",
    "backspace": "<backspace>",
    "delete": "<delete>",
    "del": "<delete>",
    "escape": "<esc>",
    "esc": "<esc>",
    "tab": "<tab>",
    "home": "<home>",
    "end": "<end>",
    "pageup": "<page_up>",
    "pagedown": "<page_down>",
    "insert": "<insert>",
    "ins": "<insert>",
    **{f"f{i}": f"<f{i}>" for i in range(1, 13)},
}


def _qt_key_to_pynput(key_string: str) -> str:
    """Convert Qt-style key string to pynput GlobalHotKeys format string.

    Converts "Ctrl+Left" → "<ctrl>+<left>", "Ctrl+T" → "<ctrl>+t".

    Raises:
        ValueError: if a part of the key string is unrecognized.
    """
    parts = key_string.split("+")
    result_parts: list[str] = []

    for part in parts:
        lower = part.strip().lower()
        if lower in _MODIFIER_MAP:
            result_parts.append(_MODIFIER_MAP[lower])
        elif lower in _SPECIAL_KEY_MAP:
            result_parts.append(_SPECIAL_KEY_MAP[lower])
        elif len(lower) == 1 and lower.isalnum():
            result_parts.append(lower)
        else:
            raise ValueError(f"Unrecognized key part: {part!r} in {key_string!r}")

    return "+".join(result_parts)


class GlobalShortcutManager(QObject):
    """System-wide hotkey manager using pynput.

    Callbacks are dispatched to the Qt main thread via QMetaObject.invokeMethod
    (QueuedConnection) — no direct Qt calls from the pynput listener thread.
    Hotkeys pass through to other applications (suppress=False).
    """

    toggle_display_triggered = Signal()
    prev_sentence_triggered = Signal()
    next_sentence_triggered = Signal()

    def __init__(self, config: AppConfig, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._config = config
        self._hotkeys: keyboard.GlobalHotKeys | None = None
        self._hotkey_dict: dict[str, Callable[[], None]] = {}
        self._build_hotkey_dict(config)

    @Slot()
    def _emit_toggle_display(self) -> None:
        self.toggle_display_triggered.emit()

    @Slot()
    def _emit_prev_sentence(self) -> None:
        self.prev_sentence_triggered.emit()

    @Slot()
    def _emit_next_sentence(self) -> None:
        self.next_sentence_triggered.emit()

    def _make_callback(self, slot_name: str) -> Callable[[], None]:
        """Return a pynput callback that safely invokes a Qt slot on the main thread."""

        def _callback() -> None:
            QMetaObject.invokeMethod(self, slot_name, Qt.ConnectionType.QueuedConnection)

        return _callback

    def _build_hotkey_dict(self, config: AppConfig) -> None:
        mapping: list[tuple[str, str]] = [
            (config.shortcut_toggle_display, "_emit_toggle_display"),
            (config.shortcut_prev_sentence, "_emit_prev_sentence"),
            (config.shortcut_next_sentence, "_emit_next_sentence"),
        ]
        self._hotkey_dict = {}
        for key_string, slot_name in mapping:
            try:
                pynput_key = _qt_key_to_pynput(key_string)
                self._hotkey_dict[pynput_key] = self._make_callback(slot_name)
                logger.debug("Registered hotkey %r -> %s", pynput_key, slot_name)
            except ValueError:
                logger.warning("Could not convert shortcut %r — skipping", key_string)

    def start(self) -> None:
        if self._hotkeys is not None:
            logger.warning("GlobalShortcutManager.start() called while already running")
            return
        self._hotkeys = keyboard.GlobalHotKeys(self._hotkey_dict, suppress=False)
        self._hotkeys.start()
        logger.info("GlobalShortcutManager started with %d hotkeys", len(self._hotkey_dict))

    def stop(self) -> None:
        if self._hotkeys is None:
            return
        self._hotkeys.stop()
        self._hotkeys.join()
        self._hotkeys = None
        logger.info("GlobalShortcutManager stopped")

    def update_shortcuts(self, config: AppConfig) -> None:
        self._config = config
        self.stop()
        self._build_hotkey_dict(config)
        self.start()
