"""Tests for src/ui/tray.py — SystemTrayManager signals and menu structure."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from src.ui.tray import SystemTrayManager


@pytest.fixture
def tray(qapp: QApplication) -> SystemTrayManager:
    return SystemTrayManager()


def test_tray_creates_without_error(qapp: QApplication) -> None:
    manager = SystemTrayManager()
    assert manager is not None


def test_tray_has_context_menu_actions(tray: SystemTrayManager) -> None:
    action_texts = [a.text() for a in tray._menu.actions() if not a.isSeparator()]
    # Toggle text is dynamic: "Hide Overlay" when visible, "Show Overlay" when hidden
    assert "Hide Overlay" in action_texts  # Default state is visible=True
    assert "Settings" in action_texts
    assert "Quit" in action_texts


def test_toggle_overlay_signal_emitted(tray: SystemTrayManager) -> None:
    received: list[None] = []
    tray.toggle_overlay.connect(lambda: received.append(None))
    actions = {a.text(): a for a in tray._menu.actions() if not a.isSeparator()}
    actions["Hide Overlay"].trigger()  # Default state is visible=True
    assert len(received) == 1


def test_settings_signal_emitted(tray: SystemTrayManager) -> None:
    received: list[None] = []
    tray.settings_requested.connect(lambda: received.append(None))
    actions = {a.text(): a for a in tray._menu.actions() if not a.isSeparator()}
    actions["Settings"].trigger()
    assert len(received) == 1


def test_quit_signal_emitted(tray: SystemTrayManager) -> None:
    received: list[None] = []
    tray.quit_requested.connect(lambda: received.append(None))
    actions = {a.text(): a for a in tray._menu.actions() if not a.isSeparator()}
    actions["Quit"].trigger()
    assert len(received) == 1


def test_menu_text_changes_with_visibility(tray: SystemTrayManager) -> None:
    """Test that toggle menu text updates when overlay visibility changes."""
    # Initial state: visible=True
    action_texts = [a.text() for a in tray._menu.actions() if not a.isSeparator()]
    assert "Hide Overlay" in action_texts

    # Update to hidden
    tray.update_overlay_visibility(False)
    action_texts = [a.text() for a in tray._menu.actions() if not a.isSeparator()]
    assert "Show Overlay" in action_texts

    # Update back to visible
    tray.update_overlay_visibility(True)
    action_texts = [a.text() for a in tray._menu.actions() if not a.isSeparator()]
    assert "Hide Overlay" in action_texts
