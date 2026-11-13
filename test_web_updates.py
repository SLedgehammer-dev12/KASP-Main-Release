"""Tests for KASP Web Edition auto-update check and download manager."""

import hashlib
import os
import sys
import time
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from kasp.api.server import app
from kasp.services import update_service
from kasp.utils.updater import (
    ReleaseAsset,
    ReleaseInfo,
    filter_releases_for_channel,
    is_newer_release,
    parse_release_tag,
)


def _make_release(tag: str, asset_name: str = "KASP.dmg", sha256: str | None = "a" * 64) -> ReleaseInfo:
    return ReleaseInfo(
        tag_name=tag,
        name=f"Release {tag}",
        body="Release notes",
        html_url=f"https://github.com/example/repo/releases/tag/{tag}",
        published_at="2026-11-13T12:00:00Z",
        prerelease=False,
        draft=False,
        assets=(
            ReleaseAsset(
                name=asset_name,
                download_url=f"https://example.com/{asset_name}",
                size=1024,
                content_type="application/octet-stream",
                sha256=sha256,
            ),
        ),
    )


def test_parse_and_filter_web_vs_desktop_releases():
    assert str(parse_release_tag("web-v4.1.0")) == "4.1.0"
    assert is_newer_release("web-v4.2.0", "web-v4.1.0") is True
    assert is_newer_release("web-v4.1.0", "web-v4.1.0") is False

    mixed = [
        _make_release("v2.6.3", "KASP v2.6.3.dmg"),
        _make_release("web-v4.2.0", "KASP Web v4.2.0-web.dmg"),
        _make_release("web-v4.1.0", "KASP Web v4.1.0-web.dmg"),
    ]
    web_only = filter_releases_for_channel(mixed, channel="web")
    desktop_only = filter_releases_for_channel(mixed, channel="desktop")

    assert [r.tag_name for r in web_only] == ["web-v4.2.0", "web-v4.1.0"]
    assert [r.tag_name for r in desktop_only] == ["v2.6.3"]


def test_api_check_updates_detects_newer_web_release():
    releases = [
        _make_release("v2.6.3", "KASP v2.6.3.dmg"),
        _make_release("web-v4.2.0", "KASP Web v4.2.0-web.dmg"),
        _make_release("web-v4.1.0", "KASP Web v4.1.0-web.dmg"),
    ]
    client_inst = update_service.get_release_client()
    with patch.object(client_inst, "fetch_releases", return_value=releases):
        tc = TestClient(app)
        resp = tc.get("/api/v1/updates/check")
        assert resp.status_code == 200
        data = resp.json()
        assert data["check_ok"] is True
        assert data["channel"] == "web"
        assert data["update_available"] is True
        assert data["newer_count"] == 1
        assert data["latest_release"]["tag_name"] == "web-v4.2.0"
        assert len(data["releases"]) == 2


def test_api_check_updates_handles_network_error_gracefully():
    client_inst = update_service.get_release_client()
    with patch.object(client_inst, "fetch_releases", side_effect=RuntimeError("offline")):
        tc = TestClient(app)
        resp = tc.get("/api/v1/updates/check?force=true")
        assert resp.status_code == 200
        data = resp.json()
        assert data["check_ok"] is False
        assert data["update_available"] is False
        assert "offline" in data["error"]


def test_api_download_manager_lifecycle_and_file_serve(tmp_path, monkeypatch):
    payload = b"KASP_WEB_TEST_BINARY_CONTENT"
    sha = hashlib.sha256(payload).hexdigest()
    releases = [_make_release("web-v4.2.0", "KASP Web v4.2.0-web.dmg", sha256=sha)]

    monkeypatch.setattr(update_service, "get_downloads_dir", lambda: tmp_path)
    client_inst = update_service.get_release_client()

    def fake_download(asset, destination, progress_callback=None, cancel_check=None):
        dest = Path(destination)
        dest.write_bytes(payload)
        if progress_callback:
            progress_callback(len(payload), len(payload))
        return dest

    with (
        patch.object(client_inst, "fetch_releases", return_value=releases),
        patch.object(client_inst, "download_asset", side_effect=fake_download),
    ):
        tc = TestClient(app)
        start_resp = tc.post(
            "/api/v1/updates/download",
            json={"tag_name": "web-v4.2.0", "asset_name": "KASP Web v4.2.0-web.dmg"},
        )
        assert start_resp.status_code == 200
        job_id = start_resp.json()["job_id"]

        for _ in range(20):
            status_resp = tc.get(f"/api/v1/updates/downloads/{job_id}")
            assert status_resp.status_code == 200
            if status_resp.json()["status"] == "completed":
                break
            time.sleep(0.05)

        final_job = tc.get(f"/api/v1/updates/downloads/{job_id}").json()
        assert final_job["status"] == "completed"
        assert final_job["percent"] == 100
        assert final_job["sha256_verified"] is True

        file_resp = tc.get(f"/api/v1/updates/downloads/{job_id}/file")
        assert file_resp.status_code == 200
        assert file_resp.content == payload


def test_web_frontend_wires_auto_update_and_modal():
    root = Path(__file__).resolve().parent
    main_js = (root / "kasp/web/src/main.js").read_text(encoding="utf-8")
    header_js = (root / "kasp/web/src/components/header.js").read_text(encoding="utf-8")
    modal_js = (root / "kasp/web/src/components/updateModal.js").read_text(encoding="utf-8")
    store_js = (root / "kasp/web/src/store/updateStore.js").read_text(encoding="utf-8")

    assert "checkWebUpdates" in main_js
    assert 'activeModal === "updates"' in main_js
    assert "btn-update-manager" in header_js
    assert "onclick=" not in modal_js
    assert "fetch(" not in modal_js
    assert "fetch(" not in store_js
    assert "/api/v1/updates/check" in store_js
    assert "/api/v1/updates/download" in store_js
