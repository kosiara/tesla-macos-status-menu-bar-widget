#!/usr/bin/env bash
set -euo pipefail

APP_NAME="TeslaBar"
VERSION="0.0.1"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DIST_DIR="$SCRIPT_DIR/dist"
BUILD_DIR="$SCRIPT_DIR/build"

echo "=== $APP_NAME v$VERSION Build ==="
echo ""

# ── 1. Check tools ──────────────────────────────────────────────
echo "[1/5] Checking dependencies..."

if ! command -v pyinstaller &>/dev/null; then
    echo "  PyInstaller not found. Installing..."
    if ! command -v pipx &>/dev/null; then
        brew install pipx
        pipx ensurepath
    fi
    pipx install pyinstaller
fi

if ! command -v create-dmg &>/dev/null; then
    echo "  create-dmg not found. Installing via Homebrew..."
    brew install create-dmg
fi

echo "  OK"

# ── 2. Clean previous build ─────────────────────────────────────
echo "[2/5] Cleaning previous build..."
rm -rf "$BUILD_DIR" "$DIST_DIR"
echo "  OK"

# ── 3. Generate .icns from .png (if needed) ─────────────────────
ICON_PNG="$SCRIPT_DIR/resources/tesla_icon.png"
ICON_ICNS="$SCRIPT_DIR/resources/tesla_icon.icns"

if [ ! -f "$ICON_ICNS" ] && [ -f "$ICON_PNG" ]; then
    echo "[3/5] Generating .icns icon from .png..."
    ICONSET_DIR="$SCRIPT_DIR/build/tesla_icon.iconset"
    mkdir -p "$ICONSET_DIR"
    for size in 16 32 64 128 256 512; do
        sips -z $size $size "$ICON_PNG" --out "$ICONSET_DIR/icon_${size}x${size}.png" &>/dev/null
        double=$((size * 2))
        sips -z $double $double "$ICON_PNG" --out "$ICONSET_DIR/icon_${size}x${size}@2x.png" &>/dev/null
    done
    iconutil -c icns "$ICONSET_DIR" -o "$ICON_ICNS"
    echo "  Created $ICON_ICNS"
else
    echo "[3/5] Icon .icns already exists, skipping."
fi

# ── 4. Run PyInstaller ──────────────────────────────────────────
echo "[4/5] Building app with PyInstaller..."
cd "$SCRIPT_DIR"
TESLABAR_PROJECT_ROOT="$SCRIPT_DIR" pyinstaller \
    --noconfirm \
    --clean \
    --distpath "$DIST_DIR" \
    --workpath "$BUILD_DIR" \
    "$SCRIPT_DIR/TeslaBar.spec"

APP_PATH="$DIST_DIR/$APP_NAME.app"
if [ ! -d "$APP_PATH" ]; then
    echo "ERROR: $APP_PATH not found. Build failed."
    exit 1
fi
echo "  Built: $APP_PATH"

# ── 5. Create DMG ───────────────────────────────────────────────
DMG_PATH="$DIST_DIR/${APP_NAME}-${VERSION}.dmg"
echo "[5/5] Creating DMG..."

# Remove existing DMG (create-dmg fails if it exists)
rm -f "$DMG_PATH"

create-dmg \
    --volname "$APP_NAME" \
    --volicon "$ICON_ICNS" \
    --window-pos 200 120 \
    --window-size 600 400 \
    --icon-size 100 \
    --icon "$APP_NAME.app" 150 185 \
    --app-drop-link 450 185 \
    --hide-extension "$APP_NAME.app" \
    "$DMG_PATH" \
    "$APP_PATH"

echo ""
echo "=== Build complete ==="
echo "  App: $APP_PATH"
echo "  DMG: $DMG_PATH"
echo ""
echo "To test the app directly:"
echo "  open \"$APP_PATH\""
