from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PyQt5.QtCore import QObject, pyqtSignal

from release_metadata import RELEASES_API_URL


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
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Release listesi alinamadi: {exc}") from exc

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
        destination_path.parent.mkdir(parents=True, exist_ok=True)

        request = urllib.request.Request(asset.download_url, headers=self.headers)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
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
                name=asset.get("name") or "asset",
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
