"""Lightweight runtime localization helpers for the KASP desktop UI."""

from __future__ import annotations

from PyQt5.QtWidgets import (
    QAction,
    QAbstractButton,
    QComboBox,
    QDialog,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMenu,
    QPlainTextEdit,
    QTabWidget,
    QTextEdit,
    QWidget,
)

from kasp.config_manager import get_config_manager
from release_metadata import APP_VERSION, RELEASE_TAG
ALL_LOGS_LABEL = "ALL LOGS"

_EXACT_TRANSLATIONS = {
    "KASP v4.6.2 - Termodinamik Analiz": "KASP v4.6.2 - Thermodynamic Analysis",
    "KASP v4.6.2 Hakkında": "About KASP v4.6.2",
    "KASP Güncelleme Notları": "KASP Release Notes",
    "KASP v4.6.2 - Kompresör Analiz ve Seçim Platformu": "KASP v4.6.2 - Compressor Analysis and Selection Platform",
    "📊 Tasarım / Simülasyon": "📊 Design / Simulation",
    "📈 Performans Değerlendirme": "📈 Performance Evaluation",
    "📋 Sistem Logları": "📋 System Logs",
    "📁 Dosya": "📁 File",
    "🛠️ Araçlar": "🛠️ Tools",
    "❓ Yardım": "❓ Help",
    "🆕 Yeni Proje": "🆕 New Project",
    "📂 Proje Aç...": "📂 Open Project...",
    "💾 Projeyi Kaydet...": "💾 Save Project...",
    "📤 Sonuçları Dışa Aktar": "📤 Export Results",
    "🚪 Çıkış": "🚪 Exit",
    "📚 Kütüphane Yöneticisi": "📚 Library Manager",
    "🧹 Önbelleği Temizle": "🧹 Clear Cache",
    "📖 Örnekler": "📖 Examples",
    "ℹ️ Hakkında": "ℹ️ About",
    "Kompresör Ekle/Düzenle": "Add/Edit Compressor",
    "Türbin Ekle/Düzenle": "Add/Edit Turbine",
    "Başarılı": "Success",
    "Hata": "Error",
    "Uyarı": "Warning",
    "Örnekler": "Examples",
    "Eksik Bilgi": "Missing Information",
    "TÜM LOGLAR": ALL_LOGS_LABEL,
    f"KASP {RELEASE_TAG}": f"KASP {RELEASE_TAG}",
}

_SUBSTRING_TRANSLATIONS = {
    "Kompresör Analiz ve Seçim Platformu": "Compressor Analysis and Selection Platform",
    "Gelişmiş termodinamik, akışkan dinamiği ve turbomakine hesaplamaları için Python tabanlı platform.": "Python-based platform for advanced thermodynamic, fluid dynamics, and turbomachinery calculations.",
    "V4.6 Yenilikleri: Responsive UI, QScrollArea sol panel, DPI ölçeklendirme.": "V4.6 updates: responsive UI, left-side QScrollArea panel, DPI scaling.",
    "Standartlar": "Standards",
    "Ekipman Kütüphanesi Yönetimi": "Equipment Library Management",
    "Üretici Filtresi:": "Manufacturer Filter:",
    "🚀 Gaz Türbinleri": "🚀 Gas Turbines",
    "💨 Kompresörler": "💨 Compressors",
    "➕ Ekle": "➕ Add",
    "✏️ Düzenle": "✏️ Edit",
    "🗑️ Sil": "🗑️ Delete",
    "🔄 Yenile": "🔄 Refresh",
    "👁️ Detay Göster": "👁️ View Details",
    "Üretici:": "Manufacturer:",
    "Tip:": "Type:",
    "Maks. Basınç Oranı:": "Max Pressure Ratio:",
    "Min. Akış": "Min Flow",
    "Maks. Akış": "Max Flow",
    "Performans Haritası (JSON):": "Performance Map (JSON):",
    "ISO Güç": "ISO Power",
    "ISO Isı Oranı": "ISO Heat Rate",
    "Yakıt Tipi:": "Fuel Type:",
    "Düzeltme Verisi (JSON):": "Correction Data (JSON):",
    "Düzeltme Faktörleri (JSON):": "Correction Factors (JSON):",
    "Hesaplanan Türbin Verimi:": "Calculated Turbine Efficiency:",
    "Hesaplanan Yakıt [kg/h]:": "Calculated Fuel [kg/h]:",
    "Termodinamik Analiz": "Thermodynamic Analysis",
    "⚠️ Geçersiz Girişler": "⚠️ Invalid Inputs",
    "Kütüphanede": "Library contains",
    "türbin ve": "turbines and",
    "kompresör bulundu.": "compressors.",
    "Hesaplama başlatmadan önce lütfen aşağıdaki alanları düzeltiniz:": "Please correct the following fields before starting the calculation:",
    "Geçersiz alanlar kırmızı kenarlık ile işaretlenmiştir.": "Invalid fields are highlighted with a red border.",
    "Giriş Basıncı": "Inlet Pressure",
    "Giriş Sıcaklığı": "Inlet Temperature",
    "Çıkış Basıncı": "Outlet Pressure",
    "Gaz Debisi": "Gas Flow Rate",
    "Birim/Kütüphane Combobox'ları güncelleniyor...": "Refreshing unit/library combo boxes...",
    "Kütüphane yöneticisi kapatıldı.": "Library manager closed.",
    "✅ Termodinamik Özellik Önbelleği temizlendi.": "✅ Thermodynamic property cache cleared.",
    "Örnek projeler ilerleyen versiyonlarda eklenecektir.": "Sample projects will be added in future versions.",
}


def get_language() -> str:
    return str(get_config_manager().get("app.language", "tr")).lower()


def is_english() -> bool:
    return get_language().startswith("en")


def tr(text: str) -> str:
    if not text or not is_english():
        return text

    translated = _EXACT_TRANSLATIONS.get(text, text)
    for source, target in _SUBSTRING_TRANSLATIONS.items():
        translated = translated.replace(source, target)
    return translated


def _translate_combo(combo: QComboBox) -> None:
    for index in range(combo.count()):
        combo.setItemText(index, tr(combo.itemText(index)))


def _translate_widget(widget: QWidget) -> None:
    if isinstance(widget, QTabWidget):
        for index in range(widget.count()):
            widget.setTabText(index, tr(widget.tabText(index)))

    if isinstance(widget, (QLabel, QAbstractButton, QGroupBox)):
        widget.setText(tr(widget.text()))

    if isinstance(widget, (QLineEdit, QTextEdit, QPlainTextEdit)):
        placeholder = widget.placeholderText()
        if placeholder:
            widget.setPlaceholderText(tr(placeholder))

    if widget.windowTitle():
        widget.setWindowTitle(tr(widget.windowTitle()))

    if widget.toolTip():
        widget.setToolTip(tr(widget.toolTip()))

    if isinstance(widget, QComboBox):
        _translate_combo(widget)


def apply_window_language(widget: QWidget) -> None:
    if not is_english():
        return

    _translate_widget(widget)
    for child in widget.findChildren(QWidget):
        _translate_widget(child)

    for menu in widget.findChildren(QMenu):
        menu.setTitle(tr(menu.title()))

    for action in widget.findChildren(QAction):
        action.setText(tr(action.text()))

    if isinstance(widget, QDialog):
        widget.setWindowTitle(tr(widget.windowTitle()))
