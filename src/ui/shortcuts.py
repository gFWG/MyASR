"""Global shortcut manager for system-wide hotkeys using pynput.

Uses ``pynput.keyboard.Listener`` with manual key-set tracking
rather than ``keyboard.HotKey``, because ``HotKey.parse`` returns
``KeyCode.from_vk(...)`` for non-modifier special keys (arrows, etc.)
while ``listener.canonical(key)`` returns ``Key`` enum members —
the two never compare equal, so arrow-key combos silently fail.

The manual approach normalises every key to a comparable form and
checks pressed-key sets against registered shortcuts directly.
"""

import logging
from typing import Callable

from pynput import keyboard
from PySide6.QtCore import QObject, QTimer, Signal, Slot

from src.config import AppConfig

logger = logging.getLogger(__name__)

_MODIFIER_MAP: dict[str, keyboard.Key] = {
    "ctrl": keyboard.Key.ctrl,
    "alt": keyboard.Key.alt,
    "shift": keyboard.Key.shift,
    "win": keyboard.Key.cmd,
    "meta": keyboard.Key.cmd,
    "super": keyboard.Key.cmd,
}

_SPECIAL_KEY_MAP: dict[str, keyboard.Key] = {
    "left": keyboard.Key.left,
    "right": keyboard.Key.right,
    "up": keyboard.Key.up,
    "down": keyboard.Key.down,
    "return": keyboard.Key.enter,
    "enter": keyboard.Key.enter,
    "space": keyboard.Key.space,
    "backspace": keyboard.Key.backspace,
    "delete": keyboard.Key.delete,
    "del": keyboard.Key.delete,
    "escape": keyboard.Key.esc,
    "esc": keyboard.Key.esc,
    "tab": keyboard.Key.tab,
    "home": keyboard.Key.home,
    "end": keyboard.Key.end,
    "pageup": keyboard.Key.page_up,
    "pagedown": keyboard.Key.page_down,
    "insert": keyboard.Key.insert,
    "ins": keyboard.Key.insert,
    **{f"f{i}": getattr(keyboard.Key, f"f{i}") for i in range(1, 13)},
}


def _normalise_key(
    key: keyboard.Key | keyboard.KeyCode,
) -> keyboard.Key | keyboard.KeyCode:
    """Normalise a key to a comparable canonical form.

    Modifier variants (e.g. ``Key.ctrl_l``, ``Key.ctrl_r``) are folded
    into their generic form (``Key.ctrl``).  ``KeyCode`` instances are
    lower-cased.  ``Key`` enum members for non-modifier special keys
    are returned as-is.
    """
    _MODIFIER_FOLD: dict[keyboard.Key, keyboard.Key] = {
        keyboard.Key.ctrl_l: keyboard.Key.ctrl,
        keyboard.Key.ctrl_r: keyboard.Key.ctrl,
        keyboard.Key.alt_l: keyboard.Key.alt,
        keyboard.Key.alt_r: keyboard.Key.alt,
        keyboard.Key.alt_gr: keyboard.Key.alt,
        keyboard.Key.shift_l: keyboard.Key.shift,
        keyboard.Key.shift_r: keyboard.Key.shift,
        keyboard.Key.cmd_l: keyboard.Key.cmd,
        keyboard.Key.cmd_r: keyboard.Key.cmd,
    }
    if isinstance(key, keyboard.Key):
        return _MODIFIER_FOLD.get(key, key)
    # KeyCode — lower-case the char if present
    if isinstance(key, keyboard.KeyCode) and key.char is not None:
        return keyboard.KeyCode.from_char(key.char.lower())
    return key


def _parse_shortcut(key_string: str) -> frozenset[keyboard.Key | keyboard.KeyCode]:
    """Parse a Qt-style shortcut string into a frozenset of normalised keys.

    Examples::

        "Ctrl+Left"  → frozenset({Key.ctrl, Key.left})
        "Ctrl+T"     → frozenset({Key.ctrl, KeyCode.from_char('t')})

    Raises:
        ValueError: If a part of the key string is unrecognised.
    """
    parts = key_string.split("+")
    keys: list[keyboard.Key | keyboard.KeyCode] = []
    for part in parts:
        lower = part.strip().lower()
        if lower in _MODIFIER_MAP:
            keys.append(_MODIFIER_MAP[lower])
        elif lower in _SPECIAL_KEY_MAP:
            keys.append(_SPECIAL_KEY_MAP[lower])
        elif len(lower) == 1 and lower.isalnum():
            keys.append(keyboard.KeyCode.from_char(lower))
        else:
            raise ValueError(f"Unrecognised key part: {part!r} in {key_string!r}")
    return frozenset(keys)


class _RegisteredHotkey:
    """A shortcut definition with its expected key set and callback."""

    __slots__ = ("keys", "callback", "label")

    def __init__(
        self,
        keys: frozenset[keyboard.Key | keyboard.KeyCode],
        callback: Callable[[], None],
        label: str,
    ) -> None:
        self.keys = keys
        self.callback = callback
        self.label = label


class GlobalShortcutManager(QObject):
    """System-wide hotkey manager using pynput.

    Tracks currently-pressed keys and compares against registered
    shortcut sets.  Keys are normalised through ``_normalise_key``
    so that ``Key.ctrl_l`` matches ``Key.ctrl``, arrow keys compare
    correctly, etc.

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
        self._hotkeys: list[_RegisteredHotkey] = []
        self._pressed: set[keyboard.Key | keyboard.KeyCode] = set()
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
        """Build registered hotkey definitions from the config."""
        mapping: list[tuple[str, str]] = [
            (config.shortcut_toggle_display, "_emit_toggle_display"),
            (config.shortcut_prev_sentence, "_emit_prev_sentence"),
            (config.shortcut_next_sentence, "_emit_next_sentence"),
        ]
        self._hotkeys = []
        for key_string, slot_name in mapping:
            try:
                keys = _parse_shortcut(key_string)
                hotkey = _RegisteredHotkey(
                    keys=keys,
                    callback=self._make_callback(slot_name),
                    label=f"{key_string} -> {slot_name}",
                )
                self._hotkeys.append(hotkey)
                logger.debug("Registered hotkey %r -> %s", key_string, slot_name)
            except ValueError:
                logger.warning("Could not parse shortcut %r — skipping", key_string)

    def _on_press(self, key: keyboard.Key | keyboard.KeyCode | None) -> None:
        """Handle key-press events from the listener."""
        if key is None:
            return
        normalised = _normalise_key(key)
        already_held = normalised in self._pressed
        self._pressed.add(normalised)
        if already_held:
            return
        logger.debug("Key pressed: %s (normalised: %s)", key, normalised)
        for hotkey in self._hotkeys:
            if hotkey.keys == self._pressed:
                hotkey.callback()

    def _on_release(self, key: keyboard.Key | keyboard.KeyCode | None) -> None:
        """Handle key-release events from the listener."""
        if key is None:
            return
        normalised = _normalise_key(key)
        self._pressed.discard(normalised)
        logger.debug("Key released: %s (normalised: %s)", key, normalised)

    def start(self) -> None:
        """Start listening for global hotkeys."""
        if self._listener is not None:
            logger.warning("GlobalShortcutManager.start() called while already running")
            return
        self._pressed.clear()
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
        self._pressed.clear()
        logger.info("GlobalShortcutManager stopped")

    def update_shortcuts(self, config: AppConfig) -> None:
        """Rebuild hotkeys from *config* and restart the listener."""
        self._config = config
        self.stop()
        self._build_hotkeys(config)
        self.start()
