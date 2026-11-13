"""KASP Web Update & Download Manager Service.

Pure service layer for checking GitHub Web releases (``web-v*``) and managing
background asset downloads with SHA-256 verification and cancellation.
"""

from __future__ import annotations

import logging
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from kasp.utils.updater import (
    DownloadCancelled,
    GitHubReleaseClient,
    ReleaseAsset,
    ReleaseInfo,
    filter_releases_for_channel,
    format_bytes,
    is_newer_release,
    newer_releases,
    pick_default_asset,
    release_status_label,
    sanitize_asset_filename,
)
from release_metadata import (
    RELEASES_API_URL,
    WEB_RELEASE_TAG,
    WEB_RELEASE_VERSION,
)

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_client: GitHubReleaseClient | None = None
_downloads: dict[str, dict[str, Any]] = {}
_cancel_events: dict[str, threading.Event] = {}


def get_release_client() -> GitHubReleaseClient:
    global _client
    with _lock:
        if _client is None:
            _client = GitHubReleaseClient(api_url=RELEASES_API_URL, timeout=10.0)
        return _client


def get_downloads_dir() -> Path:
    d = Path.home() / ".kasp" / "downloads"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _serialize_asset(asset: ReleaseAsset) -> dict[str, Any]:
    return {
        "name": asset.name,
        "size": asset.size,
        "size_human": format_bytes(asset.size),
        "content_type": asset.content_type,
        "download_url": asset.download_url,
        "sha256_available": bool(asset.sha256),
    }


def _serialize_release(release: ReleaseInfo, current_tag: str) -> dict[str, Any]:
    rec = pick_default_asset(release)
    return {
        "tag_name": release.tag_name,
        "name": release.display_name,
        "published_at": release.published_at,
        "html_url": release.html_url,
        "body": release.body,
        "prerelease": release.prerelease,
        "status_label": release_status_label(release.tag_name, current_tag),
        "is_newer": is_newer_release(release.tag_name, current_tag),
        "recommended_asset_name": rec.name if rec else None,
        "assets": [_serialize_asset(a) for a in release.assets],
    }


def check_web_updates(
    *,
    force: bool = False,
    include_prereleases: bool = False,
    max_age_seconds: float = 300.0,
) -> dict[str, Any]:
    client = get_release_client()
    checked_at = datetime.now(timezone.utc).isoformat()
    try:
        all_releases = client.fetch_releases(
            include_prereleases=include_prereleases,
            force=force,
            max_age_seconds=max_age_seconds,
        )
        web_releases = filter_releases_for_channel(all_releases, channel="web")
        newer = newer_releases(WEB_RELEASE_TAG, web_releases)
        serialized = [_serialize_release(r, WEB_RELEASE_TAG) for r in web_releases]
        latest = serialized[0] if serialized else None
        return {
            "check_ok": True,
            "error": None,
            "channel": "web",
            "platform": sys.platform,
            "current_version": WEB_RELEASE_VERSION,
            "current_tag": WEB_RELEASE_TAG,
            "checked_at": checked_at,
            "update_available": len(newer) > 0,
            "newer_count": len(newer),
            "latest_release": latest,
            "releases": serialized,
        }
    except Exception as exc:
        logger.warning("Web güncelleme kontrolü başarısız: %s", exc)
        return {
            "check_ok": False,
            "error": str(exc),
            "channel": "web",
            "platform": sys.platform,
            "current_version": WEB_RELEASE_VERSION,
            "current_tag": WEB_RELEASE_TAG,
            "checked_at": checked_at,
            "update_available": False,
            "newer_count": 0,
            "latest_release": None,
            "releases": [],
        }


def _find_release_and_asset(tag_name: str, asset_name: str) -> tuple[ReleaseInfo, ReleaseAsset]:
    client = get_release_client()
    releases = filter_releases_for_channel(client.fetch_releases(force=False, max_age_seconds=3600.0), channel="web")
    target_release = next((r for r in releases if r.tag_name == tag_name), None)
    if target_release is None:
        releases = filter_releases_for_channel(client.fetch_releases(force=True), channel="web")
        target_release = next((r for r in releases if r.tag_name == tag_name), None)
    if target_release is None:
        raise ValueError(f"Sürüm bulunamadı: {tag_name}")

    safe_asset_name = sanitize_asset_filename(asset_name)
    target_asset = next((a for a in target_release.assets if a.name == safe_asset_name), None)
    if target_asset is None:
        raise ValueError(f"Sürüm dosyası bulunamadı: {safe_asset_name}")
    return target_release, target_asset


def start_download(tag_name: str, asset_name: str) -> dict[str, Any]:
    release, asset = _find_release_and_asset(tag_name, asset_name)
    job_id = uuid.uuid4().hex[:12]
    dest_dir = get_downloads_dir()
    dest_path = dest_dir / sanitize_asset_filename(asset.name)
    cancel_event = threading.Event()
    now = time.time()

    job_state: dict[str, Any] = {
        "job_id": job_id,
        "tag_name": release.tag_name,
        "asset_name": asset.name,
        "status": "downloading",
        "downloaded_bytes": 0,
        "total_bytes": int(asset.size or 0),
        "downloaded_human": "0 B",
        "total_human": format_bytes(int(asset.size or 0)),
        "percent": 0,
        "speed_bps": 0,
        "sha256_verified": False,
        "file_path": None,
        "error": None,
        "created_at": now,
        "updated_at": now,
    }

    with _lock:
        _downloads[job_id] = job_state
        _cancel_events[job_id] = cancel_event

    def _run() -> None:
        started_at = time.monotonic()
        client = get_release_client()

        def on_progress(downloaded: int, total: int) -> None:
            elapsed = max(time.monotonic() - started_at, 0.05)
            eff_total = total or int(asset.size or 0)
            pct = min(100, int((downloaded / eff_total) * 100)) if eff_total else 0
            with _lock:
                j = _downloads.get(job_id)
                if j is None:
                    return
                j["downloaded_bytes"] = downloaded
                j["total_bytes"] = eff_total
                j["downloaded_human"] = format_bytes(downloaded)
                j["total_human"] = format_bytes(eff_total) if eff_total else "Bilinmiyor"
                j["percent"] = pct
                j["speed_bps"] = int(downloaded / elapsed)
                j["updated_at"] = time.time()

        try:
            saved_path = client.download_asset(
                asset,
                dest_path,
                progress_callback=on_progress,
                cancel_check=cancel_event.is_set,
            )
            with _lock:
                j = _downloads.get(job_id)
                if j is not None:
                    final_size = saved_path.stat().st_size if saved_path.exists() else j["downloaded_bytes"]
                    j["status"] = "completed"
                    j["downloaded_bytes"] = final_size
                    j["total_bytes"] = final_size or j["total_bytes"]
                    j["downloaded_human"] = format_bytes(final_size)
                    j["total_human"] = format_bytes(j["total_bytes"])
                    j["percent"] = 100
                    j["sha256_verified"] = True
                    j["file_path"] = str(saved_path)
                    j["updated_at"] = time.time()
        except DownloadCancelled:
            with _lock:
                j = _downloads.get(job_id)
                if j is not None:
                    j["status"] = "cancelled"
                    j["updated_at"] = time.time()
        except Exception as exc:
            logger.error("Web güncelleme indirme hatası (%s): %s", asset.name, exc)
            with _lock:
                j = _downloads.get(job_id)
                if j is not None:
                    j["status"] = "error"
                    j["error"] = str(exc)
                    j["updated_at"] = time.time()

    threading.Thread(target=_run, daemon=True, name=f"kasp-dl-{job_id}").start()
    return dict(job_state)


def list_downloads() -> list[dict[str, Any]]:
    with _lock:
        items = [dict(v) for v in _downloads.values()]
    items.sort(key=lambda x: x["created_at"], reverse=True)
    return items


def get_download(job_id: str) -> dict[str, Any] | None:
    with _lock:
        item = _downloads.get(job_id)
        return dict(item) if item is not None else None


def cancel_download(job_id: str) -> dict[str, Any] | None:
    with _lock:
        ev = _cancel_events.get(job_id)
        item = _downloads.get(job_id)
        if item is None:
            return None
        if ev is not None:
            ev.set()
        if item["status"] == "downloading":
            item["status"] = "cancelling"
            item["updated_at"] = time.time()
        return dict(item)


def get_downloaded_file_path(job_id: str) -> Path | None:
    with _lock:
        item = _downloads.get(job_id)
        if not item or item.get("status") != "completed" or not item.get("file_path"):
            return None
        candidate = Path(item["file_path"]).resolve()

    downloads_root = get_downloads_dir().resolve()
    try:
        candidate.relative_to(downloads_root)
    except ValueError:
        return None
    if not candidate.is_file():
        return None
    return candidate
