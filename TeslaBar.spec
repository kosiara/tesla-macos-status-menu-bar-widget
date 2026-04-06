# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for TeslaBar."""

import os
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

block_cipher = None

PROJECT_ROOT = os.environ.get("TESLABAR_PROJECT_ROOT", os.path.abspath(os.path.dirname(SPECPATH)))

# Collect all teslabar submodules
teslabar_hiddenimports = collect_submodules("teslabar")

# Collect dependencies that PyInstaller may miss
hidden_imports = [
    *teslabar_hiddenimports,
    # PySide6
    "PySide6.QtWidgets",
    "PySide6.QtGui",
    "PySide6.QtCore",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebEngineCore",
    # tesla-fleet-api
    *collect_submodules("tesla_fleet_api"),
    # async / networking
    "aiohttp",
    "aiofiles",
    # crypto
    "cryptography",
    "keyring",
    "keyring.backends",
    "keyring.backends.macOS",
    # images / qr
    "qrcode",
    "PIL",
    # maps
    "folium",
    "branca",
    "jinja2",
    # macOS dock hiding
    "Foundation",
    "objc",
    # other
    "certifi",
]

a = Analysis(
    [os.path.join(PROJECT_ROOT, "teslabar", "__main__.py")],
    pathex=[PROJECT_ROOT],
    binaries=[],
    datas=[
        (os.path.join(PROJECT_ROOT, "resources"), "resources"),
        (os.path.join(PROJECT_ROOT, "Info.plist"), "."),
    ],
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "unittest",
        "test",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="TeslaBar",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    target_arch=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="TeslaBar",
)

app = BUNDLE(
    coll,
    name="TeslaBar.app",
    icon=os.path.join(PROJECT_ROOT, "resources", "tesla_icon.icns"),
    bundle_identifier="com.teslabar.app",
    info_plist={
        "CFBundleName": "TeslaBar",
        "CFBundleDisplayName": "TeslaBar",
        "CFBundleIdentifier": "com.teslabar.app",
        "CFBundleVersion": "0.0.1",
        "CFBundleShortVersionString": "0.0.1",
        "CFBundlePackageType": "APPL",
        "LSUIElement": True,
        "CFBundleURLTypes": [
            {
                "CFBundleURLName": "com.teslabar.oauth",
                "CFBundleURLSchemes": ["teslabar"],
            }
        ],
        "NSHighResolutionCapable": True,
    },
)
