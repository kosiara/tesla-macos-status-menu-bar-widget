"""Main section: status, settings, open in a window."""

from PySide6.QtWidgets import QMenu
from PySide6.QtGui import QAction

from teslabar.services.tesla_api import TeslaService, VehicleState, VehicleData


class MainSection:
    """Status line, Settings, and Open in a Window menu items."""

    def __init__(
        self,
        menu: QMenu,
        tesla_service: TeslaService,
        open_status_cb,
        open_settings_cb,
        open_main_window_cb,
        start_oauth_cb,
    ) -> None:
        self._tesla = tesla_service

        # RE-AUTHENTICATE (hidden by default)
        self._reauth_action = QAction("RE-AUTHENTICATE", menu)
        self._reauth_action.triggered.connect(start_oauth_cb)
        self._reauth_action.setVisible(False)
        menu.addAction(self._reauth_action)

        # Status
        self._status_action = QAction("Status: loading...", menu)
        self._status_action.triggered.connect(open_status_cb)
        menu.addAction(self._status_action)

        menu.addSeparator()

        # Settings
        settings_action = QAction("Settings", menu)
        settings_action.triggered.connect(open_settings_cb)
        menu.addAction(settings_action)

        # Open in a window
        window_action = QAction("Open in a Window", menu)
        window_action.triggered.connect(open_main_window_cb)
        menu.addAction(window_action)

        menu.addSeparator()

    @property
    def status_action(self) -> QAction:
        return self._status_action

    @property
    def reauth_action(self) -> QAction:
        return self._reauth_action

    def update(self, vd: VehicleData) -> None:
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
        elif vd.state == VehicleState.ONLINE:
            self._reauth_action.setVisible(False)
            self._status_action.setText("Status: ONLINE")
        else:
            self._reauth_action.setVisible(False)
            self._status_action.setText("Status: LOADING...")

        if self._tesla.command_status:
            self._status_action.setText(
                f"Status: {self._tesla.command_status}"
            )
