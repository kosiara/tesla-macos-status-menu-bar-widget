"""Schedules section: precondition times and charging times."""

import asyncio

from PySide6.QtWidgets import QMenu
from PySide6.QtGui import QAction

from teslabar.services.tesla_api import TeslaService
from teslabar.ui.schedule_window import PreconditionListWindow, ChargingListWindow


class SchedulesSection:
    """Precondition times and charging times list windows."""

    def __init__(self, menu: QMenu, tesla_service: TeslaService) -> None:
        self._tesla = tesla_service
        self._precond_list_win: PreconditionListWindow | None = None
        self._charging_list_win: ChargingListWindow | None = None

        # Precondition times
        precond_list_action = QAction("Precondition Times", menu)
        precond_list_action.triggered.connect(self._open_precond_list)
        menu.addAction(precond_list_action)

        # Charging times
        charging_list_action = QAction("Charging Times", menu)
        charging_list_action.triggered.connect(self._open_charging_list)
        menu.addAction(charging_list_action)

        menu.addSeparator()

    def _open_precond_list(self) -> None:
        self._precond_list_win = PreconditionListWindow(self._tesla)
        self._precond_list_win.show()
        self._precond_list_win.raise_()
        asyncio.ensure_future(self._load_precond_list())

    async def _load_precond_list(self) -> None:
        entries = await self._tesla.get_precondition_schedules()
        if self._precond_list_win:
            self._precond_list_win.populate(entries)

    def _open_charging_list(self) -> None:
        self._charging_list_win = ChargingListWindow(self._tesla)
        self._charging_list_win.show()
        self._charging_list_win.raise_()
        asyncio.ensure_future(self._load_charging_list())

    async def _load_charging_list(self) -> None:
        entries = await self._tesla.get_charge_schedules()
        if self._charging_list_win:
            self._charging_list_win.populate(entries)
