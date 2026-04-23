"""UI tab-builder helpers for the KASP main window."""

from __future__ import annotations


def get_log_level_options():
    return ["TÜM LOGLAR", "DEBUG", "ITERATION", "INFO", "WARNING", "ERROR"]


def get_performance_flow_units():
    return ["Sm³/h", "Nm³/h", "kg/h", "kg/s"]


def get_performance_lhv_source_items(thermo_loaded):
    items = [
        "KASP Sabitleri (Hızlı/Varsayılan)",
        "Thermo Veritabanı (Gelişmiş)",
    ]
    if not thermo_loaded:
        items[1] = "Thermo Veritabanı (Kütüphane Yok)"
    return items


def build_log_tab(window):
    from PyQt5.QtGui import QFont
    from PyQt5.QtWidgets import QComboBox, QHBoxLayout, QLabel, QPushButton, QTextEdit, QVBoxLayout

    layout = QVBoxLayout(window.log_tab)

    filter_layout = QHBoxLayout()
    filter_layout.addWidget(QLabel("Log Seviyesi:"))

    window.log_level_combo = QComboBox()
    window.log_level_combo.addItems(get_log_level_options())
    window.log_level_combo.setCurrentText("INFO")
    window.log_level_combo.currentTextChanged.connect(window._filter_logs)
    filter_layout.addWidget(window.log_level_combo)

    filter_layout.addStretch()

    clear_btn = QPushButton("🧹 Logları Temizle")
    clear_btn.clicked.connect(window.clear_logs)
    filter_layout.addWidget(clear_btn)

    layout.addLayout(filter_layout)

    window.log_text = QTextEdit()
    window.log_text.setReadOnly(True)
    window.log_text.setFont(QFont("Courier", 9))
    layout.addWidget(window.log_text)

    window.all_logs = []
    window.log_handler.log_signal.connect(window.append_log)


def build_performance_tab(window, *, thermo_loaded):
    from PyQt5.QtWidgets import (
        QComboBox,
        QFormLayout,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QPushButton,
        QRadioButton,
        QVBoxLayout,
        QWidget,
    )

    layout = QHBoxLayout(window.performance_tab)

    input_panel = QWidget()
    input_layout = QVBoxLayout(input_panel)

    field_group = QGroupBox("📍 Saha Ölçümleri (ASME PTC 10)")
    field_layout = QFormLayout()

    window.perf_p1_edit = QLineEdit("49.65")
    window.perf_t1_edit = QLineEdit("19.0")
    window.perf_p2_edit = QLineEdit("75.0")
    window.perf_t2_edit = QLineEdit("60.0")

    flow_layout = QHBoxLayout()
    window.perf_flow_edit = QLineEdit("1985000")
    window.perf_flow_unit_combo = QComboBox()
    window.perf_flow_unit_combo.addItems(get_performance_flow_units())
    flow_layout.addWidget(window.perf_flow_edit)
    flow_layout.addWidget(window.perf_flow_unit_combo)

    window.perf_rpm_edit = QLineEdit("10000")
    window.perf_mech_eff_edit = QLineEdit("98.0")

    field_layout.addRow("Giriş Basıncı (P1) [bar(g)]:", window.perf_p1_edit)
    field_layout.addRow("Giriş Sıcaklığı (T1) [°C]:", window.perf_t1_edit)
    field_layout.addRow("Çıkış Basıncı (P2) [bar(g)]:", window.perf_p2_edit)
    field_layout.addRow("Çıkış Sıcaklığı (T2) [°C]:", window.perf_t2_edit)
    field_layout.addRow("Devir [RPM] (Opsiyonel):", window.perf_rpm_edit)
    field_layout.addRow("Debi:", flow_layout)
    field_layout.addRow("Mekanik Verim [%]:", window.perf_mech_eff_edit)

    field_group.setLayout(field_layout)
    input_layout.addWidget(field_group)

    driver_group = QGroupBox("⚙️ Sürücü Verileri")
    driver_layout = QVBoxLayout()

    window.radio_turb_eff = QRadioButton("Türbin Isıl Verimini Gir (Yakıtı Hesapla)")
    window.radio_fuel_cons = QRadioButton("Yakıt Tüketimini Gir (Verimi Hesapla)")
    window.radio_turb_eff.setChecked(True)

    driver_layout.addWidget(window.radio_turb_eff)

    turb_eff_layout = QHBoxLayout()
    turb_eff_layout.addWidget(QLabel("Türbin Verimi [%]:"))
    window.perf_turb_eff_edit = QLineEdit("35.0")
    turb_eff_layout.addWidget(window.perf_turb_eff_edit)
    driver_layout.addLayout(turb_eff_layout)

    driver_layout.addWidget(window.radio_fuel_cons)

    fuel_cons_layout = QHBoxLayout()
    fuel_cons_layout.addWidget(QLabel("Yakıt Tüketimi [kg/h]:"))
    window.perf_fuel_cons_edit = QLineEdit("")
    window.perf_fuel_cons_edit.setEnabled(False)
    fuel_cons_layout.addWidget(window.perf_fuel_cons_edit)
    driver_layout.addLayout(fuel_cons_layout)

    window.perf_lhv_source_combo = QComboBox()
    window.perf_lhv_source_combo.addItems(get_performance_lhv_source_items(thermo_loaded))
    if not thermo_loaded:
        window.perf_lhv_source_combo.setEnabled(False)
    driver_layout.addWidget(QLabel("LHV / HHV Kaynağı:"))
    driver_layout.addWidget(window.perf_lhv_source_combo)

    window.radio_turb_eff.toggled.connect(window._toggle_perf_driver_inputs)

    driver_group.setLayout(driver_layout)
    input_layout.addWidget(driver_group)

    window.verify_perf_btn = QPushButton("🚀 Performans Değerlendir")
    window.verify_perf_btn.setStyleSheet(
        "background-color: #e67e22; color: white; font-weight: bold; padding: 10px;"
    )
    window.verify_perf_btn.clicked.connect(window.run_performance_evaluation)
    input_layout.addWidget(window.verify_perf_btn)

    window.generate_perf_report_btn = QPushButton("📄 Performans Raporu")
    window.generate_perf_report_btn.setStyleSheet(
        "background-color: #16a085; color: white; font-weight: bold; padding: 10px;"
    )
    window.generate_perf_report_btn.clicked.connect(window.handle_performance_report)
    input_layout.addWidget(window.generate_perf_report_btn)

    input_layout.addStretch()
    layout.addWidget(input_panel, stretch=1)

    result_panel = QGroupBox("📊 Değerlendirme Sonuçları")
    result_layout = QFormLayout()

    window.perf_res_poly_eff = QLabel("-")
    window.perf_res_isen_eff = QLabel("-")
    window.perf_res_head = QLabel("-")
    window.perf_res_power_gas = QLabel("-")
    window.perf_res_power_shaft = QLabel("-")
    window.perf_res_fuel_or_eff = QLabel("-")

    for label in [
        window.perf_res_poly_eff,
        window.perf_res_isen_eff,
        window.perf_res_power_gas,
        window.perf_res_power_shaft,
        window.perf_res_fuel_or_eff,
        window.perf_res_head,
    ]:
        label.setStyleSheet("font-weight: bold; font-size: 15px; color: #2c3e50;")

    result_layout.addRow("Politropik Verim (ηp):", window.perf_res_poly_eff)
    result_layout.addRow("İzentropik Verim (ηs):", window.perf_res_isen_eff)
    result_layout.addRow("Politropik Head (Hp) [kJ/kg]:", window.perf_res_head)
    result_layout.addRow("Gaz Gücü (kW):", window.perf_res_power_gas)
    result_layout.addRow("Şaft Gücü (kW):", window.perf_res_power_shaft)

    window.perf_res_fuel_lbl = QLabel("Yakıt Tüketimi / Verim:")
    result_layout.addRow(window.perf_res_fuel_lbl, window.perf_res_fuel_or_eff)

    result_panel.setLayout(result_layout)
    layout.addWidget(result_panel, stretch=2)
