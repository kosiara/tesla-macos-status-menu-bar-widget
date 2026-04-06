"""Security section for the tray menu."""

import asyncio

from PySide6.QtWidgets import QMenu, QWidgetAction, QLabel, QMessageBox
from PySide6.QtGui import QAction, Qt

from teslabar.services.tesla_api import TeslaService, VehicleData


class SecuritySection:
    """Vehicle lock, sentry mode, and window venting."""

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

        # Venting windows (rich text, clickable)
        self._vent_label = QLabel("Venting windows: --")
        self._vent_label.setTextFormat(Qt.TextFormat.RichText)
        self._vent_label.setContentsMargins(20, 4, 20, 4)
        self._vent_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self._vent_label.mousePressEvent = lambda _: self._on_vent_toggle()
        self._vent_widget_action = QWidgetAction(menu)
        self._vent_widget_action.setDefaultWidget(self._vent_label)
        menu.addAction(self._vent_widget_action)

        self._venting = False

        menu.addSeparator()

    def update(self, vd: VehicleData, enabled: bool) -> None:
        self._lock_action.setText(
            f"Vehicle: {'Locked' if vd.is_locked else 'Not Locked'}"
        )
        self._sentry_action.setEnabled(enabled)
        self._sentry_action.setText(
            f"Sentry: {'On' if vd.sentry_mode else 'Off'}"
        )
        self._vent_widget_action.setEnabled(enabled)
        self._update_vent_label()

    def _update_vent_label(self) -> None:
        if self._venting:
            self._vent_label.setText(
                "Venting windows: <span style='color:red; font-weight:bold;'>On</span>"
            )
        else:
            self._vent_label.setText(
                "Venting windows: <span style='color:green; font-weight:bold;'>Off</span>"
            )

    def _on_sentry_toggle(self) -> None:
        new_state = not self._tesla.vehicle_data.sentry_mode
        asyncio.ensure_future(self._tesla.set_sentry_mode(new_state))

    def _on_vent_toggle(self) -> None:
        if not self._vent_widget_action.isEnabled():
            return
        if self._venting:
            self._venting = False
            self._update_vent_label()
            asyncio.ensure_future(self._tesla.close_windows())
        else:
            reply = QMessageBox.question(
                None,
                "Vent Windows",
                "Are you sure you want to open (VENT) all windows?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._venting = True
                self._update_vent_label()
                asyncio.ensure_future(self._tesla.vent_windows())
