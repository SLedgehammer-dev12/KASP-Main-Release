"""TDD verification suite for Konu #5:
1. Schultz 3-Exponent (Metot 6) real-gas & ideal-limit polytropic head accuracy vs RK45 (Metot 5)
2. End-to-end propagation of user `custom_kij` binary interaction overrides into PR/SRK solver & cache
3. Real-gas dynamic viscosity mu(P, T, y_i) across PR, SRK, AGA8, GERG-2008, and ThermoPack
4. Unit-safe top-level p_in_bar / p_out_bar / t_in_c normalization & post-VLE knockout outlet_properties
5. Complete 24-component categorized GAS_CATALOG & kij consistency (including Air/Argon/Helium)
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from kasp.api.server import app
from kasp.core.constants import SUPPORTED_GASES
from kasp.core.properties import ThermodynamicSolver
from kasp.core.thermo import ThermoEngine
from kasp.services.calculation_service import execute_design_calculation
from kasp.services.gas_service import (
    GAS_CATALOG,
    get_kij_matrix_for_composition,
    standard_composition_for_gas,
)


NATURAL_GAS_COMP = {
    "METHANE": 85.0,
    "ETHANE": 7.0,
    "PROPANE": 4.0,
    "NITROGEN": 2.0,
    "CARBONDIOXIDE": 2.0,
}


class DummyDB:
    def get_all_turbines_full_data(self):
        return []


def test_schultz_3exp_matches_rk45_at_low_and_high_pressure():
    """Metot 6 (Schultz 3-Üslü) must match exact path-integral Metot 5 (RK45) within 0.5%
    for both low-pressure near-ideal compression and high-pressure real-gas compression."""
    engine = ThermoEngine()

    for p_in_bar, p_out_bar in [(1.5, 4.5), (30.0, 90.0)]:
        base_inputs = {
            "p_in": p_in_bar,
            "p_in_unit": "bar(a)",
            "p_out": p_out_bar,
            "p_out_unit": "bar(a)",
            "t_in": 25.0,
            "t_in_unit": "°C",
            "flow": 10.0,
            "flow_unit": "kg/s",
            "poly_eff": 80.0,
            "num_stages": 1,
            "num_units": 1,
            "eos_method": "pr",
            "gas_comp": dict(NATURAL_GAS_COMP),
        }

        res_rk45 = engine.calculate_design_performance(
            {**base_inputs, "method": "Metot 5: Huntington-RK45"}
        )
        res_schultz = engine.calculate_design_performance(
            {**base_inputs, "method": "Metot 6: Schultz 3-Üslü Gerçek Gaz"}
        )

        head_rk45 = res_rk45["head_kj_kg"]
        head_schultz = res_schultz["head_kj_kg"]
        rel_head_err = abs(head_schultz - head_rk45) / head_rk45

        assert rel_head_err < 0.005, (
            f"At {p_in_bar}->{p_out_bar} bar, Schultz head ({head_schultz:.3f} kJ/kg) "
            f"deviates from RK45 ({head_rk45:.3f} kJ/kg) by {rel_head_err*100:.2f}%"
        )
        assert abs(res_schultz["t_out"] - res_rk45["t_out"]) < 0.35
        assert abs(res_schultz["actual_poly_efficiency"] - 0.80) < 0.005
        stg_pcons = abs(res_schultz["stages"][0]["power_consistency_check_kw"])
        assert stg_pcons < 15.0, f"Excessive power consistency discrepancy: {stg_pcons:.2f} kW"


def test_custom_kij_overrides_propagate_to_pr_srk_design_and_api():
    """User custom_kij overrides must alter PR/SRK Z-factor, enthalpy, head, and shaft power
    without colliding in ThermodynamicSolver's property cache."""
    sour_co2_gas = {
        "METHANE": 55.0,
        "CARBONDIOXIDE": 35.0,
        "HYDROGENSULFIDE": 10.0,
    }
    common_payload = {
        "p_in": 25.0,
        "p_in_unit": "bar(a)",
        "p_out": 85.0,
        "p_out_unit": "bar(a)",
        "t_in": 30.0,
        "t_in_unit": "°C",
        "flow": 15.0,
        "flow_unit": "kg/s",
        "poly_eff": 80.0,
        "num_stages": 1,
        "num_units": 1,
        "eos_model": "pr",
        "calc_method": "Metot 6: Schultz 3-Üslü Gerçek Gaz",
        "gas_comp": sour_co2_gas,
    }

    engine = ThermoEngine()
    db = DummyDB()

    res_zero_kij = execute_design_calculation(
        {
            **common_payload,
            "custom_kij": {
                "METHANE:CARBONDIOXIDE": 0.0,
                "METHANE:HYDROGENSULFIDE": 0.0,
                "CARBONDIOXIDE:HYDROGENSULFIDE": 0.0,
            },
        },
        engine=engine,
        db=db,
    )
    res_high_kij = execute_design_calculation(
        {
            **common_payload,
            "custom_kij": {
                "METHANE:CARBONDIOXIDE": 0.25,
                "METHANE:HYDROGENSULFIDE": 0.20,
                "CARBONDIOXIDE:HYDROGENSULFIDE": 0.20,
            },
        },
        engine=engine,
        db=db,
    )

    assert abs(res_high_kij["z_in"] - res_zero_kij["z_in"]) > 0.008
    assert abs(res_high_kij["head_kj_kg"] - res_zero_kij["head_kj_kg"]) > 0.5
    assert abs(res_high_kij["power_shaft_total_kw"] - res_zero_kij["power_shaft_total_kw"]) > 5.0

    # Verify via FastAPI /api/v1/calculations/design endpoint as well
    with TestClient(app) as client:
        r1 = client.post(
            "/api/v1/calculations/design",
            json={**common_payload, "custom_kij": {"METHANE:CARBONDIOXIDE": -0.05}},
        )
        r2 = client.post(
            "/api/v1/calculations/design",
            json={**common_payload, "custom_kij": {"METHANE:CARBONDIOXIDE": 0.28}},
        )
        assert r1.status_code == 200 and r2.status_code == 200
        d1 = r1.json()["results"]
        d2 = r2.json()["results"]
        assert abs(d2["z_in"] - d1["z_in"]) > 0.008


def test_real_gas_viscosity_responds_to_pressure_temperature_and_species():
    """PR, SRK, AGA8, GERG-2008, and ThermoPack must compute physically realistic
    dynamic viscosity mu(P, T, y_i) instead of returning hardcoded 1.1e-5 Pa.s."""
    engine = ThermoEngine()
    solver = ThermodynamicSolver()

    # Reference CoolProp natural gas viscosity at low P and high P/T
    cp_obj = engine._create_gas_object(NATURAL_GAS_COMP, "coolprop")
    st_cp_low = solver.get_properties(20.0e5, 298.15, cp_obj, "coolprop")
    st_cp_high = solver.get_properties(90.0e5, 393.15, cp_obj, "coolprop")
    mu_cp_low = st_cp_low.raw_props["mu"]
    mu_cp_high = st_cp_high.raw_props["mu"]

    for eos_name in ("pr", "srk", "aga8", "gerg2008"):
        gas_obj = engine._create_gas_object(NATURAL_GAS_COMP, eos_name)
        st_low = solver.get_properties(20.0e5, 298.15, gas_obj, eos_name)
        st_high = solver.get_properties(90.0e5, 393.15, gas_obj, eos_name)
        mu_low = st_low.raw_props["mu"]
        mu_high = st_high.raw_props["mu"]

        assert mu_low != pytest.approx(1.1e-5, abs=1e-9), f"{eos_name} still returns hardcoded 1.1e-5"
        assert mu_high > mu_low * 1.15, f"{eos_name} viscosity must increase at higher T & P"
        assert abs(mu_low - mu_cp_low) / mu_cp_low < 0.15, f"{eos_name} low-P mu {mu_low} far from CoolProp {mu_cp_low}"
        assert abs(mu_high - mu_cp_high) / mu_cp_high < 0.15, f"{eos_name} high-P mu {mu_high} far from CoolProp {mu_cp_high}"

    # Pure species check: H2 has much lower viscosity (~8.9e-6 Pa.s) than O2/Ar (~2.0-2.2e-5 Pa.s)
    h2_obj = engine._create_gas_object({"HYDROGEN": 100.0}, "pr")
    o2_obj = engine._create_gas_object({"OXYGEN": 100.0}, "pr")
    mu_h2 = solver.get_properties(2.0e5, 298.15, h2_obj, "pr").raw_props["mu"]
    mu_o2 = solver.get_properties(2.0e5, 298.15, o2_obj, "pr").raw_props["mu"]
    assert 7.5e-6 < mu_h2 < 1.05e-5
    assert 1.85e-5 < mu_o2 < 2.30e-5
    assert mu_o2 > mu_h2 * 2.0


def test_top_level_unit_conversion_and_post_vle_outlet_properties():
    """execute_design_calculation must convert gauge/imperial input units into true
    bar(a) and °C for p_in_bar, p_out_bar, and t_in_c, and evaluate outlet_properties
    with the post-knockout vapor composition."""
    engine = ThermoEngine()
    db = DummyDB()

    res_gauge = execute_design_calculation(
        {
            "p_in": 19.0,
            "p_in_unit": "bar(g)",
            "p_out": 59.0,
            "p_out_unit": "bar(g)",
            "t_in": 77.0,
            "t_in_unit": "°F",
            "flow": 10.0,
            "flow_unit": "kg/s",
            "poly_eff": 82.0,
            "num_stages": 1,
            "eos_model": "pr",
            "calc_method": "Metot 6: Schultz 3-Üslü Gerçek Gaz",
            "gas_comp": dict(NATURAL_GAS_COMP),
        },
        engine=engine,
        db=db,
    )

    assert res_gauge["p_in_bar"] == pytest.approx(20.013, abs=0.05)
    assert res_gauge["p_out_bar"] == pytest.approx(60.013, abs=0.05)
    assert res_gauge["t_in_c"] == pytest.approx(25.0, abs=0.05)

    # Rich wet hydrocarbon mixture that condenses liquid in intercooler at 60 bar, 25 °C
    wet_rich_gas = {
        "METHANE": 72.0,
        "ETHANE": 8.0,
        "PROPANE": 6.0,
        "BUTANE": 5.0,
        "HEXANE": 5.0,
        "OCTANE": 4.0,
    }
    res_vle = execute_design_calculation(
        {
            "p_in": 20.0,
            "p_in_unit": "bar(a)",
            "p_out": 110.0,
            "p_out_unit": "bar(a)",
            "t_in": 45.0,
            "t_in_unit": "°C",
            "flow": 15.0,
            "flow_unit": "kg/s",
            "poly_eff": 80.0,
            "num_stages": 2,
            "intercooler_t": 25.0,
            "eos_model": "pr",
            "calc_method": "Metot 6: Schultz 3-Üslü Gerçek Gaz",
            "gas_comp": wet_rich_gas,
        },
        engine=engine,
        db=db,
    )
    assert res_vle.get("total_liquid_knockout_kg_h", 0.0) > 10.0
    inlet_mw = res_vle["inlet_properties"]["MW"]
    outlet_mw = res_vle["outlet_properties"]["MW"]
    assert outlet_mw < inlet_mw - 0.5, (
        f"After heavy C6/C8 knockout, outlet vapor MW ({outlet_mw:.2f}) must be lighter than inlet MW ({inlet_mw:.2f})"
    )


def test_gas_catalog_covers_all_supported_gases_with_categories():
    """GAS_CATALOG and /api/v1/thermo/gases must expose all 24 SUPPORTED_GASES with
    category metadata ('hydrocarbon', 'acid_polar', 'inert_other'), including ARGON and HELIUM."""
    catalog_ids = {item["id"] for item in GAS_CATALOG}
    assert catalog_ids == set(SUPPORTED_GASES.keys())

    valid_categories = {"hydrocarbon", "acid_polar", "inert_other"}
    for item in GAS_CATALOG:
        assert item.get("category") in valid_categories, f"Missing/invalid category on {item}"

    # Air preset uses NITROGEN + OXYGEN + ARGON; kij matrix must include all 3 components
    air_comp = standard_composition_for_gas("air")
    kij_air = get_kij_matrix_for_composition(air_comp)
    assert set(kij_air["components"]) == {"NITROGEN", "OXYGEN", "ARGON"}
    assert kij_air["size"] == 3

    with TestClient(app) as client:
        resp = client.get("/api/v1/thermo/gases")
        assert resp.status_code == 200
        api_gases = resp.json()
        assert len(api_gases) == len(SUPPORTED_GASES)
        assert any(g["id"] == "ARGON" and g["category"] == "inert_other" for g in api_gases)
        assert any(g["id"] == "HELIUM" and g["category"] == "inert_other" for g in api_gases)
        assert any(g["id"] == "CARBONDIOXIDE" and g["category"] == "acid_polar" for g in api_gases)
        assert any(g["id"] == "METHANE" and g["category"] == "hydrocarbon" for g in api_gases)
