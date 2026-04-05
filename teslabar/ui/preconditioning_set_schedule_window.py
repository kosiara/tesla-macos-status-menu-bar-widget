"""Window to set a new precondition schedule."""

import asyncio
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QCheckBox,
    QGroupBox,
    QTimeEdit,
    QMessageBox,
)
from PySide6.QtCore import Qt, QTime

from teslabar.services.tesla_api import TeslaService


DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


class PreconditionSetWindow(QWidget):
    """Window to set a new precondition schedule."""

    def __init__(self, tesla_service: TeslaService, parent=None) -> None:
        super().__init__(parent)
        self._tesla = tesla_service
        self.setWindowTitle("Set Precondition Schedule")
        self.setFixedWidth(350)
        self.setWindowFlags(
            self.windowFlags() | Qt.WindowStaysOnTopHint
        )

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>Set Precondition Time</b>"))

        # Time picker
        time_group = QGroupBox("Time")
        tl = QHBoxLayout(time_group)
        self._time_edit = QTimeEdit()
        self._time_edit.setDisplayFormat("HH:mm")
        self._time_edit.setTime(QTime(7, 0))
        tl.addWidget(self._time_edit)
        layout.addWidget(time_group)

        # Day checkboxes - preselect current day
        day_group = QGroupBox("Days of Week")
        dl = QVBoxLayout(day_group)
        self._day_checks: list[QCheckBox] = []
        today_idx = datetime.now().weekday()  # 0=Mon
        for i, name in enumerate(DAY_NAMES):
            cb = QCheckBox(name)
            if i == today_idx:
                cb.setChecked(True)
            self._day_checks.append(cb)
            dl.addWidget(cb)
        layout.addWidget(day_group)

        # Buttons
        btn_layout = QHBoxLayout()
        set_btn = QPushButton("Set Schedule")
        set_btn.clicked.connect(self._on_set)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.close)
        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(set_btn)
        layout.addLayout(btn_layout)

    def _on_set(self) -> None:
        days_of_week = 0
        for i, cb in enumerate(self._day_checks):
            if cb.isChecked():
                days_of_week |= 1 << i

        if days_of_week == 0:
            QMessageBox.warning(self, "Days", "Select at least one day.")
            return

        t = self._time_edit.time()
        time_minutes = t.hour() * 60 + t.minute()

        asyncio.ensure_future(self._do_set(days_of_week, time_minutes))

    async def _do_set(self, days_of_week: int, time_minutes: int) -> None:
        success = await self._tesla.add_precondition_schedule(
            days_of_week, time_minutes
        )
        if success:
            QMessageBox.information(self, "Success", "Precondition schedule set.")
            self.close()
        else:
            QMessageBox.warning(
                self, "Failed", f"Failed: {self._tesla.command_status}"
            )
