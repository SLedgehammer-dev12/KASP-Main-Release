#!/bin/bash
# KASP macOS DMG Packaging Script
# Creates: dist/temp_dmg

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

RELEASE_VERSION=$(python3 -c "from release_metadata import RELEASE_VERSION; print(RELEASE_VERSION)")
RELEASE_APP=$(python3 -c "from release_metadata import RELEASE_MAC_APP_NAME; print(RELEASE_MAC_APP_NAME)")
RELEASE_DMG=$(python3 -c "from release_metadata import RELEASE_MAC_DMG_NAME; print(RELEASE_MAC_DMG_NAME)")
APP_PATH="dist/${RELEASE_APP}"
DMG_PATH="dist/${RELEASE_DMG}"
DMG_TEMP="dist/temp_dmg"

echo "============================================"
echo "  KASP macOS DMG Packaging — v${RELEASE_VERSION}"
echo "============================================"
echo ""

# --- Verify .app exists ---
if [ ! -d "${APP_PATH}" ]; then
    echo "ERROR: ${APP_PATH} not found!"
    echo "Run the build script first."
    exit 1
fi

echo "[1/3] Preparing DMG contents..."
rm -rf "${DMG_PATH}" "${DMG_TEMP}" 2>/dev/null || true
mkdir -p "${DMG_TEMP}"

cp -R "${APP_PATH}" "${DMG_TEMP}/"
# Create a symlink to /Applications for drag-and-drop install
ln -s /Applications "${DMG_TEMP}/Applications"

# First-launch README (Gatekeeper workaround instructions)
cat > "${DMG_TEMP}/README - Ilk Calistirma.txt" << 'EOR'
Ilk calistirmada macOS Gatekeeper uyarisi alirsaniz:

1. KASP uygulamasina SAG TIKLAYIN
2. "Ac" secenegine tiklayin
3. Acilan pencerede "Ac" butonuna basin

Bu islemi yalnizca bir kez yapmaniz yeterlidir.
Sonraki calistirmalarda normal cift tiklama ile acilir.

---

First-launch Gatekeeper workaround:

1. RIGHT-CLICK on the KASP app
2. Select "Open"
3. Click "Open" in the dialog

You only need to do this once.
Subsequent launches work with normal double-click.
EOR

echo "       Source: ${APP_PATH}"
echo "       Temp:   ${DMG_TEMP}"

echo ""
echo "[2/3] Creating DMG (hdiutil)..."
hdiutil create \
    -volname "${RELEASE_APP%.app}" \
    -srcfolder "${DMG_TEMP}" \
    -ov \
    -format UDZO \
    "${DMG_PATH}"

echo ""
echo "[3/3] Cleaning up..."
rm -rf "${DMG_TEMP}"

DMG_SIZE=$(ls -lh "${DMG_PATH}" | awk '{print $5}')
echo "       ✓ Built: ${DMG_PATH}  (${DMG_SIZE})"
echo ""
echo "============================================"
echo "  DMG SUCCESS"
echo "  File: ${DMG_PATH}"
echo "============================================"
