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


def build_examples_dialog_text():
    return tr(
        "KASP Ornek Senaryolari\n\n"
        "1) Dogal gaz kompresor tasarimi\n"
        "- Gaz: Natural Gas standard kompozisyonu veya kullanici karisimi\n"
        "- P1: 49.65 bar(g), T1: 19 C, P2: 75 bar(a)\n"
        "- Debi: 1,985,000 Sm3/h, Metot 4: Dogrudan H-S\n"
        "- Beklenen cikti: kademe sicakliklari, politropik head, motor gucu ve yakit tuketimi.\n\n"
        "2) Saha performans degerlendirmesi\n"
        "- Performans sekmesinde olculen P1/T1/P2/T2/debi girilir.\n"
        "- Saha duzeltmeleri: ortam sicakligi, ortam basinci, nem, rakim, giris ve egzoz basinc kayiplari.\n"
        "- OEM egri verisi varsa guc ve isi orani manuel faktorleri ile uygulanir.\n\n"
        "3) Fallback ve yakinsama kontrolu\n"
        "- Sonuc ozetinde fallback veya metot yakinsamama uyarisi varsa rapora da eklenir.\n"
        "- Grafikler sekmesinde T-s, P-v, guc dagilimi ve yakinsama grafikleri incelenir.\n\n"
        "Referanslar: ASME PTC 10 kompresor performans testi, ASME PTC 22 gaz turbini testi, ISO 2314 gaz turbini kabul testi."
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
        QMessageBox.information(self.window, tr("Örnekler"), build_examples_dialog_text())

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
