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
    return ["🌡️ Termodinamik", "⚡ Güç Dağılımı", "⛽ Yakıt Analizi"]


def get_graph_option_labels():
    return ["T-s Diyagramı", "P-v Diyagramı", "Güç Dağılımı", "Türbin Performansı", "Yakınsama Grafiği"]


def build_basic_results_tab(window):
    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import QComboBox, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QPushButton, QTextEdit, QVBoxLayout

    layout = QVBoxLayout(window.basic_results_tab)

    window.consistency_info_group = QGroupBox("🔄 Tutarlılık Modu Bilgisi")
    consistency_info_layout = QVBoxLayout()
    window.consistency_info_label = QLabel("Mod: Hızlı")
    window.consistency_info_label.setWordWrap(True)
    window.consistency_info_label.setStyleSheet("font-size: 10pt; padding: 5px;")
    consistency_info_layout.addWidget(window.consistency_info_label)
    window.consistency_info_group.setLayout(consistency_info_layout)
    window.consistency_info_group.setVisible(False)
    layout.addWidget(window.consistency_info_group)

    results_group = QGroupBox("🎯 Hesaplama Sonuçları")
    results_layout = QGridLayout()

    window.result_labels = {}
    window.result_unit_combos = {}

    for index, (label, key, default_unit, available_units) in enumerate(get_basic_result_definitions()):
        results_layout.addWidget(QLabel(f"{label}:"), index, 0)

        value_label = QLabel("-")
        value_label.setStyleSheet("font-weight: bold; color: #2c3e50; min-width: 80px;")
        value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        results_layout.addWidget(value_label, index, 1)
        window.result_labels[key] = value_label

        if len(available_units) > 1:
            unit_combo = QComboBox()
            unit_combo.addItems(available_units)
            unit_combo.setCurrentText(default_unit)
            unit_combo.setMaximumWidth(120)
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
    window.summary_text.setMaximumHeight(150)
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

    layout.addWidget(tabs)


def build_graphs_tab(window):
    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import QComboBox, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

    layout = QVBoxLayout(window.graphs_tab)

    graph_selection_layout = QHBoxLayout()
    graph_selection_layout.addWidget(QLabel("Grafik:"))

    window.graph_combo = QComboBox()
    window.graph_combo.addItems(get_graph_option_labels())
    graph_selection_layout.addWidget(window.graph_combo)

    window.refresh_graph_btn = QPushButton("🔄 Grafiği Yenile")
    graph_selection_layout.addWidget(window.refresh_graph_btn)

    window.save_graph_btn = QPushButton("💾 Grafiği Kaydet")
    graph_selection_layout.addWidget(window.save_graph_btn)

    graph_selection_layout.addStretch()
    layout.addLayout(graph_selection_layout)

    window.graph_widget = QWidget()
    window.graph_layout = QVBoxLayout(window.graph_widget)
    layout.addWidget(window.graph_widget)

    window.default_graph_label = QLabel("🚀 Hesaplama yapıldıktan sonra grafikler burada görüntülenecek")
    window.default_graph_label.setAlignment(Qt.AlignCenter)
    window.default_graph_label.setStyleSheet("font-size: 16px; color: #7f8c8d; padding: 50px;")
    window.graph_layout.addWidget(window.default_graph_label)
