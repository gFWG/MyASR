"""System tray manager for the MyASR Japanese learning overlay."""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QSystemTrayIcon

from src.ui.menu_factory import create_context_menu

logger = logging.getLogger(__name__)


class SystemTrayManager(QObject):
    """System tray manager with programmatic icon and context menu.

    Signals:
        settings_requested: Emitted when user requests to open settings dialog.
        toggle_overlay: Emitted when user requests to toggle overlay visibility.
        quit_requested: Emitted when user requests to quit the application.
    """

    settings_requested = Signal()
    toggle_overlay = Signal()
    quit_requested = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)

        if not QSystemTrayIcon.isSystemTrayAvailable():
            logger.warning("System tray is not available on this platform")

        self._tray = QSystemTrayIcon(self)
        self._icon_pixmap = self._create_icon_pixmap()
        self._tray.setIcon(QIcon(self._icon_pixmap))

        self._overlay_visible = True
        self._menu = create_context_menu(
            parent=None,
            on_settings=self.settings_requested.emit,
            on_toggle=self.toggle_overlay.emit,
            on_quit=self.quit_requested.emit,
            overlay_visible=self._overlay_visible,
        )

        self._tray.setContextMenu(self._menu)
        self._tray.show()

    def _create_icon_pixmap(self) -> QPixmap:
        pixmap = QPixmap(32, 32)
        pixmap.fill(QColor("#1E9E80"))

        painter = QPainter(pixmap)
        painter.setPen(QColor("#FFFFFF"))
        font = painter.font()
        font.setPointSize(20)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "M")
        painter.end()

        return pixmap

    def update_overlay_visibility(self, visible: bool) -> None:
        """Update the overlay visibility state and rebuild the menu.

        Args:
            visible: Current overlay visibility state.
        """
        self._overlay_visible = visible
        self._menu = create_context_menu(
            parent=None,
            on_settings=self.settings_requested.emit,
            on_toggle=self.toggle_overlay.emit,
            on_quit=self.quit_requested.emit,
            overlay_visible=self._overlay_visible,
        )
        self._tray.setContextMenu(self._menu)
