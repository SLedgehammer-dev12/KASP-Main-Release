import logging

import pytest

from kasp.core.models import ThermodynamicState
from kasp.core.thermo import ThermoEngine
from kasp.core.thermo_design_support import apply_fallback_tracking
from kasp.core.thermo_design_support import build_design_results_payload, summarize_method_convergence
from kasp.core.thermo_methods import ThermoMethodSuite
from kasp.ui.design_results_workflow import (
    build_design_summary_text,
    build_fallback_info_html,
    build_method_convergence_summary_lines,
)


def build_design_inputs(method="Metot 1: Ortalama Ozellikler"):
    return {
        "p_in": 20.0,
        "p_in_unit": "bar",
        "t_in": 30.0,
        "t_in_unit": "°C",
        "p_out": 60.0,
        "p_out_unit": "bar",
        "flow": 50000.0,
        "flow_unit": "kg/h",
        "gas_comp": {"METHANE": 90.0, "ETHANE": 5.0, "PROPANE": 5.0},
        "eos_method": "coolprop",
        "method": method,
        "poly_eff": 85.0,
        "num_units": 1,
        "num_stages": 1,
        "therm_eff": 35.0,
        "mech_eff": 98.0,
        "intercooler_dp_pct": 0.0,
        "intercooler_t": 40.0,
        "enable_uncertainty": False,
    }


class FakeThermoSolver:
    def get_properties(self, P_pa, T_k, gas_obj, eos_method):
        return ThermodynamicState(
            P=P_pa,
            T=T_k,
            H=2.0e5 + T_k * 2100.0,
            S=1200.0 + T_k * 2.0,
            Z=0.95,
            k=1.3,
            MW=18.0,
            Cp=2200.0,
            Cv=1692.3,
            density=max(P_pa / (461.5 * T_k), 0.1),
            phase="gas",
            raw_props={"fallback": False, "speed_of_sound": 360.0},
        )


def build_method_suite():
    return ThermoMethodSuite(
        thermo_solver=FakeThermoSolver(),
        logger=logging.getLogger("test-thermo-methods"),
    )


def test_design_calculation_routes_through_orchestrator(monkeypatch):
    pytest.importorskip("CoolProp", reason="Design refactor test requires CoolProp.")

    engine = ThermoEngine()
    captured = {}
    original = engine.design_orchestrator.run_stage_loop

    def wrapped(**kwargs):
        captured["method_key"] = kwargs["method_key"]
        return original(**kwargs)

    monkeypatch.setattr(engine.design_orchestrator, "run_stage_loop", wrapped)

    results = engine.calculate_design_performance(build_design_inputs("Metot 2: Endpoint"))

    assert captured["method_key"] == "endpoint"
    assert results["stages"]


def test_method_endpoint_coerces_invalid_iteration_limit():
    suite = build_method_suite()

    t_out, head, z_avg, history = suite.method_endpoint(
        2.0e6,
        303.15,
        6.0e6,
        0.85,
        "mock-gas",
        "mock",
        max_iter=0,
        tolerance=0,
    )

    assert t_out > 303.15
    assert head >= 0.0
    assert z_avg > 0.0
    assert history["iteration_limit"] == 1
    assert history["tolerance"] > 0.0


def test_incremental_method_caps_excessive_step_count():
    suite = build_method_suite()

    _, _, _, history = suite.method_incremental_pressure(
        2.0e6,
        303.15,
        6.0e6,
        0.85,
        "mock-gas",
        "mock",
        step_count=10000,
    )

    assert history["step_count"] == suite.MAX_INCREMENTAL_STEPS
    assert len(history["step"]) == suite.MAX_INCREMENTAL_STEPS + 1


def test_complex_coolprop_design_iteration_limit_is_capped():
    engine = ThermoEngine()
    inputs = build_design_inputs()
    inputs["eos_method"] = "coolprop"
    inputs["method_max_iter"] = 25
    inputs["gas_comp"] = {
        "METHANE": 85.0,
        "ETHANE": 5.0,
        "PROPANE": 2.0,
        "BUTANE": 1.0,
        "ISOBUTANE": 1.0,
        "PENTANE": 1.0,
        "CARBONDIOXIDE": 2.0,
        "NITROGEN": 3.0,
    }

    assert engine._limit_design_method_iterations(inputs, "coolprop", 25) == 3
    assert engine._limit_design_method_iterations(inputs, "pr", 25) == 25


def test_method_convergence_summary_flags_nonconverged_stage():
    staged_results = [
        {
            "stage": 1,
            "method_history": {
                "method_used": "averaging",
                "converged": False,
                "termination_reason": "max_iterations",
                "iteration": [0, 1, 2, 3],
                "iteration_limit": 3,
            },
        }
    ]

    summary = summarize_method_convergence(staged_results)

    assert summary == [
        {
            "stage": 1,
            "method_used": "averaging",
            "converged": False,
            "termination_reason": "max_iterations",
            "iteration_count": 3,
            "iteration_limit": 3,
        }
    ]


def test_design_payload_warns_when_method_did_not_converge():
    staged_results = [
        {
            "stage": 1,
            "delta_h_kj_kg": 100.0,
            "poly_eff_diagnostic": 0.82,
            "method_history": {
                "method_used": "averaging",
                "converged": False,
                "termination_reason": "max_iterations",
                "iteration": [0, 1, 2, 3],
                "iteration_limit": 3,
            },
        }
    ]

    payload = build_design_results_payload(
        p_in_pa=1.0e5,
        t_in_k=300.0,
        p_out_pa=2.0e5,
        final_t_out_k=340.0,
        total_poly_head_kj_kg=85.0,
        poly_eff_tgt=0.85,
        total_stage_gas_power_kw=100.0,
        total_shaft_kw=110.0,
        motor_kw=115.0,
        unit_kw=120.0,
        mech_loss_kw=10.0,
        fuel_kgh=20.0,
        mass_flow_per_unit=1.0,
        inlet_acmh=1000.0,
        num_units=1,
        total_mass_flow_kgs=1.0,
        heat_rate=10000.0,
        lhv=50000.0,
        hhv=55000.0,
        inlet_properties={},
        outlet_properties={},
        num_stages=1,
        staged_results=staged_results,
        method="Metot 1",
    )

    assert payload["method_converged"] is False
    assert payload["method_convergence"][0]["termination_reason"] == "max_iterations"
    assert any("yakinsamadi" in warning for warning in payload["warnings"])


def test_design_results_expose_real_speed_of_sound():
    pytest.importorskip("CoolProp", reason="Design refactor test requires CoolProp.")

    engine = ThermoEngine()
    results = engine.calculate_design_performance(build_design_inputs())

    assert results["design_poly_efficiency"] == pytest.approx(0.85, rel=1e-6)
    assert 0.0 < results["actual_poly_efficiency"] <= 1.0
    assert results["inlet_properties"]["a"] > 0.0
    assert results["outlet_properties"]["a"] > 0.0
    assert results["inlet_properties"]["a"] != pytest.approx(300.0)


def test_consistency_mode_stays_within_physical_efficiency_bounds():
    pytest.importorskip("CoolProp", reason="Design refactor test requires CoolProp.")

    engine = ThermoEngine()
    inputs = build_design_inputs()
    inputs.update(
        {
            "use_consistency_iteration": True,
            "max_consistency_iter": 10,
            "consistency_tolerance": 0.1,
        }
    )

    results = engine.calculate_design_performance_with_mode(inputs)

    assert 60.0 <= results["poly_eff_converged"] <= 95.0
    assert results["t_out"] < 500.0
    assert results["power_unit_kw"] < 10000.0


def test_design_results_report_fallback_usage(monkeypatch):
    engine = ThermoEngine()
    inputs = build_design_inputs()

    def fake_create_gas_object(composition, eos_method):
        return "mock-gas"

    def fake_get_properties(P_pa, T_k, gas_obj, eos_method):
        fallback = P_pa >= 5.0e6
        state = ThermodynamicState(
            P=P_pa,
            T=T_k,
            H=2.5e5 + (T_k - 273.15) * 1000.0,
            S=1200.0,
            Z=0.92,
            k=1.28,
            MW=18.0,
            Cp=2200.0,
            Cv=1718.0,
            density=12.0,
            phase="gas",
            raw_props={
                "fallback": fallback,
                "speed_of_sound": 360.0,
                "mu": 1.1e-5,
            },
        )
        engine.thermo_solver._record_run_tracking(P_pa, T_k, eos_method, state)
        return state

    def fake_run_stage_loop(**kwargs):
        state_in = engine.thermo_solver.get_properties(
            kwargs["p_in_pa"], kwargs["t_in_k"], kwargs["gas_obj"], kwargs["eos"]
        )
        state_out = engine.thermo_solver.get_properties(
            kwargs["p_out_pa"], kwargs["t_in_k"] + 45.0, kwargs["gas_obj"], kwargs["eos"]
        )
        return {
            "final_t_out_k": kwargs["t_in_k"] + 45.0,
            "total_stage_gas_power_kw": 900.0,
            "total_poly_head_kj_kg": 115.0,
            "staged_results": [
                {
                    "stage": 1,
                    "p_in": kwargs["p_in_pa"],
                    "t_in": kwargs["t_in_k"],
                    "p_out": kwargs["p_out_pa"],
                    "t_out": kwargs["t_in_k"] + 45.0,
                    "head_kj_kg": 115.0,
                    "poly_eff_design": kwargs["poly_eff_tgt"],
                    "poly_eff_diagnostic": 0.82,
                    "poly_eff": kwargs["poly_eff_tgt"],
                    "power_gas_kw": 900.0,
                    "delta_h_kj_kg": (state_out.H - state_in.H) / 1000.0,
                    "z_avg": 0.92,
                    "method_history": {"method_used": "mock"},
                    "fallback_used": True,
                    "fallback_sources": ["stage_outlet"],
                }
            ],
        }

    monkeypatch.setattr(engine, "_create_gas_object", fake_create_gas_object)
    monkeypatch.setattr(engine.thermo_solver, "get_properties", fake_get_properties)
    monkeypatch.setattr(engine.design_orchestrator, "run_stage_loop", fake_run_stage_loop)

    results = engine.calculate_design_performance(inputs)

    assert results["fallback_used"] is True
    assert results["fallback_stage_numbers"] == [1]
    assert results["fallback_state_count"] >= 1
    assert any("fallback" in warning.lower() for warning in results["warnings"])


def test_apply_fallback_tracking_adds_warning_context():
    results = {"warnings": []}
    fallback_tracking = {
        "fallback_used": True,
        "fallback_call_count": 4,
        "fallback_state_count": 2,
        "fallback_states": [{"pressure_bar_a": 60.0}],
    }
    staged_results = [{"stage": 1, "fallback_used": False}, {"stage": 2, "fallback_used": True}]

    updated = apply_fallback_tracking(
        results,
        fallback_tracking,
        staged_results,
        {"fallback_used": False},
        {"fallback_used": False},
    )

    assert updated["fallback_used"] is True
    assert updated["fallback_call_count"] == 4
    assert updated["fallback_stage_numbers"] == [2]
    assert "Etkilenen kademeler: 2" in updated["warnings"][0]


def test_design_summary_mentions_fallback():
    summary = {
        "project_name": "Fallback Demo",
        "basic_parameters": {
            "compression_ratio": 2.4,
            "total_power": 1500.0,
            "num_units": 1,
        },
        "efficiency_metrics": {"poly_efficiency": 0.85},
        "recommended_turbines": [],
    }
    results = {
        "fallback_used": True,
        "fallback_stage_numbers": [1, 2],
        "fallback_state_count": 3,
    }

    summary_text = build_design_summary_text(summary, results)

    assert "Fallback Uyarısı" in summary_text
    assert "1, 2" in summary_text


def test_design_summary_mentions_method_nonconvergence():
    summary = {
        "project_name": "Convergence Demo",
        "basic_parameters": {
            "compression_ratio": 2.4,
            "total_power": 1500.0,
            "num_units": 1,
        },
        "efficiency_metrics": {"poly_efficiency": 0.85},
        "recommended_turbines": [],
    }
    results = {
        "method_converged": False,
        "method_convergence": [
            {"stage": 1, "converged": False, "termination_reason": "max_iterations"}
        ],
    }

    lines = build_method_convergence_summary_lines(results)
    summary_text = build_design_summary_text(summary, results)

    assert "Yakinsamayan Kademeler: 1" in lines
    assert "Metot Yakinsama Uyarisi" in summary_text


def test_fallback_info_html_lists_preview_states():
    html = build_fallback_info_html(
        {
            "fallback_used": True,
            "fallback_stage_numbers": [2],
            "fallback_state_count": 2,
            "fallback_states": [
                {"pressure_bar_a": 60.0, "temperature_c": 140.2, "eos_method": "coolprop", "phase": "gas"},
                {"pressure_bar_a": 58.0, "temperature_c": 135.7, "eos_method": "coolprop", "phase": "gas"},
            ],
        }
    )

    assert "Fallback Uyarısı" in html
    assert "Etkilenen Kademeler" in html
    assert "60.00 bar(a) / 140.2°C" in html
