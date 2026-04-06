"""Security section for the tray menu."""

import asyncio

from PySide6.QtWidgets import QMenu
from PySide6.QtGui import QAction

from teslabar.services.tesla_api import TeslaService, VehicleData


class SecuritySection:
    """Vehicle lock and sentry mode display."""

    def __init__(self, menu: QMenu, tesla_service: TeslaService) -> None:
        self._tesla = tesla_service

        # Vehicle lock (not clickable)
        self._lock_action = QAction("Vehicle: --", menu)
        self._lock_action.setEnabled(False)
        menu.addAction(self._lock_action)

        # Sentry (clickable)
        self._sentry_action = QAction("Sentry: --", menu)
        self._sentry_action.triggered.connect(self._on_sentry_toggle)
        menu.addAction(self._sentry_action)

        menu.addSeparator()

    def update(self, vd: VehicleData, enabled: bool) -> None:
        self._lock_action.setText(
            f"Vehicle: {'Locked' if vd.is_locked else 'Not Locked'}"
        )
        self._sentry_action.setEnabled(enabled)
        self._sentry_action.setText(
            f"Sentry: {'On' if vd.sentry_mode else 'Off'}"
        )

    def _on_sentry_toggle(self) -> None:
        new_state = not self._tesla.vehicle_data.sentry_mode
        asyncio.ensure_future(self._tesla.set_sentry_mode(new_state))
