"""Builders for the left side of the design tab in the KASP main window."""

from __future__ import annotations


def get_pressure_unit_options():
    return ["bar(a)", "bar(g)", "psia", "psig", "kPa", "MPa", "Pa"]


def get_temperature_unit_options():
    return ["°C", "°F", "K"]


def get_design_flow_units():
    return ["kg/h", "kg/s", "Sm³/h", "Nm³/h", "MMSCFD", "MMSCMD"]


def get_design_method_options():
    return [
        "Metot 1: Ortalama Özellikler",
        "Metot 2: Uç Nokta",
        "Metot 3: Artımlı Basınç",
        "Metot 4: Doğrudan H-S",
    ]


def get_eos_display_items(coolprop_loaded, thermo_loaded):
    items = []
    if coolprop_loaded:
        items.append("🎯 Yüksek Doğruluk (CoolProp)")
    if thermo_loaded:
        items.extend(["📊 Peng-Robinson (thermo)", "📈 SRK (thermo)"])
    if not items:
        items.append("❌ Kütüphane Yok")
    return items


def get_default_gas_rows():
    return [
        ("Methane (CH₄)", 98.00),
        ("Ethane (C₂H₆)", 1.50),
        ("Propane (C₃H₈)", 0.00),
        ("n-Butane (n-C₄H₁₀)", 0.00),
        ("Nitrogen (N₂)", 0.50),
    ]


def build_project_group(window, left_layout):
    from PyQt5.QtWidgets import QFormLayout, QGroupBox, QLineEdit, QTextEdit

    project_group = QGroupBox("📋 Proje Bilgileri")
    project_layout = QFormLayout()

    window.project_name_edit = QLineEdit()
    window.project_name_edit.setPlaceholderText("Proje adını girin...")
    window.project_name_edit.setText("Yeni Kompresör Projesi")

    window.project_notes_edit = QTextEdit()
    window.project_notes_edit.setMaximumHeight(80)
    window.project_notes_edit.setPlaceholderText("Proje notları...")

    project_layout.addRow("Proje Adı *:", window.project_name_edit)
    project_layout.addRow("Notlar:", window.project_notes_edit)
    project_group.setLayout(project_layout)
    left_layout.addWidget(project_group)


def build_process_group(
    window,
    left_layout,
    *,
    line_edit_cls,
    validation_manager,
    validate_pressure,
    validate_temperature,
    validate_flow,
):
    from PyQt5.QtGui import QDoubleValidator
    from PyQt5.QtWidgets import QComboBox, QDoubleSpinBox, QGridLayout, QGroupBox, QLabel, QLineEdit, QSpinBox

    process_group = QGroupBox("⚙️ Proses Koşulları")
    process_layout = QGridLayout()

    process_layout.addWidget(QLabel("Giriş Basıncı *:"), 0, 0)
    window.p_in_edit = line_edit_cls(validation_func=validate_pressure)
    window.p_in_edit.setText("49.65")
    if validation_manager:
        validation_manager.register_input("inlet_pressure", window.p_in_edit)
    process_layout.addWidget(window.p_in_edit, 0, 1)

    window.p_in_unit_combo = QComboBox()
    window.p_in_unit_combo.addItems(get_pressure_unit_options())
    window.p_in_unit_combo.setCurrentText("bar(g)")
    process_layout.addWidget(window.p_in_unit_combo, 0, 2)

    process_layout.addWidget(QLabel("Giriş Sıcaklığı *:"), 1, 0)
    window.t_in_edit = line_edit_cls(validation_func=validate_temperature)
    window.t_in_edit.setText("19")
    if validation_manager:
        validation_manager.register_input("inlet_temperature", window.t_in_edit)
    process_layout.addWidget(window.t_in_edit, 1, 1)

    window.t_in_unit_combo = QComboBox()
    window.t_in_unit_combo.addItems(get_temperature_unit_options())
    window.t_in_unit_combo.setCurrentText("°C")
    process_layout.addWidget(window.t_in_unit_combo, 1, 2)

    process_layout.addWidget(QLabel("Çıkış Basıncı *:"), 2, 0)
    window.p_out_edit = line_edit_cls(validation_func=validate_pressure)
    window.p_out_edit.setText("75")
    if validation_manager:
        validation_manager.register_input("outlet_pressure", window.p_out_edit)
    process_layout.addWidget(window.p_out_edit, 2, 1)

    window.p_out_unit_combo = QComboBox()
    window.p_out_unit_combo.addItems(get_pressure_unit_options())
    window.p_out_unit_combo.setCurrentText("bar(a)")
    process_layout.addWidget(window.p_out_unit_combo, 2, 2)

    process_layout.addWidget(QLabel("Gaz Debisi *:"), 3, 0)
    window.flow_edit = line_edit_cls(validation_func=validate_flow)
    window.flow_edit.setText("1985000")
    if validation_manager:
        validation_manager.register_input("flow_rate", window.flow_edit)
    process_layout.addWidget(window.flow_edit, 3, 1)

    window.flow_unit_combo = QComboBox()
    window.flow_unit_combo.addItems(get_design_flow_units())
    window.flow_unit_combo.setCurrentText("Sm³/h")
    process_layout.addWidget(window.flow_unit_combo, 3, 2)

    process_layout.addWidget(QLabel("Ünite Sayısı:"), 4, 0)
    window.num_units_spin = QSpinBox()
    window.num_units_spin.setRange(1, 20)
    window.num_units_spin.setValue(1)
    process_layout.addWidget(window.num_units_spin, 4, 1)

    process_layout.addWidget(QLabel("Kademe Sayısı:"), 5, 0)
    window.num_stages_spin = QSpinBox()
    window.num_stages_spin.setRange(1, 10)
    window.num_stages_spin.setValue(1)
    window.num_stages_spin.setToolTip(
        "Kompresör kademe sayısı.\n"
        "1 = Tek kademeli (intercooler yok)\n"
        "2+ = Çok kademeli (kademeler arası eşit PR dağılımı)"
    )
    process_layout.addWidget(window.num_stages_spin, 5, 1)

    window.ic_label = QLabel("🔄 Intercooler")
    window.ic_label.setStyleSheet("font-weight: bold; color: #2980b9; font-size: 9pt;")
    window.ic_label.setEnabled(False)
    process_layout.addWidget(window.ic_label, 6, 0, 1, 3)

    process_layout.addWidget(QLabel("  Basınç Kaybı (%):"), 7, 0)
    window.ic_dp_spin = QDoubleSpinBox()
    window.ic_dp_spin.setRange(0.0, 10.0)
    window.ic_dp_spin.setSingleStep(0.5)
    window.ic_dp_spin.setValue(2.0)
    window.ic_dp_spin.setDecimals(1)
    window.ic_dp_spin.setEnabled(False)
    window.ic_dp_spin.setToolTip("Intercooler'daki basınç kaybı yüzdesi (%)")
    process_layout.addWidget(window.ic_dp_spin, 7, 1)

    process_layout.addWidget(QLabel("  Çıkış Sıcaklığı (°C):"), 8, 0)
    window.ic_temp_edit = QLineEdit("40.0")
    window.ic_temp_edit.setValidator(QDoubleValidator(0.0, 200.0, 1))
    window.ic_temp_edit.setEnabled(False)
    window.ic_temp_edit.setToolTip("Intercooler sonrası gaz sıcaklığı (°C)")
    process_layout.addWidget(window.ic_temp_edit, 8, 1)

    def _toggle_intercooler(stages):
        enabled = stages > 1
        window.ic_label.setEnabled(enabled)
        window.ic_dp_spin.setEnabled(enabled)
        window.ic_temp_edit.setEnabled(enabled)
        if not enabled:
            window.ic_label.setStyleSheet("font-weight: bold; color: #95a5a6; font-size: 9pt;")
        else:
            window.ic_label.setStyleSheet("font-weight: bold; color: #2980b9; font-size: 9pt;")

    window.num_stages_spin.valueChanged.connect(_toggle_intercooler)

    process_group.setLayout(process_layout)
    left_layout.addWidget(process_group)


def build_gas_group(window, left_layout):
    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import QComboBox, QGroupBox, QHBoxLayout, QLabel, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout

    gas_group = QGroupBox("⛽ Gaz Kompozisyonu")
    gas_layout = QVBoxLayout()

    gas_selection_layout = QHBoxLayout()
    gas_selection_layout.addWidget(QLabel("Gaz:"))

    window.gas_combo = QComboBox()
    window.gas_combo.addItems(["Özel Karışım"] + window.COMMON_COMPONENTS_DISPLAY)
    window.gas_combo.currentTextChanged.connect(window.on_gas_selection_changed)
    gas_selection_layout.addWidget(window.gas_combo)
    gas_selection_layout.addStretch()
    gas_layout.addLayout(gas_selection_layout)

    window.composition_table = QTableWidget()
    window.composition_table.setColumnCount(2)
    window.composition_table.setHorizontalHeaderLabels(["Bileşen", "%"])
    window.composition_table.horizontalHeader().setStretchLastSection(True)
    window.composition_table.setRowCount(5)
    window.composition_table.setMinimumHeight(220)

    for row, (display_name, percentage) in enumerate(get_default_gas_rows()):
        combo = QComboBox()
        combo.addItems(window.COMMON_COMPONENTS_DISPLAY)
        if display_name in window.COMMON_COMPONENTS_DISPLAY:
            combo.setCurrentText(display_name)
        window.composition_table.setCellWidget(row, 0, combo)

        percent_item = QTableWidgetItem(str(percentage))
        percent_item.setTextAlignment(Qt.AlignCenter)
        window.composition_table.setItem(row, 1, percent_item)

    gas_layout.addWidget(window.composition_table)

    comp_buttons_layout = QHBoxLayout()
    window.add_component_btn = QPushButton("➕ Bileşen Ekle")
    window.remove_component_btn = QPushButton("➖ Bileşen Sil")
    window.normalize_btn = QPushButton("📊 Normalize Et")
    comp_buttons_layout.addWidget(window.add_component_btn)
    comp_buttons_layout.addWidget(window.remove_component_btn)
    comp_buttons_layout.addWidget(window.normalize_btn)
    comp_buttons_layout.addStretch()
    gas_layout.addLayout(comp_buttons_layout)

    window.comp_total_label = QLabel("Toplam: 100.00%  ✔")
    window.comp_total_label.setStyleSheet(
        "font-weight: bold; color: #27ae60; padding: 2px 4px; border-radius: 4px;"
    )
    gas_layout.addWidget(window.comp_total_label)

    gas_group.setLayout(gas_layout)
    left_layout.addWidget(gas_group)


def configure_design_validation_context_hooks(window, *, validation_available):
    if not validation_available or not window.validation_manager:
        return

    window.p_in_unit_combo.currentTextChanged.connect(
        lambda unit: window.p_in_edit.set_validation_context({"unit": unit})
    )
    window.t_in_unit_combo.currentTextChanged.connect(
        lambda unit: window.t_in_edit.set_validation_context({"unit": unit})
    )
    window.p_out_unit_combo.currentTextChanged.connect(
        lambda unit: window.p_out_edit.set_validation_context({"unit": unit})
    )
    window.flow_unit_combo.currentTextChanged.connect(
        lambda unit: window.flow_edit.set_validation_context({"unit": unit})
    )

    window.p_in_edit.set_validation_context({"unit": window.p_in_unit_combo.currentText()})
    window.t_in_edit.set_validation_context({"unit": window.t_in_unit_combo.currentText()})
    window.p_out_edit.set_validation_context({"unit": window.p_out_unit_combo.currentText()})
    window.flow_edit.set_validation_context({"unit": window.flow_unit_combo.currentText()})


def build_calculation_group(window, left_layout, *, coolprop_loaded, thermo_loaded):
    from PyQt5.QtCore import Qt
    from PyQt5.QtGui import QDoubleValidator
    from PyQt5.QtWidgets import QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QSlider, QSpinBox

    calc_group = QGroupBox("🧮 Hesaplama Parametreleri")
    calc_layout = QFormLayout()

    window.eos_method_combo = QComboBox()
    window.eos_method_combo.addItems(get_eos_display_items(coolprop_loaded, thermo_loaded))
    if window.eos_method_combo.count():
        window.eos_method_combo.setCurrentIndex(0)

    window.method_combo = QComboBox()
    window.method_combo.addItems(get_design_method_options())

    poly_layout = QHBoxLayout()
    window.poly_eff_edit = QLineEdit("90.0")
    window.poly_eff_edit.setValidator(QDoubleValidator(50.0, 95.0, 1))
    window.poly_eff_edit.setMaximumWidth(60)
    window.poly_eff_slider = QSlider(Qt.Horizontal)
    window.poly_eff_slider.setRange(500, 950)
    window.poly_eff_slider.setValue(900)
    poly_layout.addWidget(window.poly_eff_edit)
    poly_layout.addWidget(QLabel("%"))
    poly_layout.addWidget(window.poly_eff_slider)

    therm_layout = QHBoxLayout()
    window.therm_eff_edit = QLineEdit("35.0")
    window.therm_eff_edit.setValidator(QDoubleValidator(20.0, 50.0, 1))
    window.therm_eff_edit.setMaximumWidth(60)
    window.therm_eff_slider = QSlider(Qt.Horizontal)
    window.therm_eff_slider.setRange(200, 500)
    window.therm_eff_slider.setValue(350)
    therm_layout.addWidget(window.therm_eff_edit)
    therm_layout.addWidget(QLabel("%"))
    therm_layout.addWidget(window.therm_eff_slider)

    mech_layout = QHBoxLayout()
    window.mech_eff_edit = QLineEdit("98.0")
    window.mech_eff_edit.setValidator(QDoubleValidator(80.0, 99.0, 1))
    window.mech_eff_edit.setMaximumWidth(60)
    window.mech_eff_slider = QSlider(Qt.Horizontal)
    window.mech_eff_slider.setRange(800, 990)
    window.mech_eff_slider.setValue(980)
    mech_layout.addWidget(window.mech_eff_edit)
    mech_layout.addWidget(QLabel("%"))
    mech_layout.addWidget(window.mech_eff_slider)

    calc_layout.addRow("EOS Metodu:", window.eos_method_combo)

    window.lhv_source_combo = QComboBox()
    window.lhv_source_combo.addItems([
        "KASP Sabitleri (Hızlı/Varsayılan)",
        "Thermo Veritabanı (Gelişmiş)",
    ])
    if not thermo_loaded:
        window.lhv_source_combo.setEnabled(False)
        window.lhv_source_combo.setItemText(1, "Thermo Veritabanı (Kütüphane Yok)")
    calc_layout.addRow("LHV/HHV Kaynağı:", window.lhv_source_combo)

    calc_layout.addRow("Hesaplama Metodu:", window.method_combo)
    calc_layout.addRow("Politropik Verim (%):", poly_layout)
    calc_layout.addRow("Isıl Verim (%):", therm_layout)
    calc_layout.addRow("Mekanik Verim (%):", mech_layout)

    calc_layout.addRow("", QLabel(""))
    consistency_separator = QLabel("🔄 Tutarlılık Modu (Self-Consistent)")
    consistency_separator.setStyleSheet("font-weight: bold; color: #2980b9;")
    calc_layout.addRow("", consistency_separator)

    window.consistency_check = QCheckBox("Tutarlılık İterasyonu Kullan")
    window.consistency_check.setToolTip(
        "Girdi politropik verim ile hesaplanan verim eşitlenene kadar iterasyon yapar.\n\n"
        "KAPALI (Hızlı): Tek geçiş, hızlı hesaplama\n"
        "AÇIK (Tutarlı): İteratif, yavaş ama termodinamik olarak tutarlı"
    )
    calc_layout.addRow("", window.consistency_check)

    iter_settings_layout = QHBoxLayout()
    iter_settings_layout.addWidget(QLabel("Maks. İterasyon:"))
    window.max_consistency_iter = QSpinBox()
    window.max_consistency_iter.setRange(5, 50)
    window.max_consistency_iter.setValue(20)
    window.max_consistency_iter.setEnabled(False)
    window.max_consistency_iter.setToolTip("İzin verilen maksimum iterasyon sayısı (5-50)")
    iter_settings_layout.addWidget(window.max_consistency_iter)

    iter_settings_layout.addWidget(QLabel("Tolerans (%):"))
    window.consistency_tolerance = QDoubleSpinBox()
    window.consistency_tolerance.setRange(0.01, 1.0)
    window.consistency_tolerance.setSingleStep(0.01)
    window.consistency_tolerance.setValue(0.1)
    window.consistency_tolerance.setDecimals(2)
    window.consistency_tolerance.setEnabled(False)
    window.consistency_tolerance.setToolTip("Yakınsama toleransı: |η_calc - η_used| < tol")
    iter_settings_layout.addWidget(window.consistency_tolerance)
    iter_settings_layout.addStretch()
    calc_layout.addRow("", iter_settings_layout)

    window.consistency_check.toggled.connect(
        lambda checked: [
            window.max_consistency_iter.setEnabled(checked),
            window.consistency_tolerance.setEnabled(checked),
        ]
    )

    calc_group.setLayout(calc_layout)
    left_layout.addWidget(calc_group)


def build_execution_group(window, left_layout):
    from PyQt5.QtWidgets import QGroupBox, QHBoxLayout, QLabel, QPushButton, QProgressBar, QVBoxLayout

    button_layout = QHBoxLayout()
    window.calculate_btn = QPushButton("🚀 Hesaplama Başlat")
    window.calculate_btn.setStyleSheet(
        """
            QPushButton {
                background-color: #27ae60;
                color: white;
                font-weight: bold;
                padding: 12px;
                border-radius: 6px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #2ecc71;
            }
            QPushButton:disabled {
                background-color: #95a5a6;
            }
        """
    )

    window.stop_btn = QPushButton("⏹️ Durdur")
    window.stop_btn.setEnabled(False)
    window.stop_btn.setStyleSheet(
        """
            QPushButton {
                background-color: #e74c3c;
                color: white;
                font-weight: bold;
                padding: 12px;
                border-radius: 6px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
            QPushButton:disabled {
                background-color: #95a5a6;
            }
        """
    )

    button_layout.addWidget(window.calculate_btn)
    button_layout.addWidget(window.stop_btn)
    left_layout.addLayout(button_layout)

    progress_group = QGroupBox("📊 İlerleme")
    progress_layout = QVBoxLayout()
    window.progress_bar = QProgressBar()
    window.progress_bar.setVisible(False)
    progress_layout.addWidget(window.progress_bar)

    window.progress_status_label = QLabel("Ready")
    window.progress_status_label.setVisible(False)
    window.progress_status_label.setStyleSheet("color: #7f8c8d; font-size: 9pt;")
    progress_layout.addWidget(window.progress_status_label)

    window.progress_time_label = QLabel("")
    window.progress_time_label.setVisible(False)
    window.progress_time_label.setStyleSheet("color: #3498db; font-size: 9pt;")
    progress_layout.addWidget(window.progress_time_label)

    progress_group.setLayout(progress_layout)
    left_layout.addWidget(progress_group)
    left_layout.addStretch()


def build_design_left_groups(
    window,
    left_layout,
    *,
    line_edit_cls,
    validation_manager,
    validate_pressure,
    validate_temperature,
    validate_flow,
    validation_available,
    coolprop_loaded,
    thermo_loaded,
):
    build_project_group(window, left_layout)
    build_process_group(
        window,
        left_layout,
        line_edit_cls=line_edit_cls,
        validation_manager=validation_manager,
        validate_pressure=validate_pressure,
        validate_temperature=validate_temperature,
        validate_flow=validate_flow,
    )
    build_gas_group(window, left_layout)
    configure_design_validation_context_hooks(
        window,
        validation_available=validation_available,
    )
    build_calculation_group(
        window,
        left_layout,
        coolprop_loaded=coolprop_loaded,
        thermo_loaded=thermo_loaded,
    )
    build_execution_group(window, left_layout)
