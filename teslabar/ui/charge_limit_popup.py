"""Charge limit slider popup window."""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QSlider,
    QPushButton,
)
from PySide6.QtCore import Qt, Signal

# 50-80 in steps of 5, then 80-100 in steps of 1
_VALUES = list(range(50, 80, 5)) + list(range(80, 101))


class ChargeLimitPopup(QWidget):
    charge_limit_changed = Signal(int)

    def __init__(self, current_limit: int = 80, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Set Charge Limit")
        self.setFixedWidth(320)
        self.setFixedHeight(120)
        self.setWindowFlags(
            Qt.Window | Qt.WindowStaysOnTopHint | Qt.Tool
        )

        layout = QVBoxLayout(self)

        # Label
        self._label = QLabel(f"Charge Limit: {current_limit}%")
        self._label.setStyleSheet("font-size: 14px; font-weight: bold;")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._label)

        # Slider — positions map to _VALUES
        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setMinimum(0)
        self._slider.setMaximum(len(_VALUES) - 1)
        self._slider.setSingleStep(1)
        self._slider.setPageStep(1)
        self._slider.setTickInterval(1)
        self._slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._slider.setValue(self._percent_to_pos(current_limit))
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
    def _percent_to_pos(percent: int) -> int:
        """Find the closest slider position for a given percent."""
        closest = 0
        for i, v in enumerate(_VALUES):
            if abs(v - percent) < abs(_VALUES[closest] - percent):
                closest = i
        return closest

    def _on_slider_changed(self, pos: int) -> None:
        value = _VALUES[pos]
        self._label.setText(f"Charge Limit: {value}%")

    def _on_set(self) -> None:
        value = _VALUES[self._slider.value()]
        self.charge_limit_changed.emit(value)
        self.close()
