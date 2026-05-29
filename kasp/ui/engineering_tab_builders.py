"""Engineering Dashboard — Admin diagnoztik sekmesi."""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)
from kasp.i18n import tr


def build_engineering_dashboard(parent_widget, engine=None, last_results=None):
    """Engineering Dashboard sekmesini oluşturur. Scrollable yapıdadır."""
    
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setObjectName("eng_scroll")
    
    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setSpacing(8)

    # ── 1. Hesaplama İzleme Ağacı ──
    trace_group = QGroupBox("📋 Hesaplama İzleme (Calculation Trace)")
    trace_layout = QVBoxLayout()
    trace_tree = QTreeWidget()
    trace_tree.setHeaderLabels(["Aşama / Iterasyon", "Detay"])
    trace_tree.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
    trace_tree.setAlternatingRowColors(True)
    trace_tree.setObjectName("eng_trace_tree")
    trace_layout.addWidget(trace_tree)

    export_btn = QPushButton("📤 İzleme Verisini Dışa Aktar (CSV)")
    export_btn.setObjectName("eng_export_btn")
    trace_layout.addWidget(export_btn)
    trace_group.setLayout(trace_layout)
    layout.addWidget(trace_group)

    # ── 2. Performans Paneli ──
    perf_group = QGroupBox("⚡ Performans Metrikleri")
    perf_layout = QHBoxLayout()
    perf_layout.setSpacing(12)

    perf_labels = {}
    for key, label_text in [
        ("total_calcs", "Hesaplama"),
        ("avg_time", "Ort. Süre"),
        ("eos_calls", "EOS Çağrıları"),
        ("cache_hit_rate", "Cache Hit"),
        ("fallback_count", "Fallback"),
        ("success_rate", "Başarı"),
    ]:
        box = QVBoxLayout()
        title = QLabel(label_text)
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-weight: bold; font-size: 10px; color: gray;")
        value = QLabel("—")
        value.setAlignment(Qt.AlignCenter)
        value.setStyleSheet("font-size: 16px; font-weight: bold;")
        value.setObjectName(f"eng_perf_{key}")
        box.addWidget(title)
        box.addWidget(value)
        perf_layout.addLayout(box)
        perf_labels[key] = value

    perf_group.setLayout(perf_layout)
    layout.addWidget(perf_group)

    # ── 3. Termo Sağlık Paneli ──
    health_group = QGroupBox("🩺 Termo Sağlık (Thermo Health)")
    health_layout = QVBoxLayout()
    health_table = QTableWidget(0, 5)
    health_table.setHorizontalHeaderLabels(["Konum", "Z", "Faz", "Sağlık", "Uyarılar"])
    health_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
    health_table.setObjectName("eng_health_table")
    health_layout.addWidget(health_table)
    health_group.setLayout(health_layout)
    layout.addWidget(health_group)

    # ── 4. EOS Benchmark / Fallback ──
    fallback_group = QGroupBox("🔬 Çözücü Benchmark (Solver Benchmark)")
    fallback_layout = QVBoxLayout()
    fallback_table = QTableWidget(0, 6)
    fallback_table.setHorizontalHeaderLabels(["Kademe", "Yöntem", "T (K)", "İter", "Rezidüel", "Süre (ms)"])
    fallback_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
    fallback_table.setObjectName("eng_fallback_table")
    fallback_layout.addWidget(fallback_table)
    fallback_group.setLayout(fallback_layout)
    layout.addWidget(fallback_group)

    # ── 5. EOS Shootout (genişletilmiş) ──
    eos_group = QGroupBox("🧪 EOS Karşılaştırma (EOS Shootout)")
    eos_layout = QVBoxLayout()
    eos_table = QTableWidget(0, 10)
    eos_table.setHorizontalHeaderLabels([
        "EOS", "Durum", "Fallback\nKatmanı", "Fallback\nZinciri",
        "T_out (°C)", "Head (kJ/kg)", "Power (kW)", "η_poly", "Head Δ%", "Süre (s)"
    ])
    eos_table.setObjectName("eng_eos_shootout")
    eos_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
    eos_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
    eos_layout.addWidget(eos_table)
    eos_run_btn = QPushButton("🔄 EOS Shootout Çalıştır")
    eos_run_btn.setObjectName("eng_eos_shootout_btn")
    eos_layout.addWidget(eos_run_btn)
    eos_group.setLayout(eos_layout)
    layout.addWidget(eos_group)

    # ── 5b. EOS Ham Property Karşılaştırma ──
    prop_group = QGroupBox("🔍 Ham Property Karşılaştırması (Raw Props @ Inlet & Outlet)")
    prop_layout = QVBoxLayout()
    prop_table = QTableWidget(0, 9)
    prop_table.setHorizontalHeaderLabels([
        "EOS", "MW (g/mol)", "k (Cp/Cv)", "Z", "Cp (J/kgK)",
        "Cv (J/kgK)", "ρ (kg/m³)", "Faz", "Debi (kg/s)"
    ])
    prop_table.horizontalHeader().setSectionResizeMode(8, QHeaderView.Stretch)
    prop_table.setObjectName("eng_prop_shootout")
    prop_layout.addWidget(prop_table)
    prop_group.setLayout(prop_layout)
    layout.addWidget(prop_group)

    # ── 5c. Fallback Zincir Kaydı ──
    chain_group = QGroupBox("🔄 Fallback Zincir Kaydı (Run Bazında)")
    chain_layout = QVBoxLayout()
    chain_table = QTableWidget(0, 4)
    chain_table.setHorizontalHeaderLabels(["Katman", "Kimden → Kime", "Sebep", "Çağrı"])
    chain_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
    chain_table.setObjectName("eng_chain_table")
    chain_layout.addWidget(chain_table)
    chain_group.setLayout(chain_layout)
    layout.addWidget(chain_group)

    # ── 6. Metot Shootout ──
    method_group = QGroupBox("🧮 Metot Karşılaştırma (Method Shootout)")
    method_layout = QVBoxLayout()
    method_table = QTableWidget(0, 7)
    method_table.setHorizontalHeaderLabels(["Metot", "T_out (°C)", "Head (kJ/kg)", "Power (kW)", "η_poly", "Yakınsadı", "Süre (s)"])
    method_table.setObjectName("eng_method_shootout")
    method_layout.addWidget(method_table)
    method_run_btn = QPushButton("🔄 Method Shootout Çalıştır")
    method_run_btn.setObjectName("eng_method_shootout_btn")
    method_layout.addWidget(method_run_btn)
    method_group.setLayout(method_layout)
    layout.addWidget(method_group)

    # ScrollArea'ya container'ı ata
    scroll.setWidget(container)
    
    # Parent'a scroll ekle
    outer_layout = QVBoxLayout(parent_widget)
    outer_layout.setContentsMargins(0, 0, 0, 0)
    outer_layout.addWidget(scroll)

    # Verileri doldur
    if last_results is not None:
        _populate_trace_tree(trace_tree, last_results)
        _populate_performance(perf_labels, engine)
        _populate_health(health_table, last_results)
        _populate_fallback(fallback_table, last_results)

    return {
        "trace_tree": trace_tree,
        "perf_labels": perf_labels,
        "health_table": health_table,
        "fallback_table": fallback_table,
        "eos_table": eos_table,
        "eos_run_btn": eos_run_btn,
        "prop_table": prop_table,
        "chain_table": chain_table,
        "method_table": method_table,
        "method_run_btn": method_run_btn,
        "export_btn": export_btn,
    }


def _populate_trace_tree(tree, results):
    tree.clear()
    stages = results.get("stages", [])
    for stage_data in stages:
        stage_num = stage_data.get("stage", "?")
        stage_item = QTreeWidgetItem(tree, [f"Kademe {stage_num}", f"p_in={_fmt_bar(stage_data.get('p_in'))}, p_out={_fmt_bar(stage_data.get('p_out'))}"])
        history = stage_data.get("method_history", {})
        method = history.get("method_used", "?")
        method_item = QTreeWidgetItem(stage_item, ["Metot", method])
        conv = "✓" if history.get("converged", False) else "✗"
        reason = history.get("termination_reason", "")
        QTreeWidgetItem(stage_item, ["Yakınsama", f"{conv} {reason}"])

        # Iterasyon detayları
        temps = history.get("temperature", [])
        pressures = history.get("pressure", [])
        z_factors = history.get("z_factor", [])
        k_values = history.get("k_value", [])
        for i in range(len(temps)):
            t = temps[i] - 273.15 if isinstance(temps[i], (int, float)) and temps[i] > 100 else temps[i]
            p = pressures[i] / 1e5 if isinstance(pressures[i], (int, float)) else pressures[i]
            z = z_factors[i] if i < len(z_factors) else "—"
            k = f"{k_values[i]:.4f}" if i < len(k_values) else "—"
            QTreeWidgetItem(stage_item, [
                f"Iter {i}",
                f"T={_fmt(t)}°C, P={_fmt(p)}bar, Z={_fmt(z)}, k={k}"
            ])

        # Metot 4 özel: inner iteration detail
        iter_detail = history.get("iterations_detail", [])
        for d in iter_detail:
            QTreeWidgetItem(stage_item, [
                d.get("iter", "?"),
                f"T={_fmt(d.get('T'))}K, H={_fmt(d.get('H'))}J, dH={_fmt(d.get('dH'))}J"
            ])

        # Metot 4 özel: derived values
        if "t_isentropic" in history:
            QTreeWidgetItem(stage_item, ["T_isen", f"{_fmt(history['t_isentropic'])} K"])
            QTreeWidgetItem(stage_item, ["ΔH_isen", f"{_fmt(history.get('delta_h_isentropic_kj', 0))} kJ/kg"])
            QTreeWidgetItem(stage_item, ["σ", f"{_fmt(history.get('sigma_backcomputed', 0))}"])

        # İntegral analiz
        integral = history.get("integral_analysis", {})
        if integral:
            int_item = QTreeWidgetItem(stage_item, ["İntegral Analiz", f"k={_fmt(integral.get('k_min'))}–{_fmt(integral.get('k_max'))}, aralık=%{_fmt(integral.get('k_range_percent'))}"])

    tree.expandAll()


def _populate_performance(labels, engine):
    if engine is None:
        return
    try:
        stats = engine.performance_monitor.get_statistics()
    except Exception:
        return
    mapping = {
        "total_calcs": str(stats.get("total_calculations", "—")),
        "avg_time": f"{stats.get('avg_calculation_time', 0):.4f}s",
        "eos_calls": str(stats.get("total_property_calculations", "—")),
        "cache_hit_rate": f"{stats.get('cache_hit_rate', 0):.1f}%",
        "fallback_count": str(stats.get("error_count", "—")),
        "success_rate": f"{stats.get('success_rate', 0):.1f}%",
    }
    for key, label in labels.items():
        label.setText(mapping.get(key, "—"))


def _populate_health(table, results):
    table.setRowCount(0)
    inlet = results.get("inlet_properties", {})
    outlet = results.get("outlet_properties", {})
    for label, props in [("Giriş", inlet), ("Çıkış", outlet)]:
        if not props:
            continue
        raw = props.get("raw_props", {})
        r = table.rowCount()
        table.insertRow(r)
        table.setItem(r, 0, QTableWidgetItem(label))
        table.setItem(r, 1, QTableWidgetItem(_fmt(props.get("Z", "—"))))
        table.setItem(r, 2, QTableWidgetItem(props.get("phase", raw.get("phase", "—"))))
        health = raw.get("thermo_health", "HEALTHY")
        item = QTableWidgetItem(health)
        if health == "CRITICAL":
            item.setForeground(Qt.red)
        elif health == "WARNING":
            item.setForeground(Qt.darkYellow)
        table.setItem(r, 3, item)
        reasons = raw.get("health_reasons", [])
        table.setItem(r, 4, QTableWidgetItem("; ".join(reasons) if reasons else "—"))


def _populate_fallback(table, results):
    table.setRowCount(0)
    comparisons = results.get("fallback_comparison", [])
    if isinstance(comparisons, dict):
        comparisons = [comparisons]
    for comp in comparisons:
        stage = comp.get("stage", "—")
        for method in comp.get("methods", []):
            r = table.rowCount()
            table.insertRow(r)
            table.setItem(r, 0, QTableWidgetItem(str(stage)))
            table.setItem(r, 1, QTableWidgetItem(method.get("name", "—")))
            table.setItem(r, 2, QTableWidgetItem(_fmt(method.get("temp_k", "—"))))
            table.setItem(r, 3, QTableWidgetItem(str(method.get("iterations", "—"))))
            table.setItem(r, 4, QTableWidgetItem(_fmt(method.get("residual", "—"))))
            table.setItem(r, 5, QTableWidgetItem(_fmt(method.get("time_ms", "—"))))


def _fmt(value):
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def _fmt_bar(value):
    if isinstance(value, (int, float)):
        return f"{value / 1e5:.2f}"
    return str(value)
