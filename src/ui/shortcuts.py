"""Global shortcut manager for system-wide hotkeys using pynput.

Uses ``pynput.keyboard.Listener`` with ``keyboard.HotKey`` objects
rather than the higher-level ``GlobalHotKeys`` wrapper, because the
latter silently fails on Windows 11 due to key-state de-sync and
canonical-key mismatches.  The manual approach lets us call
``listener.canonical(key)`` for robust matching on every platform.
"""

import logging
from typing import Callable

from pynput import keyboard
from PySide6.QtCore import QObject, QTimer, Signal, Slot

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

    Uses ``keyboard.Listener`` + ``keyboard.HotKey`` for reliable
    key matching on Windows 11 (avoids ``GlobalHotKeys`` silent-failure
    bug).

    Callbacks are dispatched to the Qt main thread via QTimer.singleShot
    — no direct Qt calls from the pynput listener thread.
    Hotkeys pass through to other applications (suppress=False).
    """

    toggle_display_triggered = Signal()
    prev_sentence_triggered = Signal()
    next_sentence_triggered = Signal()

    def __init__(self, config: AppConfig, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._config = config
        self._listener: keyboard.Listener | None = None
        self._hotkeys: list[keyboard.HotKey] = []
        self._hotkey_labels: dict[int, str] = {}
        self._build_hotkeys(config)

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
        slot_method = getattr(self, slot_name)

        def _callback() -> None:
            logger.info("Shortcut activated: %s", slot_name)
            QTimer.singleShot(0, slot_method)

        return _callback

    def _build_hotkeys(self, config: AppConfig) -> None:
        """Build ``keyboard.HotKey`` instances from the config."""
        mapping: list[tuple[str, str]] = [
            (config.shortcut_toggle_display, "_emit_toggle_display"),
            (config.shortcut_prev_sentence, "_emit_prev_sentence"),
            (config.shortcut_next_sentence, "_emit_next_sentence"),
        ]
        self._hotkeys = []
        self._hotkey_labels = {}
        for key_string, slot_name in mapping:
            try:
                pynput_str = _qt_key_to_pynput(key_string)
                parsed_keys = keyboard.HotKey.parse(pynput_str)
                hotkey = keyboard.HotKey(parsed_keys, self._make_callback(slot_name))
                self._hotkeys.append(hotkey)
                self._hotkey_labels[id(hotkey)] = f"{pynput_str} -> {slot_name}"
                logger.debug("Registered hotkey %r -> %s", pynput_str, slot_name)
            except ValueError:
                logger.warning("Could not convert shortcut %r — skipping", key_string)

    def _on_press(self, key: keyboard.Key | keyboard.KeyCode | None) -> None:
        """Handle key-press events from the listener."""
        if self._listener is None or key is None:
            return
        canonical = self._listener.canonical(key)
        logger.debug("Key pressed: %s (canonical: %s)", key, canonical)
        for hotkey in self._hotkeys:
            hotkey.press(canonical)

    def _on_release(self, key: keyboard.Key | keyboard.KeyCode | None) -> None:
        """Handle key-release events from the listener."""
        if self._listener is None or key is None:
            return
        canonical = self._listener.canonical(key)
        logger.debug("Key released: %s (canonical: %s)", key, canonical)
        for hotkey in self._hotkeys:
            hotkey.release(canonical)

    def start(self) -> None:
        """Start listening for global hotkeys."""
        if self._listener is not None:
            logger.warning("GlobalShortcutManager.start() called while already running")
            return
        self._listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
            suppress=False,
        )
        self._listener.start()
        logger.info("GlobalShortcutManager started with %d hotkeys", len(self._hotkeys))

    def stop(self) -> None:
        """Stop listening for global hotkeys."""
        if self._listener is None:
            return
        self._listener.stop()
        self._listener.join()
        self._listener = None
        logger.info("GlobalShortcutManager stopped")

    def update_shortcuts(self, config: AppConfig) -> None:
        """Rebuild hotkeys from *config* and restart the listener."""
        self._config = config
        self.stop()
        self._build_hotkeys(config)
        self.start()
