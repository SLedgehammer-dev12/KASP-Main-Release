"""Builders for the left side of the design tab in the KASP main window."""

from __future__ import annotations
from PyQt5.QtCore import QObject, QEvent


class HoverEventFilter(QObject):
    """Event filter to display contextual help text in the HelpGuidancePanel when hovering over widgets."""
    def __init__(self, help_label, title, desc, parent=None):
        super().__init__(parent)
        self.help_label = help_label
        self.title = title
        self.desc = desc
        
    def eventFilter(self, obj, event):
        if event.type() == QEvent.Enter:
            self.help_label.setText(f"💡 <b>{self.title}:</b> {self.desc}")
        elif event.type() == QEvent.Leave:
            self.help_label.setText("💡 <b>KASP Rehberi:</b> Detaylı mühendislik açıklamaları için fare imlecini parametrelerin üzerine getirin veya bir seçim yapın.")
        return super().eventFilter(obj, event)


def get_pressure_unit_options():
    return ["bar(a)", "bar(g)", "psia", "psig", "kPa", "MPa", "Pa"]


def get_temperature_unit_options():
    return ["°C", "°F", "K"]


def get_design_flow_units():
    return ["kg/h", "kg/s", "Sm³/h", "Nm³/h", "MMSCFD", "MMSCMD"]


def get_design_method_options():
    return [
        "Metot 5: Huntington-RK45 Diferansiyel",
        "Metot 4: Doğrudan H-S",
        "Metot 6: Schultz 3-Üslü Gerçek Gaz",
        "Metot 2: Uç Nokta",
        "Metot 3: Artımlı Basınç",
        "Metot 1: Ortalama Özellikler",
    ]


def get_solver_method_options():
    return [
        "Analitik Jakobiyen NR (AJ-NR - Hızlı)",
        "Sonlu Farklar NR (FD-NR - Standart)",
        "Brent Hibrit Yöntemi (Brent - Kararlı)",
        "Otomatik Karşılaştırmalı Benchmark (Auto)",
    ]


def get_eos_display_items(coolprop_loaded, thermo_loaded):
    items = []
    if coolprop_loaded:
        items.append("🎯 Yüksek Doğruluk (CoolProp)")
    
    items.append("🌊 SINTEF thermopack (Kübik)")
    
    # NeqSim kontrolü
    neqsim_available = False
    try:
        from kasp.core.properties import ThermodynamicSolver
        solver = ThermodynamicSolver()
        neqsim_available = solver._neqsim_available()
    except Exception:
        pass

    if neqsim_available:
        items.append("🇳🇴 Equinor NeqSim (SRK-CPA)")
    else:
        items.append("🇳🇴 NeqSim (Java/JVM Gerekli)")

    if thermo_loaded:
        items.extend(["📊 Peng-Robinson (thermo)", "📈 SRK (thermo)"])
        
    items.append("🇧🇷 Petrobras ccp (ASME)")
    
    dwsim_available = False
    try:
        import clr
        dwsim_available = True
    except (ImportError, RuntimeError):
        pass
        
    if dwsim_available:
        items.append("🇩🇪 DWSIM Thermodynamics (PR)")
    else:
        items.append("🇩🇪 DWSIM (.NET / pythonnet Eksik)")
        
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


def update_process_live_metrics(window):
    """Calculate and display live PR (Pressure Ratio) and Delta-P from current inputs."""
    try:
        if not hasattr(window, "live_metrics_badge") or window.live_metrics_badge is None:
            return
        p_in_text = (window.p_in_edit.text() if hasattr(window, "p_in_edit") and window.p_in_edit else "").replace(",", ".").strip()
        p_out_text = (window.p_out_edit.text() if hasattr(window, "p_out_edit") and window.p_out_edit else "").replace(",", ".").strip()
        if not p_in_text or not p_out_text:
            window.live_metrics_badge.setText("⚡ <b>Basınç Oranı (PR):</b> —  |  <b>ΔP:</b> —")
            return
        p_in_val = float(p_in_text)
        p_out_val = float(p_out_text)

        p_in_u = window.p_in_unit_combo.currentText() if hasattr(window, "p_in_unit_combo") and window.p_in_unit_combo else "bar(g)"
        p_out_u = window.p_out_unit_combo.currentText() if hasattr(window, "p_out_unit_combo") and window.p_out_unit_combo else "bar(a)"

        from kasp.core.units import UnitSystem
        p_in_bara = UnitSystem.convert_pressure(p_in_val, p_in_u, "bar(a)")
        p_out_bara = UnitSystem.convert_pressure(p_out_val, p_out_u, "bar(a)")

        if p_in_bara > 0 and p_out_bara > 0:
            pr = p_out_bara / p_in_bara
            dp = p_out_bara - p_in_bara
            window.live_metrics_badge.setText(
                f"⚡ <b>Basınç Oranı (PR):</b> {pr:.2f}  |  <b>ΔP:</b> {dp:+.2f} bar"
            )
        else:
            window.live_metrics_badge.setText("⚡ <b>Basınç Oranı (PR):</b> —  |  <b>ΔP:</b> —")
    except Exception:
        pass


def build_presets_bar(window, left_layout):
    """Compact quick-preset chips for common engineering processes."""
    from PyQt5.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton
    from kasp.ui.responsive import scaled_px, scaled_font_pt
    from PyQt5.QtGui import QFont

    presets_frame = QFrame()
    presets_frame.setObjectName("presets_bar")
    presets_layout = QHBoxLayout(presets_frame)
    presets_layout.setContentsMargins(scaled_px(6), scaled_px(4), scaled_px(6), scaled_px(4))
    presets_layout.setSpacing(scaled_px(6))

    title_label = QLabel("⚡ Şablonlar:")
    title_font = QFont()
    title_font.setPointSize(scaled_font_pt(9))
    title_font.setBold(True)
    title_label.setFont(title_font)
    presets_layout.addWidget(title_label)

    presets = [
        ("⚡ Doğal Gaz", "Doğal Gaz (50→75 bar)", {
            "p_in": "49.65", "p_in_u": "bar(g)",
            "t_in": "19.0", "t_in_u": "°C",
            "p_out": "75.0", "p_out_u": "bar(a)",
            "flow": "1985000", "flow_u": "Sm³/h",
            "gas": "Özel Karışım",
        }),
        ("❄️ LNG", "LNG Besleme (30→80 bar)", {
            "p_in": "30.0", "p_in_u": "bar(g)",
            "t_in": "-20.0", "t_in_u": "°C",
            "p_out": "80.0", "p_out_u": "bar(a)",
            "flow": "1200000", "flow_u": "Sm³/h",
            "gas": "Methane (CH₄)",
        }),
        ("🌿 CO₂", "CO₂ Enjeksiyonu (15→65 bar)", {
            "p_in": "15.0", "p_in_u": "bar(g)",
            "t_in": "30.0", "t_in_u": "°C",
            "p_out": "65.0", "p_out_u": "bar(a)",
            "flow": "500000", "flow_u": "Sm³/h",
            "gas": "Carbon Dioxide (CO₂)",
        }),
        ("⚡ H₂", "H₂ Karışımı (20→50 bar)", {
            "p_in": "20.0", "p_in_u": "bar(g)",
            "t_in": "20.0", "t_in_u": "°C",
            "p_out": "50.0", "p_out_u": "bar(a)",
            "flow": "800000", "flow_u": "Sm³/h",
            "gas": "Hydrogen (H₂)",
        }),
    ]

    for chip_text, full_desc, data in presets:
        btn = QPushButton(chip_text)
        btn.setProperty("class", "preset_btn")
        btn.setToolTip(f"{full_desc} için proses parametrelerini ve gazı anında doldurur")

        def _apply_preset(checked=False, d=data):
            if hasattr(window, "p_in_edit") and window.p_in_edit:
                window.p_in_edit.setText(d["p_in"])
            if hasattr(window, "p_in_unit_combo") and window.p_in_unit_combo:
                window.p_in_unit_combo.setCurrentText(d["p_in_u"])
            if hasattr(window, "t_in_edit") and window.t_in_edit:
                window.t_in_edit.setText(d["t_in"])
            if hasattr(window, "t_in_unit_combo") and window.t_in_unit_combo:
                window.t_in_unit_combo.setCurrentText(d["t_in_u"])
            if hasattr(window, "p_out_edit") and window.p_out_edit:
                window.p_out_edit.setText(d["p_out"])
            if hasattr(window, "p_out_unit_combo") and window.p_out_unit_combo:
                window.p_out_unit_combo.setCurrentText(d["p_out_u"])
            if hasattr(window, "flow_edit") and window.flow_edit:
                window.flow_edit.setText(d["flow"])
            if hasattr(window, "flow_unit_combo") and window.flow_unit_combo:
                window.flow_unit_combo.setCurrentText(d["flow_u"])
            if hasattr(window, "gas_combo") and window.gas_combo:
                window.gas_combo.setCurrentText(d["gas"])
            update_process_live_metrics(window)

        btn.clicked.connect(_apply_preset)
        presets_layout.addWidget(btn)

    presets_layout.addStretch()
    left_layout.addWidget(presets_frame)


def build_project_group(window, left_layout):
    from PyQt5.QtWidgets import QFormLayout, QGroupBox, QLineEdit, QPushButton, QTextEdit, QVBoxLayout, QWidget
    from kasp.ui.responsive import scaled_px

    project_group = QGroupBox("📋 Proje Bilgileri")
    project_main_layout = QVBoxLayout(project_group)
    project_main_layout.setContentsMargins(8, 6, 8, 6)
    project_main_layout.setSpacing(scaled_px(4))

    toggle_btn = QPushButton("▶ Proje Notlarını Göster / Düzenle")
    toggle_btn.setProperty("class", "collapse_toggle_btn")
    project_main_layout.addWidget(toggle_btn)

    content_widget = QWidget()
    project_layout = QFormLayout(content_widget)
    project_layout.setContentsMargins(0, 4, 0, 0)

    window.project_name_edit = QLineEdit()
    window.project_name_edit.setPlaceholderText("Proje adını girin...")
    window.project_name_edit.setText("Yeni Kompresör Projesi")

    window.project_notes_edit = QTextEdit()
    window.project_notes_edit.setMaximumHeight(scaled_px(70))
    window.project_notes_edit.setPlaceholderText("Proje notları...")

    project_layout.addRow("Proje Adı *:", window.project_name_edit)
    project_layout.addRow("Notlar:", window.project_notes_edit)

    content_widget.setVisible(False)
    project_main_layout.addWidget(content_widget)
    window.project_content_widget = content_widget
    window.toggle_project_notes_btn = toggle_btn

    def _toggle():
        is_hidden = content_widget.isHidden()
        content_widget.setVisible(is_hidden)
        toggle_btn.setText("▼ Proje Notlarını Gizle" if is_hidden else "▶ Proje Notlarını Göster / Düzenle")

    toggle_btn.clicked.connect(_toggle)
    window._toggle_project_group = _toggle

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
    from PyQt5.QtGui import QDoubleValidator, QFont
    from PyQt5.QtWidgets import (
        QComboBox, QDoubleSpinBox, QGridLayout, QGroupBox, QHBoxLayout,
        QLabel, QLineEdit, QSizePolicy, QSpinBox, QVBoxLayout, QWidget,
    )
    from kasp.ui.responsive import scaled_font_pt, scaled_px

    process_group = QGroupBox("⚙️ Proses Koşulları")
    process_layout = QGridLayout()
    process_layout.setSpacing(scaled_px(6))
    process_layout.setColumnStretch(0, 1)
    process_layout.setColumnStretch(1, 1)

    label_font = QFont()
    label_font.setPointSize(scaled_font_pt(10))
    label_font.setBold(True)

    def _col(lbl_text, edit_w, combo_w):
        v = QVBoxLayout()
        v.setSpacing(scaled_px(2))
        lbl = QLabel(lbl_text)
        lbl.setFont(label_font)
        v.addWidget(lbl)
        h = QHBoxLayout()
        h.setSpacing(scaled_px(4))
        edit_w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        combo_w.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        combo_w.setFixedWidth(scaled_px(75))
        combo_w.setProperty("class", "unit_combo")
        h.addWidget(edit_w)
        h.addWidget(combo_w)
        v.addLayout(h)
        return v

    # 1. P_in & P_out
    window.p_in_edit = line_edit_cls(validation_func=validate_pressure)
    window.p_in_edit.setText("49.65")
    if validation_manager:
        validation_manager.register_input("inlet_pressure", window.p_in_edit)
    window.p_in_unit_combo = QComboBox()
    window.p_in_unit_combo.addItems(get_pressure_unit_options())
    window.p_in_unit_combo.setCurrentText("bar(g)")

    window.p_out_edit = line_edit_cls(validation_func=validate_pressure)
    window.p_out_edit.setText("75")
    if validation_manager:
        validation_manager.register_input("outlet_pressure", window.p_out_edit)
    window.p_out_unit_combo = QComboBox()
    window.p_out_unit_combo.addItems(get_pressure_unit_options())
    window.p_out_unit_combo.setCurrentText("bar(a)")

    process_layout.addLayout(_col("Giriş Basıncı *:", window.p_in_edit, window.p_in_unit_combo), 0, 0)
    process_layout.addLayout(_col("Çıkış Basıncı *:", window.p_out_edit, window.p_out_unit_combo), 0, 1)

    # 2. T_in & Flow
    window.t_in_edit = line_edit_cls(validation_func=validate_temperature)
    window.t_in_edit.setText("19")
    if validation_manager:
        validation_manager.register_input("inlet_temperature", window.t_in_edit)
    window.t_in_unit_combo = QComboBox()
    window.t_in_unit_combo.addItems(get_temperature_unit_options())
    window.t_in_unit_combo.setCurrentText("°C")

    window.flow_edit = line_edit_cls(validation_func=validate_flow)
    window.flow_edit.setText("1985000")
    if validation_manager:
        validation_manager.register_input("flow_rate", window.flow_edit)
    window.flow_unit_combo = QComboBox()
    window.flow_unit_combo.addItems(get_design_flow_units())
    window.flow_unit_combo.setCurrentText("Sm³/h")

    process_layout.addLayout(_col("Giriş Sıcaklığı *:", window.t_in_edit, window.t_in_unit_combo), 1, 0)
    process_layout.addLayout(_col("Gaz Debisi *:", window.flow_edit, window.flow_unit_combo), 1, 1)

    # 3. Live Metrics Badge (PR & ΔP)
    window.live_metrics_badge = QLabel("⚡ Basınç Oranı (PR): 1.48  |  ΔP: +24.34 bar")
    window.live_metrics_badge.setObjectName("live_metrics_badge")
    metrics_font = QFont()
    metrics_font.setPointSize(scaled_font_pt(10))
    metrics_font.setBold(True)
    window.live_metrics_badge.setFont(metrics_font)
    process_layout.addWidget(window.live_metrics_badge, 2, 0, 1, 2)

    # 4. Units & Stages
    window.num_units_spin = QSpinBox()
    window.num_units_spin.setRange(1, 20)
    window.num_units_spin.setValue(1)

    window.num_stages_spin = QSpinBox()
    window.num_stages_spin.setRange(1, 10)
    window.num_stages_spin.setValue(1)
    window.num_stages_spin.setToolTip(
        "Kompresör kademe sayısı.\n"
        "1 = Tek kademeli (intercooler yok)\n"
        "2+ = Çok kademeli (kademeler arası eşit PR dağılımı)"
    )

    u_col = QVBoxLayout()
    u_col.setSpacing(scaled_px(2))
    u_lbl = QLabel("Ünite Sayısı:")
    u_lbl.setFont(label_font)
    u_col.addWidget(u_lbl)
    u_col.addWidget(window.num_units_spin)

    s_col = QVBoxLayout()
    s_col.setSpacing(scaled_px(2))
    s_lbl = QLabel("Kademe Sayısı:")
    s_lbl.setFont(label_font)
    s_col.addWidget(s_lbl)
    s_col.addWidget(window.num_stages_spin)

    process_layout.addLayout(u_col, 3, 0)
    process_layout.addLayout(s_col, 3, 1)

    # 5. Intercooler container
    window.ic_container = QWidget()
    ic_layout = QGridLayout(window.ic_container)
    ic_layout.setContentsMargins(0, 4, 0, 0)
    ic_layout.setSpacing(scaled_px(4))

    window.ic_label = QLabel("🔄 Intercooler Ayarları")
    window.ic_label.setObjectName("ic_label")
    ic_layout.addWidget(window.ic_label, 0, 0, 1, 2)

    ic_layout.addWidget(QLabel("Basınç Kaybı (%):"), 1, 0)
    window.ic_dp_spin = QDoubleSpinBox()
    window.ic_dp_spin.setRange(0.0, 10.0)
    window.ic_dp_spin.setSingleStep(0.5)
    window.ic_dp_spin.setValue(2.0)
    window.ic_dp_spin.setDecimals(1)
    window.ic_dp_spin.setEnabled(False)
    window.ic_dp_spin.setToolTip("Intercooler'daki basınç kaybı yüzdesi (%)")
    ic_layout.addWidget(window.ic_dp_spin, 1, 1)

    ic_layout.addWidget(QLabel("Çıkış Sıcaklığı (°C):"), 2, 0)
    window.ic_temp_edit = QLineEdit("40.0")
    window.ic_temp_edit.setValidator(QDoubleValidator(0.0, 200.0, 1))
    window.ic_temp_edit.setEnabled(False)
    window.ic_temp_edit.setToolTip("Intercooler sonrası gaz sıcaklığı (°C)")
    ic_layout.addWidget(window.ic_temp_edit, 2, 1)

    window.ic_container.setVisible(False)
    process_layout.addWidget(window.ic_container, 4, 0, 1, 2)

    def _toggle_intercooler(stages):
        enabled = stages > 1
        window.ic_container.setVisible(enabled)
        window.ic_label.setEnabled(enabled)
        window.ic_dp_spin.setEnabled(enabled)
        window.ic_temp_edit.setEnabled(enabled)

    window.num_stages_spin.valueChanged.connect(_toggle_intercooler)

    # Live metrics updater hook
    def _update_metrics(*_):
        update_process_live_metrics(window)

    window.p_in_edit.textChanged.connect(_update_metrics)
    window.p_out_edit.textChanged.connect(_update_metrics)
    window.p_in_unit_combo.currentTextChanged.connect(_update_metrics)
    window.p_out_unit_combo.currentTextChanged.connect(_update_metrics)
    _update_metrics()

    process_group.setLayout(process_layout)
    left_layout.addWidget(process_group)


def build_gas_group(window, left_layout):
    from PyQt5.QtCore import Qt
    from PyQt5.QtGui import QFont
    from PyQt5.QtWidgets import (
        QComboBox, QGroupBox, QHBoxLayout, QHeaderView, QLabel,
        QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
    )
    from kasp.ui.responsive import scaled_font_pt, scaled_px

    gas_group = QGroupBox("⛽ Gaz Kompozisyonu")
    gas_layout = QVBoxLayout()
    gas_layout.setSpacing(scaled_px(6))

    gas_selection_layout = QHBoxLayout()
    gas_label = QLabel("Gaz:")
    label_font = QFont()
    label_font.setPointSize(scaled_font_pt(11))
    label_font.setBold(True)
    gas_label.setFont(label_font)
    gas_selection_layout.addWidget(gas_label)

    window.gas_combo = QComboBox()
    window.gas_combo.setObjectName("main_gas_combo")
    window.gas_combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
    window.gas_combo.setMinimumContentsLength(10)
    window.gas_combo.addItems(["Özel Karışım"] + window.COMMON_COMPONENTS_DISPLAY)
    window.gas_combo.currentTextChanged.connect(window.on_gas_selection_changed)
    gas_combo_font = QFont()
    gas_combo_font.setPointSize(scaled_font_pt(11))
    gas_combo_font.setBold(True)
    window.gas_combo.setFont(gas_combo_font)
    window.gas_combo.setMinimumHeight(scaled_px(32))
    gas_selection_layout.addWidget(window.gas_combo, 1)
    gas_layout.addLayout(gas_selection_layout)

    # Seçili Gaz Durum Rozeti (13" Mac ekranında seçilen gazı anında okunaklı kılan rozet)
    window.selected_gas_badge = QLabel("🔹 Özel Karışım (Kullanıcı Tanımlı)")
    window.selected_gas_badge.setObjectName("selected_gas_badge")
    window.selected_gas_badge.setProperty("gasType", "custom")
    window.selected_gas_badge.setWordWrap(True)
    badge_font = QFont()
    badge_font.setPointSize(scaled_font_pt(10))
    badge_font.setBold(True)
    window.selected_gas_badge.setFont(badge_font)
    gas_layout.addWidget(window.selected_gas_badge)

    # Bileşen Tablosu Aç/Kapat Butonu
    window.toggle_comp_table_btn = QPushButton("▼ Bileşen Tablosunu Gizle")
    window.toggle_comp_table_btn.setProperty("class", "collapse_toggle_btn")
    gas_layout.addWidget(window.toggle_comp_table_btn)

    # Katlanabilir Tablo Kapsayıcısı
    window.comp_table_container = QWidget()
    comp_container_layout = QVBoxLayout(window.comp_table_container)
    comp_container_layout.setContentsMargins(0, 0, 0, 0)
    comp_container_layout.setSpacing(scaled_px(4))

    window.composition_table = QTableWidget()
    window.composition_table.setColumnCount(2)
    window.composition_table.setHorizontalHeaderLabels(["Bileşen", "%"])
    window.composition_table.setRowCount(5)

    # Satır yüksekliği ve sütun oranları (Bileşen sütunu esner, % sütunu sabit kalır)
    window.composition_table.verticalHeader().setDefaultSectionSize(scaled_px(36))
    window.composition_table.verticalHeader().setVisible(True)
    window.composition_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
    window.composition_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)
    window.composition_table.setColumnWidth(1, scaled_px(85))

    table_font = QFont()
    table_font.setPointSize(scaled_font_pt(11))
    window.composition_table.setFont(table_font)
    window.composition_table.setMinimumHeight(scaled_px(230))

    cell_combo_font = QFont()
    cell_combo_font.setPointSize(scaled_font_pt(10))

    for row, (display_name, percentage) in enumerate(get_default_gas_rows()):
        combo = QComboBox()
        combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        combo.setMinimumContentsLength(8)
        combo.addItems(window.COMMON_COMPONENTS_DISPLAY)
        combo.setFont(cell_combo_font)
        if display_name in window.COMMON_COMPONENTS_DISPLAY:
            combo.setCurrentText(display_name)
        combo.setToolTip(f"Bileşen: {combo.currentText()}")
        combo.currentIndexChanged.connect(window._update_composition_total_label)
        window.composition_table.setCellWidget(row, 0, combo)

        percent_item = QTableWidgetItem(str(percentage))
        percent_item.setTextAlignment(Qt.AlignCenter)
        percent_item.setFont(table_font)
        window.composition_table.setItem(row, 1, percent_item)

    comp_container_layout.addWidget(window.composition_table)

    comp_buttons_layout = QHBoxLayout()
    window.add_component_btn = QPushButton("➕ Ekle")
    window.add_component_btn.setToolTip("Yeni bileşen satırı ekle")
    window.remove_component_btn = QPushButton("➖ Sil")
    window.remove_component_btn.setToolTip("Seçili bileşen satırını sil")
    window.normalize_btn = QPushButton("📊 Normalize")
    window.normalize_btn.setToolTip("Bileşen yüzdelerini %100'e normalize et")
    comp_buttons_layout.addWidget(window.add_component_btn)
    comp_buttons_layout.addWidget(window.remove_component_btn)
    comp_buttons_layout.addWidget(window.normalize_btn)
    comp_buttons_layout.addStretch()
    comp_container_layout.addLayout(comp_buttons_layout)

    window.comp_total_label = QLabel("Toplam: 100.00%  ✔")
    window.comp_total_label.setObjectName("comp_total_label")
    window.comp_total_label.setProperty("compTotalState", "valid")
    comp_total_font = QFont()
    comp_total_font.setPointSize(scaled_font_pt(11))
    comp_total_font.setBold(True)
    window.comp_total_label.setFont(comp_total_font)
    comp_container_layout.addWidget(window.comp_total_label)

    gas_layout.addWidget(window.comp_table_container)

    def _toggle_comp():
        is_hidden = window.comp_table_container.isHidden()
        window.comp_table_container.setVisible(is_hidden)
        window.toggle_comp_table_btn.setText("▼ Bileşen Tablosunu Gizle" if is_hidden else "▶ Bileşen Tablosunu Göster")

    window.toggle_comp_table_btn.clicked.connect(_toggle_comp)
    window._toggle_comp_table = _toggle_comp

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
    from kasp.ui.responsive import scaled_px
    from PyQt5.QtWidgets import (
        QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QGridLayout,
        QGroupBox, QHBoxLayout, QLabel, QLineEdit, QSlider, QSpinBox, QWidget
    )

    # 1. Termodinamik Durum Modeli Grubu
    thermo_group = QGroupBox("🧪 Termodinamik Durum Modeli (State Model)")
    thermo_layout = QFormLayout()

    window.eos_method_combo = QComboBox()
    window.eos_method_combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
    window.eos_method_combo.setMinimumContentsLength(10)
    window.eos_method_combo.addItems(get_eos_display_items(coolprop_loaded, thermo_loaded))
    if window.eos_method_combo.count():
        window.eos_method_combo.setCurrentIndex(0)

    # NeqSim ve DWSIM devre dışı bırakma kontrolü
    for index in range(window.eos_method_combo.count()):
        text = window.eos_method_combo.itemText(index)
        if "DWSIM" in text and ("Eksik" in text or "Yok" in text):
            from PyQt5.QtCore import Qt
            j = window.eos_method_combo.model().index(index, 0)
            window.eos_method_combo.model().itemFromIndex(j).setEnabled(False)
        elif "NeqSim" in text and ("Gerekli" in text or "Eksik" in text or "Yok" in text):
            from PyQt5.QtCore import Qt
            j = window.eos_method_combo.model().index(index, 0)
            window.eos_method_combo.model().itemFromIndex(j).setEnabled(False)

    window.lhv_source_combo = QComboBox()
    window.lhv_source_combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
    window.lhv_source_combo.setMinimumContentsLength(10)
    window.lhv_source_combo.addItems([
        "KASP Sabitleri (Hızlı/Varsayılan)",
        "Thermo Veritabanı (Gelişmiş)",
        "ISO 6976 Standardı (Molar / Z Düzeltmeli)",
    ])
    if not thermo_loaded:
        from PyQt5.QtCore import Qt
        window.lhv_source_combo.setItemData(1, 0, Qt.UserRole - 1)
        window.lhv_source_combo.setItemText(1, "Thermo Veritabanı (Kütüphane Yok)")

    # Dinamik Akıllı EoS Tavsiye Rozeti
    window.eos_recommendation_badge = QLabel("💡 Öneri: Kuru doğal gaz için SINTEF thermopack / CoolProp önerilir.")
    window.eos_recommendation_badge.setWordWrap(True)
    window.eos_recommendation_badge.setStyleSheet(
        "background-color: rgba(59, 130, 246, 0.12); "
        "color: #3b82f6; "
        "border: 1px solid rgba(59, 130, 246, 0.3); "
        "border-radius: 5px; "
        "padding: 4px 8px; "
        "font-size: 11px; "
        "font-weight: 500; "
        "margin-top: 2px;"
    )

    window.solver_method_combo = QComboBox()
    window.solver_method_combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
    window.solver_method_combo.setMinimumContentsLength(10)
    window.solver_method_combo.addItems(get_solver_method_options())
    window.solver_method_combo.setCurrentIndex(0)

    thermo_layout.addRow("EoS Durum Denklemi:", window.eos_method_combo)
    thermo_layout.addRow("", window.eos_recommendation_badge)
    thermo_layout.addRow("Kök Çözücü Algoritması:", window.solver_method_combo)
    thermo_layout.addRow("LHV/HHV Kaynağı:", window.lhv_source_combo)
    thermo_group.setLayout(thermo_layout)
    left_layout.addWidget(thermo_group)

    # 2. Sıkıştırma Yolu Yöntemi Grubu
    sizing_group = QGroupBox("🧮 Sıkıştırma Yolu Entegratörü (Sizing)")
    sizing_layout = QFormLayout()

    window.method_combo = QComboBox()
    window.method_combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
    window.method_combo.setMinimumContentsLength(10)
    window.method_combo.addItems(get_design_method_options())

    from kasp.ui.gas_composition_workflow import get_smart_method_recommendation
    default_comp = {window.DISPLAY_TO_COOLPROP_KEY.get(d, d): p for d, p in get_default_gas_rows()}
    initial_rec = get_smart_method_recommendation(default_comp)
    window.method_recommendation_badge = QLabel(initial_rec)
    window.method_recommendation_badge.setWordWrap(True)
    window.method_recommendation_badge.setStyleSheet(
        "color: #1e3a8a; "
        "background-color: #eff6ff; "
        "border: 1px solid #bfdbfe; "
        "border-radius: 4px; "
        "padding: 4px 8px; "
        "font-size: 11px; "
        "font-weight: 500; "
        "margin-top: 2px;"
    )

    sizing_layout.addRow("Sıkıştırma Metodu:", window.method_combo)
    sizing_layout.addRow("", window.method_recommendation_badge)

    poly_layout = QHBoxLayout()
    window.poly_eff_edit = QLineEdit("90.0")
    window.poly_eff_edit.setValidator(QDoubleValidator(50.0, 95.0, 1))
    window.poly_eff_edit.setMaximumWidth(scaled_px(60))
    window.poly_eff_slider = QSlider(Qt.Horizontal)
    window.poly_eff_slider.setRange(500, 950)
    window.poly_eff_slider.setValue(900)
    poly_layout.addWidget(window.poly_eff_edit)
    poly_layout.addWidget(QLabel("%"))
    poly_layout.addWidget(window.poly_eff_slider)

    therm_layout = QHBoxLayout()
    window.therm_eff_edit = QLineEdit("35.0")
    window.therm_eff_edit.setValidator(QDoubleValidator(20.0, 50.0, 1))
    window.therm_eff_edit.setMaximumWidth(scaled_px(60))
    window.therm_eff_slider = QSlider(Qt.Horizontal)
    window.therm_eff_slider.setRange(200, 500)
    window.therm_eff_slider.setValue(350)
    therm_layout.addWidget(window.therm_eff_edit)
    therm_layout.addWidget(QLabel("%"))
    therm_layout.addWidget(window.therm_eff_slider)

    mech_layout = QHBoxLayout()
    window.mech_eff_edit = QLineEdit("98.0")
    window.mech_eff_edit.setValidator(QDoubleValidator(80.0, 99.0, 1))
    window.mech_eff_edit.setMaximumWidth(scaled_px(60))
    window.mech_eff_slider = QSlider(Qt.Horizontal)
    window.mech_eff_slider.setRange(800, 990)
    window.mech_eff_slider.setValue(980)
    mech_layout.addWidget(window.mech_eff_edit)
    mech_layout.addWidget(QLabel("%"))
    mech_layout.addWidget(window.mech_eff_slider)

    sizing_layout.addRow("Politropik Verim (%):", poly_layout)
    sizing_layout.addRow("Isıl Verim (%):", therm_layout)
    sizing_layout.addRow("Mekanik Verim (%):", mech_layout)

    sizing_layout.addRow("", QLabel(""))
    consistency_separator = QLabel("🔄 Tutarlılık Modu (Self-Consistent)")
    consistency_separator.setObjectName("consistency_separator")
    sizing_layout.addRow(consistency_separator)

    window.consistency_check = QCheckBox("Tutarlılık İterasyonu Kullan")
    window.consistency_check.setToolTip(
        "Girdi politropik verim ile hesaplanan verim eşitlenene kadar iterasyon yapar.\n\n"
        "KAPALI (Hızlı): Tek geçiş, hızlı hesaplama\n"
        "AÇIK (Tutarlı): İteratif, yavaş ama termodinamik olarak tutarlı"
    )
    sizing_layout.addRow(window.consistency_check)

    iter_container = QWidget()
    iter_layout = QGridLayout(iter_container)
    iter_layout.setContentsMargins(0, 2, 0, 2)
    iter_layout.setSpacing(scaled_px(4))

    iter_layout.addWidget(QLabel("Maks. İterasyon:"), 0, 0)
    window.max_consistency_iter = QSpinBox()
    window.max_consistency_iter.setRange(5, 50)
    window.max_consistency_iter.setValue(20)
    window.max_consistency_iter.setEnabled(False)
    window.max_consistency_iter.setToolTip("İzin verilen maksimum iterasyon sayısı (5-50)")
    iter_layout.addWidget(window.max_consistency_iter, 0, 1)

    iter_layout.addWidget(QLabel("Tolerans (%):"), 0, 2)
    window.consistency_tolerance = QDoubleSpinBox()
    window.consistency_tolerance.setRange(0.01, 1.0)
    window.consistency_tolerance.setSingleStep(0.01)
    window.consistency_tolerance.setValue(0.1)
    window.consistency_tolerance.setDecimals(2)
    window.consistency_tolerance.setEnabled(False)
    window.consistency_tolerance.setToolTip("Yakınsama toleransı: |η_calc - η_used| < tol")
    iter_layout.addWidget(window.consistency_tolerance, 0, 3)

    sizing_layout.addRow(iter_container)

    window.consistency_check.toggled.connect(
        lambda checked: [
            window.max_consistency_iter.setEnabled(checked),
            window.consistency_tolerance.setEnabled(checked),
        ]
    )

    sizing_group.setLayout(sizing_layout)
    left_layout.addWidget(sizing_group)


def build_execution_group(window, left_layout):
    from PyQt5.QtWidgets import QFrame, QGroupBox, QHBoxLayout, QLabel, QPushButton, QProgressBar, QVBoxLayout
    from kasp.ui.responsive import scaled_px

    # Help Guidance Panel (centralized QSS styling, zero inline CSS)
    window.help_panel = QFrame()
    window.help_panel.setObjectName("HelpGuidancePanel")
    help_panel_layout = QVBoxLayout()
    help_panel_layout.setContentsMargins(10, 10, 10, 10)
    window.help_label = QLabel("💡 <b>KASP Rehberi:</b> Detaylı mühendislik açıklamaları için fare imlecini parametrelerin üzerine getirin veya bir seçim yapın.")
    window.help_label.setObjectName("help_guidance_text")
    window.help_label.setWordWrap(True)
    help_panel_layout.addWidget(window.help_label)
    window.help_panel.setLayout(help_panel_layout)
    left_layout.addWidget(window.help_panel)

    button_layout = QHBoxLayout()
    window.calculate_btn = QPushButton("🚀 Hesaplama Başlat")
    window.calculate_btn.setObjectName("calculate_btn")
    window.calculate_btn.setMinimumHeight(scaled_px(36))

    window.stop_btn = QPushButton("⏹️ Durdur")
    window.stop_btn.setObjectName("stop_btn")
    window.stop_btn.setEnabled(False)
    window.stop_btn.setMinimumHeight(scaled_px(36))

    button_layout.addWidget(window.calculate_btn, 3)
    button_layout.addWidget(window.stop_btn, 1)

    window.progress_bar = QProgressBar()
    window.progress_bar.setVisible(False)

    window.progress_status_label = QLabel("Ready")
    window.progress_status_label.setVisible(False)
    window.progress_status_label.setObjectName("progress_status_label")

    window.progress_time_label = QLabel("")
    window.progress_time_label.setVisible(False)
    window.progress_time_label.setObjectName("progress_time_label")

    if hasattr(window, "sticky_action_layout") and window.sticky_action_layout is not None:
        window.sticky_action_layout.addLayout(button_layout)
        window.sticky_action_layout.addWidget(window.progress_bar)

        status_row = QHBoxLayout()
        status_row.addWidget(window.progress_status_label)
        status_row.addStretch()
        status_row.addWidget(window.progress_time_label)
        window.sticky_action_layout.addLayout(status_row)
    else:
        left_layout.addLayout(button_layout)
        progress_group = QGroupBox("📊 İlerleme")
        progress_layout = QVBoxLayout()
        progress_layout.addWidget(window.progress_bar)
        progress_layout.addWidget(window.progress_status_label)
        progress_layout.addWidget(window.progress_time_label)
        progress_group.setLayout(progress_layout)
        left_layout.addWidget(progress_group)

    left_layout.addStretch()


def wire_help_guidance(window):
    """Set rich HTML tooltips and hover filters for all key process and calculation inputs."""
    help_texts = {
        "p_in_edit": {
            "title": "Giriş Basıncı",
            "desc": "Kompresör giriş hattındaki mutlak veya efektif gaz basıncı."
        },
        "t_in_edit": {
            "title": "Giriş Sıcaklığı",
            "desc": "Kompresör giriş hattındaki gaz sıcaklığı."
        },
        "p_out_edit": {
            "title": "Çıkış Basıncı",
            "desc": "Kompresör çıkış hattındaki hedef mutlak veya efektif gaz basıncı."
        },
        "flow_edit": {
            "title": "Gaz Debisi",
            "desc": "Kompresörden geçen kütlesel veya hacimsel gaz akış miktarı."
        },
        "num_stages_spin": {
            "title": "Kompresör Kademe Sayısı",
            "desc": "Kademe sayısı arttıkça kademeler arası soğutma (Intercooler) etkinleştirilir, bu da sıkıştırma işini azaltır ve genel verimliliği artırır."
        },
        "gas_combo": {
            "title": "Gaz Kompozisyonu",
            "desc": "Standart doğal gaz karışımlarını seçebilir veya alt tablodan özel bileşen yüzdeleri girerek kendi gaz karışımınızı tasarlayabilirsiniz."
        },
        "eos_method_combo": {
            "title": "EoS (Hal Denklemi)",
            "desc": "<b>CoolProp (GERG-2008):</b> Saf akışkanlar ve az bileşenli kuru gazlar için referans model.<br><b>🇳🇴 Equinor NeqSim (SRK-CPA):</b> C1–C6+ zengin gaz, polar bileşenler (su, glikol, metanol) ve asit gazlarında (H₂S, CO₂ > %5) üstün faz dengesi kararlılığı.<br><b>🌊 SINTEF thermopack:</b> Zengin hidrokarbon karışımlarında ultra hızlı (~4 ms) ve faz sınırlarında son derece kararlı kübik EoS.<br><b>🇧🇷 Petrobras ccp:</b> ASME PTC 10 ve API 617 standartlarında test edilmiş resmi motor.<br><b>📊 Peng-Robinson / SRK:</b> Petrol ve gaz endüstrisi standardı kararlı kübik modeller.<br><b>🇩🇪 DWSIM Thermodynamics:</b> Polar karışımlarda ve buhar tablolarında .NET tabanlı alternatif."
        },
        "lhv_source_combo": {
            "title": "Isıl Değer Kaynağı",
            "desc": "<b>KASP Sabitleri:</b> Standart ISO 6976 tablosu kullanır.<br><b>Thermo Veritabanı:</b> Karışımın gerçek gaz düzeltmeli kimyasal potansiyel ve ısıl kapasite verilerini dinamik hesaplar."
        },
        "solver_method_combo": {
            "title": "Termodinamik Kök Çözücü",
            "desc": "<b>AJ-NR (Analitik Jakobiyen Newton-Raphson):</b> (S(P,T)-S_in=0) için analitik türev (Cp/T) kullanarak süper hızlı ve kararlı yakınsar.<br><b>FD-NR (Sonlu Farklar Newton-Raphson):</b> Standart sonlu farklar yaklaşımıyla çalışır.<br><b>Brent Hibrit:</b> Bölme ve sekant yöntemlerini birleştiren, faz değişim sınırlarında en güvenli, asla ıraksamayan çözücüdür.<br><b>Auto Benchmark:</b> Hız ve kararlılığı optimize etmek için otomatik yöntem seçer."
        },
        "method_combo": {
            "title": "Sıkıştırma Yolu Yöntemi",
            "desc": "<b>Ortalama Özellikler (Metot 1):</b> API 617 standardında giriş/çıkış ortalamasını alan hızlı yaklaşım.<br><b>Uç Nokta (Metot 2):</b> Çıkış özelliklerini referans alan ASME PTC 10 Schultz entegrasyonu.<br><b>Artımlı Basınç (Metot 3):</b> Basınç aralığını dilimlere bölüp adım adım entegre eden yol.<br><b>Doğrudan H-S (Metot 4):</b> Gerçek entalpi ve entropi değişimlerini entegre eden kararlı fiziksel yöntem.<br><b>Huntington-RK45 (Metot 5):</b> Termodinamik 1. Yasa diferansiyel denklemini (dT/dP) 4. derece Runge-Kutta ile sürekli çözen analitik altın standart.<br><b>Schultz 3-Üslü (Metot 6):</b> X (izobarik) ve Y (izotermal) sıkıştırılabilirlik türevleriyle 3 ayrı gerçek gaz üssü (nv, mT, np) hesaplayan model."
        },
        "consistency_check": {
            "title": "Tutarlılık İterasyonu",
            "desc": "Hesaplanan politropik verim ile kullanılan verim eşitlenene kadar iterasyon yapar. Termodinamik kararlılık için şiddetle tavsiye edilir."
        }
    }
    
    # Store references to prevent garbage collection
    window._hover_filters = []
    
    for attr, info in help_texts.items():
        widget = getattr(window, attr, None)
        if widget:
            # Add rich HTML Tooltip
            widget.setToolTip(f"<b>{info['title']}</b><br>{info['desc']}")
            
            # Install hover filter
            filt = HoverEventFilter(window.help_label, info['title'], info['desc'], widget)
            widget.installEventFilter(filt)
            window._hover_filters.append(filt)


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
    build_presets_bar(window, left_layout)
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
    wire_help_guidance(window)
