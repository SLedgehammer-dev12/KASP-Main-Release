from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from html import escape
from pathlib import Path
from urllib.parse import unquote, urlparse
from typing import Callable, Optional

from PyQt5.QtCore import QObject, pyqtSignal

from release_metadata import RELEASES_API_URL

logger = logging.getLogger(__name__)


class DownloadCancelled(Exception):
    """İndirme kullanıcı tarafından iptal edildiğinde fırlatılır (P4-22)."""
    pass


def _create_ssl_context() -> ssl.SSLContext:
    """Güvenli SSL bağlamı oluşturur — PyInstaller bundle uyumlu. Fail-closed: CERT_NONE kullanılmaz."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except (ImportError, Exception) as e:
        logger.debug("certifi yüklenemedi: %s", e)

    try:
        import sys
        if sys.platform == "darwin" and getattr(sys, "frozen", False):
            import os
            bundle_certs = os.path.join(sys._MEIPASS, "certifi", "cacert.pem")
            if os.path.exists(bundle_certs):
                return ssl.create_default_context(cafile=bundle_certs)
    except Exception as e:
        logger.debug("Bundle sertifikası bulunamadı: %s", e)

    # System default context - fail-closed, CERT_NONE kullanılmaz
    try:
        ctx = ssl.create_default_context()
        # Ekstra güvenlik: hostname ve cert doğrulaması zorunlu
        ctx.check_hostname = True
        ctx.verify_mode = ssl.CERT_REQUIRED
        return ctx
    except Exception as e:
        logger.critical("SSL context oluşturulamadı, güncelleme engelleniyor: %s", e)
        raise RuntimeError("Güvenli SSL bağlantısı kurulamadı; güncelleme iptal edildi.") from e


_ssl_context: ssl.SSLContext | None = None


def _get_ssl_context() -> ssl.SSLContext:
    global _ssl_context
    if _ssl_context is None:
        _ssl_context = _create_ssl_context()
    return _ssl_context


def _extract_numeric_tuple(tag: str) -> tuple[int, ...]:
    tag_str = (tag or "").strip().lstrip("v")
    numbers = re.findall(r"\d+", tag_str)
    if not numbers:
        return tuple()
    return tuple(int(value) for value in numbers)


def parse_release_tag(tag: str):
    """PEP 440 uyumlu sürüm ayrıştırıcı. Geçersiz etiketlerde eski sayısal ayrıştırıcıya düşer."""
    tag_str = (tag or "").strip().lstrip("v")
    try:
        from packaging.version import Version
        return Version(tag_str)
    except Exception:
        # Fallback: eski sayısal tuple ayrıştırıcı
        return _extract_numeric_tuple(tag)


def _version_sort_key(tag: str) -> tuple:
    """Uniform sort key that never raises TypeError between PEP 440 Version and fallback tuples."""
    parsed = parse_release_tag(tag)
    if isinstance(parsed, tuple):
        return (0, parsed, 0, "")
    release_tuple = getattr(parsed, "release", None) or _extract_numeric_tuple(tag)
    is_final = 0 if getattr(parsed, "is_prerelease", False) or getattr(parsed, "is_devrelease", False) else 1
    return (1, tuple(release_tuple), is_final, str(parsed))


def is_newer_release(candidate_tag: str, current_tag: str) -> bool:
    cand = parse_release_tag(candidate_tag)
    curr = parse_release_tag(current_tag)
    # packaging.version.Version karşılaştırmasını destekle
    try:
        return cand > curr
    except TypeError:
        # Fallback: both normalized to numeric tuples so Version vs tuple never raises TypeError
        cand_tuple = cand if isinstance(cand, tuple) else (getattr(cand, "release", None) or _extract_numeric_tuple(candidate_tag))
        curr_tuple = curr if isinstance(curr, tuple) else (getattr(curr, "release", None) or _extract_numeric_tuple(current_tag))
        return tuple(cand_tuple) > tuple(curr_tuple)


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
    sha256: Optional[str] = None


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
        self._cached_releases: list[ReleaseInfo] | None = None
        self._last_fetch_time: float = 0.0

    def fetch_releases(
        self,
        *,
        include_prereleases: bool = False,
        force: bool = False,
        max_age_seconds: float = 86400.0,
    ) -> list[ReleaseInfo]:
        if not force and self._cached_releases is not None and (time.time() - self._last_fetch_time < max_age_seconds):
            logger.debug("Önbellekten release listesi döndürülüyor (TTL: %.0fs)", max_age_seconds)
            releases = self._cached_releases
        else:
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
            self._cached_releases = releases
            self._last_fetch_time = time.time()

        releases = [release for release in releases if not release.draft]
        if not include_prereleases:
            releases = [release for release in releases if not release.prerelease]
        releases.sort(key=lambda release: _version_sort_key(release.tag_name), reverse=True)
        return releases

    def download_asset(
        self,
        asset: ReleaseAsset,
        destination: str | Path,
        progress_callback: Callable[[int, int], None] | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> Path:
        destination_path = Path(destination)
        if destination_path.exists() and destination_path.is_dir():
            destination_path = destination_path / sanitize_asset_filename(asset.name)
        elif destination_path.suffix == "":
            destination_path = destination_path / sanitize_asset_filename(asset.name)
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        # Doğrulanmamış veri asla nihai adla diskte bulunmaz: önce .part dosyasına yaz,
        # SHA256 doğrulandıktan sonra atomik olarak yeniden adlandır.
        part_path = destination_path.with_name(destination_path.name + ".part")

        request = urllib.request.Request(asset.download_url, headers=self.headers)
        hasher = hashlib.sha256()
        try:
            try:
                with urllib.request.urlopen(request, timeout=self.timeout, context=_get_ssl_context()) as response:
                    total_size = int(response.headers.get("Content-Length") or asset.size or 0)
                    downloaded = 0
                    with part_path.open("wb") as output_file:
                        while True:
                            if cancel_check is not None and cancel_check():
                                raise DownloadCancelled("İndirme kullanıcı tarafından iptal edildi.")
                            chunk = response.read(1024 * 128)
                            if not chunk:
                                break
                            output_file.write(chunk)
                            hasher.update(chunk)
                            downloaded += len(chunk)
                            if progress_callback is not None:
                                progress_callback(downloaded, total_size)
            except urllib.error.URLError as exc:
                raise RuntimeError(f"Guncelleme dosyasi indirilemedi: {exc}") from exc

            # SHA256 doğrulama (akışlı hash, fail-closed)
            if not asset.sha256:
                raise RuntimeError(
                    f"İndirilen dosya için SHA256 özeti bulunamadı (asset.digest eksik). "
                    f"Güvenlik nedeniyle dosya silindi. Lütfen release notlarında SHA256 sağlayın."
                )
            computed = hasher.hexdigest()
            if computed.lower() != asset.sha256.lower():
                raise RuntimeError(
                    f"SHA256 doğrulama başarısız: indirilen dosya bozuk veya değiştirilmiş. "
                    f"Beklenen: {asset.sha256}, Hesaplanan: {computed}"
                )
            os.replace(part_path, destination_path)
        except BaseException:
            # İptal, ağ kopması (TimeoutError, ConnectionResetError, IncompleteRead),
            # disk hatası veya doğrulama hatası: kısmi dosyayı her durumda temizle (P4-22)
            part_path.unlink(missing_ok=True)
            raise

        logger.info("SHA256 doğrulama başarılı: %s", asset.name)
        return destination_path

    @staticmethod
    def _parse_release(item: dict) -> ReleaseInfo:
        item_dict = dict(item or {})
        body = item_dict.get("body") or ""
        raw_assets = [
            a for a in (item_dict.get("assets") or [])
            if isinstance(a, dict) and a.get("browser_download_url")
        ]
        
        # Gövdedeki sıralı 64-hex özetler (sıralı blok eşleme için)
        body_hashes = re.findall(r"([a-fA-F0-9]{64})", body)

        def _extract_sha256(raw_asset, index):
            digest = (raw_asset.get("digest") or "").strip()
            if digest.startswith("sha256:"):
                return digest.replace("sha256:", "")
            name = raw_asset.get("name") or ""
            # 1) Aynı satırda ad + özet: "KASP.exe  <hash>"
            if name:
                same_line = re.search(
                    re.escape(name) + r"[^\n\r]*?([a-fA-F0-9]{64})", body, re.IGNORECASE
                )
                if same_line:
                    return same_line.group(1)
            # 2) Sıralı blok eşleme: gövdedeki özet sayısı varlık sayısına eşitse
            #    release varlıkları yükleme sırasında döndüğü için index ile eşle.
            #    Olası yanlış eşleme yine de fail-closed indirme doğrulamasında yakalanır.
            if len(raw_assets) > 1 and len(body_hashes) == len(raw_assets):
                return body_hashes[index]
            # 3) Tek varlık fallback: "sha256: <hash>" veya tek 64-hex
            if len(raw_assets) == 1:
                sha_match = re.search(r"sha256[:\s]+([a-fA-F0-9]{64})", body, re.IGNORECASE)
                if sha_match:
                    return sha_match.group(1)
                if len(body_hashes) == 1:
                    return body_hashes[0]
            # 4) Güvenle eşlenemedi -> fail-closed
            if name and body_hashes:
                logger.warning(
                    "SHA256 gövdeden varlığa güvenle eşlenemedi, atlanıyor: %s", name
                )
            return None

        assets = tuple(
            ReleaseAsset(
                name=sanitize_asset_filename(
                    asset.get("name") or filename_from_download_url(asset.get("browser_download_url") or "")
                ),
                download_url=asset.get("browser_download_url") or "",
                size=int(asset.get("size") or 0),
                content_type=asset.get("content_type") or "application/octet-stream",
                sha256=_extract_sha256(asset, index),
            )
            for index, asset in enumerate(raw_assets)
        )
        return ReleaseInfo(
            tag_name=item_dict.get("tag_name") or "",
            name=item_dict.get("name") or item_dict.get("tag_name") or "",
            body=body,
            html_url=item_dict.get("html_url") or "",
            published_at=item_dict.get("published_at") or "",
            prerelease=bool(item_dict.get("prerelease")),
            draft=bool(item_dict.get("draft")),
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


def _platform_asset_extensions() -> tuple[str, ...]:
    """Platforma uygun varlik uzantilari, tercih sirasina gore (P4-22)."""
    if sys.platform.startswith("win"):
        return (".exe", ".msi", ".zip")
    if sys.platform == "darwin":
        return (".dmg", ".pkg", ".zip", ".tar.gz")
    return (".tar.gz", ".zip", ".appimage")


def pick_default_asset(release: ReleaseInfo) -> ReleaseAsset | None:
    if not release.assets:
        return None
    extensions = _platform_asset_extensions()
    for extension in extensions:
        for asset in release.assets:
            if asset.name.lower().endswith(extension):
                return asset
    return release.assets[0]


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
    cancelled = pyqtSignal()

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
        self._cancel_requested = False

    def request_cancel(self):
        self._cancel_requested = True

    def run(self) -> None:
        try:
            def report(downloaded: int, total: int) -> None:
                percent = int((downloaded / total) * 100) if total else 0
                total_text = format_bytes(total) if total else "bilinmiyor"
                self.progress.emit(
                    percent,
                    f"{self.asset.name} indiriliyor... {format_bytes(downloaded)} / {total_text}",
                )

            path = self.client.download_asset(
                self.asset,
                self.destination,
                progress_callback=report,
                cancel_check=lambda: self._cancel_requested,
            )
            self.progress.emit(100, f"{self.asset.name} indirildi.")
            self.finished.emit(str(path))
        except DownloadCancelled:
            logger.info("Güncelleme indirmesi iptal edildi: %s", self.asset.name)
            self.cancelled.emit()
        except Exception as exc:
            self.error.emit(str(exc))
