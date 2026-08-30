#!/bin/bash
# KASP macOS Release Build Script v2.3.0
# Creates: dist/"KASP v2.3.0".app

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "============================================"
echo "  KASP macOS Release Build — v2.3.0"
echo "  Huntington-RK45 + Schultz 3-Exp + Smart Badges"
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
echo "[3/5] Cleaning previous build artifacts..."
rm -rf build/ dist/

echo ""
echo "[4/5] Building macOS App Bundle with PyInstaller..."
echo "       Spec file: $RELEASE_SPEC"
pyinstaller "$RELEASE_SPEC" --noconfirm

echo ""
echo "[5/5] Verifying build output..."
if [ -d "dist/$RELEASE_APP" ]; then
    APP_SIZE=$(du -sh "dist/$RELEASE_APP" | cut -f1)
    echo "============================================"
    echo "  BUILD SUCCESSFUL!"
    echo "  Output: dist/$RELEASE_APP ($APP_SIZE)"
    echo "============================================"
    echo ""
    echo "Next steps:"
    echo "  1. Test: open \"dist/$RELEASE_APP\""
    echo "  2. Package DMG: ./package_mac_dmg.sh"
else
    echo "============================================"
    echo "  BUILD FAILED: App bundle not found"
    echo "============================================"
    exit 1
fi
