"""Context menu factory for the MyASR Japanese learning overlay.

Provides a shared menu creation function for both system tray and overlay
context menus, ensuring consistent styling and behavior.
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtWidgets import QMenu, QWidget

_MENU_STYLE = """
QMenu {
    background-color: rgba(30, 30, 30, 230);
    color: #EEEEEE;
    border: 1px solid rgba(255, 255, 255, 30);
    border-radius: 6px;
    padding: 4px 0px;
}
QMenu::item {
    padding: 6px 24px 6px 24px;
    background-color: transparent;
}
QMenu::item:selected {
    background-color: rgba(255, 255, 255, 40);
}
QMenu::separator {
    height: 1px;
    background-color: rgba(255, 255, 255, 30);
    margin: 4px 8px;
}
"""


def create_context_menu(
    parent: QWidget | None,
    on_settings: Callable[[], None],
    on_toggle: Callable[[], None],
    on_quit: Callable[[], None],
    overlay_visible: bool = True,
) -> QMenu:
    """Create a styled context menu with consistent items.

    Args:
        parent: The parent widget for the menu.
        on_settings: Callback for settings action.
        on_toggle: Callback for toggle overlay action.
        on_quit: Callback for quit action.
        overlay_visible: Current overlay visibility state, used to set
            dynamic toggle text.

    Returns:
        A styled QMenu with Settings, Toggle, and Quit actions.
    """
    menu = QMenu(parent)
    menu.setStyleSheet(_MENU_STYLE)

    settings_action = menu.addAction("Settings")
    settings_action.triggered.connect(on_settings)

    menu.addSeparator()

    toggle_text = "Hide Overlay" if overlay_visible else "Show Overlay"
    toggle_action = menu.addAction(toggle_text)
    toggle_action.triggered.connect(on_toggle)

    menu.addSeparator()

    quit_action = menu.addAction("Quit")
    quit_action.triggered.connect(on_quit)

    return menu
