"""Performance evaluation helpers and controller for the KASP UI."""

from __future__ import annotations

import logging

from kasp.core.performance_corrections import calculate_site_correction_factors
from kasp.ui.design_input_binding import eos_method_from_ui_text, lhv_source_from_ui_text


def performance_ui_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def performance_eff_to_decimal(value, default=0.0):
    try:
        efficiency = float(value)
    except (TypeError, ValueError):
        return default
    return efficiency / 100.0 if efficiency > 1.0 else efficiency


def performance_pct_deviation(actual, expected):
    if expected in (None, 0):
        return 0.0
    return ((actual - expected) / expected) * 100.0


def convert_pressure_delta_to_kpa(value, unit):
    value = performance_ui_float(value, 0.0)
    normalized = str(unit or "kPa").lower()
    if normalized == "pa":
        return value / 1000.0
    if normalized == "kpa":
        return value
    if normalized == "mpa":
        return value * 1000.0
    if normalized in {"bar", "bar(a)", "bar(g)"}:
        return value * 100.0
    if normalized in {"psia", "psig"}:
        return value * 6.89476
    return value


def build_performance_report_inputs(ui_context, inputs, results, *, design_inputs=None):
    design_inputs = design_inputs or {}
    site_corrections = inputs.get("site_correction_inputs", {})

    return {
        "unit_name": ui_context.get("unit_name") or "Performans Testi",
        "p_in": performance_ui_float(ui_context.get("p_in"), 0.0),
        "p_in_unit": ui_context.get("p_in_unit", "bar(g)"),
        "t_in": performance_ui_float(ui_context.get("t_in"), 0.0),
        "t_in_unit": ui_context.get("t_in_unit", "degC"),
        "p_out": performance_ui_float(ui_context.get("p_out"), 0.0),
        "p_out_unit": ui_context.get("p_out_unit", "bar(g)"),
        "t_out": performance_ui_float(ui_context.get("t_out"), 0.0),
        "t_out_unit": ui_context.get("t_out_unit", "degC"),
        "flow": performance_ui_float(ui_context.get("flow"), 0.0),
        "flow_unit": ui_context.get("flow_unit", "kg/s"),
        "flow_kgs": inputs["flow_kgs"],
        "p1_pa": inputs["p1_pa"],
        "p2_pa": inputs["p2_pa"],
        "fuel_flow": results.get("fuel_cons_kg_h", 0.0),
        "fuel_flow_unit": "kg/h",
        "ambient_temp": site_corrections.get(
            "ambient_temp_c", design_inputs.get("ambient_temp", performance_ui_float(ui_context.get("t_in"), 0.0))
        ),
        "ambient_pressure": site_corrections.get(
            "ambient_pressure_kpa", design_inputs.get("ambient_pressure", 101.325)
        ),
        "humidity": site_corrections.get("relative_humidity_pct", design_inputs.get("humidity", 60.0)),
        "altitude": site_corrections.get("altitude_m", design_inputs.get("altitude", 0.0)),
        "performance_standard": site_corrections.get("standard", ui_context.get("performance_standard", "ASME PTC 10")),
        "site_correction_inputs": site_corrections,
    }


def build_performance_report_payload(
    report_inputs,
    raw_results,
    *,
    design_inputs=None,
    design_results=None,
    evaluate_status_fn=None,
):
    design_inputs = design_inputs or {}
    design_results = design_results or {}

    actual_poly_eff = performance_eff_to_decimal(raw_results.get("poly_eff", 0.0))
    actual_therm_eff = performance_eff_to_decimal(
        raw_results.get("actual_therm_eff", raw_results.get("turb_eff", 0.0))
    )
    actual_heat_rate = raw_results.get("actual_heat_rate", 0.0)
    actual_power = raw_results.get("shaft_power_kw", 0.0)
    correction_factors = raw_results.get("correction_factors") or calculate_site_correction_factors(
        report_inputs.get("site_correction_inputs", {})
    )
    corrected_power = raw_results.get("corrected_power_kw", actual_power)
    corrected_heat_rate = raw_results.get("corrected_heat_rate", actual_heat_rate)

    design_poly_eff = performance_eff_to_decimal(
        design_results.get(
            "design_poly_efficiency",
            design_inputs.get("poly_eff", raw_results.get("poly_eff", 0.0)),
        )
    )
    expected_therm_eff = performance_eff_to_decimal(
        design_inputs.get("therm_eff", raw_results.get("turb_eff", 0.0))
    )
    expected_heat_rate = design_results.get("heat_rate", actual_heat_rate)
    expected_power = design_results.get("power_shaft_per_unit_kw", actual_power)

    test_mass_flow = performance_ui_float(report_inputs.get("flow_kgs", report_inputs.get("flow", 0.0)), 0.0)
    fuel_flow_kgh = performance_ui_float(report_inputs.get("fuel_flow", 0.0), 0.0)
    compression_ratio = (
        performance_ui_float(report_inputs.get("p2_pa", report_inputs.get("p_out", 0.0)), 0.0)
        / max(performance_ui_float(report_inputs.get("p1_pa", report_inputs.get("p_in", 1.0)), 1.0), 1e-9)
    )
    poly_head = raw_results.get("poly_head_kj_kg", 0.0)

    perf_results = {
        "actual_poly_eff": actual_poly_eff,
        "design_poly_eff": design_poly_eff,
        "expected_poly_eff": design_poly_eff,
        "deviation_poly_eff": performance_pct_deviation(actual_poly_eff, design_poly_eff),
        "actual_therm_eff": actual_therm_eff,
        "expected_therm_eff": expected_therm_eff,
        "deviation_therm_eff": performance_pct_deviation(actual_therm_eff, expected_therm_eff),
        "actual_heat_rate": actual_heat_rate,
        "expected_heat_rate": expected_heat_rate,
        "deviation_heat_rate": performance_pct_deviation(actual_heat_rate, expected_heat_rate),
        "actual_power": actual_power,
        "expected_power": expected_power,
        "deviation_power": performance_pct_deviation(actual_power, expected_power),
        "corrected_power": corrected_power,
        "corrected_heat_rate": corrected_heat_rate,
        "deviation_corrected_power": performance_pct_deviation(corrected_power, expected_power),
        "deviation_corrected_heat_rate": performance_pct_deviation(corrected_heat_rate, expected_heat_rate),
        "test_conditions": {
            "mass_flow": test_mass_flow,
            "fuel_flow": fuel_flow_kgh,
            "compression_ratio": compression_ratio,
            "head": poly_head,
        },
        "corrected_values": {
            "power": corrected_power,
            "heat_rate": corrected_heat_rate,
            "correction_factors": correction_factors,
        },
    }

    if evaluate_status_fn is not None:
        perf_results["performance_status"] = evaluate_status_fn(perf_results)

    return report_inputs, perf_results


def get_driver_input_mode_state(use_turbine_efficiency):
    if use_turbine_efficiency:
        return {
            "turb_eff_enabled": True,
            "fuel_cons_enabled": False,
            "turb_eff_text": "35.0",
            "fuel_cons_text": "",
        }
    return {
        "turb_eff_enabled": False,
        "fuel_cons_enabled": True,
        "turb_eff_text": "",
        "fuel_cons_text": "500.0",
    }


class PerformanceInputBinder:
    """Collect and normalize performance inputs from the UI."""

    def __init__(self, window, *, engine, message_box_factory=None):
        self.window = window
        self.engine = engine
        self._message_box_factory = message_box_factory or self._qt_message_box

    @staticmethod
    def _qt_message_box():
        from PyQt5.QtWidgets import QMessageBox

        return QMessageBox

    def collect(self):
        eos_method, eos_error = eos_method_from_ui_text(self.window.eos_method_combo.currentText())
        if eos_error:
            self._message_box_factory().critical(self.window, "Hata", eos_error)
            return None, None

        gas_comp = self.window._get_gas_composition()
        total_percentage = sum(gas_comp.values())
        if abs(total_percentage - 100.0) > 0.01:
            QMessageBox = self._message_box_factory()
            reply = QMessageBox.warning(
                self.window,
                "Uyari",
                (
                    f"Gaz kompozisyonlari toplami %100 degil (su anki: %{total_percentage:.2f}).\n"
                    "Normalizasyon yapilsin mi?"
                ),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if reply == QMessageBox.Yes:
                self.window.normalize_composition()
                gas_comp = self.window._get_gas_composition()
            else:
                return None, None

        gas_obj = self.engine._create_gas_object(gas_comp, eos_method)
        p1_unit = self.window.perf_p1_unit_combo.currentText()
        t1_unit = self.window.perf_t1_unit_combo.currentText()
        p2_unit = self.window.perf_p2_unit_combo.currentText()
        t2_unit = self.window.perf_t2_unit_combo.currentText()
        flow_unit = self.window.perf_flow_unit_combo.currentText()
        ambient_temp_unit = self.window.perf_ambient_temp_unit_combo.currentText()
        ambient_pressure_unit = self.window.perf_ambient_pressure_unit_combo.currentText()
        inlet_loss_unit = self.window.perf_inlet_loss_unit_combo.currentText()
        exhaust_loss_unit = self.window.perf_exhaust_loss_unit_combo.currentText()

        ambient_temp_k = self.engine.convert_temperature_to_k(
            performance_ui_float(self.window.perf_ambient_temp_edit.text(), 15.0),
            ambient_temp_unit,
        )
        ambient_pressure_kpa = (
            self.engine.convert_pressure_to_pa(
                performance_ui_float(self.window.perf_ambient_pressure_edit.text(), 101.325),
                ambient_pressure_unit,
            )
            / 1000.0
        )

        inputs = {
            "p1_pa": self.engine.convert_pressure_to_pa(float(self.window.perf_p1_edit.text()), p1_unit),
            "t1_k": self.engine.convert_temperature_to_k(float(self.window.perf_t1_edit.text()), t1_unit),
            "p2_pa": self.engine.convert_pressure_to_pa(float(self.window.perf_p2_edit.text()), p2_unit),
            "t2_k": self.engine.convert_temperature_to_k(float(self.window.perf_t2_edit.text()), t2_unit),
            "flow_kgs": self.engine.convert_flow_to_kgs(
                float(self.window.perf_flow_edit.text()),
                flow_unit,
                gas_obj,
                eos_method,
            ),
            "rpm": performance_ui_float(self.window.perf_rpm_edit.text(), 0.0),
            "mech_eff": float(self.window.perf_mech_eff_edit.text()),
            "driver_mode": "turb_eff" if self.window.radio_turb_eff.isChecked() else "fuel_cons",
            "driver_val": float(
                self.window.perf_turb_eff_edit.text()
                if self.window.radio_turb_eff.isChecked()
                else self.window.perf_fuel_cons_edit.text()
            ),
            "gas_comp": gas_comp,
            "eos_method": eos_method,
            "lhv_source": lhv_source_from_ui_text(self.window.perf_lhv_source_combo.currentText()),
            "site_correction_inputs": {
                "standard": self.window.perf_standard_combo.currentText(),
                "ambient_temp_c": ambient_temp_k - 273.15,
                "ambient_pressure_kpa": ambient_pressure_kpa,
                "relative_humidity_pct": performance_ui_float(self.window.perf_humidity_edit.text(), 60.0),
                "altitude_m": performance_ui_float(self.window.perf_altitude_edit.text(), 0.0),
                "inlet_pressure_loss_kpa": convert_pressure_delta_to_kpa(
                    self.window.perf_inlet_loss_edit.text(), inlet_loss_unit
                ),
                "exhaust_pressure_loss_kpa": convert_pressure_delta_to_kpa(
                    self.window.perf_exhaust_loss_edit.text(), exhaust_loss_unit
                ),
                "manual_power_factor": performance_ui_float(self.window.perf_manual_power_factor_edit.text(), 1.0),
                "manual_heat_rate_factor": performance_ui_float(
                    self.window.perf_manual_heat_rate_factor_edit.text(), 1.0
                ),
            },
        }
        return inputs, flow_unit


class PerformanceResultsPresenter:
    """Render performance results back to the UI."""

    def __init__(self, window):
        self.window = window

    def apply(self, results):
        self.window.perf_res_poly_eff.setText(f"%{results['poly_eff']:.2f}")
        self.window.perf_res_isen_eff.setText(f"%{results['isen_eff']:.2f}")
        self.window.perf_res_head.setText(f"{results['poly_head_kj_kg']:.1f}")
        self.window.perf_res_power_gas.setText(f"{results['gas_power_kw']:.0f}")
        self.window.perf_res_power_shaft.setText(
            f"Motor: {results['motor_power_kw']:.0f} | Saft: {results['shaft_power_kw']:.0f}"
        )
        if hasattr(self.window, "perf_res_corrected"):
            self.window.perf_res_corrected.setText(
                f"Guc: {results.get('corrected_power_kw', 0.0):.0f} kW | "
                f"Isi Orani: {results.get('corrected_heat_rate', 0.0):.0f} kJ/kWh"
            )

        if self.window.radio_turb_eff.isChecked():
            self.window.perf_res_fuel_lbl.setText("Hesaplanan Yakit [kg/h]:")
            self.window.perf_res_fuel_or_eff.setText(f"{results['fuel_cons_kg_h']:.1f}")
        else:
            self.window.perf_res_fuel_lbl.setText("Hesaplanan Turbin Verimi:")
            self.window.perf_res_fuel_or_eff.setText(f"%{results['turb_eff']:.1f}")


class PerformanceEvaluationController:
    """Handle performance evaluation workflow outside the main window class."""

    def __init__(self, window, *, engine):
        self.window = window
        self.engine = engine
        self.logger = logging.getLogger(self.__class__.__name__)
        self.input_binder = PerformanceInputBinder(window, engine=engine)
        self.results_presenter = PerformanceResultsPresenter(window)

    def toggle_driver_inputs(self):
        state = get_driver_input_mode_state(self.window.radio_turb_eff.isChecked())
        self.window.perf_turb_eff_edit.setEnabled(state["turb_eff_enabled"])
        self.window.perf_fuel_cons_edit.setEnabled(state["fuel_cons_enabled"])
        self.window.perf_turb_eff_edit.setText(state["turb_eff_text"])
        self.window.perf_fuel_cons_edit.setText(state["fuel_cons_text"])

    @staticmethod
    def _qt_message_box():
        from PyQt5.QtWidgets import QMessageBox

        return QMessageBox

    def _collect_report_context(self, flow_unit):
        return {
            "unit_name": self.window.project_name_edit.text() or "Performans Testi",
            "p_in": self.window.perf_p1_edit.text(),
            "p_in_unit": self.window.perf_p1_unit_combo.currentText(),
            "t_in": self.window.perf_t1_edit.text(),
            "t_in_unit": self.window.perf_t1_unit_combo.currentText(),
            "p_out": self.window.perf_p2_edit.text(),
            "p_out_unit": self.window.perf_p2_unit_combo.currentText(),
            "t_out": self.window.perf_t2_edit.text(),
            "t_out_unit": self.window.perf_t2_unit_combo.currentText(),
            "flow": self.window.perf_flow_edit.text(),
            "flow_unit": flow_unit,
            "performance_standard": self.window.perf_standard_combo.currentText(),
        }

    def build_report_payload(self, report_inputs, raw_results):
        return build_performance_report_payload(
            report_inputs,
            raw_results,
            design_inputs=self.window.last_design_inputs,
            design_results=self.window.last_design_results_raw,
            evaluate_status_fn=self.engine._evaluate_performance_status,
        )

    def run_evaluation(self):
        try:
            inputs, flow_unit = self.input_binder.collect()
            if inputs is None:
                return

            standard = inputs["site_correction_inputs"].get("standard", "ASME PTC 10")
            self.window.append_log(f"[INFO] Performans degerlendirmesi baslatildi ({standard}).")
            results = self.engine.evaluate_performance(inputs)

            report_inputs = build_performance_report_inputs(
                self._collect_report_context(flow_unit),
                inputs,
                results,
                design_inputs=self.window.last_design_inputs,
            )
            self.window.last_perf_inputs, self.window.last_perf_results = self.build_report_payload(
                report_inputs, results
            )

            self.results_presenter.apply(results)

            dim_result = self._compute_perf_dimensionless(inputs, results)
            if dim_result:
                results["_dimensionless"] = dim_result
                self._display_dimensionless(dim_result)

            self.window.append_log("[SUCCESS] Performans degerlendirmesi basariyla tamamlandi.")

        except Exception as exc:
            self.logger.error("Performans degerlendirme UI hatasi: %s", exc)
            self._qt_message_box().critical(
                self.window,
                "Hata",
                f"Degerlendirme sirasinda hata olustu:\n{exc}",
            )

    def _compute_perf_dimensionless(self, inputs, engine_results):
        D_mm = self.window.perf_impeller_D_edit.text().strip()
        b_mm = self.window.perf_impeller_b_edit.text().strip()
        rpm_text = self.window.perf_rpm_edit.text().strip()

        if not D_mm or not rpm_text:
            self.window.perf_res_psi.setText("-")
            self.window.perf_res_phi.setText("-")
            self.window.perf_res_Re.setText("-")
            self.window.perf_res_Ma.setText("-")
            self.window.perf_res_similarity.setText("")
            return None

        try:
            D_m = float(D_mm) / 1000.0
            speed_rpm = float(rpm_text)
            b_m = float(b_mm) / 1000.0 if b_mm else D_m * 0.05
        except (ValueError, TypeError):
            return None

        gas_obj = self.engine._create_gas_object(inputs["gas_comp"], inputs["eos_method"])
        p1 = inputs["p1_pa"]
        t1 = inputs["t1_k"]
        state_in = self.engine.thermo_solver.get_properties(p1, t1, gas_obj, inputs["eos_method"])
        flow_kgs = inputs["flow_kgs"]
        Q_m3s = flow_kgs / state_in.density if state_in.density > 0 else 0.0
        head_pol = engine_results.get("poly_head_kj_kg", 0) * 1000.0

        from kasp.core.aerodynamics import CompressorAerodynamics
        dim_result = CompressorAerodynamics.calculate_dimensionless(
            head_pol, Q_m3s, state_in, speed_rpm=speed_rpm, D_m=D_m, b_m=b_m
        )

        if self.window.last_design_results_raw and self.window.last_design_results_raw.get("dimensionless"):
            ref_dim = self.window.last_design_results_raw["dimensionless"]
            from kasp.core.compliance import check_ptc10_similarity
            similarity = check_ptc10_similarity(ref_dim, dim_result)
            dim_result["_similarity"] = similarity

        return dim_result

    def _display_dimensionless(self, dim_result):
        self.window.perf_res_psi.setText(f"{dim_result.get('psi', 0):.4f}")
        self.window.perf_res_phi.setText(f"{dim_result.get('phi', 0):.4f}")
        self.window.perf_res_Re.setText(f"{dim_result.get('Re', 0):.2e}")
        self.window.perf_res_Ma.setText(f"{dim_result.get('Ma', 0):.4f}")

        sim = dim_result.get("_similarity")
        if sim and sim.get("all_ok"):
            self.window.perf_res_similarity.setText(
                "✅ ASME PTC 10 benzerlik sartlari saglandi."
            )
            self.window.perf_res_similarity.setStyleSheet("color: #2e7d32; font-weight: bold;")
        elif sim:
            failed = [k for k, v in sim.items() if k != "all_ok" and not v.get("ok", True)]
            self.window.perf_res_similarity.setText(
                f"❌ Benzerlik saglanamadi: {', '.join(failed)}"
            )
            self.window.perf_res_similarity.setStyleSheet("color: #c62828;")
        else:
            self.window.perf_res_similarity.setText("")
            self.window.perf_res_similarity.setStyleSheet("")
