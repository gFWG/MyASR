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
    assert "Show/Hide Overlay" in action_texts
    assert "Settings" in action_texts
    assert "Learning History" in action_texts
    assert "Quick Export" in action_texts
    assert "Quit" in action_texts


def test_toggle_overlay_signal_emitted(tray: SystemTrayManager) -> None:
    received: list[None] = []
    tray.toggle_overlay.connect(lambda: received.append(None))
    actions = {a.text(): a for a in tray._menu.actions() if not a.isSeparator()}
    actions["Show/Hide Overlay"].trigger()
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


def test_quick_export_signal_emitted(tray: SystemTrayManager) -> None:
    received: list[None] = []
    tray.quick_export_requested.connect(lambda: received.append(None))
    actions = {a.text(): a for a in tray._menu.actions() if not a.isSeparator()}
    actions["Quick Export"].trigger()
    assert len(received) == 1


def test_update_review_badge_with_zero(tray: SystemTrayManager) -> None:
    tray.update_review_badge(0)
    action_texts = [a.text() for a in tray._menu.actions() if not a.isSeparator()]
    assert "Review (coming soon)" in action_texts
