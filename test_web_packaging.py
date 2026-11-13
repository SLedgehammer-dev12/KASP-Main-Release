"""Tests for KASP Web Edition packaging, metadata, icons, launcher, and workflow."""

import os
import socket
import sys
from unittest.mock import patch

import yaml

from release_metadata import (
    RELEASE_VERSION,
    WEB_BUILD_COMMAND,
    WEB_CFBUNDLE_VERSION,
    WEB_EXE_NAME,
    WEB_ICON_ICNS,
    WEB_ICON_ICO,
    WEB_MAC_APP_NAME,
    WEB_MAC_BUILD_COMMAND,
    WEB_MAC_DMG_NAME,
    WEB_MAC_DMG_SCRIPT,
    WEB_MAC_SPEC_FILENAME,
    WEB_RELEASE_TAG,
    WEB_RELEASE_VERSION,
    WEB_SPEC_FILENAME,
)
import run_web

_ROOT = os.path.dirname(os.path.abspath(__file__))


def _path(rel: str) -> str:
    return os.path.join(_ROOT, rel)


def test_web_version_is_distinct_from_desktop():
    assert WEB_RELEASE_VERSION != RELEASE_VERSION
    assert WEB_RELEASE_VERSION.endswith("-web")
    assert WEB_RELEASE_TAG == f"web-v{WEB_CFBUNDLE_VERSION}"
    assert WEB_CFBUNDLE_VERSION == "4.1.1"


def test_web_artifact_files_exist():
    for rel in (
        WEB_SPEC_FILENAME,
        WEB_MAC_SPEC_FILENAME,
        WEB_MAC_DMG_SCRIPT,
        WEB_ICON_ICO,
        WEB_ICON_ICNS,
        ".github/workflows/release-web.yml",
    ):
        assert os.path.exists(_path(rel)), f"Missing web packaging file: {rel}"

    assert WEB_SPEC_FILENAME in WEB_BUILD_COMMAND
    assert WEB_MAC_SPEC_FILENAME in WEB_MAC_BUILD_COMMAND
    assert WEB_EXE_NAME.endswith(".exe")
    assert WEB_MAC_APP_NAME.endswith(".app")
    assert WEB_MAC_DMG_NAME.endswith(".dmg")


def test_web_specs_use_run_web_and_web_icons():
    win_spec = open(_path(WEB_SPEC_FILENAME), encoding="utf-8").read()
    mac_spec = open(_path(WEB_MAC_SPEC_FILENAME), encoding="utf-8").read()

    assert '["run_web.py"]' in win_spec
    assert "WEB_ICON_ICO" in win_spec
    assert '["run_web.py"]' in mac_spec
    assert "WEB_ICON_ICNS" in mac_spec
    assert "com.kasp.web" in mac_spec


def test_web_workflow_yaml_valid_and_targets_both_platforms():
    wf = yaml.safe_load(
        open(_path(".github/workflows/release-web.yml"), encoding="utf-8")
    )
    assert "jobs" in wf
    assert "release-web-win" in wf["jobs"]
    assert "release-web-mac" in wf["jobs"]
    assert wf["jobs"]["release-web-win"]["runs-on"] == "windows-latest"
    assert wf["jobs"]["release-web-mac"]["runs-on"] == "macos-latest"


def test_find_available_port_falls_back_to_ephemeral_when_preferred_busy():
    # Bind a single socket to simulate all preferred ports failing
    with patch("socket.socket") as mock_sock_cls:
        busy_sock = mock_sock_cls.return_value.__enter__.return_value
        # First 4 bind calls raise OSError, 5th (port 0) succeeds and returns 54321
        busy_sock.bind.side_effect = [OSError("busy")] * 4 + [None]
        busy_sock.getsockname.return_value = ("127.0.0.1", 54321)

        port = run_web.find_available_port(preferred_ports=(8080, 8000, 8081, 8082))
        assert port == 54321


def test_run_web_main_respects_no_browser_flag():
    with (
        patch.dict(os.environ, {"KASP_API_PORT": "59991"}, clear=False),
        patch("uvicorn.run") as mock_uvicorn,
        patch("run_web._wait_and_open_browser") as mock_opener,
    ):
        run_web.main(["--no-browser"])
        mock_opener.assert_not_called()
        mock_uvicorn.assert_called_once()
        args, kwargs = mock_uvicorn.call_args
        assert kwargs["port"] == 59991
        assert kwargs["host"] == "127.0.0.1"


def test_ensure_std_streams_handles_none_streams(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    monkeypatch.setenv("HOME", str(tmp_path))
    run_web._ensure_std_streams()
    assert sys.stdout is not None
    assert sys.stderr is not None
