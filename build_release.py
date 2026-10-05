"""Small helper that prints the canonical local/release build commands."""

from __future__ import annotations

from release_metadata import (
    LOCAL_BUILD_COMMAND,
    LOCAL_BUILD_SCRIPT,
    LOCAL_SPEC_FILENAME,
    RELEASE_BUILD_COMMAND,
    RELEASE_MAC_BUILD_COMMAND,
    RELEASE_MAC_DMG_SCRIPT,
    RELEASE_MAC_SPEC_FILENAME,
    RELEASE_SPEC_FILENAME,
)


def main() -> None:
    print(f"Windows release spec : {RELEASE_SPEC_FILENAME}")
    print(f"Windows release      : {RELEASE_BUILD_COMMAND}")
    print(f"macOS release spec   : {RELEASE_MAC_SPEC_FILENAME}")
    print(f"macOS release        : {RELEASE_MAC_BUILD_COMMAND}")
    print(f"macOS DMG            : ./{RELEASE_MAC_DMG_SCRIPT}")
    print()
    print(f"Local Windows script : .\\{LOCAL_BUILD_SCRIPT}")
    print(f"Local Windows build  : {LOCAL_BUILD_COMMAND}")
    print(f"Local spec           : {LOCAL_SPEC_FILENAME}")
    print()
    print("Recommended Windows release command:")
    print(f"  {RELEASE_BUILD_COMMAND}")
    print("Recommended macOS release command:")
    print(f"  {RELEASE_MAC_BUILD_COMMAND}  &&  ./{RELEASE_MAC_DMG_SCRIPT}")


if __name__ == "__main__":
    main()
