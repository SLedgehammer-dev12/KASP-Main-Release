"""Small helper that prints the canonical local/release build commands."""

from __future__ import annotations

from release_metadata import (
    LOCAL_BUILD_SCRIPT,
    LOCAL_SPEC_FILENAME,
    RELEASE_BUILD_SCRIPT,
    RELEASE_SPEC_FILENAME,
)


def main() -> None:
    print(f"Release build script : .\\{RELEASE_BUILD_SCRIPT}")
    print(f"Release spec         : {RELEASE_SPEC_FILENAME}")
    print(f"Local spec           : {LOCAL_SPEC_FILENAME}")
    print()
    print("Direct local PyInstaller command:")
    print(f".\\venv\\Scripts\\pyinstaller.exe --clean {LOCAL_SPEC_FILENAME}")
    print()
    print("Recommended release command:")
    print(f".\\{RELEASE_BUILD_SCRIPT}")


if __name__ == "__main__":
    main()
