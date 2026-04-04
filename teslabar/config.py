"""Application configuration and persistent settings."""

import json
import platform
from pathlib import Path


def _app_data_dir() -> Path:
    if platform.system() == "Darwin":
        base = Path.home() / "Library" / "Application Support"
    elif platform.system() == "Windows":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path.home() / ".config"
    d = base / "TeslaBar"
    d.mkdir(parents=True, exist_ok=True)
    return d


import os

APP_NAME = "TeslaBar"
APP_DATA_DIR = _app_data_dir()
CONFIG_FILE = APP_DATA_DIR / "config.json"
ENCRYPTED_CREDS_FILE = APP_DATA_DIR / "credentials.enc"
VIRTUAL_KEY_FILE = APP_DATA_DIR / "virtual_key.pem"
VIRTUAL_PUB_KEY_FILE = APP_DATA_DIR / "virtual_key_pub.pem"

DEFAULT_CONFIG = {
    "refresh_interval_seconds": 15,
    "temperature_unit": "C",
    "github_pages_domain": "",
    "oauth_redirect_uri": "teslabar://callback",
    "region": "eu",  # "na", "eu", or "cn"
}


def load_config() -> dict:
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            stored = json.load(f)
        merged = {**DEFAULT_CONFIG, **stored}
        return merged
    return dict(DEFAULT_CONFIG)


def save_config(cfg: dict) -> None:
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)
