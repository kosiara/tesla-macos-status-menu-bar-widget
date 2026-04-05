"""Schedule windows for precondition and charging schedules."""

import asyncio
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QFrame,
    QCheckBox,
    QTimeEdit,
    QGroupBox,
    QMessageBox,
)
from PySide6.QtCore import Qt, QTime

from teslabar.services.tesla_api import TeslaService, ScheduleEntry


DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


class ScheduleListWindow(QWidget):
    """Base class for displaying and deleting schedule entries."""

    def __init__(
        self, title: str, tesla_service: TeslaService, parent=None
    ) -> None:
        super().__init__(parent)
        self._tesla = tesla_service
        self.setWindowTitle(title)
        self.setMinimumWidth(800)
        self.setMinimumHeight(300)
        self.setWindowFlags(
            self.windowFlags() | Qt.WindowStaysOnTopHint
        )

        layout = QVBoxLayout(self)
        self._title_label = QLabel(f"<b>{title}</b>")
        layout.addWidget(self._title_label)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll_content = QWidget()
        self._scroll_layout = QVBoxLayout(self._scroll_content)
        self._scroll_layout.setAlignment(Qt.AlignTop)
        self._scroll.setWidget(self._scroll_content)
        layout.addWidget(self._scroll)

        self._empty_label = QLabel("No schedules found.")
        self._empty_label.setStyleSheet("color: gray;")
        self._scroll_layout.addWidget(self._empty_label)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn, alignment=Qt.AlignRight)

    def populate(self, entries: list[ScheduleEntry]) -> None:
        # Clear existing
        while self._scroll_layout.count():
            item = self._scroll_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not entries:
            self._empty_label = QLabel("No schedules found.")
            self._empty_label.setStyleSheet("color: gray;")
            self._scroll_layout.addWidget(self._empty_label)
            return

        for entry in entries:
            frame = QFrame()
            frame.setFrameShape(QFrame.Shape.StyledPanel)
            fl = QHBoxLayout(frame)

            info_text = (
                f"<b>{entry.time_str}</b> — "
                f"{', '.join(entry.days_list) or 'No days'}"
            )
            if entry.name:
                info_text = f"{entry.name}: {info_text}"
            if not entry.enabled:
                info_text += " (disabled)"
            fl.addWidget(QLabel(info_text))
            fl.addStretch()

            del_btn = QPushButton("🗑")
            del_btn.setFixedWidth(40)
            del_btn.setToolTip("Delete this schedule")
            del_btn.clicked.connect(
                lambda checked=False, eid=entry.id: self._on_delete(eid)
            )
            fl.addWidget(del_btn)

            self._scroll_layout.addWidget(frame)

    def _on_delete(self, schedule_id: int) -> None:
        raise NotImplementedError


class PreconditionListWindow(ScheduleListWindow):
    def __init__(self, tesla_service: TeslaService, parent=None) -> None:
        super().__init__("Precondition Schedules", tesla_service, parent)

    def _on_delete(self, schedule_id: int) -> None:
        confirm = QMessageBox.question(
            self,
            "Delete",
            "Delete this precondition schedule?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            loop = asyncio.get_event_loop()
            asyncio.ensure_future(self._do_delete(schedule_id))

    async def _do_delete(self, schedule_id: int) -> None:
        success = await self._tesla.remove_precondition_schedule(schedule_id)
        if success:
            entries = await self._tesla.get_precondition_schedules()
            self.populate(entries)


class ChargingListWindow(ScheduleListWindow):
    def __init__(self, tesla_service: TeslaService, parent=None) -> None:
        super().__init__("Charging Schedules", tesla_service, parent)

    def _on_delete(self, schedule_id: int) -> None:
        confirm = QMessageBox.question(
            self,
            "Delete",
            "Delete this charging schedule?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            asyncio.ensure_future(self._do_delete(schedule_id))

    async def _do_delete(self, schedule_id: int) -> None:
        success = await self._tesla.remove_charge_schedule(schedule_id)
        if success:
            entries = await self._tesla.get_charge_schedules()
            self.populate(entries)


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
