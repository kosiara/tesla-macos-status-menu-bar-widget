"""System tray icon and menu — the main entry point for the app UI."""

import asyncio
import logging
import secrets
import webbrowser
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication,
    QSystemTrayIcon,
    QMenu,
    QWidgetAction,
    QLabel,
)
from PySide6.QtGui import QIcon, QAction, QPixmap, Qt
from PySide6.QtCore import QTimer

from teslabar.config import load_config
from teslabar.services.tesla_api import TeslaService, VehicleState
from teslabar.services.oauth_server import (
    start_callback_server,
    stop_callback_server,
    get_callback_result,
    get_local_redirect_uri,
)
from teslabar.ui.settings_window import SettingsWindow
from teslabar.ui.status_window import StatusWindow
from teslabar.ui.main_window import MainWindow
from teslabar.ui.charge_limit_popup import ChargeLimitPopup
from teslabar.ui.schedule_window import (
    PreconditionListWindow,
    ChargingListWindow,
    PreconditionSetWindow,
)

logger = logging.getLogger(__name__)

RESOURCES = Path(__file__).parent.parent.parent / "resources"


class TeslaBarTray:
    def __init__(
        self, app: QApplication, tesla_service: TeslaService, password: str
    ) -> None:
        self._app = app
        self._tesla = tesla_service
        self._password = password
        self._cfg = load_config()
        self._tesla._reauth_callback = self._start_oauth_flow

        # Child windows (kept alive to avoid GC)
        self._settings_win: SettingsWindow | None = None
        self._status_win: StatusWindow | None = None
        self._main_win: MainWindow | None = None
        self._charge_limit_popup: ChargeLimitPopup | None = None
        self._precond_list_win: PreconditionListWindow | None = None
        self._charging_list_win: ChargingListWindow | None = None
        self._precond_set_win: PreconditionSetWindow | None = None

        # Menu refresh state
        self._menu_is_open = False
        self._refresh_timer = QTimer()
        self._refresh_timer.timeout.connect(self._on_menu_refresh)
        self._refresh_timer.setInterval(5000)

        # OAuth polling
        self._oauth_timer = QTimer()
        self._oauth_timer.timeout.connect(self._poll_oauth_callback)
        self._oauth_state: str = ""

        # Build tray
        self._tray = QSystemTrayIcon()
        icon_path = RESOURCES / "tesla_icon.png"
        if icon_path.exists():
            self._tray.setIcon(QIcon(str(icon_path)))
        else:
            self._tray.setIcon(self._app.style().standardIcon(
                self._app.style().StandardPixmap.SP_ComputerIcon
            ))
        self._tray.setToolTip("TeslaBar")

        self._build_menu()
        self._tray.show()

    def _build_menu(self) -> None:
        menu = QMenu()

        # RE-AUTHENTICATE (hidden by default, shown when auth expired)
        self._reauth_action = QAction("RE-AUTHENTICATE", menu)
        self._reauth_action.triggered.connect(self._start_oauth_flow)
        self._reauth_action.setVisible(False)
        menu.addAction(self._reauth_action)

        # 0. STATUS
        self._status_action = QAction("Status: loading...", menu)
        self._status_action.triggered.connect(self._open_status)
        menu.addAction(self._status_action)

        menu.addSeparator()

        # 1. Settings
        settings_action = QAction("Settings", menu)
        settings_action.triggered.connect(self._open_settings)
        menu.addAction(settings_action)

        # 2. Open in a window
        window_action = QAction("Open in a Window", menu)
        window_action.triggered.connect(self._open_main_window)
        menu.addAction(window_action)

        menu.addSeparator()

        # 3. Battery
        self._battery_action = QAction("Battery: --%", menu)
        self._battery_action.setEnabled(False)
        menu.addAction(self._battery_action)

        # 4. Start/Stop Charge
        self._charge_toggle_action = QAction("Start Charge", menu)
        self._charge_toggle_action.triggered.connect(self._on_charge_toggle)
        menu.addAction(self._charge_toggle_action)

        # 5. Charger status
        self._charger_status_label = QLabel("Charger: --")
        self._charger_status_label.setTextFormat(Qt.TextFormat.RichText)
        self._charger_status_label.setContentsMargins(20, 4, 20, 4)
        charger_widget_action = QWidgetAction(menu)
        charger_widget_action.setDefaultWidget(self._charger_status_label)
        menu.addAction(charger_widget_action)

        menu.addSeparator()

        # 7. Vehicle security (not clickable)
        self._lock_action = QAction("Vehicle: --", menu)
        self._lock_action.setEnabled(False)
        menu.addAction(self._lock_action)

        # 8. Sentry (not clickable)
        self._sentry_action = QAction("Sentry: --", menu)
        self._sentry_action.setEnabled(False)
        menu.addAction(self._sentry_action)

        menu.addSeparator()

        # 9. Charge level limit
        self._charge_limit_action = QAction("Charge Limit: --%", menu)
        self._charge_limit_action.triggered.connect(self._open_charge_limit)
        menu.addAction(self._charge_limit_action)

        # 10. Set Precondition schedule
        precond_set_action = QAction("Set Precondition Schedule", menu)
        precond_set_action.triggered.connect(self._open_precond_set)
        menu.addAction(precond_set_action)

        # 11. Climate On/Off
        self._climate_action = QAction("Climate: --", menu)
        self._climate_action.triggered.connect(self._on_climate_toggle)
        menu.addAction(self._climate_action)

        menu.addSeparator()

        # 12. Precondition times
        precond_list_action = QAction("Precondition Times", menu)
        precond_list_action.triggered.connect(self._open_precond_list)
        menu.addAction(precond_list_action)

        # 13. Charging times
        charging_list_action = QAction("Charging Times", menu)
        charging_list_action.triggered.connect(self._open_charging_list)
        menu.addAction(charging_list_action)

        menu.addSeparator()

        # 14. Quit
        quit_action = QAction("Quit", menu)
        quit_action.triggered.connect(self._on_quit)
        menu.addAction(quit_action)

        # Track menu open/close for refresh
        menu.aboutToShow.connect(self._on_menu_about_to_show)
        menu.aboutToHide.connect(self._on_menu_about_to_hide)

        self._menu = menu
        self._tray.setContextMenu(menu)

    def _on_menu_about_to_show(self) -> None:
        self._menu_is_open = True
        self._on_menu_refresh()  # immediate refresh
        self._refresh_timer.start()

    def _on_menu_about_to_hide(self) -> None:
        self._menu_is_open = False
        self._refresh_timer.stop()

    def _on_menu_refresh(self) -> None:
        asyncio.ensure_future(self._do_refresh())

    async def _do_refresh(self) -> None:
        try:
            await self._tesla.fetch_vehicle_data()
        except BaseException as e:
            err_name = type(e).__name__.lower()
            err_msg = str(e).lower()
            if "expired" in err_name or "expired" in err_msg or "oauthexpired" in err_name:
                self._tesla.vehicle_data.state = VehicleState.AUTH_EXPIRED
            elif "vehicleoffline" in err_name or "not 'online'" in err_msg:
                self._tesla.vehicle_data.state = VehicleState.ASLEEP
                self._update_menu()
                awake = await self._tesla._wake_if_needed()
                if awake:
                    await self._tesla.fetch_vehicle_data()
            else:
                logger.error("Refresh error: %s", e)
                self._tesla.vehicle_data.state = VehicleState.ERROR
                self._tesla.vehicle_data.error_message = str(e)
        self._update_menu()

    def _update_menu(self) -> None:
        vd = self._tesla.vehicle_data
        cfg = load_config()
        unit = cfg.get("temperature_unit", "C")

        is_error = vd.state in (
            VehicleState.ERROR,
            VehicleState.AUTH_EXPIRED,
            VehicleState.OFFLINE,
            VehicleState.UNKNOWN,
        )
        is_online = vd.state == VehicleState.ONLINE

        # RE-AUTHENTICATE visibility
        if vd.state == VehicleState.AUTH_EXPIRED:
            self._reauth_action.setVisible(True)
            self._status_action.setText("Status: AUTH EXPIRED")
        elif vd.state == VehicleState.ERROR:
            self._reauth_action.setVisible(False)
            self._status_action.setText("Status: ERROR")
        elif vd.state == VehicleState.OFFLINE:
            self._reauth_action.setVisible(False)
            self._status_action.setText("Status: OFFLINE/UNREACHABLE")
        elif vd.state == VehicleState.ASLEEP:
            self._reauth_action.setVisible(False)
            self._status_action.setText("Status: ASLEEP")
        elif vd.state == VehicleState.WAKING:
            self._reauth_action.setVisible(False)
            self._status_action.setText("Status: WAKING...")
        elif is_online:
            self._reauth_action.setVisible(False)
            self._status_action.setText("Status: ONLINE")
        else:
            self._reauth_action.setVisible(False)
            self._status_action.setText("Status: LOADING...")

        if self._tesla.command_status:
            self._status_action.setText(
                f"Status: {self._tesla.command_status}"
            )

        # Grey out items on error
        enabled = is_online or vd.state == VehicleState.ASLEEP
        self._charge_toggle_action.setEnabled(enabled)
        self._charge_limit_action.setEnabled(enabled)
        self._climate_action.setEnabled(enabled)

        # Battery
        self._battery_action.setText(f"Battery: {vd.battery_level}%")

        # Charge toggle
        if vd.charging_state == "Charging":
            self._charge_toggle_action.setText("Stop Charge")
        else:
            self._charge_toggle_action.setText("Start Charge")

        # Charger status
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

        # Security
        self._lock_action.setText(
            f"Vehicle: {'Locked' if vd.is_locked else 'Not Locked'}"
        )
        self._sentry_action.setText(
            f"Sentry: {'On' if vd.sentry_mode else 'Off'}"
        )

        # Charge limit
        self._charge_limit_action.setText(f"Charge Limit: {vd.charge_limit}%")

        # Climate
        climate_text = "Climate: On" if vd.climate_on else "Climate: Off"
        if vd.inside_temp is not None:
            temp = vd.inside_temp
            if unit == "F":
                temp = temp * 9 / 5 + 32
            climate_text += f" ({temp:.1f}°{unit})"
        self._climate_action.setText(climate_text)

        # Update status window if open
        if self._status_win and self._status_win.isVisible():
            self._status_win.refresh()
        if self._main_win and self._main_win.isVisible():
            self._main_win.update_display()

    # --- Actions ---

    def _open_status(self) -> None:
        if self._status_win is None or not self._status_win.isVisible():
            self._status_win = StatusWindow(self._tesla)
        self._status_win.refresh()
        self._status_win.show()
        self._status_win.raise_()
        self._status_win.activateWindow()

    def _open_settings(self) -> None:
        if self._settings_win is None or not self._settings_win.isVisible():
            self._settings_win = SettingsWindow(self._tesla, self._password)
        self._settings_win.show()
        self._settings_win.raise_()
        self._settings_win.activateWindow()

    def _open_main_window(self) -> None:
        if self._main_win is None or not self._main_win.isVisible():
            self._main_win = MainWindow(self._tesla)
        self._main_win.update_display()
        self._main_win.show()
        self._main_win.raise_()
        self._main_win.activateWindow()

    def _on_charge_toggle(self) -> None:
        vd = self._tesla.vehicle_data
        if vd.charging_state == "Charging":
            asyncio.ensure_future(self._tesla.stop_charge())
        else:
            asyncio.ensure_future(self._tesla.start_charge())

    def _open_charge_limit(self) -> None:
        current = self._tesla.vehicle_data.charge_limit
        self._charge_limit_popup = ChargeLimitPopup(current)
        self._charge_limit_popup.charge_limit_changed.connect(
            self._on_charge_limit_set
        )
        self._charge_limit_popup.show()
        self._charge_limit_popup.raise_()

    def _on_charge_limit_set(self, percent: int) -> None:
        asyncio.ensure_future(self._tesla.set_charge_limit(percent))

    def _on_climate_toggle(self) -> None:
        if self._tesla.vehicle_data.climate_on:
            asyncio.ensure_future(self._tesla.climate_off())
        else:
            asyncio.ensure_future(self._tesla.climate_on())

    def _open_precond_set(self) -> None:
        self._precond_set_win = PreconditionSetWindow(self._tesla)
        self._precond_set_win.show()
        self._precond_set_win.raise_()

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

    # --- OAuth ---

    def _start_oauth_flow(self) -> None:
        self._oauth_state = secrets.token_urlsafe(32)
        redirect_uri = get_local_redirect_uri()
        start_callback_server()
        url = self._tesla.get_oauth_url(redirect_uri, self._oauth_state)
        webbrowser.open(url)
        self._oauth_timer.start(1000)
        self._status_action.setText("Status: Waiting for OAuth...")

    def _poll_oauth_callback(self) -> None:
        result = get_callback_result()
        if result is None:
            return
        self._oauth_timer.stop()
        stop_callback_server()

        if "error" in result:
            logger.error("OAuth error: %s", result["error"])
            self._status_action.setText("Status: OAuth failed")
            return

        code = result.get("code")
        if code:
            asyncio.ensure_future(self._complete_oauth(code))

    async def _complete_oauth(self, code: str) -> None:
        try:
            redirect_uri = get_local_redirect_uri()
            await self._tesla.exchange_code(code, redirect_uri)
            # Save tokens in encrypted store
            from teslabar.crypto.credential_store import (
                load_credentials,
                save_credentials,
            )
            try:
                creds = load_credentials(self._password)
            except Exception:
                creds = {
                    "client_id": self._tesla._client_id,
                    "client_secret": self._tesla._client_secret,
                }
            tokens = self._tesla.get_tokens()
            creds.update(tokens)
            save_credentials(creds, self._password)

            self._status_action.setText("Status: Authenticated!")
            logger.info("OAuth authentication successful")

            # One-time partner registration (needed for Fleet API access)
            domain = load_config().get("github_pages_domain", "")
            await self._tesla.register_partner(domain)

            # Discover vehicle
            await self._tesla.discover_vehicle()
            self._update_menu()
        except BaseException as e:
            logger.error("OAuth completion failed: %s", e)
            self._status_action.setText(f"Status: Auth error - {e}")

    def _on_quit(self) -> None:
        asyncio.ensure_future(self._tesla.close())
        self._tray.hide()
        self._app.quit()
