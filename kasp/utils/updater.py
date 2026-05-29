from __future__ import annotations

import json
import logging
import re
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass
from html import escape
from pathlib import Path
from urllib.parse import unquote, urlparse
from typing import Callable

from PyQt5.QtCore import QObject, pyqtSignal

from release_metadata import RELEASES_API_URL

logger = logging.getLogger(__name__)


def _create_ssl_context() -> ssl.SSLContext:
    """Güvenli SSL bağlamı oluşturur — PyInstaller bundle uyumlu."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except (ImportError, Exception):
        pass

    try:
        import sys
        if sys.platform == "darwin" and getattr(sys, "frozen", False):
            import os
            bundle_certs = os.path.join(sys._MEIPASS, "certifi", "cacert.pem")
            if os.path.exists(bundle_certs):
                return ssl.create_default_context(cafile=bundle_certs)
    except Exception:
        pass

    try:
        return ssl.create_default_context()
    except Exception:
        pass

    logger.warning("SSL sertifika doğrulaması devre dışı — güvenli olmayan bağlantı kullanılıyor.")
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


_ssl_context: ssl.SSLContext | None = None


def _get_ssl_context() -> ssl.SSLContext:
    global _ssl_context
    if _ssl_context is None:
        _ssl_context = _create_ssl_context()
    return _ssl_context


def parse_release_tag(tag: str) -> tuple[int, ...]:
    numbers = re.findall(r"\d+", (tag or "").strip().lower().lstrip("v"))
    if not numbers:
        return tuple()
    return tuple(int(value) for value in numbers)


def is_newer_release(candidate_tag: str, current_tag: str) -> bool:
    return parse_release_tag(candidate_tag) > parse_release_tag(current_tag)


def format_bytes(size: int) -> str:
    units = ["B", "KB", "MB", "GB"]
    value = float(max(size, 0))
    for unit in units:
        if value < 1024.0 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024.0
    return f"{int(size)} B"


def sanitize_asset_filename(name: str, *, default: str = "KASP_Update.bin") -> str:
    safe_name = Path((name or "").replace("\\", "/")).name.strip()
    return safe_name or default


def filename_from_download_url(download_url: str, *, default: str = "KASP_Update.bin") -> str:
    parsed = urlparse(download_url or "")
    return sanitize_asset_filename(unquote(Path(parsed.path).name), default=default)


def default_download_filename(release_tag: str, asset: "ReleaseAsset | None" = None) -> str:
    if asset is not None and asset.name:
        return sanitize_asset_filename(asset.name)
    tag = (release_tag or "unknown").strip() or "unknown"
    return sanitize_asset_filename(f"KASP_{tag}.bin")


@dataclass(frozen=True)
class ReleaseAsset:
    name: str
    download_url: str
    size: int
    content_type: str


@dataclass(frozen=True)
class ReleaseInfo:
    tag_name: str
    name: str
    body: str
    html_url: str
    published_at: str
    prerelease: bool
    draft: bool
    assets: tuple[ReleaseAsset, ...]

    @property
    def display_name(self) -> str:
        return self.name or self.tag_name


class GitHubReleaseClient:
    def __init__(self, api_url: str = RELEASES_API_URL, timeout: float = 8.0):
        self.api_url = api_url
        self.timeout = timeout
        self.headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "KASP-Updater",
        }

    def fetch_releases(self, *, include_prereleases: bool = False) -> list[ReleaseInfo]:
        request = urllib.request.Request(self.api_url, headers=self.headers)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout, context=_get_ssl_context()) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Release listesi alinamadi: {exc}") from exc

        if isinstance(payload, dict):
            payload = [payload]
        if not isinstance(payload, list):
            raise RuntimeError("Release listesi beklenen formatta degil.")

        releases = [self._parse_release(item) for item in payload]
        releases = [release for release in releases if not release.draft]
        if not include_prereleases:
            releases = [release for release in releases if not release.prerelease]
        releases.sort(key=lambda release: parse_release_tag(release.tag_name), reverse=True)
        return releases

    def download_asset(
        self,
        asset: ReleaseAsset,
        destination: str | Path,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> Path:
        destination_path = Path(destination)
        if destination_path.exists() and destination_path.is_dir():
            destination_path = destination_path / sanitize_asset_filename(asset.name)
        elif destination_path.suffix == "":
            destination_path = destination_path / sanitize_asset_filename(asset.name)
        destination_path.parent.mkdir(parents=True, exist_ok=True)

        request = urllib.request.Request(asset.download_url, headers=self.headers)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout, context=_get_ssl_context()) as response:
                total_size = int(response.headers.get("Content-Length") or asset.size or 0)
                downloaded = 0
                with destination_path.open("wb") as output_file:
                    while True:
                        chunk = response.read(1024 * 128)
                        if not chunk:
                            break
                        output_file.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback is not None:
                            progress_callback(downloaded, total_size)
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Guncelleme dosyasi indirilemedi: {exc}") from exc

        return destination_path

    @staticmethod
    def _parse_release(item: dict) -> ReleaseInfo:
        assets = tuple(
            ReleaseAsset(
                name=sanitize_asset_filename(
                    asset.get("name") or filename_from_download_url(asset.get("browser_download_url") or "")
                ),
                download_url=asset.get("browser_download_url") or "",
                size=int(asset.get("size") or 0),
                content_type=asset.get("content_type") or "application/octet-stream",
            )
            for asset in item.get("assets", [])
            if asset.get("browser_download_url")
        )
        return ReleaseInfo(
            tag_name=item.get("tag_name") or "",
            name=item.get("name") or item.get("tag_name") or "",
            body=item.get("body") or "",
            html_url=item.get("html_url") or "",
            published_at=item.get("published_at") or "",
            prerelease=bool(item.get("prerelease")),
            draft=bool(item.get("draft")),
            assets=assets,
        )


def newer_releases(current_tag: str, releases: list[ReleaseInfo]) -> list[ReleaseInfo]:
    return [release for release in releases if is_newer_release(release.tag_name, current_tag)]


def unseen_releases(last_seen_tag: str, releases: list[ReleaseInfo]) -> list[ReleaseInfo]:
    if not releases:
        return []

    visible = []
    for release in releases:
        if last_seen_tag and release.tag_name == last_seen_tag:
            break
        visible.append(release)
    return visible


def release_status_label(release_tag: str, current_tag: str) -> str:
    if not current_tag:
        return ""
    if release_tag == current_tag:
        return "Kurulu surum"
    if is_newer_release(release_tag, current_tag):
        return "Yeni surum"
    return "Eski surum"


def build_release_notes_html(
    releases: list[ReleaseInfo],
    current_tag: str = "",
    *,
    heading: str = "KASP Surum Notlari",
) -> str:
    parts = [f"<h3>{escape(heading)}</h3>"]
    if current_tag:
        parts.append(f"<p>Yuklu surum: <b>{escape(current_tag)}</b></p>")

    if not releases:
        parts.append("<p>Release notu bulunamadi.</p>")
        return "".join(parts)

    for release in releases:
        status = release_status_label(release.tag_name, current_tag)
        published_at = escape(release.published_at or "-")
        body = escape(release.body or "Release notu bulunmuyor.")
        title = escape(release.display_name)
        tag = escape(release.tag_name or "-")
        url = escape(release.html_url or "")

        parts.append("<hr>")
        parts.append(f"<h4>{title} <small>({tag})</small></h4>")
        parts.append(f"<p><b>Durum:</b> {escape(status or '-')}<br>")
        parts.append(f"<b>Yayin Tarihi:</b> {published_at}")
        if url:
            parts.append(f"<br><b>Baglanti:</b> <a href=\"{url}\">{url}</a>")
        parts.append("</p>")
        parts.append(
            "<pre style=\"white-space: pre-wrap; font-family: Consolas, 'Courier New', monospace;\">"
            f"{body}"
            "</pre>"
        )

    return "".join(parts)


def pick_default_asset(release: ReleaseInfo) -> ReleaseAsset | None:
    if not release.assets:
        return None
    exe_asset = next((asset for asset in release.assets if asset.name.lower().endswith(".exe")), None)
    return exe_asset or release.assets[0]


class ReleaseCheckWorker(QObject):
    finished = pyqtSignal(object, object)
    error = pyqtSignal(str)

    def __init__(self, client: GitHubReleaseClient, current_tag: str, parent=None):
        super().__init__(parent)
        self.client = client
        self.current_tag = current_tag

    def run(self) -> None:
        try:
            releases = self.client.fetch_releases()
            self.finished.emit(releases, newer_releases(self.current_tag, releases))
        except Exception as exc:
            self.error.emit(str(exc))


class ReleaseDownloadWorker(QObject):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(
        self,
        client: GitHubReleaseClient,
        asset: ReleaseAsset,
        destination: str,
        parent=None,
    ):
        super().__init__(parent)
        self.client = client
        self.asset = asset
        self.destination = destination

    def run(self) -> None:
        try:
            def report(downloaded: int, total: int) -> None:
                percent = int((downloaded / total) * 100) if total else 0
                total_text = format_bytes(total) if total else "bilinmiyor"
                self.progress.emit(
                    percent,
                    f"{self.asset.name} indiriliyor... {format_bytes(downloaded)} / {total_text}",
                )

            path = self.client.download_asset(self.asset, self.destination, progress_callback=report)
            self.progress.emit(100, f"{self.asset.name} indirildi.")
            self.finished.emit(str(path))
        except Exception as exc:
            self.error.emit(str(exc))
