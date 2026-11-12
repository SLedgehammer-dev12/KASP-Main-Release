"""Konu #6 Regression & Accuracy Suite:
1. ASME PTC-10 / Schultz (1962) exact polytropic head factor & efficiency (ideal + real gas round-trip).
2. Case-insensitive canonical 6-method routing across ThermoEngine & CalculationService.
3. Real-gas Bridgman temperature exponent in Classical Methods 1-3 & Direct H-S at high pressure (50->180 bar).
4. Mass-flow-weighted multi-stage total polytropic efficiency under interstage VLE knockout.
5. ThermodynamicSolver sub-millikelvin cache resolution & CoolProp AbstractState fast path parity.
6. Real EOS thermodynamic states & turbine metrics in ChartDataBuilder (P-v, T-s, h-s, Sankey, k-Z, Radar).
"""

from __future__ import annotations

import math
import pytest

from kasp.core.aerodynamics import CompressorAerodynamics
from kasp.core.models import ThermodynamicState
from kasp.core.properties import ThermodynamicSolver
from kasp.core.thermo import ThermoEngine
from kasp.core.thermo_design_support import (
    calculate_total_actual_poly_efficiency,
    select_design_method_key,
)
from kasp.services.calculation_service import (
    execute_design_calculation,
    resolve_supported_method,
)
from kasp.services.chart_data_builder import build_all_chart_payloads
from kasp.services.performance_service import evaluate_field_performance


class _IdealGasMockSolver:
    """Exact calorically perfect ideal-gas solver (Z=1, Cp=const, Cv=const)."""

    cp = 1005.0
    cv = 718.0
    r_spec = 287.0
    mw = 28.9647
    p0 = 100000.0
    t0 = 300.0

    @property
    def k(self) -> float:
        return self.cp / self.cv

    def get_properties(self, p_pa: float, t_k: float, gas_obj=None, eos: str = "ideal") -> ThermodynamicState:
        rho = p_pa / (self.r_spec * t_k)
        h = self.cp * t_k
        s = self.cp * math.log(t_k / self.t0) - self.r_spec * math.log(p_pa / self.p0)
        a = math.sqrt(self.k * self.r_spec * t_k)
        return ThermodynamicState(
            P=float(p_pa),
            T=float(t_k),
            H=float(h),
            S=float(s),
            Z=1.0,
            k=float(self.k),
            k_s=float(self.k),
            MW=self.mw,
            Cp=self.cp,
            Cv=self.cv,
            density=float(rho),
            speed_of_sound=float(a),
            phase="Gaz",
            raw_props={"mu": 1.8e-5},
        )


def test_schultz_factor_and_polytropic_efficiency_ideal_gas_exact():
    """For an ideal gas (Z=1, Cp=const), Schultz f_s must equal 1.000 and poly_eff must match exact target."""
    solver = _IdealGasMockSolver()
    p1, t1 = 1.0e5, 300.0
    p2 = 3.5e5
    eta_target = 0.80

    m_poly = ((solver.k - 1.0) / solver.k) / eta_target
    t2 = t1 * ((p2 / p1) ** m_poly)

    s_in = solver.get_properties(p1, t1, {"AIR": 1.0}, "ideal")
    s_out = solver.get_properties(p2, t2, {"AIR": 1.0}, "ideal")

    f_s = CompressorAerodynamics.calculate_schultz_factor(
        s_in, s_out, p2, solver, {"AIR": 1.0}, "ideal", solver.r_spec
    )
    assert f_s == pytest.approx(1.0, abs=1e-3)

    eta_calc = CompressorAerodynamics.calculate_polytropic_efficiency(
        s_in, s_out, solver.r_spec, solver, {"AIR": 1.0}, "ideal"
    )
    assert eta_calc == pytest.approx(eta_target, abs=1e-3)


def test_canonical_case_insensitive_method_routing():
    """Canonical lowercase keys and calc_method aliases must route to all 6 distinct methods."""
    expected_keys = {
        "average": "average",
        "method_1": "average",
        "endpoint": "endpoint",
        "method_2": "endpoint",
        "incremental": "incremental",
        "incremental_pressure": "incremental",
        "method_3": "incremental",
        "direct_hs": "direct_hs",
        "hs": "direct_hs",
        "method_4": "direct_hs",
        "huntington_rk45": "huntington_rk45",
        "rk45": "huntington_rk45",
        "method_5": "huntington_rk45",
        "schultz_3exp": "schultz_3exp",
        "method_6": "schultz_3exp",
    }
    for raw, expected in expected_keys.items():
        assert select_design_method_key(raw) == expected, f"select_design_method_key({raw!r}) failed"
        resolved = resolve_supported_method(raw)
        assert select_design_method_key(resolved) == expected, f"resolve_supported_method({raw!r}) -> {resolved!r} failed"

    # Also verify ThermoEngine accepts calc_method alias directly
    eng = ThermoEngine()
    res = eng.calculate_design_performance(
        {
            "p_in": 20.0,
            "p_in_unit": "bar(a)",
            "p_out": 50.0,
            "p_out_unit": "bar(a)",
            "t_in": 25.0,
            "t_in_unit": "°C",
            "flow": 100000.0,
            "flow_unit": "Sm³/h",
            "poly_eff": 82.0,
            "num_stages": 1,
            "gas_comp": {"CH4": 90.0, "C2H6": 7.0, "C3H8": 3.0},
            "eos_method": "pr",
            "calc_method": "huntington_rk45",
        }
    )
    assert res["calculation_method"] == "Metot 5: Huntington-RK45 Diferansiyel"


def test_real_gas_design_and_ptc10_field_roundtrip_consistency():
    """Forward design at 82% (50->180 bar, 1 stage) and inverse PTC-10 field evaluation must agree."""
    comp = {"CH4": 88.0, "C2H6": 7.0, "C3H8": 3.0, "N2": 1.0, "CO2": 1.0}
    res = execute_design_calculation(
        {
            "p_in": 50.0,
            "p_in_unit": "bar(a)",
            "p_out": 180.0,
            "p_out_unit": "bar(a)",
            "t_in": 30.0,
            "t_in_unit": "°C",
            "flow": 150000.0,
            "flow_unit": "Sm3/h",
            "poly_eff": 82.0,
            "stages": 1,
            "gas_comp": comp,
            "eos": "PR",
            "method": "huntington_rk45",
        }
    )
    assert "Metot 5" in res["calculation_method"]
    assert res["actual_poly_efficiency"] == pytest.approx(0.82, abs=0.006)
    assert res["stages"][0]["poly_eff_diagnostic"] == pytest.approx(0.82, abs=0.006)

    perf = evaluate_field_performance(
        {
            "p_in": 50.0,
            "p_in_unit": "bar(a)",
            "t_in": 30.0,
            "t_in_unit": "°C",
            "p_out": 180.0,
            "p_out_unit": "bar(a)",
            "t_out": res["t_out_c"],
            "t_out_unit": "°C",
            "flow": 150000.0,
            "flow_unit": "Sm³/h",
            "gas_comp": comp,
            "eos_model": "pr",
        }
    )
    assert perf["actual_poly_eff"] == pytest.approx(82.0, abs=0.6)


def test_high_pressure_classical_methods_no_efficiency_collapse():
    """At 50->180 bar (where k_s > 2.0), Methods 1-6 must use real-gas temperature exponent and stay near 82%."""
    comp = {"CH4": 88.0, "C2H6": 7.0, "C3H8": 3.0, "N2": 1.0, "CO2": 1.0}
    for m in ["average", "endpoint", "incremental", "direct_hs", "huntington_rk45", "schultz_3exp"]:
        r = execute_design_calculation(
            {
                "p_in": 50.0,
                "p_out": 180.0,
                "t_in": 25.0,
                "flow": 100000.0,
                "flow_unit": "Sm3/h",
                "poly_eff": 82.0,
                "stages": 2,
                "gas_comp": comp,
                "eos": "PR",
                "method": m,
                "intercooler_t": 35.0,
                "intercooler_dp_pct": 2.0,
            }
        )
        act_eff = r["actual_poly_efficiency"]
        assert 0.79 <= act_eff <= 0.845, f"{m}: actual_poly_efficiency={act_eff:.4f} collapsed at high pressure"
        assert r["t_out_c"] < 152.0, f"{m}: unphysical t_out_c={r['t_out_c']:.2f} °C at 50->180 bar"


def test_multistage_mass_weighted_total_poly_efficiency():
    """When interstage VLE knockout reduces downstream stage mass flow, total efficiency must conserve energy."""
    stages = [
        {"stage": 1, "mass_flow_kgs": 12.0, "head_kj_kg": 80.0, "delta_h_kj_kg": 100.0, "poly_eff_diagnostic": 0.80},
        {"stage": 2, "mass_flow_kgs": 6.0, "head_kj_kg": 90.0, "delta_h_kj_kg": 100.0, "poly_eff_diagnostic": 0.90},
    ]
    # Total polytropic power = 12*80 + 6*90 = 1500 kW; Total gas power = 12*100 + 6*100 = 1800 kW -> 1500/1800 = 5/6
    eff = calculate_total_actual_poly_efficiency(stages, 170.0, 0.82)
    assert eff == pytest.approx(1500.0 / 1800.0, abs=1e-4)


def test_solver_cache_sub_centikelvin_precision_and_coolprop_fast_path():
    """Cache must not quantize 0.004 K finite-difference perturbations to 0.0, and CoolProp fast path must match."""
    solver = ThermodynamicSolver()
    comp = {"CH4": 0.90, "C2H6": 0.07, "C3H8": 0.03}
    s1 = solver.get_properties(60e5, 310.000, comp, "pr")
    s2 = solver.get_properties(60e5, 310.004, comp, "pr")
    cp_fd = (s2.H - s1.H) / 0.004
    assert cp_fd == pytest.approx(s1.Cp, rel=1e-2)

    CP = pytest.importorskip("CoolProp.CoolProp")
    gas_str = "HEOS::Methane[0.90]&Ethane[0.07]&Propane[0.03]"
    st_cp = solver.get_properties(40e5, 315.0, gas_str, "coolprop")
    assert st_cp.H == pytest.approx(CP.PropsSI("Hmass", "P", 40e5, "T", 315.0, gas_str), rel=1e-4)
    assert st_cp.S == pytest.approx(CP.PropsSI("Smass", "P", 40e5, "T", 315.0, gas_str), rel=1e-4)
    assert st_cp.Z == pytest.approx(CP.PropsSI("Z", "P", 40e5, "T", 315.0, gas_str), rel=1e-4)
    assert st_cp.raw_props["mu"] == pytest.approx(CP.PropsSI("V", "P", 40e5, "T", 315.0, gas_str), rel=1e-3)


def test_chart_data_builder_uses_real_thermodynamic_states_and_turbine_metrics():
    """Interactive chart builders must reflect real EOS v, s, Z/k paths, Sankey fuel balance, and turbine scores."""
    inputs = {
        "p_in": 50.0,
        "p_out": 180.0,
        "t_in": 25.0,
        "flow": 120000.0,
        "flow_unit": "Sm3/h",
        "poly_eff": 82.0,
        "stages": 2,
        "gas_comp": {"CH4": 88.0, "C2H6": 7.0, "C3H8": 3.0, "N2": 1.0, "CO2": 1.0},
        "eos": "PR",
        "method": "schultz_3exp",
        "intercooler_t": 35.0,
        "intercooler_dp_pct": 2.0,
        "driver_thermal_eff_pct": 31.0,
    }
    results = execute_design_calculation(inputs)
    selected_units = [
        {
            "name": "HighEff-OptLoad",
            "available_power_kw": results["power_unit_kw"] * 1.12,
            "site_heat_rate_kj_kwh": 9200.0,
            "iso_heat_rate_kj_kwh": 9000.0,
            "power_margin_pct": 12.0,
            "surge_margin_pct": 22.0,
            "stonewall_margin_pct": 25.0,
            "selection_score": 91.0,
        },
        {
            "name": "LowEff-Oversized",
            "available_power_kw": results["power_unit_kw"] * 1.85,
            "site_heat_rate_kj_kwh": 12500.0,
            "iso_heat_rate_kj_kwh": 12200.0,
            "power_margin_pct": 85.0,
            "surge_margin_pct": 18.0,
            "stonewall_margin_pct": 20.0,
            "selection_score": 68.0,
        },
    ]

    charts = build_all_chart_payloads(inputs, results, selected_units=selected_units)

    # 1. P-v uses real inlet specific volume (~0.025 m3/kg at 50 bar, NOT hardcoded 0.85)
    assert charts["pv_diagram"]["polytropic_path"]["v"][0] == pytest.approx(results["v_in"], rel=0.05)
    assert charts["pv_diagram"]["polytropic_path"]["v"][0] < 0.05

    # 2. h-s uses real inlet entropy (results["s_in"] / 1000, NOT hardcoded 5.20)
    s_in_kj = results["s_in"] / 1000.0
    assert charts["hs_mollier"]["actual_path"]["s"][0] == pytest.approx(s_in_kj, abs=0.05)

    # 3. T-s stage 1 inlet entropy matches real s_in_kj (NOT hardcoded 5.0)
    assert charts["ts_diagram"]["actual_path"]["s"][0] == pytest.approx(s_in_kj, abs=0.05)

    # 4. Sankey fuel input reflects 31% driver thermal efficiency (NOT hardcoded 35%)
    expected_fuel_kw = results["power_shaft_total_kw"] / 0.31
    sankey_links = charts["power_sankey"]["links"]
    sankey_total_fuel_kw = sankey_links[0]["value"] + sankey_links[1]["value"]
    assert sankey_total_fuel_kw == pytest.approx(expected_fuel_kw, rel=0.03)

    # 5. Radar differentiates efficiency (axis 1) and load factor (axis 3) across turbines
    t0_r = charts["turbine_radar"]["series"][0]["values"]
    t1_r = charts["turbine_radar"]["series"][1]["values"]
    assert t0_r[1] > t1_r[1] + 5.0, f"Radar efficiency score did not differentiate: {t0_r[1]} vs {t1_r[1]}"
    assert t0_r[3] != t1_r[3], f"Radar load score remained identical: {t0_r[3]} vs {t1_r[3]}"
