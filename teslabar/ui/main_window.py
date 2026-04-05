"""Main window mode - shows all menu bar info with auto-refresh."""

import asyncio
import logging

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QGroupBox,
    QTabWidget,
)
from PySide6.QtCore import Qt, QTimer

from teslabar.config import load_config
from teslabar.services.tesla_api import TeslaService, VehicleState

logger = logging.getLogger(__name__)


class MainWindow(QWidget):
    def __init__(self, tesla_service: TeslaService, parent=None) -> None:
        super().__init__(parent)
        self._tesla = tesla_service
        self._cfg = load_config()

        self.setWindowTitle("TeslaBar")
        self.setMinimumWidth(380)
        self.setMinimumHeight(450)
        self.setWindowFlags(
            self.windowFlags() | Qt.WindowStaysOnTopHint
        )

        self._build_ui()

        interval = self._cfg.get("refresh_interval_seconds", 15) * 1000
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_refresh)
        self._timer.start(interval)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_general_tab(), "General")
        self._tabs.addTab(self._build_location_tab(), "Location")
        self._tabs.currentChanged.connect(self._on_tab_changed)
        layout.addWidget(self._tabs)

        close_btn = QPushButton("Close Window")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn, alignment=Qt.AlignRight)

    def _build_general_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Status
        self._status_label = QLabel("Status: loading...")
        self._status_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(self._status_label)

        self._cmd_label = QLabel("")
        self._cmd_label.setStyleSheet("color: #0066cc;")
        layout.addWidget(self._cmd_label)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep)

        # Battery
        battery_group = QGroupBox("Battery & Charging")
        bl = QVBoxLayout(battery_group)
        self._battery_label = QLabel("Battery: --%")
        self._battery_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        bl.addWidget(self._battery_label)

        self._charge_status_label = QLabel("Charger: --")
        self._charge_status_label.setTextFormat(Qt.TextFormat.RichText)
        bl.addWidget(self._charge_status_label)

        self._charge_limit_label = QLabel("Charge Limit: --%")
        bl.addWidget(self._charge_limit_label)

        charge_btn_layout = QHBoxLayout()
        self._start_charge_btn = QPushButton("Start Charge")
        self._start_charge_btn.clicked.connect(self._on_start_charge)
        self._stop_charge_btn = QPushButton("Stop Charge")
        self._stop_charge_btn.clicked.connect(self._on_stop_charge)
        charge_btn_layout.addWidget(self._start_charge_btn)
        charge_btn_layout.addWidget(self._stop_charge_btn)
        bl.addLayout(charge_btn_layout)
        layout.addWidget(battery_group)

        # Security
        sec_group = QGroupBox("Security")
        sl = QVBoxLayout(sec_group)
        self._lock_label = QLabel("Vehicle: --")
        sl.addWidget(self._lock_label)
        self._sentry_label = QLabel("Sentry: --")
        sl.addWidget(self._sentry_label)
        layout.addWidget(sec_group)

        # Climate
        climate_group = QGroupBox("Climate")
        cl = QVBoxLayout(climate_group)
        self._climate_label = QLabel("Climate: --")
        cl.addWidget(self._climate_label)
        self._climate_btn = QPushButton("Toggle Climate")
        self._climate_btn.clicked.connect(self._on_toggle_climate)
        cl.addWidget(self._climate_btn)
        layout.addWidget(climate_group)

        layout.addStretch()
        return tab

    def _build_location_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        self._location_status_label = QLabel("")
        self._location_status_label.setStyleSheet("color: #0066cc;")
        layout.addWidget(self._location_status_label)

        self._lat_label = QLabel("Latitude: --")
        self._lat_label.setStyleSheet("font-size: 14px;")
        layout.addWidget(self._lat_label)

        self._lon_label = QLabel("Longitude: --")
        self._lon_label.setStyleSheet("font-size: 14px;")
        layout.addWidget(self._lon_label)

        self._location_updated_label = QLabel("")
        self._location_updated_label.setStyleSheet("color: gray; font-size: 12px;")
        layout.addWidget(self._location_updated_label)

        refresh_btn = QPushButton("Refresh Location")
        refresh_btn.clicked.connect(self._on_refresh_location)
        layout.addWidget(refresh_btn)

        layout.addStretch()
        return tab

    def _on_tab_changed(self, index: int) -> None:
        if index == 1:  # Location tab
            self._on_refresh_location()

    def _on_refresh_location(self) -> None:
        self._location_status_label.setText("Fetching location...")
        asyncio.ensure_future(self._do_refresh_location())

    async def _do_refresh_location(self) -> None:
        try:
            vehicle = await self._tesla._ensure_vehicle()
            logger.info("Fetching location via vehicle_data(endpoints=['drive_state'])")
            resp = await vehicle.vehicle_data(endpoints=["drive_state"])
            logger.info("Location API response: %s", resp)
            data = resp.get("response", {})
            drive = data.get("drive_state", {})
            lat = drive.get("latitude")
            lon = drive.get("longitude")
            if lat is not None and lon is not None:
                self._tesla._update_location(data)
                self._lat_label.setText(f"Latitude: {lat:.6f}")
                self._lon_label.setText(f"Longitude: {lon:.6f}")
                self._location_status_label.setText("Location fetched successfully.")
                self._location_status_label.setStyleSheet("color: green;")
                import time
                from datetime import datetime
                self._location_updated_label.setText(
                    f"Updated: {datetime.now().strftime('%H:%M:%S')}"
                )
            else:
                self._location_status_label.setText(
                    "Location not available (vehicle may be asleep)."
                )
                self._location_status_label.setStyleSheet("color: orange;")
                # Show saved location if available
                vd = self._tesla.vehicle_data
                if vd.latitude and vd.longitude:
                    self._lat_label.setText(f"Latitude: {vd.latitude:.6f} (saved)")
                    self._lon_label.setText(f"Longitude: {vd.longitude:.6f} (saved)")
        except BaseException as e:
            self._location_status_label.setText(f"Error: {e}")
            self._location_status_label.setStyleSheet("color: red;")
            # Show saved location as fallback
            vd = self._tesla.vehicle_data
            if vd.latitude and vd.longitude:
                self._lat_label.setText(f"Latitude: {vd.latitude:.6f} (saved)")
                self._lon_label.setText(f"Longitude: {vd.longitude:.6f} (saved)")

    def _on_refresh(self) -> None:
        asyncio.ensure_future(self._do_refresh())

    async def _do_refresh(self) -> None:
        try:
            await self._tesla.fetch_vehicle_data()
        except BaseException as e:
            err_name = type(e).__name__.lower()
            err_msg = str(e).lower()
            if "vehicleoffline" in err_name or "not 'online'" in err_msg:
                self._tesla.vehicle_data.state = VehicleState.ASLEEP
                self.update_display()
                awake = await self._tesla._wake_if_needed()
                if awake:
                    await self._tesla.fetch_vehicle_data()
            else:
                self._tesla.vehicle_data.state = VehicleState.ERROR
                self._tesla.vehicle_data.error_message = str(e)
        self.update_display()

    def update_display(self) -> None:
        vd = self._tesla.vehicle_data
        unit = self._cfg.get("temperature_unit", "C")

        state_text = vd.state.value.upper()
        if vd.state == VehicleState.ERROR:
            self._status_label.setStyleSheet(
                "font-size: 14px; font-weight: bold; color: red;"
            )
        elif vd.state == VehicleState.ONLINE:
            self._status_label.setStyleSheet(
                "font-size: 14px; font-weight: bold; color: green;"
            )
        else:
            self._status_label.setStyleSheet(
                "font-size: 14px; font-weight: bold; color: orange;"
            )
        self._status_label.setText(f"Status: {state_text}")
        self._cmd_label.setText(self._tesla.command_status)

        self._battery_label.setText(f"Battery: {vd.battery_level}%")
        charging_state = vd.charging_state
        if charging_state == "Charging":
            color = "green"
        elif charging_state in ("Stopped", "Disconnected"):
            color = "red"
        else:
            color = "orange"
        self._charge_status_label.setText(
            f"Charger: <span style='color:{color}'>{charging_state}</span>"
        )
        self._charge_limit_label.setText(f"Charge Limit: {vd.charge_limit}%")

        self._lock_label.setText(
            f"Vehicle: {'Locked' if vd.is_locked else 'Not Locked'}"
        )
        self._sentry_label.setText(
            f"Sentry: {'On' if vd.sentry_mode else 'Off'}"
        )

        climate_text = "On" if vd.climate_on else "Off"
        if vd.inside_temp is not None:
            temp = vd.inside_temp
            if unit == "F":
                temp = temp * 9 / 5 + 32
            climate_text += f" (Inside: {temp:.1f}°{unit})"
        self._climate_label.setText(f"Climate: {climate_text}")

    def _on_start_charge(self) -> None:
        asyncio.ensure_future(self._tesla.start_charge())

    def _on_stop_charge(self) -> None:
        asyncio.ensure_future(self._tesla.stop_charge())

    def _on_toggle_climate(self) -> None:
        if self._tesla.vehicle_data.climate_on:
            asyncio.ensure_future(self._tesla.climate_off())
        else:
            asyncio.ensure_future(self._tesla.climate_on())

    def closeEvent(self, event) -> None:
        self._timer.stop()
        super().closeEvent(event)
