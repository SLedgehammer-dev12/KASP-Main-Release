"""Performance evaluation helpers and controller for the KASP UI."""

from __future__ import annotations

import logging

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


def build_performance_report_inputs(ui_context, inputs, results, *, design_inputs=None):
    design_inputs = design_inputs or {}

    return {
        "unit_name": ui_context.get("unit_name") or "Performans Testi",
        "p_in": performance_ui_float(ui_context.get("p_in"), 0.0),
        "p_in_unit": "bar(g)",
        "t_in": performance_ui_float(ui_context.get("t_in"), 0.0),
        "t_in_unit": "°C",
        "p_out": performance_ui_float(ui_context.get("p_out"), 0.0),
        "p_out_unit": "bar(g)",
        "t_out": performance_ui_float(ui_context.get("t_out"), 0.0),
        "t_out_unit": "°C",
        "flow": performance_ui_float(ui_context.get("flow"), 0.0),
        "flow_unit": ui_context.get("flow_unit", "kg/s"),
        "flow_kgs": inputs["flow_kgs"],
        "p1_pa": inputs["p1_pa"],
        "p2_pa": inputs["p2_pa"],
        "fuel_flow": results.get("fuel_cons_kg_h", 0.0),
        "fuel_flow_unit": "kg/h",
        "ambient_temp": design_inputs.get("ambient_temp", performance_ui_float(ui_context.get("t_in"), 0.0)),
        "ambient_pressure": design_inputs.get("ambient_pressure", 101.325),
        "humidity": design_inputs.get("humidity", 60.0),
        "altitude": design_inputs.get("altitude", 0.0),
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
        "test_conditions": {
            "mass_flow": test_mass_flow,
            "fuel_flow": fuel_flow_kgh,
            "compression_ratio": compression_ratio,
            "head": poly_head,
        },
        "corrected_values": {
            "correction_factors": {
                "temperature": performance_ui_float(report_inputs.get("ambient_temp", 15.0), 15.0),
                "pressure": performance_ui_float(report_inputs.get("ambient_pressure", 101.325), 101.325),
                "humidity": performance_ui_float(report_inputs.get("humidity", 60.0), 60.0),
                "altitude": performance_ui_float(report_inputs.get("altitude", 0.0), 0.0),
            }
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
                "Uyarı",
                (
                    f"Gaz kompozisyonları toplamı %100 değil (Şu anki: %{total_percentage:.2f}).\n"
                    "Normalizasyon yapılsın mı?"
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
        flow_unit = self.window.perf_flow_unit_combo.currentText()

        inputs = {
            "p1_pa": self.engine.convert_pressure_to_pa(float(self.window.perf_p1_edit.text()), "bar(g)"),
            "t1_k": self.engine.convert_temperature_to_k(float(self.window.perf_t1_edit.text()), "°C"),
            "p2_pa": self.engine.convert_pressure_to_pa(float(self.window.perf_p2_edit.text()), "bar(g)"),
            "t2_k": self.engine.convert_temperature_to_k(float(self.window.perf_t2_edit.text()), "°C"),
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
            f"Motor: {results['motor_power_kw']:.0f} | Şaft: {results['shaft_power_kw']:.0f}"
        )

        if self.window.radio_turb_eff.isChecked():
            self.window.perf_res_fuel_lbl.setText("Hesaplanan Yakıt [kg/h]:")
            self.window.perf_res_fuel_or_eff.setText(f"{results['fuel_cons_kg_h']:.1f}")
        else:
            self.window.perf_res_fuel_lbl.setText("Hesaplanan Türbin Verimi:")
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
            "t_in": self.window.perf_t1_edit.text(),
            "p_out": self.window.perf_p2_edit.text(),
            "t_out": self.window.perf_t2_edit.text(),
            "flow": self.window.perf_flow_edit.text(),
            "flow_unit": flow_unit,
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

            self.window.append_log("[INFO] Performans değerlendirmesi başlatıldı (ASME PTC 10).")
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
            self.window.append_log("[SUCCESS] Performans değerlendirmesi başarıyla tamamlandı.")

        except Exception as exc:
            self.logger.error("Performans değerlendirme UI hatası: %s", exc)
            self._qt_message_box().critical(
                self.window,
                "Hata",
                f"Değerlendirme sırasında hata oluştu:\n{exc}",
            )
