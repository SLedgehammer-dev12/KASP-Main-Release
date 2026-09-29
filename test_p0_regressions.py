"""P0 regression tests: numerical trust fixes (energy balance, method-5 convergence,
solver residual validation, health bridge, fallback traceability/cache safety).
"""

import logging

import pytest

from kasp.core.properties import ThermodynamicSolver
from kasp.core.mixture import GasMixtureBuilder
from kasp.core.models import ThermodynamicState


def _methane_thermo_obj():
    return GasMixtureBuilder.build_thermo_data(
        GasMixtureBuilder.validate_and_normalize({"METHANE": 1.0})
    )


# ── P0-1: non-physical Δh is marked, not silently corrected ──────────────────

def test_design_payload_marks_invalid_energy_balance():
    from kasp.core.thermo_design_support import build_design_results_payload

    staged = [
        {
            "stage": 1,
            "delta_h_kj_kg": 10.0,
            "energy_balance_ok": False,
            "delta_h_source": "head_over_eta",
            "compressor_selectable": False,
            "selection_warnings": ["Non-fiziksel enerji dengesi"],
            "analysis_scope": "INVALID",
        }
    ]
    results = build_design_results_payload(
        p_in_pa=1e5,
        t_in_k=300.0,
        p_out_pa=5e5,
        final_t_out_k=400.0,
        total_poly_head_kj_kg=100.0,
        poly_eff_tgt=85.0,
        total_stage_gas_power_kw=10.0,
        total_shaft_kw=12.0,
        motor_kw=13.0,
        unit_kw=14.0,
        mech_loss_kw=2.0,
        fuel_kgh=1.0,
        mass_flow_per_unit=1.0,
        inlet_acmh=100.0,
        num_units=1,
        total_mass_flow_kgs=1.0,
        heat_rate=9000.0,
        lhv=50000.0,
        hhv=55000.0,
        inlet_properties={},
        outlet_properties={},
        num_stages=1,
        staged_results=staged,
        method="Metot 5: Huntington-RK45",
    )

    assert results["analysis_scope"] == "INVALID"
    assert results["energy_balance_ok"] is False
    assert results["compressor_selectable"] is False
    assert any("enerji dengesi" in w.lower() for w in results["warnings"])


# ── P0-2: method-5 convergence contract ──────────────────────────────────────

def test_method5_history_contract_fixed_step():
    from kasp.core.thermo_methods import ThermoMethodSuite

    suite = ThermoMethodSuite(thermo_solver=ThermodynamicSolver(), logger=logging.getLogger("t5"))
    gas_obj = GasMixtureBuilder.build_thermo_data(
        GasMixtureBuilder.validate_and_normalize({"METHANE": 0.9, "ETHANE": 0.1})
    )

    _, _, _, hist = suite.method_huntington_rk45(
        2e6, 300.0, 6e6, 0.85, gas_obj, "pr", step_count=10, adaptive=False
    )
    assert hist["converged"] is True
    assert hist["termination_reason"] == "fixed_step"


def test_method5_history_contract_adaptive():
    from kasp.core.thermo_methods import ThermoMethodSuite

    suite = ThermoMethodSuite(thermo_solver=ThermodynamicSolver(), logger=logging.getLogger("t5"))
    gas_obj = GasMixtureBuilder.build_thermo_data(
        GasMixtureBuilder.validate_and_normalize({"METHANE": 0.9, "ETHANE": 0.1})
    )

    _, _, _, hist = suite.method_huntington_rk45(
        2e6, 300.0, 6e6, 0.85, gas_obj, "pr", step_count=20, adaptive=True
    )
    assert hist["converged"] in (True, False)
    assert hist["termination_reason"] in {
        "converged",
        "fixed_step",
        "max_iterations",
        "h_min_tolerance_exceeded",
    }


# ── P0-3: SolverChain validates residual before accepting ────────────────────

def _state_in():
    return ThermodynamicState(
        P=1e5, T=300.0, H=0.0, S=0.0, Z=1.0, k=1.3, MW=28.0,
        Cp=1000.0, Cv=700.0, density=1.0, phase="gas",
    )


def test_solver_chain_skips_nonconverged_first_solver(monkeypatch):
    from kasp.core import aerodynamics as aero
    from kasp.core import fallback as fb

    tracker = fb.FallbackTracker()
    chain = fb.SolverChain(tracker)

    monkeypatch.setattr(
        aero.CompressorAerodynamics, "calculate_isentropic_temp_fd_nr",
        staticmethod(lambda *a, **k: (350.0, 5, 50.0)),
    )
    monkeypatch.setattr(
        aero.CompressorAerodynamics, "calculate_isentropic_temp_aj_nr",
        staticmethod(lambda *a, **k: (340.0, 4, 0.2)),
    )
    monkeypatch.setattr(
        aero.CompressorAerodynamics, "calculate_isentropic_temp_brent",
        staticmethod(lambda *a, **k: (341.0, 6, 1.0)),
    )

    T = chain.find_isentropic_temp(_state_in(), 5e5, None, None, "pr", solver_method="auto")
    assert T == 340.0
    assert tracker.solver_nonconverged_info() == {}


def test_solver_chain_marks_when_no_solver_converges(monkeypatch):
    from kasp.core import aerodynamics as aero
    from kasp.core import fallback as fb

    tracker = fb.FallbackTracker()
    chain = fb.SolverChain(tracker)

    monkeypatch.setattr(
        aero.CompressorAerodynamics, "calculate_isentropic_temp_fd_nr",
        staticmethod(lambda *a, **k: (350.0, 5, 50.0)),
    )
    monkeypatch.setattr(
        aero.CompressorAerodynamics, "calculate_isentropic_temp_aj_nr",
        staticmethod(lambda *a, **k: (345.0, 4, 40.0)),
    )
    monkeypatch.setattr(
        aero.CompressorAerodynamics, "calculate_isentropic_temp_brent",
        staticmethod(lambda *a, **k: (341.0, 6, 30.0)),
    )

    T = chain.find_isentropic_temp(_state_in(), 5e5, None, None, "pr", solver_method="auto")
    assert T == 341.0  # brent has the smallest residual and is chosen
    info = tracker.solver_nonconverged_info()
    assert "brent" in info


# ── P0-4: health info reaches the result bridge ──────────────────────────────

def test_health_bridge_exposes_health_fields():
    from kasp.core.thermo import ThermoEngine

    engine = ThermoEngine()
    gas_obj = engine._create_gas_object({"METHANE": 1.0}, "pr")
    props = engine._get_thermo_properties(1e5, -50.0, gas_obj, "pr")

    assert "thermo_health" in props
    assert props["thermo_health"] in ("WARNING", "CRITICAL")
    assert isinstance(props["health_reasons"], list)
    assert props["fallback"] is True


def test_engineering_health_table_shows_critical():
    pytest.importorskip("PyQt5", reason="PyQt5 required")
    from PyQt5.QtWidgets import QApplication, QTableWidget

    from kasp.ui.engineering_tab_builders import _populate_health

    app = QApplication.instance() or QApplication([])
    table = QTableWidget()
    table.setColumnCount(5)
    results = {
        "inlet_properties": {
            "Z": 0.2,
            "phase": "two-phase",
            "thermo_health": "CRITICAL",
            "health_reasons": ["Akışkan iki fazlı bölgeye girdi"],
        },
        "outlet_properties": {},
    }
    _populate_health(table, results)
    assert table.rowCount() == 1
    assert table.item(0, 3).text() == "CRITICAL"
    assert "iki fazlı" in table.item(0, 4).text()


# ── P0-5: fallback states are traceable and never poison the cache ───────────

def test_fallback_state_is_marked_and_not_cached():
    solver = ThermodynamicSolver()
    gas_obj = _methane_thermo_obj()

    state = solver.get_properties(1e5, -50.0, gas_obj, "pr")

    assert state.raw_props.get("fallback") is True
    assert state.raw_props.get("thermo_health") in ("WARNING", "CRITICAL")
    assert state.raw_props.get("health_reasons")
    assert solver.get_cache_stats()["size"] == 0


def test_effective_eos_surface_defaults_to_requested():
    from kasp.core.thermo import ThermoEngine

    engine = ThermoEngine()
    inputs = {
        "project_name": "P0 effective eos",
        "p_in": 20.0,
        "p_in_unit": "bar(a)",
        "t_in": 30.0,
        "t_in_unit": "°C",
        "p_out": 60.0,
        "p_out_unit": "bar(a)",
        "flow": 10.0,
        "flow_unit": "kg/s",
        "gas_comp": {"METHANE": 90.0, "ETHANE": 10.0},
        "eos_method": "pr",
        "method": "Metot 1: Ortalama Özellikler",
        "poly_eff": 85.0,
        "therm_eff": 35.0,
        "mech_eff": 98.0,
        "num_units": 1,
        "num_stages": 1,
        "enable_uncertainty": False,
    }
    results = engine.calculate_design_performance(inputs)
    assert results.get("requested_eos") == "pr"
    assert results.get("effective_eos") in ("pr", "srk", "thermopack", "aga8", "neqsim", "coolprop")


def test_schultz_factor_isothermal_limit_consistency():
    import math
    from kasp.core.aerodynamics import CompressorAerodynamics

    solver = ThermodynamicSolver()
    gas_obj = _methane_thermo_obj()
    r_spec = 8314.462618 / 16.043

    s_in = solver.get_properties(20e5, 300.0, gas_obj, "pr")
    # Isothermal state (T_out == T_in => sigma == 0)
    s_out_iso = solver.get_properties(60e5, 300.0, gas_obj, "pr")
    # Near-isothermal state (T_out = 300.01 K => sigma ~ 3e-5)
    s_out_near = solver.get_properties(60e5, 300.01, gas_obj, "pr")

    f_iso = CompressorAerodynamics.calculate_schultz_factor(
        s_in, s_out_iso, 60e5, solver, gas_obj, "pr", r_spec
    )
    f_near = CompressorAerodynamics.calculate_schultz_factor(
        s_in, s_out_near, 60e5, solver, gas_obj, "pr", r_spec
    )
    assert math.isclose(f_iso, f_near, rel_tol=1e-3)


def test_coolprop_string_mw_inference_prevents_air_fallback():
    solver = ThermodynamicSolver()
    mw = solver.infer_mw_g_mol("HEOS::Methane[0.9]&Ethane[0.1]")
    assert mw is not None
    # 0.9 * 16.043 + 0.1 * 30.07 = 17.4457 g/mol (not 28.96 Air!)
    assert 17.0 < mw < 18.0


def test_intercooler_temperature_fahrenheit_conversion():
    from kasp.core.thermo import ThermoEngine

    engine = ThermoEngine()
    ctx = engine._prepare_design_context(
        {
            "p_in": 10.0,
            "p_in_unit": "bar(a)",
            "t_in": 30.0,
            "t_in_unit": "°C",
            "p_out": 40.0,
            "p_out_unit": "bar(a)",
            "flow": 10.0,
            "flow_unit": "kg/s",
            "gas_comp": {"METHANE": 100.0},
            "intercooler_t": 104.0,
            "intercooler_t_unit": "°F",
        }
    )
    # 104 °F == 40 °C == 313.15 K
    assert ctx["ic_t_k"] == pytest.approx(313.15, abs=0.05)


def test_evaluate_performance_clamps_efficiency_and_warns():
    from kasp.core.thermo import ThermoEngine

    engine = ThermoEngine()
    # Outlet temperature above inlet (so actual_dh > 0) but below isentropic T2s (~410 K) => raw_isen_eff > 1.0
    res = engine.evaluate_performance(
        {
            "p1_pa": 20e5,
            "t1_k": 303.15,
            "p2_pa": 60e5,
            "t2_k": 350.15,
            "flow_kgs": 10.0,
            "mech_eff": 98.0,
            "driver_mode": "turb_eff",
            "driver_val": 150.0,
            "gas_comp": {"NITROGEN": 100.0},
            "eos_method": "pr",
        }
    )
    assert 0.0 <= res["isen_eff"] <= 100.0
    assert 0.0 <= res["turb_eff"] <= 100.0
    # Inert gas (N2) must not fabricate fuel consumption via 50,000 kJ/kg LHV fallback
    assert res["fuel_cons_kg_h"] == 0.0
    assert res.get("warnings")


def test_performance_report_generation_no_keyerror(tmp_path):
    from kasp.core.thermo import ThermoEngine
    from kasp.utils.reporting import ReportGenerator

    engine = ThermoEngine()
    eval_inputs = {
        "p1_pa": 20e5,
        "t1_k": 303.15,
        "p2_pa": 50e5,
        "t2_k": 398.15,
        "flow_kgs": 12.0,
        "mech_eff": 98.0,
        "driver_mode": "turb_eff",
        "driver_val": 34.0,
        "gas_comp": {"METHANE": 95.0, "ETHANE": 5.0},
        "eos_method": "pr",
    }
    results = engine.evaluate_performance(eval_inputs)
    report_inputs = {
        "project_name": "Perf Report Check",
        "p_in": 20.0,
        "p_in_unit": "bar(a)",
        "t_in": 30.0,
        "t_in_unit": "°C",
        "p_out": 50.0,
        "p_out_unit": "bar(a)",
        "t_out": 125.0,
        "t_out_unit": "°C",
        "flow": 12.0,
        "flow_unit": "kg/s",
        "gas_comp": {"METHANE": 95.0, "ETHANE": 5.0},
        "eos_method": "pr",
        "ambient_temp": 20.0,
        "ambient_pressure": 101.325,
    }
    pdf_path = tmp_path / "perf_report.pdf"
    gen = ReportGenerator(str(pdf_path), engine)
    ok = gen.generate_performance_report(report_inputs, results)
    assert ok is True
    assert pdf_path.exists() and pdf_path.stat().st_size > 1000

