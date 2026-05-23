"""Design-results presentation helpers for the KASP UI."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass


GRAPH_KEY_BY_LABEL = {
    "T-s Diyagramı": "ts_diagram",
    "T-s Diagram": "ts_diagram",
    "P-v Diyagramı": "pv_diagram",
    "P-v Diagram": "pv_diagram",
    "H-S (Mollier)": "hs_mollier",
    "Güç Dağılımı (Sankey)": "power_breakdown",
    "Power Flow (Sankey)": "power_breakdown",
    "k-Z Basınç Yolu": "kz_path",
    "k-Z Pressure Path": "kz_path",
    "Kademe Özeti": "stage_overview",
    "Stage Overview": "stage_overview",
    "Türbin Radarı": "performance_comparison",
    "Turbine Radar": "performance_comparison",
    "Yakınsama Dashboard": "convergence",
    "Convergence Dashboard": "convergence",
}


def build_consistency_info_html(results):
    if not results.get("consistency_mode", False):
        return None

    converged_icon = "✓" if results.get("consistency_converged", False) else "⚠️"
    info_text = (
        f"<b>Mod:</b> Tutarlı (Self-Consistent) {converged_icon}<br>"
        f"<b>Hedef Verim:</b> {results['poly_eff_target']:.2f}%<br>"
        f"<b>Yakınsanan Verim:</b> {results['poly_eff_converged']:.2f}%<br>"
        f"<b>Hesaplanan Verim:</b> {results['actual_poly_efficiency']*100:.2f}%<br>"
        f"<b>İterasyon:</b> {results['consistency_iterations']}<br>"
        f"<b>Final Residual:</b> {results['final_residual']:.4f}%"
    )

    if not results.get("consistency_converged", False):
        info_text += "<br><span style='color:orange;'>⚠️ Maksimum iter aşıldı!</span>"
    if results.get("fallback_used", False):
        info_text += "<br><span style='color:#b45309;'><b>Fallback:</b> Termodinamik kütüphane bazı noktalarda ideal gaz fallback kullandı.</span>"
    return info_text


def build_fallback_summary_lines(results):
    if not results.get("fallback_used", False):
        return []

    lines = ["Fallback Uyarısı: Termodinamik kütüphane bazı noktalarda ideal gaz fallback kullandı."]
    if results.get("fallback_stage_numbers"):
        stage_text = ", ".join(str(stage) for stage in results["fallback_stage_numbers"])
        lines.append(f"Etkilenen Kademeler: {stage_text}")
    if results.get("fallback_state_count"):
        lines.append(f"Benzersiz Fallback Durumu: {results['fallback_state_count']}")
    return lines


def build_method_convergence_summary_lines(results):
    convergence = results.get("method_convergence") or []
    if not convergence or results.get("method_converged", True):
        return []

    failed = [item for item in convergence if not item.get("converged", False)]
    if not failed:
        return []

    stage_text = ", ".join(str(item.get("stage")) for item in failed)
    reason_text = ", ".join(
        sorted({str(item.get("termination_reason") or "bilinmiyor") for item in failed})
    )
    return [
        "Metot Yakinsama Uyarisi: En az bir kademede son tahmin kullanildi.",
        f"Yakinsamayan Kademeler: {stage_text}",
        f"Neden: {reason_text}",
    ]


def build_fallback_info_html(results):
    if not results.get("fallback_used", False):
        return None

    html_lines = [
        "<b>Fallback Uyarısı:</b> Termodinamik kütüphane bazı noktalarda ideal gaz fallback kullandı."
    ]
    if results.get("fallback_stage_numbers"):
        stage_text = ", ".join(str(stage) for stage in results["fallback_stage_numbers"])
        html_lines.append(f"<b>Etkilenen Kademeler:</b> {stage_text}")
    if results.get("fallback_state_count"):
        html_lines.append(f"<b>Benzersiz Fallback Durumu:</b> {results['fallback_state_count']}")

    preview_states = results.get("fallback_states") or []
    if preview_states:
        preview_parts = []
        for state in preview_states[:3]:
            preview_parts.append(
                f"{state['pressure_bar_a']:.2f} bar(a) / {state['temperature_c']:.1f}°C"
            )
        html_lines.append(f"<b>Örnek Durumlar:</b> {'; '.join(preview_parts)}")

    return "<br>".join(html_lines)


def build_design_summary_text(summary, results):
    recommended_turbines = summary.get("recommended_turbines") or []
    recommended_turbine = recommended_turbines[0]["turbine"] if recommended_turbines else "Yok"
    fallback_lines = build_fallback_summary_lines(results)
    method_lines = build_method_convergence_summary_lines(results)

    if results.get("consistency_mode", False):
        converged_text = "✓ Yakınsadı" if results.get("consistency_converged") else "⚠️ Max iter aşıldı"
        summary_text = (
            "🔄 Mod: Tutarlı (Self-Consistent)\n"
            f"Proje: {summary['project_name']}\n"
            f"Hedef Verim: {results['poly_eff_target']:.1f}% → "
            f"Yakınsanan: {results['poly_eff_converged']:.1f}% "
            f"({converged_text}, {results['consistency_iterations']} iter)\n"
            f"Sıkıştırma Oranı: {summary['basic_parameters']['compression_ratio']:.2f}\n"
            f"Toplam Güç: {summary['basic_parameters']['total_power']:.0f} kW "
            f"({summary['basic_parameters']['num_units']} Ünite)\n"
            f"Önerilen Türbin: {recommended_turbine}"
        )
        extra_lines = fallback_lines + method_lines
        if extra_lines:
            summary_text += "\n" + "\n".join(extra_lines)
        return summary_text

    summary_text = (
        "⚡ Mod: Hızlı\n"
        f"Proje: {summary['project_name']}\n"
        f"Sıkıştırma Oranı: {summary['basic_parameters']['compression_ratio']:.2f}\n"
        f"Politropik Verim (Girdi): {summary['efficiency_metrics']['poly_efficiency']*100:.1f}%\n"
        f"Toplam Güç İhtiyacı: {summary['basic_parameters']['total_power']:.0f} kW "
        f"({summary['basic_parameters']['num_units']} Ünite)\n"
        f"Önerilen Türbin: {recommended_turbine}"
    )
    extra_lines = fallback_lines + method_lines
    if extra_lines:
        summary_text += "\n" + "\n".join(extra_lines)
    return summary_text


def get_selected_unit_value(unit, *keys, default=None):
    if isinstance(unit, dict):
        for key in keys:
            if key in unit:
                return unit[key]
        return default

    for key in keys:
        if hasattr(unit, key):
            return getattr(unit, key)
    return default


def describe_selected_turbine(unit):
    return {
        "turbine_name": get_selected_unit_value(unit, "turbine_name", "turbine", default="Bilinmiyor"),
        "available_power": get_selected_unit_value(unit, "available_power_kw", default=0.0),
        "iso_power": get_selected_unit_value(unit, "iso_power_kw", "iso_power", default=0.0),
        "site_heat_rate": get_selected_unit_value(unit, "site_heat_rate", default=0.0),
        "efficiency_rating": get_selected_unit_value(unit, "efficiency_rating", default="-"),
        "power_margin": get_selected_unit_value(unit, "power_margin_percent", default=0.0),
        "surge_margin": get_selected_unit_value(unit, "surge_margin_percent", "surge_margin", default=0.0),
        "recommendation": get_selected_unit_value(unit, "recommendation_level", default="-"),
    }


def build_selected_turbine_labels(details):
    return {
        "turbine_name": str(details["turbine_name"]),
        "power": f"{details['available_power']:.0f} kW (ISO: {details['iso_power']:.0f} kW)",
        "efficiency": f"Isi Orani: {details['site_heat_rate']:.0f} kJ/kWh ({details['efficiency_rating']})",
        "margin": f"Guc: {details['power_margin']:.1f}%, Surge: {details['surge_margin']:.1f}%",
        "recommendation": str(details["recommendation"]),
    }


def serialize_selected_units(selected_units):
    serialized = []
    for unit in selected_units or []:
        if isinstance(unit, dict):
            serialized.append(unit)
        elif is_dataclass(unit):
            serialized.append(asdict(unit))
        else:
            serialized.append({"repr": str(unit)})
    return serialized


class DesignResultsPresenter:
    """Render design calculation results and related result views."""

    get_selected_unit_value = staticmethod(get_selected_unit_value)
    serialize_selected_units = staticmethod(serialize_selected_units)
    describe_selected_turbine = staticmethod(describe_selected_turbine)
    build_selected_turbine_labels = staticmethod(build_selected_turbine_labels)

    def __init__(self, window, *, engine, graph_manager):
        self.window = window
        self.engine = engine
        self.graph_manager = graph_manager

    @staticmethod
    def _qt_table_widget_item():
        from PyQt5.QtWidgets import QTableWidgetItem

        return QTableWidgetItem

    @staticmethod
    def _format_static_result(key, value):
        if key == "compression_ratio":
            return f"{value:.2f}"
        if key == "actual_poly_efficiency":
            return f"{value * 100:.2f}"
        return f"{value:.1f}"

    def apply_results(self, results, selected_units):
        if not results:
            return

        self.window.last_raw_results = results

        consistency_html = build_consistency_info_html(results)
        if consistency_html:
            self.window.consistency_info_group.setVisible(True)
            self.window.consistency_info_label.setText(consistency_html)
        else:
            self.window.consistency_info_group.setVisible(False)

        fallback_html = build_fallback_info_html(results)
        fallback_group = getattr(self.window, "fallback_info_group", None)
        fallback_label = getattr(self.window, "fallback_info_label", None)
        if fallback_group is not None and fallback_label is not None:
            if fallback_html:
                fallback_group.setVisible(True)
                fallback_label.setText(fallback_html)
            else:
                fallback_group.setVisible(False)

        for key, label in self.window.result_labels.items():
            if key not in results:
                continue
            value = results[key]
            if key in self.window.result_unit_combos:
                current_unit = self.window.result_unit_combos[key].currentText()
                self.update_single_result_unit(key, current_unit)
            else:
                label.setText(self._format_static_result(key, value))

        summary = self.engine.generate_summary_report(self.window.last_design_inputs, results, selected_units)
        self.window.summary_text.setText(build_design_summary_text(summary, results))

        self.populate_detailed_tables(results)
        self.graph_manager.generate_all_graphs(self.window.last_design_inputs, results, selected_units)
        self.refresh_current_graph()
        self.populate_turbine_table(selected_units)

    def update_single_result_unit(self, key, new_unit):
        if not getattr(self.window, "last_raw_results", None):
            return

        results = self.window.last_raw_results
        if key not in results or key not in self.window.result_labels:
            return

        value = results.get(key, 0)

        if key in ["power_unit_kw", "power_unit_total_kw"]:
            converted = self.engine.convert_result_value(value, "kW", new_unit, "power")
            self.window.result_labels[key].setText(f"{converted:.0f}")
            return

        if key == "head_kj_kg":
            converted = self.engine.convert_result_value(value, "kJ/kg", new_unit, "head")
            self.window.result_labels[key].setText(f"{converted:.2f}")
            return

        if key == "heat_rate":
            converted = self.engine.convert_result_value(value, "kJ/kWh", new_unit, "heat_rate")
            self.window.result_labels[key].setText(f"{converted:.0f}")
            return

        if key == "t_out":
            converted = self.engine.convert_result_value(value, "°C", new_unit, "temperature")
            self.window.result_labels[key].setText(f"{converted:.1f}")
            return

        if key in ["fuel_total_kgh", "fuel_unit_kgh"]:
            try:
                gas_comp = (self.window.last_design_inputs or {}).get("gas_comp")
                eos_method = (self.window.last_design_inputs or {}).get("eos_method")
                fuel_gas_obj = None
                if gas_comp and eos_method:
                    fuel_gas_obj = self.engine._create_gas_object(gas_comp, eos_method)

                converted = self.engine.convert_result_value(
                    value,
                    "kg/h",
                    new_unit,
                    "fuel_flow",
                    fuel_gas_obj,
                    eos_method,
                    results.get("lhv"),
                )
                if new_unit in {"J/h", "cal/h"}:
                    self.window.result_labels[key].setText(f"{converted:.2e}")
                elif new_unit in {"Sm³/h", "Nm³/h"}:
                    self.window.result_labels[key].setText(f"{converted:.1f}")
                else:
                    self.window.result_labels[key].setText(f"{converted:.0f}")
            except Exception:
                self.window.result_labels[key].setText("N/A")

    def populate_turbine_table(self, selected_units):
        QTableWidgetItem = self._qt_table_widget_item()

        self.window.turbine_table.setRowCount(len(selected_units))
        for row, unit in enumerate(selected_units):
            details = describe_selected_turbine(unit)
            score = get_selected_unit_value(unit, "selection_score", default=0.0)
            self.window.turbine_table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
            self.window.turbine_table.setItem(row, 1, QTableWidgetItem(str(details["turbine_name"])))
            self.window.turbine_table.setItem(row, 2, QTableWidgetItem(f"{details['available_power']:.0f}"))
            self.window.turbine_table.setItem(row, 3, QTableWidgetItem(f"{details['site_heat_rate']:.0f}"))
            self.window.turbine_table.setItem(row, 4, QTableWidgetItem(str(details["efficiency_rating"])))
            self.window.turbine_table.setItem(row, 5, QTableWidgetItem(f"{details['surge_margin']:.1f}%"))
            self.window.turbine_table.setItem(row, 6, QTableWidgetItem(f"{score:.1f}"))
            self.window.turbine_table.setItem(row, 7, QTableWidgetItem(str(details["recommendation"])))

    def populate_detailed_tables(self, results):
        QTableWidgetItem = self._qt_table_widget_item()

        thermo_props = ["Z", "rho", "k", "Cp", "Cv", "H", "S", "phase", "mu", "a"]
        units = ["-", "kg/m³", "-", "J/kg-K", "J/kg-K", "J/kg", "J/kg-K", "-", "Pa-s", "m/s"]
        display_names = ["Z Faktörü", "Yoğunluk", "İz. Üs (k)", "Cp (Özgül Isı)", "Cv (Özgül Isı)", "Entalpi (H)", "Entropi (S)", "Faz Durumu", "Viskozite", "Ses Hızı"]

        self.window.thermo_table.setRowCount(len(thermo_props))

        in_props = results["inlet_properties"]
        out_props = results["outlet_properties"]

        for index, (prop, unit, name) in enumerate(zip(thermo_props, units, display_names)):
            val_in = in_props.get(prop, 0)
            val_out = out_props.get(prop, 0)
            
            is_numeric = isinstance(val_in, (int, float)) and isinstance(val_out, (int, float)) and not isinstance(val_in, bool)
            if is_numeric:
                change = ((val_out - val_in) / val_in) * 100 if val_in != 0 else 0
                change_str = f"{change:+.1f}%"
                val_in_str = f"{val_in:.4e}" if prop in ["mu", "rho", "Cp", "Cv", "H", "S"] else f"{val_in:.3f}"
                val_out_str = f"{val_out:.4e}" if prop in ["mu", "rho", "Cp", "Cv", "H", "S"] else f"{val_out:.3f}"
            else:
                change_str = "-"
                val_in_str = str(val_in)
                val_out_str = str(val_out)

            self.window.thermo_table.setItem(index, 0, QTableWidgetItem(name))
            self.window.thermo_table.setItem(index, 1, QTableWidgetItem(val_in_str))
            self.window.thermo_table.setItem(index, 2, QTableWidgetItem(val_out_str))
            self.window.thermo_table.setItem(index, 3, QTableWidgetItem(unit))
            self.window.thermo_table.setItem(index, 4, QTableWidgetItem(change_str))

        self.window.power_table.setRowCount(4)
        power_data = [
            ("Gaz Gücü", results["power_gas_per_unit_kw"], results["power_gas_total_kw"]),
            ("Şaft Gücü", results["power_shaft_per_unit_kw"], results["power_shaft_total_kw"]),
            ("Motor Gücü (Gerekli)", results["power_unit_kw"], results["power_unit_total_kw"]),
            ("Mekanik Kayıp", results["mech_loss_per_unit_kw"], results["mech_loss_total_kw"]),
        ]

        for index, (name, per_unit, total) in enumerate(power_data):
            self.window.power_table.setItem(index, 0, QTableWidgetItem(name))
            self.window.power_table.setItem(index, 1, QTableWidgetItem(f"{per_unit:.0f} kW"))
            self.window.power_table.setItem(index, 2, QTableWidgetItem(f"{total:.0f} kW"))

        self.window.fuel_table.setRowCount(3)
        self.window.fuel_table.setItem(0, 0, QTableWidgetItem("LHV"))
        self.window.fuel_table.setItem(0, 1, QTableWidgetItem(f"{results['lhv']:.0f} kJ/kg"))
        self.window.fuel_table.setItem(1, 0, QTableWidgetItem("HHV"))
        self.window.fuel_table.setItem(1, 1, QTableWidgetItem(f"{results['hhv']:.0f} kJ/kg"))
        self.window.fuel_table.setItem(2, 0, QTableWidgetItem("Toplam Yakıt Akışı"))
        self.window.fuel_table.setItem(2, 1, QTableWidgetItem(f"{results['fuel_total_kgh']:.1f} kg/h"))

        # Fallback Karşılaştırması Tablosunu Doldur
        comparisons = results.get("fallback_comparison", [])
        if comparisons:
            self.window.fallback_table.setRowCount(len(comparisons) * 3)
            row_idx = 0
            for comp in comparisons:
                stage_name = comp.get("stage", "Performans")
                for method in comp.get("methods", []):
                    self.window.fallback_table.setItem(row_idx, 0, QTableWidgetItem(stage_name))
                    self.window.fallback_table.setItem(row_idx, 1, QTableWidgetItem(method["name"]))
                    self.window.fallback_table.setItem(row_idx, 2, QTableWidgetItem(f"{method['temp_k']:.2f} K ({method['temp_k']-273.15:.2f} °C)"))
                    self.window.fallback_table.setItem(row_idx, 3, QTableWidgetItem(str(method["iterations"])))
                    self.window.fallback_table.setItem(row_idx, 4, QTableWidgetItem(f"{method['residual']:.4f}"))
                    self.window.fallback_table.setItem(row_idx, 5, QTableWidgetItem(f"{method['time_ms']:.2f} ms"))
                    row_idx += 1
        else:
            self.window.fallback_table.setRowCount(1)
            self.window.fallback_table.setItem(0, 0, QTableWidgetItem("-"))
            self.window.fallback_table.setItem(0, 1, QTableWidgetItem("Hesaplamalar esnasında fallback mekanizmasına düşülmedi."))
            self.window.fallback_table.setItem(0, 2, QTableWidgetItem("-"))
            self.window.fallback_table.setItem(0, 3, QTableWidgetItem("-"))
            self.window.fallback_table.setItem(0, 4, QTableWidgetItem("-"))
            self.window.fallback_table.setItem(0, 5, QTableWidgetItem("-"))

    def _get_current_graph_label(self):
        bg = getattr(self.window, "graph_button_group", None)
        if bg and bg.checkedButton():
            return bg.checkedButton().text()
        combo = getattr(self.window, "graph_combo", None)
        if combo:
            return combo.currentText()
        return "T-s Diyagramı"

    def refresh_current_graph(self, graph_label=None):
        current_graph_name = graph_label or self._get_current_graph_label()

        for index in reversed(range(self.window.graph_layout.count())):
            item = self.window.graph_layout.takeAt(index)
            widget = item.widget()
            if widget:
                widget.setParent(None)

        self.window.default_graph_label.setParent(self.window.graph_widget)
        self.window.default_graph_label.setVisible(True)

        if self.window.last_design_results_raw and self.graph_manager.current_graphs:
            graph_key = GRAPH_KEY_BY_LABEL.get(current_graph_name)
            canvas = self.graph_manager.current_graphs.get(graph_key)

            if canvas:
                canvas.setParent(self.window.graph_widget)
                self.window.default_graph_label.setVisible(False)
                self.window.graph_layout.addWidget(canvas)
                if hasattr(canvas, "draw_idle"):
                    canvas.draw_idle()
                canvas.show()
                self._set_graph_description(current_graph_name)
            else:
                self.window.default_graph_label.setText(
                    f"Grafik verisi mevcut değil veya kütüphane ({current_graph_name}) yüklü değil."
                )
                self.window.graph_layout.addWidget(self.window.default_graph_label)
                self.window.default_graph_label.setVisible(True)
        else:
            self.window.graph_layout.addWidget(self.window.default_graph_label)

    def _set_graph_description(self, label):
        try:
            from kasp.i18n import is_english
        except ImportError:
            is_english = lambda: False
        en = is_english()
        desc_map = {
            "T-s Diyagramı": (
                "Sıkıştırma prosesini sıcaklık-entropi düzleminde gösterir. İzentropik (dikey) ve gerçek proses karşılaştırması.",
                "Shows the compression process on the temperature-entropy plane. Compares isentropic (vertical) vs actual process."
            ),
            "P-v Diyagramı": (
                "Basınç-özgül hacim düzleminde politropik ve izentropik sıkıştırma eğrileri. Gölgeli alan = sıkıştırma işi.",
                "Polytropic and isentropic compression curves on the pressure-specific volume plane. Shaded area = compression work."
            ),
            "H-S (Mollier)": (
                "Endüstri standardı Mollier diyagramı. ΔH_isen ve ΔH_actual oklarıyla entalpi farklarını gösterir.",
                "Industry-standard Mollier diagram. Shows enthalpy differences with ΔH_isen and ΔH_actual arrows."
            ),
            "Güç Dağılımı (Sankey)": (
                "Yakıt girişinden gaz gücüne enerji akışı. Her kayıp kademesi oransal olarak gösterilir.",
                "Energy flow from fuel input to gas power. Each loss stage is shown proportionally."
            ),
            "k-Z Basınç Yolu": (
                "Sıkıştırma boyunca k (Cp/Cv) ve Z (sıkıştırılabilirlik) değişimi. API 617 integral metodu referansı.",
                "Evolution of k (Cp/Cv) and Z (compressibility) along the compression path. API 617 integral method reference."
            ),
            "Kademe Özeti": (
                "Her kademe için P, T, η_poly, Head değerlerini karşılaştırmalı bar chart olarak sunar.",
                "Comparative bar charts of P, T, η_poly, Head values for each stage."
            ),
            "Türbin Radarı": (
                "5 eksenli radar grafik: Güç uygunluğu, Isıl verim, Surge marjı, Stonewall marjı, Tip skoru.",
                "5-axis radar chart: Power fitness, Thermal efficiency, Surge margin, Stonewall margin, Type score."
            ),
            "Yakınsama Dashboard": (
                "3 panelli: η yakınsaması, T çıkış sıcaklığı, logaritmik kalıntı (residual).",
                "3-panel dashboard: η convergence, T outlet temperature, logarithmic residual."
            ),
        }
        # EN label fallback
        en_labels = {
            "T-s Diagram": "T-s Diyagramı", "P-v Diagram": "P-v Diyagramı",
            "Power Flow (Sankey)": "Güç Dağılımı (Sankey)", "k-Z Pressure Path": "k-Z Basınç Yolu",
            "Stage Overview": "Kademe Özeti", "Turbine Radar": "Türbin Radarı",
            "Convergence Dashboard": "Yakınsama Dashboard",
        }
        tr_key = en_labels.get(label, label)
        pair = desc_map.get(tr_key)
        desc = pair[1] if (en and pair) else (pair[0] if pair else "")
        lbl = getattr(self.window, "graph_desc_label", None)
        if lbl and desc:
            lbl.setText(desc)

    def apply_selected_turbine_selection(self, selected_rows, selected_units):
        if not selected_rows or not selected_units:
            return

        row = selected_rows[0].row()
        if row >= len(selected_units):
            return

        details = describe_selected_turbine(selected_units[row])
        labels = build_selected_turbine_labels(details)
        self.window.selected_turbine_label.setText(labels["turbine_name"])
        self.window.turbine_power_label.setText(labels["power"])
        self.window.turbine_efficiency_label.setText(labels["efficiency"])
        self.window.turbine_margin_label.setText(labels["margin"])
        self.window.turbine_recommendation_label.setText(labels["recommendation"])
