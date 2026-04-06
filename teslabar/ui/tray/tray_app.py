"""System tray icon and menu — the main entry point for the app UI."""

import asyncio
import logging
import secrets
import webbrowser
from pathlib import Path

from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QWidgetAction, QLabel
from PySide6.QtGui import QIcon, QAction
from PySide6.QtCore import QTimer

from teslabar.config import load_config
from teslabar.services.tesla_api import TeslaService, VehicleState
from teslabar.services.oauth_server import (
    start_callback_server,
    stop_callback_server,
    get_callback_result,
    get_local_redirect_uri,
)
from teslabar.ui.settings.settings_window import SettingsWindow
from teslabar.ui.status.status_window import StatusWindow
from teslabar.ui.mainwindow.main_window import MainWindow
from teslabar.ui.tray.tray_app_main import MainSection
from teslabar.ui.tray.tray_app_battery_charging import BatteryChargingSection
from teslabar.ui.tray.tray_app_security import SecuritySection
from teslabar.ui.tray.tray_app_switches import SwitchesSection
from teslabar.ui.tray.tray_app_schedules import SchedulesSection

logger = logging.getLogger(__name__)

RESOURCES = Path(__file__).parent.parent.parent.parent / "resources"


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

        # Invisible spacer to force menu width on macOS
        spacer = QLabel()
        spacer.setFixedWidth(210)
        spacer.setFixedHeight(2)
        spacer_action = QWidgetAction(menu)
        spacer_action.setDefaultWidget(spacer)
        menu.addAction(spacer_action)

        # Section 1: Status, Settings, Open in a Window
        self._main_section = MainSection(
            menu,
            self._tesla,
            open_status_cb=self._open_status,
            open_settings_cb=self._open_settings,
            open_main_window_cb=self._open_main_window,
            start_oauth_cb=self._start_oauth_flow,
        )

        # Section 2: Battery, Start/Stop Charge, Charger status
        self._battery_section = BatteryChargingSection(menu, self._tesla)

        # Section 3: Vehicle lock, Sentry
        self._security_section = SecuritySection(menu)

        # Section 4: Charge limit, Cabin temp, Temp limit, Precondition schedule, Climate
        self._switches_section = SwitchesSection(menu, self._tesla)

        # Section 5: Precondition times, Charging times
        self._schedules_section = SchedulesSection(menu, self._tesla)

        # Quit
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
        self._on_menu_refresh()
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
        is_online = vd.state == VehicleState.ONLINE
        enabled = is_online or vd.state == VehicleState.ASLEEP

        self._main_section.update(vd)
        self._battery_section.update(vd, enabled)
        self._security_section.update(vd)
        self._switches_section.update(vd, enabled)

        # Update child windows if open
        if self._status_win and self._status_win.isVisible():
            self._status_win.refresh()
        if self._main_win and self._main_win.isVisible():
            self._main_win.update_display()

    # --- Window openers ---

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

    # --- OAuth ---

    def _start_oauth_flow(self) -> None:
        self._oauth_state = secrets.token_urlsafe(32)
        redirect_uri = get_local_redirect_uri()
        start_callback_server()
        url = self._tesla.get_oauth_url(redirect_uri, self._oauth_state)
        webbrowser.open(url)
        self._oauth_timer.start(1000)
        self._main_section.status_action.setText("Status: Waiting for OAuth...")

    def _poll_oauth_callback(self) -> None:
        result = get_callback_result()
        if result is None:
            return
        self._oauth_timer.stop()
        stop_callback_server()

        if "error" in result:
            logger.error("OAuth error: %s", result["error"])
            self._main_section.status_action.setText("Status: OAuth failed")
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

            self._main_section.status_action.setText("Status: Authenticated!")
            logger.info("OAuth authentication successful")

            # One-time partner registration (needed for Fleet API access)
            domain = load_config().get("github_pages_domain", "")
            await self._tesla.register_partner(domain)

            # Discover vehicle
            await self._tesla.discover_vehicle()
            self._update_menu()
        except BaseException as e:
            logger.error("OAuth completion failed: %s", e)
            self._main_section.status_action.setText(f"Status: Auth error - {e}")

    def _on_quit(self) -> None:
        asyncio.ensure_future(self._tesla.close())
        self._tray.hide()
        self._app.quit()
