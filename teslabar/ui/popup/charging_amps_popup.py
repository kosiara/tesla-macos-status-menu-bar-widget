"""Charging amps slider popup window."""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QSlider,
    QPushButton,
)
from PySide6.QtCore import Qt, Signal

_MIN_AMPS = 6
_MAX_AMPS = 16


class ChargingAmpsPopup(QWidget):
    charging_amps_changed = Signal(int)

    def __init__(self, current_amps: int = 16, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Set Charging Amps")
        self.setFixedWidth(320)
        self.setFixedHeight(120)
        self.setWindowFlags(
            Qt.Window | Qt.WindowStaysOnTopHint | Qt.Tool
        )

        layout = QVBoxLayout(self)

        # Label
        self._label = QLabel(f"Charging Amps: {current_amps}A")
        self._label.setStyleSheet("font-size: 14px; font-weight: bold;")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._label)

        # Slider — 6A to 16A
        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setMinimum(_MIN_AMPS)
        self._slider.setMaximum(_MAX_AMPS)
        self._slider.setSingleStep(1)
        self._slider.setPageStep(1)
        self._slider.setTickInterval(1)
        self._slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._slider.setValue(max(_MIN_AMPS, min(_MAX_AMPS, current_amps)))
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

    def _on_slider_changed(self, value: int) -> None:
        self._label.setText(f"Charging Amps: {value}A")

    def _on_set(self) -> None:
        self.charging_amps_changed.emit(self._slider.value())
        self.close()
