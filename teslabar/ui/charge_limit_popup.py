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
        self._label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._label)

        # Slider
        self._slider = QSlider(Qt.Horizontal)
        self._slider.setMinimum(50)
        self._slider.setMaximum(100)
        self._slider.setSingleStep(5)
        self._slider.setPageStep(5)
        self._slider.setTickInterval(5)
        self._slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._slider.setValue(current_limit)
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
        snapped = round(value / 5) * 5
        if snapped != value:
            self._slider.setValue(snapped)
            return
        self._label.setText(f"Charge Limit: {snapped}%")

    def _on_set(self) -> None:
        value = round(self._slider.value() / 5) * 5
        self.charge_limit_changed.emit(value)
        self.close()
