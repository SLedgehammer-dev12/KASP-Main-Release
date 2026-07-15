"""
KASP Release Builder (v2.1)

Tek parametrik build aracı. release_metadata.py'den versiyon okur.
PyInstaller ile Windows ve macOS için tek dosya build çıktısı üretir.

Kullanim:
    python build_release.py --platform windows
    python build_release.py --platform macos
    python build_release.py --platform all
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

from release_metadata import (
    RELEASE_VERSION, RELEASE_ARTIFACT_BASENAME,
    RELEASE_SPEC_FILENAME, RELEASE_MAC_SPEC_FILENAME,
    LOCAL_SPEC_FILENAME,
)


def _get_python() -> str:
    return sys.executable


def _run_pyinstaller(spec_file: str, name: str, extra_args: list[str] | None = None):
    cmd = [
        _get_python(), "-m", "PyInstaller",
        "--clean", "--noconfirm",
        "--onefile", "--windowed",
        f"--name={name}",
        spec_file,
    ]
    if extra_args:
        cmd.extend(extra_args)
    print(f"[BUILD] {' '.join(cmd)}")
    subprocess.run(cmd, check=True)


def build_windows():
    _run_pyinstaller(RELEASE_SPEC_FILENAME, RELEASE_ARTIFACT_BASENAME, [
        "--add-data=kasp_config.json;.",
        "--add-data=resources;resources",
    ])
    print(f"[OK] Windows build: dist/{RELEASE_ARTIFACT_BASENAME}.exe")


def build_macos():
    if sys.platform != "darwin":
        print("[SKIP] macOS build requires running on macOS")
        return
    _run_pyinstaller(RELEASE_MAC_SPEC_FILENAME, RELEASE_ARTIFACT_BASENAME, [
        "--add-data=kasp_config.json:.",
        "--add-data=resources:resources",
    ])
    print(f"[OK] macOS build: dist/{RELEASE_ARTIFACT_BASENAME}.app")


def build_local():
    _run_pyinstaller(LOCAL_SPEC_FILENAME, f"KASP_v{RELEASE_VERSION}_local", [
        "--add-data=kasp_config.json;.",
        "--add-data=resources;resources",
    ])
    print(f"[OK] Local build: dist/KASP_v{RELEASE_VERSION}_local.exe")


def main():
    parser = argparse.ArgumentParser(
        description=f"KASP v{RELEASE_VERSION} Release Builder"
    )
    parser.add_argument(
        "--platform", choices=["windows", "macos", "all", "local"],
        default="windows",
        help="Target platform (default: windows)"
    )
    parser.add_argument(
        "--version", action="version",
        version=f"KASP Release Builder v{RELEASE_VERSION}"
    )
    args = parser.parse_args()

    print(f"KASP Release Builder v{RELEASE_VERSION}")
    print(f"Artifact name: {RELEASE_ARTIFACT_BASENAME}")
    print(f"Platform: {args.platform}")
    print("-" * 50)

    try:
        if args.platform in ("windows", "all"):
            build_windows()
        if args.platform in ("macos", "all"):
            build_macos()
        if args.platform == "local":
            build_local()
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Build failed: {e}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print("[ERROR] PyInstaller not found. Run: pip install pyinstaller", file=sys.stderr)
        sys.exit(1)

    print("-" * 50)
    print("[DONE] Build completed successfully.")


if __name__ == "__main__":
    main()
