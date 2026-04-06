"""Security section for the tray menu."""

from PySide6.QtWidgets import QMenu
from PySide6.QtGui import QAction

from teslabar.services.tesla_api import VehicleData


class SecuritySection:
    """Vehicle lock and sentry mode display."""

    def __init__(self, menu: QMenu) -> None:
        # Vehicle lock (not clickable)
        self._lock_action = QAction("Vehicle: --", menu)
        self._lock_action.setEnabled(False)
        menu.addAction(self._lock_action)

        # Sentry (not clickable)
        self._sentry_action = QAction("Sentry: --", menu)
        self._sentry_action.setEnabled(False)
        menu.addAction(self._sentry_action)

        menu.addSeparator()

    def update(self, vd: VehicleData) -> None:
        self._lock_action.setText(
            f"Vehicle: {'Locked' if vd.is_locked else 'Not Locked'}"
        )
        self._sentry_action.setText(
            f"Sentry: {'On' if vd.sentry_mode else 'Off'}"
        )
