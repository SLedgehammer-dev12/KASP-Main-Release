"""General window action and log workflow helpers for the KASP UI."""

from __future__ import annotations

import logging

from kasp.i18n import ALL_LOGS_LABEL, APP_VERSION, tr


def filter_logs_by_level(logs, selected_level):
    """Return logs visible for the requested filter level."""
    if selected_level in {"TÃœM LOGLAR", "TÜM LOGLAR", ALL_LOGS_LABEL}:
        return list(logs)
    return [log for log in logs if selected_level in log]


def build_about_dialog_text(version=APP_VERSION):
    """Build the about-dialog body text."""
    return tr(
        f"KASP v{version} - Kompresör Analiz ve Seçim Platformu\n\n"
        "Gelişmiş termodinamik, akışkan dinamiği ve turbomakine hesaplamaları için Python tabanlı platform.\n\n"
        "V4.6 Yenilikleri: Responsive UI, QScrollArea sol panel, DPI ölçeklendirme.\n\n"
        "Standartlar: ASME PTC-10, ASME PTC-22, API 616/617, ISO 2314"
    )


class WindowActionController:
    """Handle general window actions outside the main window class."""

    def __init__(self, window, *, engine, library_manager_cls=None):
        self.window = window
        self.engine = engine
        self.logger = logging.getLogger(self.__class__.__name__)
        self._library_manager_cls = library_manager_cls

    @staticmethod
    def _qt_message_box():
        from PyQt5.QtWidgets import QMessageBox

        return QMessageBox

    @staticmethod
    def _default_library_manager_cls():
        from kasp.ui.library_manager import LibraryManagerWindow

        return LibraryManagerWindow

    def _get_library_manager_cls(self):
        return self._library_manager_cls or self._default_library_manager_cls()

    def open_library_manager(self):
        manager = self._get_library_manager_cls()(self.window)
        manager.exec_()
        if self.window.last_selected_units:
            self.window._populate_turbine_table(self.window.last_selected_units)
        self.window.logger.info(tr("Kütüphane yöneticisi kapatıldı."))

    def clear_engine_cache(self):
        QMessageBox = self._qt_message_box()
        self.engine.clear_cache()
        QMessageBox.information(self.window, tr("Başarılı"), tr("✅ Termodinamik Özellik Önbelleği temizlendi."))

    def show_about_dialog(self):
        QMessageBox = self._qt_message_box()
        QMessageBox.about(self.window, tr(f"KASP v{APP_VERSION} Hakkında"), build_about_dialog_text(APP_VERSION))

    def show_examples(self):
        QMessageBox = self._qt_message_box()
        QMessageBox.information(self.window, tr("Örnekler"), tr("Örnek projeler ilerleyen versiyonlarda eklenecektir."))

    def clear_logs(self):
        self.window.log_text.clear()
        self.window.all_logs = []
        self.window.logger.info("Sistem logları temizlendi.")

    def append_log(self, message):
        self.window.all_logs.append(message)
        current_level = self.window.log_level_combo.currentText()
        if current_level in {"TÃœM LOGLAR", "TÜM LOGLAR", ALL_LOGS_LABEL} or current_level in message:
            self.window.log_text.append(message)

    def filter_logs(self, selected_level):
        self.window.log_text.clear()
        for entry in filter_logs_by_level(self.window.all_logs, selected_level):
            self.window.log_text.append(entry)
