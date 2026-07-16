"""General window action and log workflow helpers for the KASP UI."""

from __future__ import annotations

import logging

from kasp.i18n import ALL_LOGS_LABEL, APP_VERSION, tr, is_english


def filter_logs_by_level(logs, selected_level):
    """Return logs visible for the requested filter level — level-aware matching."""
    if selected_level in {"TUM LOGLAR", ALL_LOGS_LABEL}:
        return list(logs)
    level_markers = ["DEBUG", "ITERATION", "INFO", "WARNING", "ERROR", "CRITICAL"]
    level_idx = level_markers.index(selected_level) if selected_level in level_markers else -1
    if level_idx < 0:
        return [log for log in logs if selected_level in log]
    result = []
    for log in logs:
        for marker in level_markers[level_idx:]:
            if marker in log:
                result.append(log)
                break
    return result


def build_about_dialog_text(version=APP_VERSION):
    """Build the about-dialog body text."""
    if is_english():
        return (
            f"KASP v{version} - Compressor Analysis and Selection Platform\n\n"
            "An advanced thermodynamic, fluid dynamics, and turbomachinery calculation engine.\n\n"
            "--- Calculation Methodology ---\n"
            "• Aerodynamics & Thermodynamic Core:\n"
            "  - Computes isentropic/polytropic compressor performance using standard ASME PTC 10.\n"
            "  - Employs CoolProp (HEOS), Peng-Robinson (PR), and Soave-Redlich-Kwong (SRK) Equations of State (EoS).\n"
            "• Equation of State (EoS) Fallback Chain:\n"
            "  - Stage 1: Primary EoS (e.g., CoolProp/AGA8) for high-accuracy multi-component mixtures.\n"
            "  - Stage 2: Cubic EoS (Peng-Robinson / SRK) if primary fails near critical limits or phase envelopes.\n"
            "  - Stage 3: Ideal Gas Equation as the ultimate fallback to prevent application crashes.\n"
            "• Isentropic Temperature Fallback Root-Finding Solvers:\n"
            "  - 1. Finite Difference Newton-Raphson (FD-NR): Uses standard numerical gradients.\n"
            "  - 2. Analytical Jacobian Newton-Raphson (AJ-NR): High-speed solver utilizing the exact thermodynamic relation (dS/dT)_P = Cp/T.\n"
            "  - 3. Brent's Method: A robust, hybrid root-finding solver with dynamically bounded intervals ensuring 100% convergence under EoS instabilities.\n\n"
            "Standards: ASME PTC-10, ASME PTC-22, API 616/617, ISO 2314"
        )
    else:
        return (
            f"KASP v{version} - Kompresör Analiz ve Seçim Platformu\n\n"
            "Gelişmiş termodinamik, akışkan dinamiği ve turbomakine hesaplamaları için Python tabanlı platform.\n\n"
            "--- Hesaplama Yöntemi ---\n"
            "• Aerodinamik & Termodinamik Çekirdek:\n"
            "  - ASME PTC 10 standardına uygun olarak izantropik/politropik kompresör performansını hesaplar.\n"
            "  - CoolProp (HEOS), Peng-Robinson (PR) ve Soave-Redlich-Kwong (SRK) Durum Denklemlerini (EoS) kullanır.\n"
            "• Durum Denklemi (EoS) Fallback Sırası:\n"
            "  - 1. Kademe: Birincil EoS (örn. CoolProp/AGA8), çok bileşenli karışımlar için yüksek doğruluk sağlar.\n"
            "  - 2. Kademe: Birincil EoS kritik sınırlarda veya iki fazlı bölgede hata verdiğinde Kübik EoS (Peng-Robinson / SRK) devreye girer.\n"
            "  - 3. Kademe: Programın çökmesini önlemek için nihai güvenlik ağı olarak İdeal Gaz Denklemi kullanılır.\n"
            "• İzantropik Sıcaklık Fallback Kök Bulucu Çözücüler:\n"
            "  - 1. Sonlu Farklar Newton-Raphson (FD-NR): Standart sayısal gradyanları kullanır.\n"
            "  - 2. Analitik Jakobiyen Newton-Raphson (AJ-NR): (dS/dT)_P = Cp/T analitik termodinamik özdeşliğini kullanan yüksek hızlı çözücü.\n"
            "  - 3. Brent Metodu: EoS kararsızlıkları altında %100 yakınsama garantisi sunan, dinamik aralık sınırlamalı robust hibrit çözücü.\n\n"
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

    def show_thermodynamics_handbook(self):
        from kasp.ui.dialogs import ThermodynamicsHandbookDialog
        dialog = ThermodynamicsHandbookDialog(self.window)
        dialog.exec_()

    def clear_logs(self):
        self.window.log_text.clear()
        self.window.all_logs = []
        self.window.logger.info("Sistem logları temizlendi.")

    def append_log(self, message):
        self.window.all_logs.append(message)
        current_level = self.window.log_level_combo.currentText()
        if current_level in {"TUM LOGLAR", ALL_LOGS_LABEL}:
            self.window.log_text.append(message)
        else:
            visible = filter_logs_by_level([message], current_level)
            if visible:
                self.window.log_text.append(message)
        from PyQt5.QtWidgets import QApplication
        QApplication.processEvents()

    def filter_logs(self, selected_level):
        self.window.log_text.clear()
        for entry in filter_logs_by_level(self.window.all_logs, selected_level):
            self.window.log_text.append(entry)
