"""Switches section: charge limit, cabin temp, climate, precondition schedule."""

import asyncio

from PySide6.QtWidgets import QMenu, QWidgetAction, QLabel
from PySide6.QtGui import QAction, Qt

from teslabar.config import load_config
from teslabar.services.tesla_api import TeslaService, VehicleData
from teslabar.ui.popup.charge_limit_popup import ChargeLimitPopup
from teslabar.ui.popup.cabin_temp_popup import CabinTempPopup
from teslabar.ui.popup.charging_amps_popup import ChargingAmpsPopup
from teslabar.ui.tray.tray_app_preheating import PreheatingSection
from teslabar.ui.schedule.preconditioning_set_schedule_window import PreconditionSetWindow


class SwitchesSection:
    """Charge limit, cabin temp, temperature limit, precondition schedule, climate."""

    def __init__(self, menu: QMenu, tesla_service: TeslaService) -> None:
        self._tesla = tesla_service
        self._charge_limit_popup: ChargeLimitPopup | None = None
        self._charging_amps_popup: ChargingAmpsPopup | None = None
        self._cabin_temp_popup: CabinTempPopup | None = None
        self._precond_set_win: PreconditionSetWindow | None = None

        # Preheating
        self._preheating = PreheatingSection(menu, tesla_service)
        # menu.addAction(self._preheating.widget_action)

        # Charge limit (rich text, clickable)
        self._charge_limit_label = QLabel("Charge Limit: --%")
        self._charge_limit_label.setTextFormat(Qt.TextFormat.RichText)
        self._charge_limit_label.setContentsMargins(20, 4, 20, 4)
        self._charge_limit_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self._charge_limit_label.mousePressEvent = lambda _: self._open_charge_limit()
        charge_limit_widget = QWidgetAction(menu)
        charge_limit_widget.setDefaultWidget(self._charge_limit_label)
        self._charge_limit_widget_action = charge_limit_widget
        menu.addAction(charge_limit_widget)

        # Charge rate (rich text, clickable)
        self._charge_rate_label = QLabel("Charge rate: --")
        self._charge_rate_label.setTextFormat(Qt.TextFormat.RichText)
        self._charge_rate_label.setContentsMargins(20, 4, 20, 4)
        self._charge_rate_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self._charge_rate_label.mousePressEvent = lambda _: self._open_charging_amps()
        charge_rate_widget = QWidgetAction(menu)
        charge_rate_widget.setDefaultWidget(self._charge_rate_label)
        self._charge_rate_widget_action = charge_rate_widget
        menu.addAction(charge_rate_widget)

        # Cabin temperature (rich text, clickable)
        self._cabin_temp_label = QLabel("Cabin Temperature: --")
        self._cabin_temp_label.setTextFormat(Qt.TextFormat.RichText)
        self._cabin_temp_label.setContentsMargins(20, 4, 20, 4)
        self._cabin_temp_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cabin_temp_label.mousePressEvent = lambda _: self._open_cabin_temp()
        cabin_temp_widget = QWidgetAction(menu)
        cabin_temp_widget.setDefaultWidget(self._cabin_temp_label)
        menu.addAction(cabin_temp_widget)

        # Temperature limit
        self._temp_limit_action = QAction("Temperature Limit: --", menu)
        self._temp_limit_action.triggered.connect(self._open_cabin_temp)
        menu.addAction(self._temp_limit_action)

        # Set Precondition schedule
        precond_set_action = QAction("Set Precondition Schedule", menu)
        precond_set_action.triggered.connect(self._open_precond_set)
        menu.addAction(precond_set_action)

        # Climate On/Off
        self._climate_action = QAction("Climate: --", menu)
        self._climate_action.triggered.connect(self._on_climate_toggle)
        menu.addAction(self._climate_action)

        # Low Power Mode (rich text, clickable)
        self._low_power_label = QLabel("Low power mode: --")
        self._low_power_label.setTextFormat(Qt.TextFormat.RichText)
        self._low_power_label.setContentsMargins(20, 4, 20, 4)
        self._low_power_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self._low_power_label.mousePressEvent = lambda _: self._on_low_power_toggle()
        low_power_widget = QWidgetAction(menu)
        low_power_widget.setDefaultWidget(self._low_power_label)
        self._low_power_widget_action = low_power_widget
        menu.addAction(low_power_widget)

        menu.addSeparator()

    def update(self, vd: VehicleData, enabled: bool) -> None:
        cfg = load_config()
        unit = cfg.get("temperature_unit", "C")

        self._charge_limit_widget_action.setEnabled(enabled)
        self._charge_rate_widget_action.setEnabled(enabled)
        self._climate_action.setEnabled(enabled)

        # Preheating
        self._preheating.update(vd.is_preconditioning, enabled)

        # Charge limit
        cl = vd.charge_limit
        if cl <= 80:
            cl_color = "green"
        elif cl <= 95:
            cl_color = "orange"
        else:
            cl_color = "red"
        self._charge_limit_label.setText(
            f"Charge Limit: <span style='color:{cl_color}; font-weight:bold;'>{cl}%</span>"
        )

        # Charge rate
        amps = vd.charger_actual_current
        phases = vd.charger_phases
        voltage = vd.charger_voltage

        if amps >= 16:
            a_color = "green"
        elif amps >= 12:
            a_color = "orange"
        else:
            a_color = "red"

        if voltage >= 220:
            v_color = "green"
        elif voltage >= 210:
            v_color = "orange"
        else:
            v_color = "red"

        # Tesla API returns 2 for 3-phase, 1 for 1-phase
        actual_phases = {1: 1, 2: 3}.get(phases, None) if phases else None

        if actual_phases == 3:
            p_color = "green"
        else:
            p_color = "red"

        phases_str = f"{actual_phases}f" if actual_phases else "--f"
        self._charge_rate_label.setText(
            f"Charge rate: "
            f"<span style='color:{a_color}; font-weight:bold;'>{amps}A</span> / "
            f"<span style='color:{p_color}; font-weight:bold;'>{phases_str}</span> / "
            f"<span style='color:{v_color}; font-weight:bold;'>{voltage}V</span>"
        )

        # Cabin temperature
        if vd.inside_temp is not None:
            cabin_t = vd.inside_temp
            if cabin_t < 20:
                t_color = "blue"
            elif cabin_t <= 25:
                t_color = "orange"
            else:
                t_color = "red"
            self._cabin_temp_label.setText(
                f"Cabin Temperature: <span style='color:{t_color}'>{cabin_t:.1f}°C</span>"
            )
        else:
            self._cabin_temp_label.setText("Cabin Temperature: --")

        # Temperature limit
        if vd.driver_temp_setting is not None:
            self._temp_limit_action.setText(
                f"Temperature Limit: {vd.driver_temp_setting:.1f}°C"
            )
        else:
            self._temp_limit_action.setText("Temperature Limit: --")

        # Climate
        climate_text = "Climate: On" if vd.climate_on else "Climate: Off"
        if vd.inside_temp is not None:
            temp = vd.inside_temp
            if unit == "F":
                temp = temp * 9 / 5 + 32
            climate_text += f" ({temp:.1f}°{unit})"
        self._climate_action.setText(climate_text)

        # Low Power Mode
        self._low_power_widget_action.setEnabled(enabled)
        if vd.low_power_mode:
            self._low_power_label.setText(
                "Low power mode: <span style='color:red; font-weight:bold;'>ON</span>"
            )
        else:
            self._low_power_label.setText(
                "Low power mode: <span style='color:green; font-weight:bold;'>OFF</span>"
            )

    def _open_charge_limit(self) -> None:
        current = self._tesla.vehicle_data.charge_limit
        self._charge_limit_popup = ChargeLimitPopup(current)
        self._charge_limit_popup.charge_limit_changed.connect(self._on_charge_limit_set)
        self._charge_limit_popup.show()
        self._charge_limit_popup.raise_()

    def _on_charge_limit_set(self, percent: int) -> None:
        asyncio.ensure_future(self._tesla.set_charge_limit(percent))

    def _open_charging_amps(self) -> None:
        if not self._charge_rate_widget_action.isEnabled():
            return
        current = self._tesla.vehicle_data.charger_actual_current or 16
        self._charging_amps_popup = ChargingAmpsPopup(current)
        self._charging_amps_popup.charging_amps_changed.connect(self._on_charging_amps_set)
        self._charging_amps_popup.show()
        self._charging_amps_popup.raise_()

    def _on_charging_amps_set(self, amps: int) -> None:
        asyncio.ensure_future(self._tesla.set_charging_amps(amps))

    def _open_cabin_temp(self) -> None:
        current = self._tesla.vehicle_data.driver_temp_setting or 20.0
        self._cabin_temp_popup = CabinTempPopup(current)
        self._cabin_temp_popup.cabin_temp_changed.connect(self._on_cabin_temp_set)
        self._cabin_temp_popup.show()
        self._cabin_temp_popup.raise_()

    def _on_cabin_temp_set(self, temp: float) -> None:
        asyncio.ensure_future(self._tesla.set_cabin_temp(temp))

    def _on_climate_toggle(self) -> None:
        if self._tesla.vehicle_data.climate_on:
            asyncio.ensure_future(self._tesla.climate_off())
        else:
            asyncio.ensure_future(self._tesla.climate_on())

    def _on_low_power_toggle(self) -> None:
        if not self._low_power_widget_action.isEnabled():
            return
        new_state = not self._tesla.vehicle_data.low_power_mode
        asyncio.ensure_future(self._tesla.set_low_power_mode(new_state))

    def _open_precond_set(self) -> None:
        self._precond_set_win = PreconditionSetWindow(self._tesla)
        self._precond_set_win.show()
        self._precond_set_win.raise_()
