"""Helpers for binding design-input widgets to shared KASP contracts."""

from __future__ import annotations

from kasp.core.contracts import get_design_input_defaults, normalize_design_inputs


def eos_method_from_ui_text(selected_text):
    """Translate a UI combo label into the engine eos_method code."""
    if "CoolProp" in selected_text:
        return "coolprop", None
    if "Peng-Robinson" in selected_text:
        return "pr", None
    if "SRK" in selected_text:
        return "srk", None
    if "Kütüphane Yok" in selected_text:
        return None, "EOS Hatası: Geçerli bir EOS metodu seçiniz (Kütüphane yüklü değil)."

    normalized = selected_text.lower().strip()
    if normalized in {"coolprop", "pr", "srk"}:
        return normalized, None
    return normalized, f"EOS Hatası: Bilinmeyen veya yanlış eşleşen EOS metodu: {selected_text}"


def lhv_source_from_ui_text(selected_text):
    """Translate a UI combo label into the engine lhv source code."""
    return "thermo" if "Thermo" in selected_text else "kasp"


class DesignInputBinder:
    """Centralize widget <-> normalized design input mapping."""

    def __init__(self, window, *, thermo_loaded):
        self.window = window
        self.thermo_loaded = thermo_loaded

    def collect(self):
        """Collect normalized design inputs from the bound window widgets."""
        inputs = {}
        errors = []
        window = self.window

        inputs["project_name"] = window.project_name_edit.text()
        inputs["notes"] = window.project_notes_edit.toPlainText()

        inputs["p_in"] = window.p_in_edit.text()
        inputs["p_in_unit"] = window.p_in_unit_combo.currentText()
        inputs["t_in"] = window.t_in_edit.text()
        inputs["t_in_unit"] = window.t_in_unit_combo.currentText()
        inputs["p_out"] = window.p_out_edit.text()
        inputs["p_out_unit"] = window.p_out_unit_combo.currentText()
        inputs["flow"] = window.flow_edit.text()
        inputs["flow_unit"] = window.flow_unit_combo.currentText()
        inputs["num_units"] = window.num_units_spin.value()
        inputs["num_stages"] = window.num_stages_spin.value()
        inputs["intercooler_dp_pct"] = (
            window.ic_dp_spin.value() if window.num_stages_spin.value() > 1 else 0.0
        )

        try:
            inputs["intercooler_t"] = (
                float(window.ic_temp_edit.text()) if window.num_stages_spin.value() > 1 else 40.0
            )
        except ValueError:
            inputs["intercooler_t"] = 40.0

        eos_method, eos_error = eos_method_from_ui_text(window.eos_method_combo.currentText())
        if eos_error:
            errors.append(eos_error)
        elif eos_method:
            inputs["eos_method"] = eos_method

        inputs["method"] = window.method_combo.currentText()
        inputs["lhv_source"] = lhv_source_from_ui_text(window.lhv_source_combo.currentText())

        try:
            inputs["poly_eff"] = float(window.poly_eff_edit.text())
            inputs["therm_eff"] = float(window.therm_eff_edit.text())
            inputs["mech_eff"] = float(window.mech_eff_edit.text())
        except ValueError:
            errors.append("Verimlilik değerleri (Politropik, Isıl, Mekanik) sayısal olmalıdır.")

        inputs["use_consistency_iteration"] = window.consistency_check.isChecked()
        inputs["max_consistency_iter"] = window.max_consistency_iter.value()
        inputs["consistency_tolerance"] = window.consistency_tolerance.value()

        gas_comp = window._get_gas_composition()
        total_percentage = sum(gas_comp.values())
        if not gas_comp:
            errors.append("Gaz kompozisyonu tanımlanmalıdır.")
        inputs["gas_comp"] = gas_comp

        inputs["ambient_temp"] = float(window.t_in_edit.text())
        inputs["ambient_pressure"] = 101.325
        inputs["altitude"] = 0
        inputs["humidity"] = 60

        if errors:
            raise ValueError("\n".join(errors))

        return normalize_design_inputs(inputs), total_percentage

    def apply(self, inputs):
        """Populate bound widgets from normalized design inputs."""
        normalized = normalize_design_inputs(inputs)
        window = self.window

        window.project_name_edit.setText(str(normalized.get("project_name", "")))
        window.project_notes_edit.setPlainText(normalized.get("notes", ""))
        window.p_in_edit.setText(str(normalized.get("p_in", "")))
        window.p_in_unit_combo.setCurrentText(normalized.get("p_in_unit", "bar(g)"))
        window.t_in_edit.setText(str(normalized.get("t_in", "")))
        window.t_in_unit_combo.setCurrentText(normalized.get("t_in_unit", "°C"))
        window.p_out_edit.setText(str(normalized.get("p_out", "")))
        window.p_out_unit_combo.setCurrentText(normalized.get("p_out_unit", "bar(a)"))
        window.flow_edit.setText(str(normalized.get("flow", "")))
        window.flow_unit_combo.setCurrentText(normalized.get("flow_unit", "Sm³/h"))
        window.num_units_spin.setValue(normalized.get("num_units", 1))
        window.num_stages_spin.setValue(normalized.get("num_stages", 1))
        window.ic_dp_spin.setValue(normalized.get("intercooler_dp_pct", 2.0))
        window.ic_temp_edit.setText(str(normalized.get("intercooler_t", 40.0)))

        self._apply_eos_method(normalized.get("eos_method", "coolprop"))
        window.method_combo.setCurrentText(normalized.get("method", "Metot 1: Ortalama Özellikler"))

        if normalized.get("lhv_source", "kasp") == "thermo" and self.thermo_loaded:
            window.lhv_source_combo.setCurrentIndex(1)
        else:
            window.lhv_source_combo.setCurrentIndex(0)

        window.poly_eff_edit.setText(str(normalized.get("poly_eff", 90.0)))
        window.therm_eff_edit.setText(str(normalized.get("therm_eff", 35.0)))
        window.mech_eff_edit.setText(str(normalized.get("mech_eff", 98.0)))

        window.consistency_check.setChecked(normalized.get("use_consistency_iteration", False))
        window.max_consistency_iter.setValue(normalized.get("max_consistency_iter", 20))
        window.consistency_tolerance.setValue(normalized.get("consistency_tolerance", 0.1))

        self._apply_gas_composition(normalized.get("gas_comp", {}))
        return normalized

    def reset_to_defaults(self):
        """Reset the form to shared default inputs."""
        return self.apply(get_design_input_defaults())

    def _apply_eos_method(self, eos_method):
        window = self.window
        for index in range(window.eos_method_combo.count()):
            text = window.eos_method_combo.itemText(index)
            mapped, error = eos_method_from_ui_text(text)
            if error:
                continue
            if mapped == eos_method:
                window.eos_method_combo.setCurrentIndex(index)
                return
        if window.eos_method_combo.count():
            window.eos_method_combo.setCurrentIndex(0)

    def _apply_gas_composition(self, gas_comp):
        window = self.window
        window.composition_table.setRowCount(0)
        if not gas_comp:
            return

        from PyQt5.QtCore import Qt
        from PyQt5.QtWidgets import QComboBox, QTableWidgetItem

        for component_key, percentage in gas_comp.items():
            row = window.composition_table.rowCount()
            window.composition_table.insertRow(row)

            combo = QComboBox()
            combo.addItems(window.COMMON_COMPONENTS_DISPLAY)
            display_name = window.COOLPROP_GAS_MAP.get(component_key, component_key)
            if display_name in window.COMMON_COMPONENTS_DISPLAY:
                combo.setCurrentText(display_name)

            window.composition_table.setCellWidget(row, 0, combo)

            percent_item = QTableWidgetItem(str(percentage))
            percent_item.setTextAlignment(Qt.AlignCenter)
            window.composition_table.setItem(row, 1, percent_item)
