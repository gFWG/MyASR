"""Custom Qt widgets for MyASR application."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QDoubleSpinBox,
    QHBoxLayout,
    QPushButton,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QWidget,
)


class SliderSpinBox(QWidget):
    """Composite widget combining a slider with a synchronized spinbox.

    Provides intuitive visual adjustment via slider while allowing
    precise numeric input via spinbox.

    Args:
        parent: Optional parent widget.

    Signals:
        valueChanged: Emitted when the value changes (int).
    """

    valueChanged = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._syncing = False  # Prevent recursive signal loops

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._slider = QSlider()
        self._slider.setOrientation(Qt.Orientation.Horizontal)
        self._spinbox = QSpinBox()

        layout.addWidget(self._slider, stretch=3)
        layout.addWidget(self._spinbox, stretch=1)

        # Bi-directional sync
        self._slider.valueChanged.connect(self._on_slider_changed)
        self._spinbox.valueChanged.connect(self._on_spinbox_changed)

    def _on_slider_changed(self, value: int) -> None:
        """Sync spinbox when slider changes and emit signal."""
        if not self._syncing:
            self._syncing = True
            self._spinbox.setValue(value)
            self._syncing = False
            self.valueChanged.emit(value)

    def _on_spinbox_changed(self, value: int) -> None:
        """Sync slider when spinbox changes and emit signal."""
        if not self._syncing:
            self._syncing = True
            self._slider.setValue(value)
            self._syncing = False
            self.valueChanged.emit(value)

    def setValue(self, value: int) -> None:
        """Set value programmatically without triggering duplicate signals.

        Args:
            value: The integer value to set.
        """
        self._syncing = True
        self._slider.setValue(value)
        self._spinbox.setValue(value)
        self._syncing = False

    def value(self) -> int:
        """Get the current value.

        Returns:
            Current integer value from the spinbox.
        """
        return self._spinbox.value()

    def setRange(self, min_val: int, max_val: int) -> None:
        """Set the minimum and maximum values for both controls.

        Args:
            min_val: Minimum allowed value.
            max_val: Maximum allowed value.
        """
        self._slider.setRange(min_val, max_val)
        self._spinbox.setRange(min_val, max_val)

    def setSingleStep(self, step: int) -> None:
        """Set the step increment for both controls.

        Args:
            step: Step value for slider and spinbox.
        """
        self._slider.setSingleStep(step)
        self._spinbox.setSingleStep(step)

    def setSuffix(self, suffix: str) -> None:
        """Set a suffix string for the spinbox (e.g., " ms").

        Args:
            suffix: Suffix string to display after the value.
        """
        self._spinbox.setSuffix(suffix)


class SliderDoubleSpinBox(QWidget):
    """Composite widget combining a slider with a synchronized double spinbox.

    Uses integer scaling internally for the slider while presenting
    float values in the spinbox. For example, with decimals=2, a slider
    value of 50 represents 0.50.

    Args:
        decimals: Number of decimal places (default: 2).
        parent: Optional parent widget.

    Signals:
        valueChanged: Emitted when the value changes (float).
    """

    valueChanged = Signal(float)

    def __init__(self, decimals: int = 2, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._decimals = decimals
        self._scale = 10**decimals
        self._syncing = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._slider = QSlider()
        self._slider.setOrientation(Qt.Orientation.Horizontal)
        self._spinbox = QDoubleSpinBox()
        self._spinbox.setDecimals(decimals)

        layout.addWidget(self._slider, stretch=3)
        layout.addWidget(self._spinbox, stretch=1)

        self._slider.valueChanged.connect(self._on_slider_changed)
        self._spinbox.valueChanged.connect(self._on_spinbox_changed)

    def _on_slider_changed(self, value: int) -> None:
        """Sync spinbox when slider changes and emit signal."""
        if not self._syncing:
            self._syncing = True
            float_value = value / self._scale
            self._spinbox.setValue(float_value)
            self._syncing = False
            self.valueChanged.emit(float_value)

    def _on_spinbox_changed(self, value: float) -> None:
        """Sync slider when spinbox changes and emit signal."""
        if not self._syncing:
            self._syncing = True
            int_value = int(round(value * self._scale))
            self._slider.setValue(int_value)
            self._syncing = False
            self.valueChanged.emit(value)

    def setValue(self, value: float) -> None:
        """Set value programmatically without triggering duplicate signals.

        Args:
            value: The float value to set.
        """
        self._syncing = True
        int_value = int(round(value * self._scale))
        self._slider.setValue(int_value)
        self._spinbox.setValue(value)
        self._syncing = False

    def value(self) -> float:
        """Get the current value.

        Returns:
            Current float value from the spinbox.
        """
        return self._spinbox.value()

    def setRange(self, min_val: float, max_val: float) -> None:
        """Set the minimum and maximum values for both controls.

        Args:
            min_val: Minimum allowed value.
            max_val: Maximum allowed value.
        """
        self._slider.setRange(int(round(min_val * self._scale)), int(round(max_val * self._scale)))
        self._spinbox.setRange(min_val, max_val)

    def setSingleStep(self, step: float) -> None:
        """Set the step increment for both controls.

        Args:
            step: Step value for slider and spinbox.
        """
        self._slider.setSingleStep(int(round(step * self._scale)))
        self._spinbox.setSingleStep(step)

    def setDecimals(self, decimals: int) -> None:
        """Set the number of decimal places for the spinbox.

        Args:
            decimals: Number of decimal places.
        """
        self._decimals = decimals
        self._scale = 10**decimals
        self._spinbox.setDecimals(decimals)

    def setSuffix(self, suffix: str) -> None:
        """Set a suffix string for the spinbox.

        Args:
            suffix: Suffix string to display after the value.
        """
        self._spinbox.setSuffix(suffix)


# Windows 11 style stylesheet for JLPT level segmented control
# Middle/last buttons: remove left border to avoid double borders between buttons
_JLPT_SELECTOR_BASE_STYLE = """
JlptLevelSelector QPushButton {
    background-color: transparent;
    border: 2px solid #c0c0c0;
    border-left: none;
    padding: 6px 16px;
    min-width: 40px;
    font-size: 13px;
    margin: 0px;
}
JlptLevelSelector QPushButton:hover:!checked {
    background-color: rgba(0, 0, 0, 0.05);
}
JlptLevelSelector QPushButton:checked {
    background-color: #0078D4;
    color: white;
}
"""

# First button: has left border and rounded left corners
_FIRST_BUTTON_STYLE = """
border-left: 2px solid #c0c0c0;
border-top-left-radius: 4px;
border-bottom-left-radius: 4px;
"""

# Last button: rounded right corners
_LAST_BUTTON_STYLE = """
border-top-right-radius: 4px;
border-bottom-right-radius: 4px;
"""


class JlptLevelSelector(QWidget):
    """Segmented control for JLPT level selection (N1-N5).

    A Windows 11 style segmented button group with mutually exclusive selection.
    Displays buttons from N1 (hardest) to N5 (easiest) left to right.

    Args:
        parent: Optional parent widget.

    Signals:
        valueChanged: Emitted when level changes (int, 1-5).
    """

    valueChanged = Signal(int)

    # JLPT levels: N1 (hardest) to N5 (easiest)
    _LEVELS = [1, 2, 3, 4, 5]
    _LABELS = ["N1", "N2", "N3", "N4", "N5"]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("JlptLevelSelector")

        # Prevent the widget from expanding horizontally
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)  # Connected buttons

        self._button_group = QButtonGroup(self)
        self._button_group.setExclusive(True)

        self._buttons: list[QPushButton] = []
        for i, (level, label) in enumerate(zip(self._LEVELS, self._LABELS)):
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            self._button_group.addButton(btn, level)  # button ID = level (1-5)
            layout.addWidget(btn)
            self._buttons.append(btn)

        # Set default selection (N3)
        self._buttons[2].setChecked(True)

        # Apply Windows 11 style
        self.setStyleSheet(_JLPT_SELECTOR_BASE_STYLE)
        # Apply rounded corners to first and last buttons
        self._buttons[0].setStyleSheet(_FIRST_BUTTON_STYLE)
        self._buttons[-1].setStyleSheet(_LAST_BUTTON_STYLE)

        # Connect signal
        self._button_group.idClicked.connect(self._on_button_clicked)

    def _on_button_clicked(self, button_id: int) -> None:
        """Handle button click and emit valueChanged signal."""
        self.valueChanged.emit(button_id)

    def value(self) -> int:
        """Get the current JLPT level.

        Returns:
            Current level (1-5), where 1 is N1 (hardest) and 5 is N5 (easiest).
        """
        checked = self._button_group.checkedId()
        return checked if checked != -1 else 3  # Default to N3 if none selected

    def setValue(self, level: int) -> None:
        """Set the JLPT level programmatically.

        Args:
            level: Level to set (1-5). Clamped to valid range if out of bounds.
        """
        level = max(1, min(5, level))
        idx = level - 1  # Convert to 0-based index
        self._buttons[idx].setChecked(True)
