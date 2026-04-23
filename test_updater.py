from __future__ import annotations

import json

from kasp.utils.updater import (
    GitHubReleaseClient,
    format_bytes,
    is_newer_release,
    newer_releases,
    parse_release_tag,
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

    def fake_urlopen(request, timeout=0):
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
                }
            ],
        }
    ).assets[0]

    def fake_urlopen(request, timeout=0):
        return _FakeResponse(b"hello world", headers={"Content-Length": "11"})

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    target = tmp_path / "KASP.v1.1.exe"
    client.download_asset(asset, target)

    assert target.read_bytes() == b"hello world"
    assert format_bytes(11) == "11 B"
