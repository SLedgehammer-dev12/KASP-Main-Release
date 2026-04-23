"""Design-results presentation helpers for the KASP UI."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass


GRAPH_KEY_BY_LABEL = {
    "T-s Diyagramı": "ts_diagram",
    "P-v Diyagramı": "pv_diagram",
    "Güç Dağılımı": "power_breakdown",
    "Türbin Performansı": "performance_comparison",
    "Yakınsama Grafiği": "convergence",
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
    return info_text


def build_design_summary_text(summary, results):
    recommended_turbines = summary.get("recommended_turbines") or []
    recommended_turbine = recommended_turbines[0]["turbine"] if recommended_turbines else "Yok"

    if results.get("consistency_mode", False):
        converged_text = "✓ Yakınsadı" if results.get("consistency_converged") else "⚠️ Max iter aşıldı"
        return (
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

    return (
        "⚡ Mod: Hızlı\n"
        f"Proje: {summary['project_name']}\n"
        f"Sıkıştırma Oranı: {summary['basic_parameters']['compression_ratio']:.2f}\n"
        f"Politropik Verim (Girdi): {summary['efficiency_metrics']['poly_efficiency']*100:.1f}%\n"
        f"Toplam Güç İhtiyacı: {summary['basic_parameters']['total_power']:.0f} kW "
        f"({summary['basic_parameters']['num_units']} Ünite)\n"
        f"Önerilen Türbin: {recommended_turbine}"
    )


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
        elif key == "head_kj_kg":
            converted = self.engine.convert_result_value(value, "kJ/kg", new_unit, "head")
            self.window.result_labels[key].setText(f"{converted:.2f}")
        elif key == "heat_rate":
            converted = self.engine.convert_result_value(value, "kJ/kWh", new_unit, "heat_rate")
            self.window.result_labels[key].setText(f"{converted:.0f}")
        elif key == "t_out":
            converted = self.engine.convert_result_value(value, "°C", new_unit, "temperature")
            self.window.result_labels[key].setText(f"{converted:.1f}")
        elif key in ["fuel_total_kgh", "fuel_unit_kgh"]:
            if new_unit == "lb/h":
                converted = value / 0.45359237
                self.window.result_labels[key].setText(f"{converted:.0f}")
            elif new_unit == "Sm³/h":
                fuel_gas_density_std = results.get("fuel_gas_density_std")
                if fuel_gas_density_std and fuel_gas_density_std > 0:
                    converted = value / fuel_gas_density_std
                    self.window.result_labels[key].setText(f"{converted:.1f}")
                else:
                    converted = value / 0.75
                    self.window.result_labels[key].setText(f"{converted:.1f} (est)")
            elif new_unit in {"cal/h", "J/h"}:
                lhv_kj_kg = results.get("lhv")
                if lhv_kj_kg and lhv_kj_kg > 0:
                    energy_kj_h = value * lhv_kj_kg
                    if new_unit == "cal/h":
                        converted = energy_kj_h * 239.006
                    else:
                        converted = energy_kj_h * 1000
                    self.window.result_labels[key].setText(f"{converted:.2e}")
                else:
                    self.window.result_labels[key].setText("LHV Yok")
            else:
                self.window.result_labels[key].setText(f"{value:.0f}")

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

        self.window.thermo_table.setRowCount(6)
        thermo_props = ["Z", "rho", "k", "Cp", "mu", "a"]
        units = ["-", "kg/m³", "-", "J/kg-K", "Pa-s", "m/s"]
        display_names = ["Z Faktörü", "Yoğunluk", "İz. Üs (k)", "Cp", "Viskozite", "Ses Hızı"]

        in_props = results["inlet_properties"]
        out_props = results["outlet_properties"]

        for index, (prop, unit, name) in enumerate(zip(thermo_props, units, display_names)):
            val_in = in_props.get(prop, 0)
            val_out = out_props.get(prop, 0)
            change = ((val_out - val_in) / val_in) * 100 if val_in != 0 else 0

            self.window.thermo_table.setItem(index, 0, QTableWidgetItem(name))
            self.window.thermo_table.setItem(
                index, 1, QTableWidgetItem(f"{val_in:.4e}" if prop in ["mu", "rho", "Cp"] else f"{val_in:.3f}")
            )
            self.window.thermo_table.setItem(
                index, 2, QTableWidgetItem(f"{val_out:.4e}" if prop in ["mu", "rho", "Cp"] else f"{val_out:.3f}")
            )
            self.window.thermo_table.setItem(index, 3, QTableWidgetItem(unit))
            self.window.thermo_table.setItem(index, 4, QTableWidgetItem(f"{change:+.1f}%"))

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

    def refresh_current_graph(self):
        current_graph_name = self.window.graph_combo.currentText()

        for index in reversed(range(self.window.graph_layout.count())):
            item = self.window.graph_layout.takeAt(index)
            widget = item.widget()
            if widget and widget is not self.window.default_graph_label:
                widget.setParent(None)

        self.window.default_graph_label.setVisible(True)

        if self.window.last_design_results_raw and self.graph_manager.current_graphs:
            self.window.default_graph_label.setVisible(False)

            graph_key = GRAPH_KEY_BY_LABEL.get(current_graph_name)
            canvas = self.graph_manager.current_graphs.get(graph_key)

            if canvas:
                self.window.default_graph_label.setVisible(False)
                self.window.graph_layout.addWidget(canvas)
            else:
                self.window.default_graph_label.setText(
                    f"Grafik verisi mevcut değil veya kütüphane ({current_graph_name}) yüklü değil."
                )
                self.window.default_graph_label.setVisible(True)

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
