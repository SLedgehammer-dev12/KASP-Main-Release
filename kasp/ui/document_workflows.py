"""Document and project workflow helpers for the main window."""

from __future__ import annotations

import datetime
import json
import logging

from kasp.core.contracts import get_design_input_defaults
from kasp.utils.reporting import ReportGenerator

DESIGN_REPORT_UNITS = {
    "power_unit": "kW",
    "head_unit": "kJ/kg",
    "heat_rate": "kJ/kWh",
    "lhv": "kJ/kg",
    "hhv": "kJ/kg",
    "fuel_unit": "kg/h",
}


def sanitize_project_basename(name, fallback):
    """Return a filesystem-friendly basename preserving current UI behavior."""
    value = (name or "").strip()
    if not value:
        value = fallback
    return value.replace(" ", "_")


def default_design_report_filename(project_name):
    return f"{sanitize_project_basename(project_name, 'Proje')}_Tasarim_Raporu.pdf"


def default_results_export_filename(project_name):
    return f"{sanitize_project_basename(project_name, 'Proje')}_Sonuclar.json"


def default_performance_report_filename(unit_name):
    return f"{sanitize_project_basename(unit_name, 'Performans')}_Performans_Raporu.pdf"


def build_results_export_payload(inputs, results, selected_units, *, exported_at=None):
    """Build the JSON payload used by results export."""
    return {
        "inputs": inputs,
        "results": results,
        "selected_units": selected_units,
        "date": (exported_at or datetime.datetime.now()).isoformat(),
    }


class DocumentWorkflowController:
    """Handle project and report workflows outside the main window class."""

    def __init__(self, window, *, engine, project_manager, reportlab_loaded):
        self.window = window
        self.engine = engine
        self.project_manager = project_manager
        self.reportlab_loaded = reportlab_loaded
        self.logger = logging.getLogger(self.__class__.__name__)

    @staticmethod
    def _qt_widgets():
        from PyQt5.QtWidgets import QFileDialog, QMessageBox

        return QFileDialog, QMessageBox

    def new_project(self):
        _, QMessageBox = self._qt_widgets()
        reply = QMessageBox.question(
            self.window,
            "Yeni Proje",
            "Mevcut projeyi temizlemek istediğinizden emin misiniz?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply != QMessageBox.Yes:
            return

        defaults = get_design_input_defaults()
        self.window._populate_ui_from_inputs(defaults)
        self.window.last_design_inputs = defaults
        self.window.last_design_results_raw = {}
        self.window.last_selected_units = []
        self.window.last_perf_inputs = None
        self.window.last_perf_results = None
        self.logger.info("Yeni proje oluşturuldu")

    def save_project(self):
        QFileDialog, QMessageBox = self._qt_widgets()
        try:
            file_path, _ = QFileDialog.getSaveFileName(
                self.window,
                "Projeyi Kaydet",
                "",
                "KASP Proje Dosyası (*.kasp);;Tüm Dosyalar (*)",
            )

            if not file_path:
                return

            inputs = self.window._get_design_inputs()
            if inputs is None:
                return

            success, message = self.project_manager.save_project(
                file_path,
                inputs,
                self.window.last_design_results_raw,
            )

            if success:
                QMessageBox.information(
                    self.window,
                    "Başarılı",
                    f"✅ Proje kaydedildi:\n{message}",
                )
                self.logger.info("Proje kaydedildi: %s", file_path)
            else:
                QMessageBox.critical(
                    self.window,
                    "Hata",
                    f"❌ Proje kaydedilemedi:\n{message}",
                )

        except Exception as e:
            self.logger.error("Proje kaydetme hatası: %s", e, exc_info=True)
            QMessageBox.critical(self.window, "Hata", f"❌ Kaydetme hatası:\n{e}")

    def load_project(self):
        QFileDialog, QMessageBox = self._qt_widgets()
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self.window,
                "Proje Aç",
                "",
                "KASP Proje Dosyası (*.kasp);;Tüm Dosyalar (*)",
            )

            if not file_path:
                return

            success, inputs, results = self.project_manager.load_project(file_path)
            if not success:
                QMessageBox.critical(
                    self.window,
                    "Hata",
                    f"❌ Proje yüklenemedi:\n{inputs}",
                )
                return

            self.window._populate_ui_from_inputs(inputs)
            self.window.last_design_inputs = inputs
            self.window.last_design_results_raw = results or {}
            self.window.last_selected_units = []
            self.window.last_perf_inputs = None
            self.window.last_perf_results = None

            if results:
                self.window._update_results_ui(results, [])

            QMessageBox.information(
                self.window,
                "Başarılı",
                f"✅ Proje yüklendi:\n{inputs.get('project_name', 'İsimsiz')}",
            )
            self.logger.info("Proje yüklendi: %s", file_path)
        except Exception as e:
            self.logger.error("Proje yükleme hatası: %s", e, exc_info=True)
            QMessageBox.critical(self.window, "Hata", f"❌ Yükleme hatası:\n{e}")

    def handle_design_report(self):
        QFileDialog, QMessageBox = self._qt_widgets()
        if not self.window.last_design_results_raw or not self.window.last_design_inputs or not self.reportlab_loaded:
            if not self.reportlab_loaded:
                QMessageBox.critical(
                    self.window,
                    "Hata",
                    "Raporlama Kütüphanesi (ReportLab) yüklü değil.",
                )
            else:
                QMessageBox.warning(
                    self.window,
                    "Uyarı",
                    "Önce başarılı bir tasarım hesaplaması yapın.",
                )
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self.window,
            "Tasarım Raporunu Kaydet",
            default_design_report_filename(self.window.project_name_edit.text()),
            "PDF Files (*.pdf)",
        )

        if not file_path:
            return

        try:
            reporter = ReportGenerator(file_path, self.engine)
            reporter.generate_design_report(
                self.window.last_design_inputs,
                self.window.last_design_results_raw,
                self.window.last_selected_units,
                DESIGN_REPORT_UNITS,
            )
            QMessageBox.information(
                self.window,
                "Başarılı",
                f"✅ Rapor başarıyla oluşturuldu:\n{file_path}",
            )
        except Exception as e:
            self.logger.error("Rapor oluşturma hatası: %s", e)
            QMessageBox.critical(self.window, "Hata", f"Rapor oluşturulurken hata oluştu: {e}")

    def export_results(self):
        QFileDialog, QMessageBox = self._qt_widgets()
        if not self.window.last_design_results_raw:
            QMessageBox.warning(self.window, "Uyarı", "Önce bir hesaplama yapın.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self.window,
            "Sonuçları Dışa Aktar",
            default_results_export_filename(self.window.project_name_edit.text()),
            "JSON Files (*.json)",
        )

        if not file_path:
            return

        try:
            export_data = build_results_export_payload(
                self.window.last_design_inputs,
                self.window.last_design_results_raw,
                self.window._serialize_selected_units(self.window.last_selected_units),
            )
            with open(file_path, "w", encoding="utf-8") as handle:
                json.dump(export_data, handle, indent=4, ensure_ascii=False, default=str)
            QMessageBox.information(
                self.window,
                "Başarılı",
                f"✅ Sonuçlar başarıyla dışa aktarıldı:\n{file_path}",
            )
        except Exception as e:
            self.logger.error("Sonuç dışa aktarma hatası: %s", e)
            QMessageBox.critical(
                self.window,
                "Hata",
                f"Sonuçlar dışa aktarılırken hata oluştu: {e}",
            )

    def handle_performance_report(self):
        QFileDialog, QMessageBox = self._qt_widgets()
        if not self.reportlab_loaded:
            QMessageBox.critical(
                self.window,
                "Hata",
                "Raporlama Kütüphanesi (ReportLab) yüklü değil.",
            )
            return

        if not self.window.last_perf_inputs or not self.window.last_perf_results:
            QMessageBox.warning(
                self.window,
                "Uyarı",
                "Önce bir performans değerlendirmesi yapın.",
            )
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self.window,
            "Performans Raporunu Kaydet",
            default_performance_report_filename(self.window.last_perf_inputs.get("unit_name", "Performans")),
            "PDF Files (*.pdf)",
        )

        if not file_path:
            return

        try:
            reporter = ReportGenerator(file_path, self.engine)
            reporter.generate_performance_report(
                self.window.last_perf_inputs,
                self.window.last_perf_results,
            )
            QMessageBox.information(
                self.window,
                "Başarılı",
                f"✅ Performans raporu oluşturuldu:\n{file_path}",
            )
        except Exception as e:
            self.logger.error("Performans raporu oluşturma hatası: %s", e)
            QMessageBox.critical(
                self.window,
                "Hata",
                f"Performans raporu oluşturulurken hata oluştu: {e}",
            )
