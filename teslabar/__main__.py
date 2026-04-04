"""TeslaBar - main entry point."""

import asyncio
import logging
import platform
import sys

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

from teslabar.crypto.credential_store import credentials_exist, load_credentials
from teslabar.services.tesla_api import TeslaService
from teslabar.ui.password_dialog import PasswordDialog
from teslabar.ui.tray_app import TeslaBarTray

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


class AsyncHelper:
    """Runs the asyncio event loop alongside Qt's event loop."""

    def __init__(self, app: QApplication) -> None:
        self._app = app
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._timer = QTimer()
        self._timer.timeout.connect(self._process_async)
        self._timer.start(10)  # 10ms tick

    def _process_async(self) -> None:
        self._loop.stop()
        self._loop.run_forever()


def main() -> None:
    # macOS: hide dock icon
    if platform.system() == "Darwin":
        try:
            from Foundation import NSBundle
            info = NSBundle.mainBundle().infoDictionary()
            info["LSUIElement"] = "1"
        except ImportError:
            logger.warning(
                "pyobjc not available — app will appear in Dock. "
                "Install pyobjc-framework-Cocoa to hide it."
            )

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("TeslaBar")

    # Integrate asyncio with Qt
    async_helper = AsyncHelper(app)

    # Password dialog
    pw_dialog = PasswordDialog()
    result = pw_dialog.exec()
    if result != PasswordDialog.DialogCode.Accepted:
        sys.exit(0)

    password = pw_dialog.password
    creds = pw_dialog.credentials

    # Load config for region
    from teslabar.config import load_config
    cfg = load_config()

    # Set up Tesla service
    tesla = TeslaService()
    tesla.configure(
        client_id=creds.get("client_id", ""),
        client_secret=creds.get("client_secret", ""),
        access_token=creds.get("access_token", ""),
        refresh_token=creds.get("refresh_token", ""),
        token_expiry=creds.get("token_expiry", 0.0),
        region=cfg.get("region", "eu"),
    )

    # If we have tokens, try to discover vehicle immediately
    domain = cfg.get("github_pages_domain", "")
    async def _startup_discover():
        try:
            if tesla.is_authenticated and not tesla.token_expired:
                await tesla.register_partner(domain)
                await tesla.discover_vehicle()
            elif tesla.is_authenticated and tesla._refresh_token:
                success = await tesla.refresh_access_token()
                if success:
                    from teslabar.crypto.credential_store import (
                        load_credentials as _load,
                        save_credentials as _save,
                    )
                    try:
                        stored = _load(password)
                    except Exception:
                        stored = dict(creds)
                    stored.update(tesla.get_tokens())
                    _save(stored, password)
                    await tesla.register_partner(domain)
                    await tesla.discover_vehicle()
        except Exception as e:
            logger.error("Startup discovery failed: %s", e)

    if tesla.is_authenticated:
        asyncio.ensure_future(_startup_discover())

    # Create tray
    tray = TeslaBarTray(app, tesla, password)

    # If no OAuth tokens yet, start OAuth flow automatically
    if not creds.get("access_token"):
        tray._start_oauth_flow()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
