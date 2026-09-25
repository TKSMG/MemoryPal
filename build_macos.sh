#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

echo "MemoryPal macOS build"
echo

PYTHON_EXE="${MEMORYPAL_PYTHON:-}"
if [[ -z "$PYTHON_EXE" ]]; then
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_EXE="python3"
  else
    PYTHON_EXE="python"
  fi
fi

"$PYTHON_EXE" - <<'PY'
import tkinter as tk
print(f"Tkinter is available: Tk {tk.TkVersion}")
PY

BUILD_TOOLS="${TMPDIR:-/tmp}/memorypal-macos-tools"
TEMP_BUILD="${TMPDIR:-/tmp}/memorypal-macos-build-$$"
ARTIFACT_SUFFIX="${MEMORYPAL_MAC_ARTIFACT_SUFFIX:-macOS}"
APP_BUNDLE="$TEMP_BUILD/release/MemoryPal.app"
ICONSET="$TEMP_BUILD/memorypal.iconset"
ICON_FILE="$TEMP_BUILD/memorypal.icns"
ICON_SOURCE="$PWD/assets/memorypal-logo-preview.png"
RELEASE_DIR="$PWD/release/macos"
DMG_ROOT="$TEMP_BUILD/dmg-root"
DMG_PATH="$PWD/release/MemoryPal-${ARTIFACT_SUFFIX}.dmg"
ZIP_PATH="$PWD/release/MemoryPal-${ARTIFACT_SUFFIX}-app.zip"

rm -rf "$BUILD_TOOLS" "$TEMP_BUILD"
mkdir -p "$BUILD_TOOLS" "$TEMP_BUILD" "$ICONSET" "$PWD/release"

"$PYTHON_EXE" -m pip install --upgrade --target "$BUILD_TOOLS" -r requirements-build.txt
export PYTHONPATH="$BUILD_TOOLS:${PYTHONPATH:-}"

if [[ -f "$ICON_SOURCE" ]]; then
  for size in 16 32 128 256 512; do
    sips -z "$size" "$size" "$ICON_SOURCE" --out "$ICONSET/icon_${size}x${size}.png" >/dev/null
    retina=$((size * 2))
    sips -z "$retina" "$retina" "$ICON_SOURCE" --out "$ICONSET/icon_${size}x${size}@2x.png" >/dev/null
  done
  iconutil -c icns "$ICONSET" -o "$ICON_FILE"
else
  echo "Icon source not found: $ICON_SOURCE"
  exit 1
fi

"$PYTHON_EXE" -m PyInstaller \
  --noconfirm \
  --clean \
  --onedir \
  --windowed \
  --name MemoryPal \
  --icon "$ICON_FILE" \
  --osx-bundle-identifier "com.memorypal.trainer" \
  --paths "$PWD/latest_app" \
  --add-data "$PWD/assets/memorypal.ico:assets" \
  --add-data "$PWD/assets/memorypal-logo-preview.png:assets" \
  --add-data "$PWD/assets/memorypal-logo.svg:assets" \
  --hidden-import pypdf \
  --hidden-import memorypal.pdftext \
  --exclude-module sounddevice \
  --exclude-module cv2 \
  --exclude-module pyttsx3 \
  --exclude-module SpeechRecognition \
  --exclude-module pyaudio \
  --exclude-module pyaudioop \
  --exclude-module numpy \
  --distpath "$TEMP_BUILD/release" \
  --workpath "$TEMP_BUILD/build" \
  --specpath "$TEMP_BUILD/build" \
  "$PWD/latest_app/MemoryPalDesktop.py"

if [[ ! -d "$APP_BUNDLE" ]]; then
  echo "PyInstaller did not create $APP_BUNDLE"
  exit 1
fi

rm -rf "$RELEASE_DIR"
mkdir -p "$RELEASE_DIR"
ditto "$APP_BUNDLE" "$RELEASE_DIR/MemoryPal.app"

if command -v codesign >/dev/null 2>&1; then
  codesign --force --deep --sign - "$RELEASE_DIR/MemoryPal.app" || true
fi

rm -rf "$DMG_ROOT" "$DMG_PATH" "$ZIP_PATH"
mkdir -p "$DMG_ROOT"
ditto "$RELEASE_DIR/MemoryPal.app" "$DMG_ROOT/MemoryPal.app"
ln -s /Applications "$DMG_ROOT/Applications"
hdiutil create -volname "MemoryPal" -srcfolder "$DMG_ROOT" -ov -format UDZO "$DMG_PATH"
ditto -c -k --sequesterRsrc --keepParent "$RELEASE_DIR/MemoryPal.app" "$ZIP_PATH"

echo
echo "Built $RELEASE_DIR/MemoryPal.app"
echo "Built $DMG_PATH"
echo "Built $ZIP_PATH"
