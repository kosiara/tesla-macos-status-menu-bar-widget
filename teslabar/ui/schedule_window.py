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

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        refresh_btn = QPushButton("⟳")
        refresh_btn.setFixedWidth(40)
        refresh_btn.setToolTip("Refresh")
        refresh_btn.setStyleSheet("font-size: 18px;")
        refresh_btn.clicked.connect(self._on_refresh)
        btn_layout.addWidget(refresh_btn)
        close_btn = QPushButton("Close")
        close_btn.setStyleSheet("font-size: 18px;")
        close_btn.clicked.connect(self.close)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

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
                f"    <b>{entry.time_str}</b> — "
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

    def _on_refresh(self) -> None:
        raise NotImplementedError

    def _on_delete(self, schedule_id: int) -> None:
        raise NotImplementedError


class PreconditionListWindow(ScheduleListWindow):
    def __init__(self, tesla_service: TeslaService, parent=None) -> None:
        super().__init__("Precondition Schedules", tesla_service, parent)
        self._entries: list[ScheduleEntry] = []

    def populate(self, entries: list[ScheduleEntry]) -> None:
        self._entries = entries
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

            enabled_cb = QCheckBox()
            enabled_cb.setChecked(entry.enabled)
            enabled_cb.toggled.connect(
                lambda checked, e=entry: self._on_toggle_enabled(e, checked)
            )
            fl.addWidget(enabled_cb)

            info_text = (
                f"<b>{entry.time_str}</b> — "
                f"{', '.join(entry.days_list) or 'No days'}"
            )
            if entry.name:
                info_text = f"{entry.name}: {info_text}"
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

    def _on_refresh(self) -> None:
        asyncio.ensure_future(self._do_refresh())

    async def _do_refresh(self) -> None:
        entries = await self._tesla.get_precondition_schedules()
        self.populate(entries)

    def _on_toggle_enabled(self, entry: ScheduleEntry, enabled: bool) -> None:
        asyncio.ensure_future(self._do_toggle_enabled(entry, enabled))

    async def _do_toggle_enabled(self, entry: ScheduleEntry, enabled: bool) -> None:
        success = await self._tesla.toggle_precondition_schedule(entry, enabled)
        if success:
            entries = await self._tesla.get_precondition_schedules()
            self.populate(entries)

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

    def _on_refresh(self) -> None:
        asyncio.ensure_future(self._do_refresh())

    async def _do_refresh(self) -> None:
        entries = await self._tesla.get_charge_schedules()
        self.populate(entries)

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


