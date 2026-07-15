"""
KASP Update Service (v2.1)

Handles GitHub release checking, download progress tracking, and
installer launch. Extracted from main_window.py for reuse across
dialogs and the API server.

TODO(v2.2): Move remaining UI-specific methods from main_window.py
(_show_update_dialog, _maybe_show_release_notes, etc.) into this module.
"""

from __future__ import annotations

import logging
from typing import Optional, Callable

from PyQt5.QtCore import QObject, QThread, pyqtSignal

from kasp.utils.updater import (
    GitHubReleaseClient, ReleaseCheckWorker, ReleaseDownloadWorker,
    ReleaseAsset, ReleaseInfo, newer_releases, pick_default_asset,
    format_bytes, RELEASES_API_URL, RELEASE_TAG,
)

logger = logging.getLogger(__name__)


class UpdateService(QObject):
    check_finished = pyqtSignal(object, object)
    check_error = pyqtSignal(str)
    download_progress = pyqtSignal(int, str)
    download_finished = pyqtSignal(str)
    download_error = pyqtSignal(str)

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._check_thread: Optional[QThread] = None
        self._check_worker: Optional[ReleaseCheckWorker] = None
        self._download_thread: Optional[QThread] = None
        self._download_worker: Optional[ReleaseDownloadWorker] = None

    @property
    def is_checking(self) -> bool:
        return self._check_thread is not None and self._check_thread.isRunning()

    @property
    def is_downloading(self) -> bool:
        return self._download_thread is not None and self._download_thread.isRunning()

    def check_for_updates(self, current_tag: str = RELEASE_TAG):
        if self.is_checking:
            logger.info("Update check already in progress")
            return

        self._check_thread = QThread(self)
        client = GitHubReleaseClient(api_url=RELEASES_API_URL, timeout=8.0)
        self._check_worker = ReleaseCheckWorker(client, current_tag)
        self._check_worker.moveToThread(self._check_thread)

        self._check_thread.started.connect(self._check_worker.run)
        self._check_worker.finished.connect(self._on_check_finished)
        self._check_worker.error.connect(self._on_check_error)
        self._check_thread.start()

    def _on_check_finished(self, releases, newer):
        self.check_finished.emit(releases, newer)
        self._cleanup_check()

    def _on_check_error(self, message: str):
        self.check_error.emit(message)
        self._cleanup_check()

    def _cleanup_check(self):
        if self._check_thread:
            self._check_thread.quit()
            self._check_thread.wait(2000)
        self._check_thread = None
        self._check_worker = None

    def download_release(self, asset: ReleaseAsset, destination: str):
        if self.is_downloading:
            logger.info("Download already in progress")
            return

        self._download_thread = QThread(self)
        client = GitHubReleaseClient(api_url=RELEASES_API_URL, timeout=60)
        self._download_worker = ReleaseDownloadWorker(client, asset, destination)
        self._download_worker.moveToThread(self._download_thread)

        self._download_thread.started.connect(self._download_worker.run)
        self._download_worker.progress.connect(self.download_progress.emit)
        self._download_worker.finished.connect(self._on_download_finished)
        self._download_worker.error.connect(self._on_download_error)
        self._download_thread.start()

    def _on_download_finished(self, path: str):
        self.download_finished.emit(path)
        self._cleanup_download()

    def _on_download_error(self, message: str):
        self.download_error.emit(message)
        self._cleanup_download()

    def _cleanup_download(self):
        if self._download_thread:
            self._download_thread.quit()
            self._download_thread.wait(2000)
        self._download_thread = None
        self._download_worker = None

    @staticmethod
    def pick_asset(release: ReleaseInfo) -> Optional[ReleaseAsset]:
        return pick_default_asset(release)

    @staticmethod
    def filter_newer(current_tag: str, releases: list) -> list:
        return newer_releases(current_tag, releases)

    @staticmethod
    def format_size(size: int) -> str:
        return format_bytes(size)
