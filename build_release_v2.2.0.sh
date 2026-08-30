#!/bin/bash
# KASP macOS Release Build Script v2.2.0
# Creates: dist/"KASP v2.2.0".app
# V2.0.1: Thermopack bundle fix + fallback log spam suppression

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "============================================"
echo "  KASP macOS Release Build — v2.2.0"
echo "  Thermopack Bundle Fix + Log Spam Suppression"
echo "============================================"
echo ""

# --- Read metadata ---
RELEASE_SPEC=$(python3 -c "from release_metadata import RELEASE_MAC_SPEC_FILENAME; print(RELEASE_MAC_SPEC_FILENAME)")
RELEASE_APP=$(python3 -c "from release_metadata import RELEASE_MAC_APP_NAME; print(RELEASE_MAC_APP_NAME)")

echo "[1/5] Verifying virtual environment..."
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
echo "[2/5] Checking DWSIM DLL (optional for macOS)..."
if [ -f "kasp/core/libs/DWSIM.Thermodynamics.StandaloneLibrary.dll" ]; then
    echo "       ✓ DWSIM DLL found — will be bundled"
else
    echo "       ⚠ DWSIM DLL not found — DWSIM option will be disabled (requires Mono/.NET SDK)"
fi

echo ""
echo "[3/5] Cleaning previous builds..."
rm -rf build/ dist/ "${RELEASE_APP}" 2>/dev/null || true

echo ""
echo "[4/5] Building with PyInstaller (spec: ${RELEASE_SPEC})..."
pyinstaller --clean "${RELEASE_SPEC}"

echo ""
echo "[5/5] Fixing .app extension and verifying..."
if [ -d "dist/${RELEASE_APP}" ]; then
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
    echo "[6/6] Ad-hoc codesigning for Gatekeeper bypass..."
    codesign --force --deep --sign - "${APP_PATH}" 2>/dev/null
    if [ $? -eq 0 ]; then
        echo "       ✓ Codesigned (ad-hoc): ${APP_PATH}"
    else
        echo "       ⚠ codesign skipped (not available or failed — app still functional)"
    fi

    echo ""
    echo "============================================"
    echo "  Build SUCCESS"
    echo "  App: ${APP_PATH}"
    echo "  SHA-256:"
    echo "  shasum -a 256 ${APP_PATH}"
    echo ""
    echo "  Next: ./package_mac_dmg.sh"
    echo "============================================"
else
    echo "       ✗ ERROR: ${APP_PATH} not found!"
    exit 1
fi
