from __future__ import annotations

import json

from kasp.utils.updater import (
    build_release_notes_html,
    default_download_filename,
    GitHubReleaseClient,
    format_bytes,
    is_newer_release,
    newer_releases,
    parse_release_tag,
    sanitize_asset_filename,
    unseen_releases,
)


class _FakeResponse:
    def __init__(self, payload: bytes, headers: dict[str, str] | None = None):
        self._payload = payload
        self.headers = headers or {}

    def read(self, size: int = -1) -> bytes:
        if size == -1:
            payload, self._payload = self._payload, b""
            return payload
        chunk, self._payload = self._payload[:size], self._payload[size:]
        return chunk

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_release_tag_parser_and_comparison():
    assert parse_release_tag("v1.10") > parse_release_tag("v1.2")
    assert is_newer_release("v1.1", "v1.0")
    assert not is_newer_release("v1.0", "v1.1")


def test_fetch_releases_parses_assets_and_detects_newer(monkeypatch):
    payload = [
        {
            "tag_name": "v1.1",
            "name": "KASP v1.1",
            "body": "Updater support",
            "html_url": "https://example/releases/v1.1",
            "published_at": "2026-04-24T00:00:00Z",
            "prerelease": False,
            "draft": False,
            "assets": [
                {
                    "name": "KASP.v1.1.exe",
                    "browser_download_url": "https://example/assets/v1.1.exe",
                    "size": 1024,
                    "content_type": "application/octet-stream",
                }
            ],
        },
        {
            "tag_name": "v1.0",
            "name": "KASP v1.0",
            "body": "Old release",
            "html_url": "https://example/releases/v1.0",
            "published_at": "2026-04-23T00:00:00Z",
            "prerelease": False,
            "draft": False,
            "assets": [],
        },
    ]

    def fake_urlopen(request, timeout=0, **_kw):
        return _FakeResponse(json.dumps(payload).encode("utf-8"))

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    client = GitHubReleaseClient(api_url="https://example/api/releases")
    releases = client.fetch_releases()

    assert [release.tag_name for release in releases] == ["v1.1", "v1.0"]
    assert releases[0].assets[0].name == "KASP.v1.1.exe"
    assert [release.tag_name for release in newer_releases("v1.0", releases)] == ["v1.1"]


def test_download_asset_writes_file(monkeypatch, tmp_path):
    client = GitHubReleaseClient(api_url="https://example/api/releases")
    asset = client._parse_release(
        {
            "tag_name": "v1.1",
            "name": "KASP v1.1",
            "body": "",
            "html_url": "",
            "published_at": "",
            "prerelease": False,
            "draft": False,
            "assets": [
                {
                    "name": "KASP.v1.1.exe",
                    "browser_download_url": "https://example/assets/v1.1.exe",
                    "size": 11,
                    "content_type": "application/octet-stream",
                    "digest": "sha256:b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9",
                }
            ],
        }
    ).assets[0]

    def fake_urlopen(request, timeout=0, **_kw):
        return _FakeResponse(b"hello world", headers={"Content-Length": "11"})

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    target = tmp_path / "KASP.v1.1.exe"
    client.download_asset(asset, target)

    assert target.read_bytes() == b"hello world"
    assert format_bytes(11) == "11 B"


def test_download_asset_accepts_directory_destination(monkeypatch, tmp_path):
    client = GitHubReleaseClient(api_url="https://example/api/releases")
    asset = client._parse_release(
        {
            "tag_name": "v1.1",
            "assets": [
                {
                    "name": "KASP.v1.1.exe",
                    "browser_download_url": "https://example/assets/v1.1.exe",
                    "size": 5,
                    "digest": "sha256:2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824",
                }
            ],
        }
    ).assets[0]

    def fake_urlopen(request, timeout=0, **_kw):
        return _FakeResponse(b"hello", headers={"Content-Length": "5"})

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    target = client.download_asset(asset, tmp_path)

    assert target == tmp_path / "KASP.v1.1.exe"
    assert target.read_bytes() == b"hello"


def test_fetch_releases_accepts_single_release_object(monkeypatch):
    payload = {
        "tag_name": "v1.2",
        "name": "KASP v1.2",
        "body": "Single object response",
        "html_url": "https://example/releases/v1.2",
        "published_at": "2026-04-25T00:00:00Z",
        "prerelease": False,
        "draft": False,
        "assets": [],
    }

    def fake_urlopen(request, timeout=0, **_kw):
        return _FakeResponse(json.dumps(payload).encode("utf-8"))

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    releases = GitHubReleaseClient(api_url="https://example/api/releases/latest").fetch_releases()

    assert [release.tag_name for release in releases] == ["v1.2"]


def test_asset_filename_is_sanitized_and_can_fallback_to_url():
    client = GitHubReleaseClient(api_url="https://example/api/releases")
    release = client._parse_release(
        {
            "tag_name": "v1.2",
            "assets": [
                {
                    "name": "../unsafe/KASP.exe",
                    "browser_download_url": "https://example/assets/KASP.exe",
                },
                {
                    "name": "",
                    "browser_download_url": "https://example/assets/KASP%20Portable.exe",
                },
            ],
        }
    )

    assert sanitize_asset_filename("../unsafe/KASP.exe") == "KASP.exe"
    assert release.assets[0].name == "KASP.exe"
    assert release.assets[1].name == "KASP Portable.exe"


def test_default_download_filename_prefers_sanitized_asset_name():
    client = GitHubReleaseClient(api_url="https://example/api/releases")
    asset = client._parse_release(
        {
            "tag_name": "v1.2",
            "assets": [{"name": "../KASP.exe", "browser_download_url": "https://example/KASP.exe"}],
        }
    ).assets[0]

    assert default_download_filename("v1.2", asset) == "KASP.exe"
    assert default_download_filename("v1.2", None) == "KASP_v1.2.bin"


def test_unseen_releases_stops_at_last_seen_tag():
    client = GitHubReleaseClient(api_url="https://example/api/releases")
    releases = [
        client._parse_release(
            {
                "tag_name": "v1.2",
                "name": "KASP v1.2",
                "body": "Latest notes",
                "html_url": "https://example/releases/v1.2",
                "published_at": "2026-04-25T00:00:00Z",
                "prerelease": False,
                "draft": False,
                "assets": [],
            }
        ),
        client._parse_release(
            {
                "tag_name": "v1.1",
                "name": "KASP v1.1",
                "body": "Old notes",
                "html_url": "https://example/releases/v1.1",
                "published_at": "2026-04-24T00:00:00Z",
                "prerelease": False,
                "draft": False,
                "assets": [],
            }
        ),
        client._parse_release(
            {
                "tag_name": "v1.0",
                "name": "KASP v1.0",
                "body": "Very old notes",
                "html_url": "https://example/releases/v1.0",
                "published_at": "2026-04-23T00:00:00Z",
                "prerelease": False,
                "draft": False,
                "assets": [],
            }
        ),
    ]

    assert [release.tag_name for release in unseen_releases("v1.0", releases)] == ["v1.2", "v1.1"]
    assert [release.tag_name for release in unseen_releases("v1.2", releases)] == []


def test_build_release_notes_html_contains_all_visible_releases():
    client = GitHubReleaseClient(api_url="https://example/api/releases")
    releases = [
        client._parse_release(
            {
                "tag_name": "v1.2",
                "name": "KASP v1.2",
                "body": "Line 1\nLine 2",
                "html_url": "https://example/releases/v1.2",
                "published_at": "2026-04-25T00:00:00Z",
                "prerelease": False,
                "draft": False,
                "assets": [],
            }
        ),
        client._parse_release(
            {
                "tag_name": "v1.1",
                "name": "KASP v1.1",
                "body": "Previous release",
                "html_url": "https://example/releases/v1.1",
                "published_at": "2026-04-24T00:00:00Z",
                "prerelease": False,
                "draft": False,
                "assets": [],
            }
        ),
    ]

    html = build_release_notes_html(releases, "v1.1")

    assert "KASP v1.2" in html
    assert "KASP v1.1" in html
    assert "Yeni surum" in html
    assert "Kurulu surum" in html
