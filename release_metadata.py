"""Canonical source/release metadata used by build and packaging helpers."""

from __future__ import annotations

APP_VERSION = "4.6.2"
RELEASE_VERSION = "1.1"
RELEASE_TAG = f"v{RELEASE_VERSION}"

RELEASE_REPOSITORY_OWNER = "SLedgehammer-dev12"
RELEASE_REPOSITORY_NAME = "KASP-Main-Release"
RELEASE_REPOSITORY = f"{RELEASE_REPOSITORY_OWNER}/{RELEASE_REPOSITORY_NAME}"
RELEASES_API_URL = (
    f"https://api.github.com/repos/{RELEASE_REPOSITORY_OWNER}/{RELEASE_REPOSITORY_NAME}/releases"
)

RELEASE_EXE_STEM = f"KASP {RELEASE_TAG}"
RELEASE_EXE_NAME = f"{RELEASE_EXE_STEM}.exe"
RELEASE_SPEC_FILENAME = f"KASP_release_{RELEASE_TAG}.spec"
RELEASE_BUILD_SCRIPT = f"build_release_{RELEASE_TAG}.bat"

LOCAL_EXE_STEM = "KASP local build"
LOCAL_EXE_NAME = f"{LOCAL_EXE_STEM}.exe"
LOCAL_SPEC_FILENAME = "KASP_release_local.spec"
LOCAL_BUILD_SCRIPT = "build_release_local.bat"
