from kasp.ui.performance_workflow import (
    PerformanceInputBinder,
    PerformanceEvaluationController,
    PerformanceResultsPresenter,
    build_performance_report_inputs,
    build_performance_report_payload,
    get_driver_input_mode_state,
    performance_eff_to_decimal,
)


class DummyEdit:
    def __init__(self, value):
        self._value = value
        self.enabled = True

    def text(self):
        return self._value

    def setText(self, value):
        self._value = value

    def setEnabled(self, enabled):
        self.enabled = enabled


class DummyCombo:
    def __init__(self, value):
        self._value = value

    def currentText(self):
        return self._value


class DummyRadio:
    def __init__(self, checked):
        self._checked = checked

    def isChecked(self):
        return self._checked


class DummyLabel:
    def __init__(self):
        self.value = None

    def setText(self, value):
        self.value = value


class DummyMessageBox:
    Yes = 1
    No = 2
    critical_calls = []
    warning_calls = []

    @classmethod
    def critical(cls, *args):
        cls.critical_calls.append(args)

    @classmethod
    def warning(cls, *args):
        cls.warning_calls.append(args)
        return cls.Yes


class DummyEngine:
    def _create_gas_object(self, gas_comp, eos_method):
        return {"gas_comp": gas_comp, "eos_method": eos_method}

    def convert_pressure_to_pa(self, value, unit):
        assert unit == "bar(g)"
        return value * 100000.0

    def convert_temperature_to_k(self, value, unit):
        assert unit == "°C"
        return value + 273.15

    def convert_flow_to_kgs(self, value, unit, gas_obj, eos_method):
        assert unit == "kg/s"
        assert gas_obj["eos_method"] == eos_method
        return value


class DummyPerformanceWindow:
    def __init__(self, *, turb_eff_mode=True):
        self.eos_method_combo = DummyCombo("CoolProp")
        self.perf_lhv_source_combo = DummyCombo("Thermo Veritabanı")
        self.perf_flow_unit_combo = DummyCombo("kg/s")
        self.perf_p1_edit = DummyEdit("1.2")
        self.perf_t1_edit = DummyEdit("25")
        self.perf_p2_edit = DummyEdit("4.8")
        self.perf_t2_edit = DummyEdit("95")
        self.perf_flow_edit = DummyEdit("12.5")
        self.perf_rpm_edit = DummyEdit("5200")
        self.perf_mech_eff_edit = DummyEdit("97")
        self.perf_turb_eff_edit = DummyEdit("31")
        self.perf_fuel_cons_edit = DummyEdit("580")
        self.radio_turb_eff = DummyRadio(turb_eff_mode)
        self.project_name_edit = DummyEdit("GT-1")
        self.perf_res_poly_eff = DummyLabel()
        self.perf_res_isen_eff = DummyLabel()
        self.perf_res_head = DummyLabel()
        self.perf_res_power_gas = DummyLabel()
        self.perf_res_power_shaft = DummyLabel()
        self.perf_res_fuel_lbl = DummyLabel()
        self.perf_res_fuel_or_eff = DummyLabel()
        self.normalized = False

    def _get_gas_composition(self):
        return {"Methane": 100.0}

    def normalize_composition(self):
        self.normalized = True


def test_performance_eff_to_decimal_supports_percent_and_decimal_inputs():
    assert performance_eff_to_decimal(78.5) == 0.785
    assert performance_eff_to_decimal(0.82) == 0.82
    assert performance_eff_to_decimal("bad", default=0.4) == 0.4


def test_build_performance_report_inputs_uses_design_site_conditions_when_available():
    payload = build_performance_report_inputs(
        {
            "unit_name": "GT-1",
            "p_in": "1.2",
            "t_in": "25",
            "p_out": "4.8",
            "t_out": "95",
            "flow": "12.5",
            "flow_unit": "kg/s",
        },
        {"flow_kgs": 12.5, "p1_pa": 120000.0, "p2_pa": 480000.0},
        {"fuel_cons_kg_h": 640.0},
        design_inputs={"ambient_temp": 18.0, "ambient_pressure": 99.1, "humidity": 45.0, "altitude": 850.0},
    )

    assert payload["unit_name"] == "GT-1"
    assert payload["ambient_temp"] == 18.0
    assert payload["ambient_pressure"] == 99.1
    assert payload["humidity"] == 45.0
    assert payload["altitude"] == 850.0
    assert payload["flow_kgs"] == 12.5
    assert payload["fuel_flow"] == 640.0


def test_build_performance_report_payload_computes_expected_metrics_and_status():
    report_inputs = {
        "flow_kgs": 12.5,
        "fuel_flow": 640.0,
        "p1_pa": 120000.0,
        "p2_pa": 480000.0,
        "ambient_temp": 18.0,
        "ambient_pressure": 99.1,
        "humidity": 45.0,
        "altitude": 850.0,
    }
    raw_results = {
        "poly_eff": 78.0,
        "actual_therm_eff": 29.0,
        "actual_heat_rate": 11200.0,
        "shaft_power_kw": 4200.0,
        "poly_head_kj_kg": 165.0,
    }

    _, payload = build_performance_report_payload(
        report_inputs,
        raw_results,
        design_inputs={"therm_eff": 32.0},
        design_results={"design_poly_efficiency": 0.81, "heat_rate": 10500.0, "power_shaft_per_unit_kw": 4000.0},
        evaluate_status_fn=lambda values: "ok" if values["deviation_power"] >= 5.0 else "check",
    )

    assert payload["actual_poly_eff"] == 0.78
    assert payload["design_poly_eff"] == 0.81
    assert round(payload["deviation_power"], 2) == 5.0
    assert payload["test_conditions"]["compression_ratio"] == 4.0
    assert payload["corrected_values"]["correction_factors"]["pressure"] == 99.1
    assert payload["performance_status"] == "ok"


def test_performance_input_binder_collects_engine_inputs_without_qt():
    binder = PerformanceInputBinder(
        DummyPerformanceWindow(),
        engine=DummyEngine(),
        message_box_factory=lambda: DummyMessageBox,
    )

    inputs, flow_unit = binder.collect()

    assert flow_unit == "kg/s"
    assert inputs["p1_pa"] == 120000.0
    assert round(inputs["t1_k"], 2) == 298.15
    assert inputs["flow_kgs"] == 12.5
    assert inputs["driver_mode"] == "turb_eff"
    assert inputs["driver_val"] == 31.0
    assert inputs["lhv_source"] == "thermo"


def test_performance_results_presenter_formats_turbine_efficiency_mode():
    window = DummyPerformanceWindow(turb_eff_mode=False)
    presenter = PerformanceResultsPresenter(window)

    presenter.apply(
        {
            "poly_eff": 78.4,
            "isen_eff": 74.2,
            "poly_head_kj_kg": 165.3,
            "gas_power_kw": 3900.0,
            "motor_power_kw": 4100.0,
            "shaft_power_kw": 4050.0,
            "fuel_cons_kg_h": 612.8,
            "turb_eff": 30.5,
        }
    )

    assert window.perf_res_poly_eff.value == "%78.40"
    assert window.perf_res_power_shaft.value == "Motor: 4100 | Şaft: 4050"
    assert window.perf_res_fuel_lbl.value == "Hesaplanan Türbin Verimi:"
    assert window.perf_res_fuel_or_eff.value == "%30.5"


def test_get_driver_input_mode_state_switches_active_input_defaults():
    assert get_driver_input_mode_state(True) == {
        "turb_eff_enabled": True,
        "fuel_cons_enabled": False,
        "turb_eff_text": "35.0",
        "fuel_cons_text": "",
    }
    assert get_driver_input_mode_state(False) == {
        "turb_eff_enabled": False,
        "fuel_cons_enabled": True,
        "turb_eff_text": "",
        "fuel_cons_text": "500.0",
    }


def test_performance_controller_toggle_driver_inputs_updates_widgets():
    window = DummyPerformanceWindow(turb_eff_mode=False)
    controller = PerformanceEvaluationController(window, engine=DummyEngine())

    controller.toggle_driver_inputs()

    assert window.perf_turb_eff_edit.text() == ""
    assert window.perf_turb_eff_edit.enabled is False
    assert window.perf_fuel_cons_edit.text() == "500.0"
    assert window.perf_fuel_cons_edit.enabled is True
