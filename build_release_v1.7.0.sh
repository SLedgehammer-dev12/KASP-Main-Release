#!/bin/bash
# KASP macOS Release Build Script v1.7.0
# Creates: dist/KASP v1.7.0.app
# V1.7.0: Responsive UI + QSplitter panels + 8 enhanced graphs.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "============================================"
echo "  KASP macOS Release Build — v1.7.0"
echo "============================================"
echo ""

# --- Read metadata ---
RELEASE_SPEC=$(python3 -c "from release_metadata import RELEASE_MAC_SPEC_FILENAME; print(RELEASE_MAC_SPEC_FILENAME)")
RELEASE_APP=$(python3 -c "from release_metadata import RELEASE_MAC_APP_NAME; print(RELEASE_MAC_APP_NAME)")

echo "[1/4] Verifying virtual environment..."
if [ -d ".venv" ]; then
    source .venv/bin/activate
elif [ -d "venv" ]; then
    source venv/bin/activate
else
    echo "ERROR: No virtual environment found (.venv or venv)."
    echo "Run: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

echo "       Python: $(python3 --version)"
echo "       PyInstaller: $(pip show pyinstaller 2>/dev/null | grep Version || echo 'NOT FOUND')"

echo ""
echo "[2/4] Cleaning previous builds..."
rm -rf build/ dist/ "${RELEASE_APP}" 2>/dev/null || true

echo ""
echo "[3/4] Building with PyInstaller (spec: ${RELEASE_SPEC})..."
pyinstaller --clean "${RELEASE_SPEC}"

echo ""
echo "[4/4] Fixing .app extension and verifying..."
if [ -d "dist/${RELEASE_APP}" ]; then
    echo "       ✓ Already built with .app extension directly by PyInstaller."
    APP_PATH="dist/${RELEASE_APP}"
elif [ -d "dist/${RELEASE_APP%.app}" ]; then
    echo "       Renaming to add .app extension..."
    mv "dist/${RELEASE_APP%.app}" "dist/${RELEASE_APP}"
    APP_PATH="dist/${RELEASE_APP}"
else
    echo "       ✗ ERROR: Neither dist/${RELEASE_APP} nor dist/${RELEASE_APP%.app} found!"
    exit 1
fi

if [ -d "${APP_PATH}" ]; then
    APP_SIZE=$(du -sh "${APP_PATH}" | cut -f1)
    echo "       ✓ Built:  ${APP_PATH}  (${APP_SIZE})"
    echo ""
    echo "============================================"
    echo "  Build SUCCESS"
    echo "  App: ${APP_PATH}"
    echo "  Next: ./package_mac_dmg.sh"
    echo "============================================"
else
    echo "       ✗ ERROR: ${APP_PATH} not found!"
    exit 1
fi
