"""Battery & charging section for the tray menu."""

import asyncio

from PySide6.QtWidgets import QMenu, QWidgetAction, QLabel
from PySide6.QtGui import QAction, Qt

from teslabar.services.tesla_api import TeslaService, VehicleData


class BatteryChargingSection:
    """Battery level, start/stop charge, and charger status."""

    def __init__(self, menu: QMenu, tesla_service: TeslaService) -> None:
        self._tesla = tesla_service

        # Battery (not clickable)
        self._battery_action = QAction("Battery: --%", menu)
        self._battery_action.setEnabled(False)
        menu.addAction(self._battery_action)

        # Start/Stop Charge
        self._charge_toggle_action = QAction("Start Charge", menu)
        self._charge_toggle_action.triggered.connect(self._on_charge_toggle)
        menu.addAction(self._charge_toggle_action)

        # Charger status (rich text)
        self._charger_status_label = QLabel("Charger: --")
        self._charger_status_label.setTextFormat(Qt.TextFormat.RichText)
        self._charger_status_label.setContentsMargins(20, 4, 20, 4)
        charger_widget_action = QWidgetAction(menu)
        charger_widget_action.setDefaultWidget(self._charger_status_label)
        menu.addAction(charger_widget_action)

        menu.addSeparator()

    def update(self, vd: VehicleData, enabled: bool) -> None:
        self._battery_action.setText(f"Battery: {vd.battery_level}%")
        self._charge_toggle_action.setEnabled(enabled)

        if vd.charging_state == "Charging":
            self._charge_toggle_action.setText("Stop Charge")
        else:
            self._charge_toggle_action.setText("Start Charge")

        cs = vd.charging_state
        if cs == "Charging":
            cs_color = "green"
        elif cs in ("Stopped", "Disconnected"):
            cs_color = "red"
        else:
            cs_color = "orange"
        self._charger_status_label.setText(
            f"Charger: <span style='color:{cs_color}'>{cs}</span>"
        )

    def _on_charge_toggle(self) -> None:
        if self._tesla.vehicle_data.charging_state == "Charging":
            asyncio.ensure_future(self._tesla.stop_charge())
        else:
            asyncio.ensure_future(self._tesla.start_charge())
