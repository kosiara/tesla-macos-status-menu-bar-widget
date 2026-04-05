"""Cabin temperature slider popup window."""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QSlider,
    QPushButton,
)
from PySide6.QtCore import Qt, Signal

# 16.0 to 32.0 in steps of 0.5 → 33 positions
_MIN_TEMP = 16.0
_MAX_TEMP = 32.0
_STEP = 0.5
_VALUES = [_MIN_TEMP + i * _STEP for i in range(int((_MAX_TEMP - _MIN_TEMP) / _STEP) + 1)]


class CabinTempPopup(QWidget):
    cabin_temp_changed = Signal(float)

    def __init__(self, current_temp: float = 20.0, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Set Cabin Temperature")
        self.setFixedWidth(320)
        self.setFixedHeight(120)
        self.setWindowFlags(
            Qt.Window | Qt.WindowStaysOnTopHint | Qt.Tool
        )

        layout = QVBoxLayout(self)

        # Label
        self._label = QLabel(f"Cabin Temp: {current_temp:.1f}°C")
        self._label.setStyleSheet("font-size: 14px; font-weight: bold;")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._label)

        # Slider
        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setMinimum(0)
        self._slider.setMaximum(len(_VALUES) - 1)
        self._slider.setSingleStep(1)
        self._slider.setPageStep(2)
        self._slider.setTickInterval(2)
        self._slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._slider.setValue(self._temp_to_pos(current_temp))
        self._slider.valueChanged.connect(self._on_slider_changed)
        layout.addWidget(self._slider)

        # Buttons
        btn_layout = QHBoxLayout()
        set_btn = QPushButton("Set")
        set_btn.clicked.connect(self._on_set)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.close)
        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(set_btn)
        layout.addLayout(btn_layout)

    @staticmethod
    def _temp_to_pos(temp: float) -> int:
        """Find the closest slider position for a given temperature."""
        closest = 0
        for i, v in enumerate(_VALUES):
            if abs(v - temp) < abs(_VALUES[closest] - temp):
                closest = i
        return closest

    def _on_slider_changed(self, pos: int) -> None:
        value = _VALUES[pos]
        self._label.setText(f"Cabin Temp: {value:.1f}°C")

    def _on_set(self) -> None:
        value = _VALUES[self._slider.value()]
        self.cabin_temp_changed.emit(value)
        self.close()
