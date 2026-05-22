"""UI tab-builder helpers for the KASP main window."""

from __future__ import annotations

from kasp.ui.design_left_panel_builders import (
    get_design_flow_units,
    get_pressure_unit_options,
    get_temperature_unit_options,
)


def get_log_level_options():
    return ["TÜM LOGLAR", "DEBUG", "ITERATION", "INFO", "WARNING", "ERROR"]


def get_performance_flow_units():
    return get_design_flow_units()


def get_performance_standard_options():
    return ["ASME PTC 10", "ASME PTC 22", "ISO 2314"]


def build_unit_input_row(edit_widget, unit_items, default_unit):
    from PyQt5.QtWidgets import QComboBox, QHBoxLayout

    layout = QHBoxLayout()
    combo = QComboBox()
    combo.addItems(unit_items)
    combo.setCurrentText(default_unit)
    layout.addWidget(edit_widget)
    layout.addWidget(combo)
    return layout, combo


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

    window.perf_standard_combo = QComboBox()
    window.perf_standard_combo.addItems(get_performance_standard_options())
    window.perf_standard_combo.setCurrentText("ASME PTC 10")
    input_layout.addWidget(QLabel("Performans Standardı:"))
    input_layout.addWidget(window.perf_standard_combo)

    field_group = QGroupBox("📍 Saha Ölçümleri (ASME PTC 10)")
    field_layout = QFormLayout()

    window.perf_p1_edit = QLineEdit("49.65")
    window.perf_t1_edit = QLineEdit("19.0")
    window.perf_p2_edit = QLineEdit("75.0")
    window.perf_t2_edit = QLineEdit("60.0")

    pressure_units = get_pressure_unit_options()
    temperature_units = get_temperature_unit_options()
    window.perf_p1_layout, window.perf_p1_unit_combo = build_unit_input_row(window.perf_p1_edit, pressure_units, "bar(g)")
    window.perf_t1_layout, window.perf_t1_unit_combo = build_unit_input_row(window.perf_t1_edit, temperature_units, "°C")
    window.perf_p2_layout, window.perf_p2_unit_combo = build_unit_input_row(window.perf_p2_edit, pressure_units, "bar(g)")
    window.perf_t2_layout, window.perf_t2_unit_combo = build_unit_input_row(window.perf_t2_edit, temperature_units, "°C")

    window.perf_flow_edit = QLineEdit("1985000")
    window.perf_flow_layout, window.perf_flow_unit_combo = build_unit_input_row(
        window.perf_flow_edit, get_performance_flow_units(), "Sm³/h"
    )

    window.perf_rpm_edit = QLineEdit("")
    window.perf_mech_eff_edit = QLineEdit("98.0")

    field_layout.addRow("Giriş Basıncı (P1):", window.perf_p1_layout)
    field_layout.addRow("Giriş Sıcaklığı (T1):", window.perf_t1_layout)
    field_layout.addRow("Çıkış Basıncı (P2):", window.perf_p2_layout)
    field_layout.addRow("Çıkış Sıcaklığı (T2):", window.perf_t2_layout)
    field_layout.addRow("Debi:", window.perf_flow_layout)
    field_layout.addRow("Mekanik Verim [%]:", window.perf_mech_eff_edit)

    field_group.setLayout(field_layout)
    input_layout.addWidget(field_group)

    impeller_group = QGroupBox("🔧 Cark Geometrisi (ASME PTC 10 Benzerlik — Opsiyonel)")
    impeller_layout = QFormLayout()
    window.perf_impeller_D_edit = QLineEdit("")
    window.perf_impeller_b_edit = QLineEdit("")
    impeller_layout.addRow("Cark Capi (D) [mm]:", window.perf_impeller_D_edit)
    impeller_layout.addRow("Kanat Genisligi (b) [mm]:", window.perf_impeller_b_edit)
    impeller_layout.addRow("Devir [RPM]:", window.perf_rpm_edit)
    impeller_group.setToolTip("Opsiyonel: Cark geometrisi girilirse ASME PTC 10 benzerlik kontrolu yapilir.")
    impeller_group.setLayout(impeller_layout)
    input_layout.addWidget(impeller_group)

    correction_group = QGroupBox("Saha Duzeltme Faktorleri (ISO 2314 / ASME PTC 22)")
    correction_layout = QFormLayout()

    window.perf_ambient_temp_edit = QLineEdit("15.0")
    window.perf_ambient_pressure_edit = QLineEdit("101.325")
    window.perf_humidity_edit = QLineEdit("60.0")
    window.perf_altitude_edit = QLineEdit("0.0")
    window.perf_inlet_loss_edit = QLineEdit("0.0")
    window.perf_exhaust_loss_edit = QLineEdit("0.0")
    window.perf_manual_power_factor_edit = QLineEdit("1.0")
    window.perf_manual_heat_rate_factor_edit = QLineEdit("1.0")

    window.perf_ambient_temp_layout, window.perf_ambient_temp_unit_combo = build_unit_input_row(
        window.perf_ambient_temp_edit, temperature_units, "°C"
    )
    window.perf_ambient_pressure_layout, window.perf_ambient_pressure_unit_combo = build_unit_input_row(
        window.perf_ambient_pressure_edit, pressure_units, "kPa"
    )
    window.perf_inlet_loss_layout, window.perf_inlet_loss_unit_combo = build_unit_input_row(
        window.perf_inlet_loss_edit, pressure_units, "kPa"
    )
    window.perf_exhaust_loss_layout, window.perf_exhaust_loss_unit_combo = build_unit_input_row(
        window.perf_exhaust_loss_edit, pressure_units, "kPa"
    )

    correction_layout.addRow("Ortam Sicakligi:", window.perf_ambient_temp_layout)
    correction_layout.addRow("Ortam Basinci:", window.perf_ambient_pressure_layout)
    correction_layout.addRow("Bagil Nem [%]:", window.perf_humidity_edit)
    correction_layout.addRow("Rakim [m]:", window.perf_altitude_edit)
    correction_layout.addRow("Giris Havasi Basinc Kaybi:", window.perf_inlet_loss_layout)
    correction_layout.addRow("Egzoz Cikis Basinc Kaybi:", window.perf_exhaust_loss_layout)
    correction_layout.addRow("OEM Guc Faktoru [carpan]:", window.perf_manual_power_factor_edit)
    correction_layout.addRow("OEM Isi Orani Faktoru [carpan]:", window.perf_manual_heat_rate_factor_edit)
    correction_group.setToolTip(
        "Referans sartlar: 15 C, 101.325 kPa, %60 RH. OEM egrileri varsa manuel carpanlara girilebilir."
    )
    correction_group.setLayout(correction_layout)
    input_layout.addWidget(correction_group)

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
    window.verify_perf_btn.setObjectName("verify_perf_btn")
    window.verify_perf_btn.clicked.connect(window.run_performance_evaluation)
    input_layout.addWidget(window.verify_perf_btn)

    window.generate_perf_report_btn = QPushButton("📄 Performans Raporu")
    window.generate_perf_report_btn.setObjectName("generate_perf_report_btn")
    window.generate_perf_report_btn.clicked.connect(window.handle_performance_report)
    input_layout.addWidget(window.generate_perf_report_btn)

    input_layout.addStretch()
    # V4.7: Responsive stretch ratios based on screen breakpoint
    try:
        from kasp.ui.responsive import breakpoint_stretch_factors
        in_stretch, out_stretch = breakpoint_stretch_factors()
    except Exception:
        in_stretch, out_stretch = 1, 2
    layout.addWidget(input_panel, stretch=in_stretch)

    result_panel = QGroupBox("📊 Değerlendirme Sonuçları")
    result_layout = QFormLayout()

    window.perf_res_poly_eff = QLabel("-")
    window.perf_res_isen_eff = QLabel("-")
    window.perf_res_head = QLabel("-")
    window.perf_res_power_gas = QLabel("-")
    window.perf_res_power_shaft = QLabel("-")
    window.perf_res_corrected = QLabel("-")
    window.perf_res_fuel_or_eff = QLabel("-")

    for label in [
        window.perf_res_poly_eff,
        window.perf_res_isen_eff,
        window.perf_res_power_gas,
        window.perf_res_power_shaft,
        window.perf_res_corrected,
        window.perf_res_fuel_or_eff,
        window.perf_res_head,
    ]:
        label.setProperty("resultLabel", "true")

    result_layout.addRow("Politropik Verim (ηp):", window.perf_res_poly_eff)
    result_layout.addRow("İzentropik Verim (ηs):", window.perf_res_isen_eff)
    result_layout.addRow("Politropik Head (Hp) [kJ/kg]:", window.perf_res_head)
    result_layout.addRow("Gaz Gücü (kW):", window.perf_res_power_gas)
    result_layout.addRow("Şaft Gücü (kW):", window.perf_res_power_shaft)
    result_layout.addRow("ISO'ya Duzeltilmis:", window.perf_res_corrected)

    window.perf_res_fuel_lbl = QLabel("Yakıt Tüketimi / Verim:")
    result_layout.addRow(window.perf_res_fuel_lbl, window.perf_res_fuel_or_eff)

    window.perf_res_psi = QLabel("-")
    window.perf_res_phi = QLabel("-")
    window.perf_res_Re = QLabel("-")
    window.perf_res_Ma = QLabel("-")
    window.perf_res_similarity = QLabel("")
    window.perf_res_similarity.setWordWrap(True)
    for lbl in [window.perf_res_psi, window.perf_res_phi, window.perf_res_Re, window.perf_res_Ma]:
        lbl.setProperty("resultLabel", "true")

    result_layout.addRow("Head Katsayisi (ψ):", window.perf_res_psi)
    result_layout.addRow("Debi Katsayisi (φ):", window.perf_res_phi)
    result_layout.addRow("Reynolds (Re):", window.perf_res_Re)
    result_layout.addRow("Mach (Ma):", window.perf_res_Ma)
    result_layout.addRow(window.perf_res_similarity)

    result_panel.setLayout(result_layout)
    layout.addWidget(result_panel, stretch=out_stretch)
