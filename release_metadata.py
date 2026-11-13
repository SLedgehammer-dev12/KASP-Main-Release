"""Canonical source/release metadata used by build and packaging helpers."""

from __future__ import annotations

RELEASE_VERSION = "2.6.2"
APP_VERSION = RELEASE_VERSION
RELEASE_TAG = f"v{RELEASE_VERSION}"

RELEASE_REPOSITORY_OWNER = "SLedgehammer-dev12"
RELEASE_REPOSITORY_NAME = "KASP-Main-Release"
RELEASE_REPOSITORY = f"{RELEASE_REPOSITORY_OWNER}/{RELEASE_REPOSITORY_NAME}"
RELEASES_API_URL = (
    f"https://api.github.com/repos/{RELEASE_REPOSITORY_OWNER}/{RELEASE_REPOSITORY_NAME}/releases"
)

# ── Windows release artifacts ───────────────────────────────────────────
RELEASE_EXE_STEM = f"KASP {RELEASE_TAG}"
RELEASE_EXE_NAME = f"{RELEASE_EXE_STEM}.exe"
RELEASE_SPEC_FILENAME = f"KASP_release_{RELEASE_TAG}.spec"
RELEASE_BUILD_COMMAND = f"pyinstaller --clean {RELEASE_SPEC_FILENAME}"

# ── macOS release artifacts ─────────────────────────────────────────────
RELEASE_MAC_APP_NAME = f"KASP {RELEASE_TAG}.app"
RELEASE_MAC_DMG_NAME = f"KASP {RELEASE_TAG}.dmg"
RELEASE_MAC_SPEC_FILENAME = f"KASP_release_{RELEASE_TAG}_mac.spec"
RELEASE_MAC_BUILD_COMMAND = f"pyinstaller --clean {RELEASE_MAC_SPEC_FILENAME}"
RELEASE_MAC_DMG_SCRIPT = "package_mac_dmg.sh"

# ── Local (dev) build artifacts ─────────────────────────────────────────
LOCAL_EXE_STEM = "KASP local build"
LOCAL_EXE_NAME = f"{LOCAL_EXE_STEM}.exe"
LOCAL_SPEC_FILENAME = "KASP_release_local.spec"
LOCAL_BUILD_SCRIPT = "build_release_local.bat"
LOCAL_BUILD_COMMAND = f"pyinstaller --clean {LOCAL_SPEC_FILENAME}"

# ── Web Edition release metadata ────────────────────────────────────────
WEB_RELEASE_VERSION = "4.1.0-web"
WEB_CFBUNDLE_VERSION = WEB_RELEASE_VERSION.split("-", 1)[0]
WEB_RELEASE_TAG = f"web-v{WEB_CFBUNDLE_VERSION}"
WEB_EXE_STEM = f"KASP Web v{WEB_RELEASE_VERSION}"
WEB_EXE_NAME = f"{WEB_EXE_STEM}.exe"
WEB_SPEC_FILENAME = f"KASP_Web_v{WEB_RELEASE_VERSION}.spec"
WEB_BUILD_COMMAND = f"pyinstaller --clean {WEB_SPEC_FILENAME}"

WEB_MAC_APP_STEM = f"KASP Web v{WEB_RELEASE_VERSION}"
WEB_MAC_APP_NAME = f"{WEB_MAC_APP_STEM}.app"
WEB_MAC_DMG_NAME = f"{WEB_MAC_APP_STEM}.dmg"
WEB_MAC_SPEC_FILENAME = f"KASP_Web_v{WEB_RELEASE_VERSION}_mac.spec"
WEB_MAC_BUILD_COMMAND = f"pyinstaller --clean {WEB_MAC_SPEC_FILENAME}"
WEB_MAC_DMG_SCRIPT = "package_web_mac_dmg.sh"
WEB_ICON_ICO = "resources/web_icon.ico"
WEB_ICON_ICNS = "resources/web_icon.icns"
