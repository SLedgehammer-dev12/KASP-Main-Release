"""Builders for the design-results tabs in the KASP main window."""

from __future__ import annotations


def get_design_result_tab_titles():
    return ["📈 Temel Sonuçlar", "🚀 Türbin Seçimi", "📊 Detaylı Analiz", "📉 Grafikler"]


def get_basic_result_definitions():
    return [
        ("Çıkış Sıcaklığı", "t_out", "°C", ["°C", "°F", "K"]),
        ("Politropik Head", "head_kj_kg", "kJ/kg", ["kJ/kg", "J/kg", "Btu/lb", "ft-lbf/lbm"]),
        ("Sıkıştırma Oranı", "compression_ratio", "", [""]),
        ("Politropik Verim", "actual_poly_efficiency", "%", ["%"]),
        ("Motor Gücü (Ünite)", "power_unit_kw", "kW", ["kW", "MW", "hp"]),
        ("Toplam Motor Gücü", "power_unit_total_kw", "kW", ["kW", "MW", "hp"]),
        ("Isı Oranı", "heat_rate", "kJ/kWh", ["kJ/kWh", "Btu/kWh", "kcal/kWh"]),
        ("Ünite Yakıt Tüketimi", "fuel_unit_kgh", "kg/h", ["kg/h", "lb/h", "Sm³/h", "cal/h", "J/h"]),
        ("Toplam Yakıt Tüketimi", "fuel_total_kgh", "kg/h", ["kg/h", "lb/h", "Sm³/h", "cal/h", "J/h"]),
    ]


def get_turbine_table_headers():
    return ["Sıra", "Türbin", "Güç (kW)", "Isı Oranı", "Verimlilik", "Surge Margin", "Seçim Puanı", "Öneri"]


def get_detailed_analysis_tab_titles():
    return ["🌡️ Termodinamik", "⚡ Güç Dağılımı", "⛽ Yakıt Analizi", "⚠️ Fallback Karşılaştırması"]


def get_graph_option_labels():
    try:
        from kasp.i18n import is_english
    except ImportError:
        is_english = lambda: False

    if is_english():
        return [
            "T-s Diagram", "P-v Diagram", "H-S (Mollier)",
            "Power Flow (Sankey)", "k-Z Pressure Path", "Stage Overview",
            "Turbine Radar", "Convergence Dashboard",
        ]
    return [
        "T-s Diyagramı", "P-v Diyagramı", "H-S (Mollier)",
        "Güç Dağılımı (Sankey)", "k-Z Basınç Yolu", "Kademe Özeti",
        "Türbin Radarı", "Yakınsama Dashboard",
    ]


def build_basic_results_tab(window):
    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import QComboBox, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QPushButton, QTextEdit, QVBoxLayout

    layout = QVBoxLayout(window.basic_results_tab)

    window.consistency_info_group = QGroupBox("🔄 Tutarlılık Modu Bilgisi")
    consistency_info_layout = QVBoxLayout()
    window.consistency_info_label = QLabel("Mod: Hızlı")
    window.consistency_info_label.setObjectName("consistency_info_label")
    window.consistency_info_label.setWordWrap(True)
    consistency_info_layout.addWidget(window.consistency_info_label)
    window.consistency_info_group.setLayout(consistency_info_layout)
    window.consistency_info_group.setVisible(False)
    layout.addWidget(window.consistency_info_group)

    window.fallback_info_group = QGroupBox("⚠️ Termodinamik Fallback Uyarısı")
    fallback_info_layout = QVBoxLayout()
    window.fallback_info_label = QLabel("Fallback kullanılmadı.")
    window.fallback_info_label.setWordWrap(True)
    window.fallback_info_label.setObjectName("fallback_info_label")
    fallback_info_layout.addWidget(window.fallback_info_label)
    window.fallback_info_group.setLayout(fallback_info_layout)
    window.fallback_info_group.setVisible(False)
    layout.addWidget(window.fallback_info_group)

    results_group = QGroupBox("🎯 Hesaplama Sonuçları")
    results_layout = QGridLayout()

    window.result_labels = {}
    window.result_unit_combos = {}

    for index, (label, key, default_unit, available_units) in enumerate(get_basic_result_definitions()):
        results_layout.addWidget(QLabel(f"{label}:"), index, 0)

        value_label = QLabel("-")
        value_label.setObjectName("value_label")
        value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        results_layout.addWidget(value_label, index, 1)
        window.result_labels[key] = value_label

        if len(available_units) > 1:
            unit_combo = QComboBox()
            unit_combo.addItems(available_units)
            unit_combo.setCurrentText(default_unit)
            from kasp.ui.responsive import scaled_px
            unit_combo.setMaximumWidth(scaled_px(120))
            unit_combo.currentTextChanged.connect(lambda unit, result_key=key: window._update_single_result_unit(result_key, unit))
            results_layout.addWidget(unit_combo, index, 2)
            window.result_unit_combos[key] = unit_combo
        else:
            results_layout.addWidget(QLabel(default_unit), index, 2)

    results_group.setLayout(results_layout)
    layout.addWidget(results_group)

    summary_group = QGroupBox("📊 Performans Özeti")
    summary_layout = QVBoxLayout()
    window.summary_text = QTextEdit()
    window.summary_text.setMaximumHeight(scaled_px(150))
    window.summary_text.setReadOnly(True)
    summary_layout.addWidget(window.summary_text)
    summary_group.setLayout(summary_layout)
    layout.addWidget(summary_group)

    quick_actions_group = QGroupBox("⚡ Hızlı İşlemler")
    quick_layout = QHBoxLayout()
    window.export_results_btn = QPushButton("📤 Sonuçları Dışa Aktar")
    window.generate_report_btn = QPushButton("📋 Rapor Oluştur")
    window.save_project_btn = QPushButton("💾 Projeyi Kaydet")
    quick_layout.addWidget(window.export_results_btn)
    quick_layout.addWidget(window.generate_report_btn)
    quick_layout.addWidget(window.save_project_btn)
    quick_actions_group.setLayout(quick_layout)
    layout.addWidget(quick_actions_group)
    layout.addStretch()


def build_turbine_selection_tab(window):
    from PyQt5.QtWidgets import QFormLayout, QGroupBox, QLabel, QTableWidget, QVBoxLayout
    from PyQt5.QtWidgets import QHeaderView

    layout = QVBoxLayout(window.turbine_selection_tab)

    window.turbine_table = QTableWidget()
    window.turbine_table.setColumnCount(8)
    window.turbine_table.setHorizontalHeaderLabels(get_turbine_table_headers())
    header = window.turbine_table.horizontalHeader()
    header.setSectionResizeMode(1, QHeaderView.Stretch)

    layout.addWidget(QLabel("🚀 Önerilen Türbinler:"))
    layout.addWidget(window.turbine_table)

    detail_group = QGroupBox("👁️ Türbin Detayları")
    detail_layout = QFormLayout()
    window.selected_turbine_label = QLabel("Türbin seçin...")
    window.turbine_power_label = QLabel("-")
    window.turbine_efficiency_label = QLabel("-")
    window.turbine_margin_label = QLabel("-")
    window.turbine_recommendation_label = QLabel("-")

    detail_layout.addRow("Seçilen Türbin:", window.selected_turbine_label)
    detail_layout.addRow("Mevcut Güç:", window.turbine_power_label)
    detail_layout.addRow("Verimlilik:", window.turbine_efficiency_label)
    detail_layout.addRow("Güç Marjı:", window.turbine_margin_label)
    detail_layout.addRow("Öneri:", window.turbine_recommendation_label)

    detail_group.setLayout(detail_layout)
    layout.addWidget(detail_group)


def build_detailed_results_tab(window):
    from PyQt5.QtWidgets import QTableWidget, QTabWidget, QVBoxLayout, QWidget

    layout = QVBoxLayout(window.detailed_results_tab)
    tabs = QTabWidget()

    thermo_tab = QWidget()
    thermo_layout = QVBoxLayout(thermo_tab)
    window.thermo_table = QTableWidget()
    window.thermo_table.setColumnCount(5)
    window.thermo_table.setHorizontalHeaderLabels(["Özellik", "Giriş", "Çıkış", "Birim", "Değişim"])
    thermo_layout.addWidget(window.thermo_table)
    tabs.addTab(thermo_tab, get_detailed_analysis_tab_titles()[0])

    power_tab = QWidget()
    power_layout = QVBoxLayout(power_tab)
    window.power_table = QTableWidget()
    window.power_table.setColumnCount(3)
    window.power_table.setHorizontalHeaderLabels(["Parametre", "Ünite Başına", "Toplam"])
    power_layout.addWidget(window.power_table)
    tabs.addTab(power_tab, get_detailed_analysis_tab_titles()[1])

    fuel_tab = QWidget()
    fuel_layout = QVBoxLayout(fuel_tab)
    window.fuel_table = QTableWidget()
    window.fuel_table.setColumnCount(2)
    window.fuel_table.setHorizontalHeaderLabels(["Parametre", "Değer"])
    fuel_layout.addWidget(window.fuel_table)
    tabs.addTab(fuel_tab, get_detailed_analysis_tab_titles()[2])

    fallback_tab = QWidget()
    fallback_layout = QVBoxLayout(fallback_tab)
    window.fallback_table = QTableWidget()
    window.fallback_table.setColumnCount(6)
    window.fallback_table.setHorizontalHeaderLabels(["Kademe / Bölüm", "Çözücü Metot", "Hesaplanan Sıcaklık", "İterasyon", "Entropi Artığı (dS)", "Süre (ms)"])
    fallback_layout.addWidget(window.fallback_table)
    tabs.addTab(fallback_tab, get_detailed_analysis_tab_titles()[3])

    layout.addWidget(tabs)


def build_graphs_tab(window):
    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import (
        QButtonGroup, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
    )

    layout = QVBoxLayout(window.graphs_tab)
    layout.setContentsMargins(0, 0, 0, 0)

    window.graph_button_group = QButtonGroup(window)
    window.graph_button_group.setExclusive(True)

    button_row = QHBoxLayout()
    button_row.setSpacing(2)
    graph_labels = get_graph_option_labels()
    for i, label in enumerate(graph_labels):
        btn = QPushButton(label)
        btn.setCheckable(True)
        btn.setFlat(True)
        if i == 0:
            btn.setChecked(True)
        btn.setStyleSheet(
            "QPushButton { padding: 4px 10px; border-radius: 4px; font-size: 10pt; }"
            "QPushButton:checked { font-weight: bold; border-bottom: 2px solid palette(highlight); }"
        )
        btn.clicked.connect(lambda checked, idx=i: window.on_graph_button_clicked(idx))
        window.graph_button_group.addButton(btn, i)
        button_row.addWidget(btn)
    button_row.addStretch()
    button_row_widget = QWidget()
    button_row_widget.setLayout(button_row)
    layout.addWidget(button_row_widget)

    window.graph_widget = QWidget()
    window.graph_layout = QVBoxLayout(window.graph_widget)
    window.graph_layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(window.graph_widget, stretch=1)

    window.default_graph_label = QLabel("🚀 Hesaplama yapıldıktan sonra grafikler burada görüntülenecek")
    window.default_graph_label.setAlignment(Qt.AlignCenter)
    window.default_graph_label.setObjectName("default_graph_label")
    window.graph_layout.addWidget(window.default_graph_label)

    bottom_row = QHBoxLayout()
    window.graph_desc_label = QLabel("Grafik seçin...")
    window.graph_desc_label.setWordWrap(True)
    bottom_row.addWidget(window.graph_desc_label, stretch=1)

    window.refresh_graph_btn = QPushButton("🔄 Yenile")
    window.save_graph_btn = QPushButton("💾 PNG")
    window.save_svg_btn = QPushButton("💾 SVG")
    window.save_pdf_btn = QPushButton("💾 PDF")
    bottom_row.addWidget(window.refresh_graph_btn)
    bottom_row.addWidget(window.save_graph_btn)
    bottom_row.addWidget(window.save_svg_btn)
    bottom_row.addWidget(window.save_pdf_btn)

    window.graph_combo = None  # geriye dönük uyumluluk — artık kullanılmıyor
    bottom_widget = QWidget()
    bottom_widget.setLayout(bottom_row)
    layout.addWidget(bottom_widget)
