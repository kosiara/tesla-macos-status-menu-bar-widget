# tesla-macos-status-menu-bar-widget

A macOS (and Windows) menu bar app for controlling your Tesla vehicle via the Tesla Fleet API. Built with Python 3.14 and PySide6.

## Project Structure

```
widget/
├── run.sh                          # Quick launcher
├── Info.plist                      # macOS: LSUIElement + URL scheme
├── pyproject.toml                  # Python project config
├── requirements.txt
├── resources/
│   └── tesla_icon.png              # Tesla logo for menu bar
└── teslabar/
    ├── __init__.py
    ├── __main__.py                 # Entry point + asyncio-Qt bridge
    ├── config.py                   # Settings persistence (JSON)
    ├── crypto/
    │   ├── credential_store.py     # AES-GCM encryption + Keychain
    │   └── virtual_key.py          # EC key pair gen + GitHub Pages guide
    ├── services/
    │   ├── oauth_server.py         # Local HTTP callback for OAuth
    │   └── tesla_api.py            # Tesla Fleet API wrapper
    └── ui/
        ├── charge_limit_popup.py   # Slider popup (50-100%)
        ├── main_window.py          # "Open in Window" mode + auto-refresh
        ├── password_dialog.py      # First-run + returning user flows
        ├── schedule_window.py      # Precondition & Charging schedule mgmt
        ├── settings_window.py      # Settings + Virtual Key + QR code
        ├── status_window.py        # Logs/errors/vehicle state
        └── tray_app.py             # System tray icon + main menu
```

## Key Features

- **Password-encrypted credentials** — AES-256-GCM via PBKDF2, stored in macOS Keychain (falls back to file on Windows)
- **3 attempt lockout** — 5s delay per attempt, 60s lockout after 3 failures
- **OAuth 2.0 flow** — Local HTTP server on port 8457 for callback, auto-opens browser
- **Token refresh** — Checks expiry before each API call, auto-refreshes; shows RE-AUTHENTICATE when refresh token is dead
- **Menu bar only** — LSUIElement hides from Dock; NSBundle runtime override for development
- **Refresh on menu open only** — No API calls when menu is closed
- **Window mode** — Auto-refreshes at configurable interval (default 15s)
- **Virtual key** — EC P-256 key pair, QR code for tesla.com/_ak/<domain>, GitHub Pages instructions
- **All specified menu items** — Status, Settings, Window mode, Battery, Charge toggle, Charger status, Lock status (read-only), Sentry (read-only), Charge limit slider, Precondition schedule, Climate toggle, Schedule lists, Quit
- **Region selector** — EU/NA/CN
- **Tesla Fleet API** — Uses python-tesla-fleet-api library with proper per-VIN VehicleFleet objects

## Running

```bash
./run.sh
# or
source .venv/bin/activate && python -m teslabar
```

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install PySide6 tesla-fleet-api cryptography keyring "qrcode[pil]" aiohttp
```

On first launch, you'll be prompted to set a password and enter your Tesla OAuth Client ID and Client Secret from [developer.tesla.com](https://developer.tesla.com).
