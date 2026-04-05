"""Location tab widget for the main window."""

import asyncio
import logging

import folium
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QLineEdit,
)
from PySide6.QtWebEngineWidgets import QWebEngineView

from teslabar.config import load_config, save_config
from teslabar.services.tesla_api import TeslaService

logger = logging.getLogger(__name__)

DEFAULT_LAT = 52.23
DEFAULT_LON = 21.01
DEFAULT_ZOOM = 5


class LocationTab(QWidget):
    def __init__(self, tesla_service: TeslaService, parent=None) -> None:
        super().__init__(parent)
        self._tesla = tesla_service
        self._superchargers: list[dict] = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Fetch from API section
        self._location_status_label = QLabel("")
        self._location_status_label.setStyleSheet("color: #0066cc;")
        layout.addWidget(self._location_status_label)

        refresh_btn = QPushButton("Fetch Location from Vehicle")
        refresh_btn.clicked.connect(self._on_refresh_location)
        layout.addWidget(refresh_btn)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep)

        # Manual / saved location
        info_label = QLabel("Location:")
        info_label.setStyleSheet("font-size: 13px; font-weight: bold;")
        layout.addWidget(info_label)

        lat_row = QHBoxLayout()
        lat_row.addWidget(QLabel("Latitude:"))
        self._lat_input = QLineEdit()
        self._lat_input.setPlaceholderText("e.g. 52.229676")
        lat_row.addWidget(self._lat_input)
        layout.addLayout(lat_row)

        lon_row = QHBoxLayout()
        lon_row.addWidget(QLabel("Longitude:"))
        self._lon_input = QLineEdit()
        self._lon_input.setPlaceholderText("e.g. 21.012229")
        lon_row.addWidget(self._lon_input)
        layout.addLayout(lon_row)

        save_btn = QPushButton("Save Location")
        save_btn.clicked.connect(self._on_save_location)
        layout.addWidget(save_btn)

        self._location_save_label = QLabel("")
        self._location_save_label.setStyleSheet("color: gray; font-size: 12px;")
        layout.addWidget(self._location_save_label)

        # Supercharger button
        self._supercharger_btn = QPushButton("Find nearest Superchargers")
        self._supercharger_btn.clicked.connect(self._on_find_superchargers)
        layout.addWidget(self._supercharger_btn)

        self._supercharger_status_label = QLabel("")
        self._supercharger_status_label.setStyleSheet("color: gray; font-size: 12px;")
        layout.addWidget(self._supercharger_status_label)

        # Map view
        self._map_view = QWebEngineView()
        self._map_view.setMinimumHeight(300)
        layout.addWidget(self._map_view)

        # Load saved values and show map
        self._load_location_inputs()
        self._update_map()

    def _load_location_inputs(self) -> None:
        cfg = load_config()
        lat = cfg.get("vehicle_latitude")
        lon = cfg.get("vehicle_longitude")
        if lat is not None:
            self._lat_input.setText(str(lat))
        if lon is not None:
            self._lon_input.setText(str(lon))

    def _get_input_coords(self) -> tuple[float | None, float | None]:
        try:
            lat = float(self._lat_input.text())
            lon = float(self._lon_input.text())
            return lat, lon
        except (ValueError, TypeError):
            return None, None

    def _update_map(self, lat: float | None = None, lon: float | None = None) -> None:
        if lat is None or lon is None:
            lat, lon = self._get_input_coords()
        has_coords = lat is not None and lon is not None
        zoom = 15 if has_coords and not self._superchargers else DEFAULT_ZOOM
        if has_coords and self._superchargers:
            zoom = 9
        center = [lat, lon] if has_coords else [DEFAULT_LAT, DEFAULT_LON]
        m = folium.Map(location=center, zoom_start=zoom)

        # Vehicle marker (blue)
        if has_coords:
            folium.Marker(
                [lat, lon],
                popup=f"Vehicle: {lat:.6f}, {lon:.6f}",
                tooltip="Vehicle location",
                icon=folium.Icon(color="blue", icon="car", prefix="fa"),
            ).add_to(m)

        # Supercharger markers (red)
        for sc in self._superchargers:
            sc_lat = sc.get("location", {}).get("lat")
            sc_lon = sc.get("location", {}).get("long")
            if sc_lat is None or sc_lon is None:
                continue
            name = sc.get("name", "Supercharger")
            stalls = sc.get("available_stalls", "?")
            total = sc.get("total_stalls", "?")
            dist_km = sc.get("distance_miles", 0) * 1.60934
            popup_text = (
                f"<b>{name}</b><br>"
                f"Stalls: {stalls}/{total}<br>"
                f"Distance: {dist_km:.1f} km"
            )
            folium.Marker(
                [sc_lat, sc_lon],
                popup=folium.Popup(popup_text, max_width=250),
                tooltip=name,
                icon=folium.Icon(color="red", icon="bolt", prefix="fa"),
            ).add_to(m)

        self._map_view.setHtml(m._repr_html_())

    def _on_save_location(self) -> None:
        try:
            lat = float(self._lat_input.text())
            lon = float(self._lon_input.text())
        except ValueError:
            self._location_save_label.setText("Invalid coordinates. Enter decimal numbers.")
            self._location_save_label.setStyleSheet("color: red; font-size: 12px;")
            return
        cfg = load_config()
        cfg["vehicle_latitude"] = lat
        cfg["vehicle_longitude"] = lon
        save_config(cfg)
        self._tesla.vehicle_data.latitude = lat
        self._tesla.vehicle_data.longitude = lon
        logger.info("Home location saved manually: %.6f, %.6f", lat, lon)
        self._location_save_label.setText(f"Saved: {lat:.6f}, {lon:.6f}")
        self._location_save_label.setStyleSheet("color: green; font-size: 12px;")
        self._update_map(lat, lon)

    def on_tab_selected(self) -> None:
        """Called when user switches to the Location tab."""
        self._on_refresh_location()

    def _on_refresh_location(self) -> None:
        self._location_status_label.setText("Fetching location...")
        self._location_status_label.setStyleSheet("color: #0066cc;")
        asyncio.ensure_future(self._do_refresh_location())

    async def _do_refresh_location(self) -> None:
        lat, lon = None, None
        try:
            vehicle = await self._tesla._ensure_vehicle()

            # Try drive_state first
            logger.info("Fetching location via vehicle_data(endpoints=['drive_state'])")
            resp = await vehicle.vehicle_data(endpoints=["drive_state"])
            logger.info("drive_state response: %s", resp)
            data = resp.get("response", {})
            drive = data.get("drive_state", {})
            lat = drive.get("latitude")
            lon = drive.get("longitude")

            # Fall back to location_data if drive_state had no coordinates
            if lat is None or lon is None:
                try:
                    logger.info("drive_state had no coordinates, trying location_data")
                    resp2 = await vehicle.vehicle_data(endpoints=["location_data"])
                    logger.info("location_data response: %s", resp2)
                    data2 = resp2.get("response", {})
                    loc = data2.get("drive_state", {})
                    lat = loc.get("latitude")
                    lon = loc.get("longitude")
                except BaseException as e2:
                    logger.warning("location_data endpoint failed: %s", e2)

            if lat is not None and lon is not None:
                self._tesla._update_location({"drive_state": {"latitude": lat, "longitude": lon}})
                self._lat_input.setText(str(lat))
                self._lon_input.setText(str(lon))
                self._location_status_label.setText("Location fetched — press Save to store it.")
                self._location_status_label.setStyleSheet("color: green;")
                from datetime import datetime
                self._location_save_label.setText(
                    f"Updated: {datetime.now().strftime('%H:%M:%S')}"
                )
                self._update_map(lat, lon)
            else:
                self._location_status_label.setText(
                    "Could not fetch location. Enter coordinates manually."
                )
                self._location_status_label.setStyleSheet("color: orange;")
        except BaseException as e:
            logger.error("Location fetch error: %s", e)
            self._location_status_label.setText(f"Error: {e}")
            self._location_status_label.setStyleSheet("color: red;")

    def _on_find_superchargers(self) -> None:
        self._supercharger_status_label.setText("Searching for nearby Superchargers...")
        self._supercharger_status_label.setStyleSheet("color: #0066cc; font-size: 12px;")
        asyncio.ensure_future(self._do_find_superchargers())

    async def _do_find_superchargers(self) -> None:
        try:
            sites = await self._tesla.nearby_charging_sites(radius=200)
            self._superchargers = sites
            count = len(sites)
            if count:
                self._supercharger_status_label.setText(f"Found {count} Supercharger(s).")
                self._supercharger_status_label.setStyleSheet("color: green; font-size: 12px;")
            else:
                self._supercharger_status_label.setText("No Superchargers found nearby.")
                self._supercharger_status_label.setStyleSheet("color: orange; font-size: 12px;")
            self._update_map()
        except BaseException as e:
            logger.error("Supercharger search error: %s", e)
            self._supercharger_status_label.setText(f"Error: {e}")
            self._supercharger_status_label.setStyleSheet("color: red; font-size: 12px;")
