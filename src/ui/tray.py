"""System tray manager for the MyASR Japanese learning overlay."""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

logger = logging.getLogger(__name__)


class SystemTrayManager(QObject):
    """System tray manager with programmatic icon and context menu."""

    settings_requested = Signal()
    review_requested = Signal()
    toggle_overlay = Signal()
    quit_requested = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)

        if not QSystemTrayIcon.isSystemTrayAvailable():
            logger.warning("System tray is not available on this platform")

        self._tray = QSystemTrayIcon(self)
        self._icon_pixmap = self._create_icon_pixmap()
        self._tray.setIcon(QIcon(self._icon_pixmap))

        self._menu = QMenu()
        self._setup_menu()

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

    def _setup_menu(self) -> None:
        settings_action = self._menu.addAction("Settings")
        settings_action.triggered.connect(self.settings_requested.emit)

        self._review_action = self._menu.addAction("Review (coming soon)")
        self._review_action.setEnabled(False)

        self._menu.addSeparator()

        toggle_action = self._menu.addAction("Show/Hide Overlay")
        toggle_action.triggered.connect(self.toggle_overlay.emit)

        quit_action = self._menu.addAction("Quit")
        quit_action.triggered.connect(self.quit_requested.emit)

    def update_review_badge(self, count: int) -> None:
        if count > 0:
            self._review_action.setText(f"Review ({count} due)")
        else:
            self._review_action.setText("Review (coming soon)")
        self._review_action.setEnabled(False)
