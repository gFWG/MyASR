"""Tests for src.ui.widgets custom widgets."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from src.ui.widgets import JlptLevelSelector, SliderDoubleSpinBox, SliderSpinBox


class TestSliderSpinBox:
    """Tests for SliderSpinBox composite widget."""

    def test_initial_value_is_zero(self, qapp: QApplication) -> None:
        """Default value should be 0."""
        widget = SliderSpinBox()
        assert widget.value() == 0

    def test_set_value_updates_both_controls(self, qapp: QApplication) -> None:
        """Setting value should sync slider and spinbox."""
        widget = SliderSpinBox()
        widget.setRange(0, 100)
        widget.setValue(50)
        assert widget.value() == 50
        assert widget._slider.value() == 50
        assert widget._spinbox.value() == 50

    def test_set_range_applies_to_both(self, qapp: QApplication) -> None:
        """setRange should configure both slider and spinbox."""
        widget = SliderSpinBox()
        widget.setRange(10, 200)
        assert widget._slider.minimum() == 10
        assert widget._slider.maximum() == 200
        assert widget._spinbox.minimum() == 10
        assert widget._spinbox.maximum() == 200

    def test_set_single_step(self, qapp: QApplication) -> None:
        """setSingleStep should apply to both controls."""
        widget = SliderSpinBox()
        widget.setSingleStep(5)
        assert widget._slider.singleStep() == 5
        assert widget._spinbox.singleStep() == 5

    def test_set_suffix(self, qapp: QApplication) -> None:
        """setSuffix should apply to spinbox only."""
        widget = SliderSpinBox()
        widget.setSuffix(" ms")
        assert widget._spinbox.suffix() == " ms"

    def test_slider_change_syncs_spinbox(self, qapp: QApplication) -> None:
        """Moving slider should update spinbox value."""
        widget = SliderSpinBox()
        widget.setRange(0, 100)
        widget._slider.setValue(75)
        assert widget._spinbox.value() == 75

    def test_spinbox_change_syncs_slider(self, qapp: QApplication) -> None:
        """Changing spinbox should update slider value."""
        widget = SliderSpinBox()
        widget.setRange(0, 100)
        widget._spinbox.setValue(30)
        assert widget._slider.value() == 30

    def test_value_changed_signal_emitted(self, qapp: QApplication) -> None:
        """valueChanged signal should be emitted on value change."""
        widget = SliderSpinBox()
        widget.setRange(0, 100)
        received: list[int] = []
        widget.valueChanged.connect(received.append)

        widget._slider.setValue(42)
        assert len(received) == 1
        assert received[0] == 42

    def test_set_value_suppresses_signals(self, qapp: QApplication) -> None:
        """setValue should not emit signals during programmatic update."""
        widget = SliderSpinBox()
        widget.setRange(0, 100)
        received: list[int] = []
        widget.valueChanged.connect(received.append)

        widget.setValue(55)
        # setValue suppresses signals during programmatic update
        # This is intentional to prevent signal spam when populating from config
        assert len(received) == 0
        assert widget.value() == 55


class TestSliderDoubleSpinBox:
    """Tests for SliderDoubleSpinBox composite widget."""

    def test_initial_value_is_zero(self, qapp: QApplication) -> None:
        """Default value should be 0.0."""
        widget = SliderDoubleSpinBox()
        assert widget.value() == 0.0

    def test_set_value_updates_both_controls(self, qapp: QApplication) -> None:
        """Setting value should sync slider and spinbox with proper scaling."""
        widget = SliderDoubleSpinBox(decimals=2)
        widget.setRange(0.0, 1.0)
        widget.setValue(0.5)
        assert widget.value() == pytest.approx(0.5)
        # Slider uses integer scale: 0.5 * 100 = 50
        assert widget._slider.value() == 50

    def test_set_range_with_floats(self, qapp: QApplication) -> None:
        """setRange should scale float values for slider."""
        widget = SliderDoubleSpinBox(decimals=2)
        widget.setRange(0.1, 0.95)
        # Slider range: 0.1 * 100 = 10, 0.95 * 100 = 95
        assert widget._slider.minimum() == 10
        assert widget._slider.maximum() == 95
        assert widget._spinbox.minimum() == pytest.approx(0.1)
        assert widget._spinbox.maximum() == pytest.approx(0.95)

    def test_slider_change_syncs_spinbox(self, qapp: QApplication) -> None:
        """Moving slider should update spinbox with scaled value."""
        widget = SliderDoubleSpinBox(decimals=2)
        widget.setRange(0.0, 1.0)
        widget._slider.setValue(75)  # 75 / 100 = 0.75
        assert widget._spinbox.value() == pytest.approx(0.75)

    def test_spinbox_change_syncs_slider(self, qapp: QApplication) -> None:
        """Changing spinbox should update slider with scaled value."""
        widget = SliderDoubleSpinBox(decimals=2)
        widget.setRange(0.0, 1.0)
        widget._spinbox.setValue(0.25)
        assert widget._slider.value() == 25

    def test_value_changed_signal_emitted(self, qapp: QApplication) -> None:
        """valueChanged signal should emit float value."""
        widget = SliderDoubleSpinBox(decimals=2)
        widget.setRange(0.0, 1.0)
        received: list[float] = []
        widget.valueChanged.connect(received.append)

        widget._slider.setValue(30)  # 0.30
        assert len(received) == 1
        assert received[0] == pytest.approx(0.30)

    def test_set_single_step_scales_for_slider(self, qapp: QApplication) -> None:
        """setSingleStep should scale the step value for slider."""
        widget = SliderDoubleSpinBox(decimals=2)
        widget.setSingleStep(0.05)  # 0.05 * 100 = 5
        assert widget._slider.singleStep() == 5
        assert widget._spinbox.singleStep() == pytest.approx(0.05)

    def test_set_decimals_updates_scale(self, qapp: QApplication) -> None:
        """setDecimals should recalculate the scale factor."""
        widget = SliderDoubleSpinBox(decimals=2)
        assert widget._scale == 100

        widget.setDecimals(3)
        assert widget._scale == 1000
        assert widget._spinbox.decimals() == 3

    def test_set_suffix(self, qapp: QApplication) -> None:
        """setSuffix should apply to spinbox."""
        widget = SliderDoubleSpinBox()
        widget.setSuffix(" %")
        assert widget._spinbox.suffix() == " %"

    def test_precision_with_high_decimals(self, qapp: QApplication) -> None:
        """Test with 3 decimal places."""
        widget = SliderDoubleSpinBox(decimals=3)
        widget.setRange(0.0, 1.0)
        widget.setValue(0.123)
        assert widget.value() == pytest.approx(0.123)
        assert widget._slider.value() == 123


class TestJlptLevelSelector:
    """Tests for JlptLevelSelector segmented control widget."""

    def test_initial_value_is_n3(self, qapp: QApplication) -> None:
        """Default value should be N3 (level 3)."""
        widget = JlptLevelSelector()
        assert widget.value() == 3

    def test_has_five_buttons(self, qapp: QApplication) -> None:
        """Should have 5 buttons for N1-N5."""
        widget = JlptLevelSelector()
        assert len(widget._buttons) == 5

    def test_button_labels(self, qapp: QApplication) -> None:
        """Buttons should be labeled N1 through N5."""
        widget = JlptLevelSelector()
        labels = [btn.text() for btn in widget._buttons]
        assert labels == ["N1", "N2", "N3", "N4", "N5"]

    def test_buttons_are_checkable(self, qapp: QApplication) -> None:
        """All buttons should be checkable."""
        widget = JlptLevelSelector()
        for btn in widget._buttons:
            assert btn.isCheckable()

    def test_buttons_are_exclusive(self, qapp: QApplication) -> None:
        """Only one button should be checked at a time."""
        widget = JlptLevelSelector()
        widget._buttons[0].setChecked(True)  # N1
        assert widget._buttons[0].isChecked()
        assert not widget._buttons[1].isChecked()

        widget._buttons[4].setChecked(True)  # N5
        assert widget._buttons[4].isChecked()
        assert not widget._buttons[0].isChecked()

    def test_set_value(self, qapp: QApplication) -> None:
        """setValue should check the correct button."""
        widget = JlptLevelSelector()

        widget.setValue(1)  # N1
        assert widget.value() == 1
        assert widget._buttons[0].isChecked()

        widget.setValue(5)  # N5
        assert widget.value() == 5
        assert widget._buttons[4].isChecked()

    def test_set_value_clamped_to_valid_range(self, qapp: QApplication) -> None:
        """setValue should clamp values to valid range 1-5."""
        widget = JlptLevelSelector()

        widget.setValue(0)  # Below minimum
        assert widget.value() == 1

        widget.setValue(10)  # Above maximum
        assert widget.value() == 5

        widget.setValue(-5)  # Negative
        assert widget.value() == 1

    def test_value_changed_signal_on_button_click(self, qapp: QApplication) -> None:
        """Clicking a button should emit valueChanged signal."""
        widget = JlptLevelSelector()
        received: list[int] = []
        widget.valueChanged.connect(received.append)

        # Simulate button click via button group
        widget._buttons[0].click()  # N1
        assert len(received) == 1
        assert received[0] == 1

        widget._buttons[4].click()  # N5
        assert len(received) == 2
        assert received[1] == 5

    def test_value_changed_signal_not_emitted_on_set_value(self, qapp: QApplication) -> None:
        """setValue should not emit valueChanged signal (programmatic update)."""
        widget = JlptLevelSelector()
        received: list[int] = []
        widget.valueChanged.connect(received.append)

        widget.setValue(2)
        assert len(received) == 0
        assert widget.value() == 2

    def test_all_levels_selectable(self, qapp: QApplication) -> None:
        """All levels N1-N5 should be selectable."""
        widget = JlptLevelSelector()

        for level in [1, 2, 3, 4, 5]:
            widget.setValue(level)
            assert widget.value() == level
            assert widget._buttons[level - 1].isChecked()
