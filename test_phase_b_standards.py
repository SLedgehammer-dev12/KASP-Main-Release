"""
Test suite for Phase B: Standards Compliance & Test Conversion
- ASME PTC 10:2022 Section 5.3 Reynolds Number & Mach Correction
- ASME PTC 10 Type 1 & Type 2 Test Validity Checks
- ISO 6976:2016 Real Gas Volumetric LHV/HHV & Wobbe Index
- Equal Work Stage Pressure Ratio Optimization Integration
"""

import pytest
import math
from kasp.core.compliance import ASME_PTC10_Compliance
from kasp.core.thermo import ThermoEngine


def test_asme_ptc10_reynolds_correction_factor():
    """Verify ASME PTC 10 Section 5.3 Reynolds correction factor calculation."""
    # Test case: Re_test = 5e5, Re_spec = 2e6 (Shop test at lower density / speed)
    loss_ratio, ra_test, ra_spec = ASME_PTC10_Compliance.calculate_reynolds_correction_factor(
        re_test=5e5,
        re_spec=2e6,
        b2_m=0.025,
        ra_um=1.6,
        x_fraction=0.30,
        n_exp=0.12,
    )
    assert 0.8 < loss_ratio < 1.2
    assert 0.5 <= ra_test <= 1.0
    assert 0.5 <= ra_spec <= 1.0
    # Because Re_test < Re_spec, the specified condition has lower losses (loss_ratio < 1.0, higher efficiency)
    assert loss_ratio < 1.0


def test_asme_ptc10_performance_correction():
    """Verify performance_correction_to_standard_conditions applies Reynolds and speed scaling."""
    measured_test = {
        "head": 120.0,         # kJ/kg
        "efficiency": 82.0,    # percent
        "speed_rpm": 9500.0,
        "reynolds_number": 8e5,
        "mach_number": 0.82,
        "volume_ratio": 2.45,
        "test_type": "Type 2",
    }
    site_conditions = {
        "speed_rpm": 10000.0,
        "reynolds_number": 1.8e6,
        "mach_number": 0.84,
        "volume_ratio": 2.48,
        "mass_flow_kgs": 35.0,
    }

    corrected = ASME_PTC10_Compliance.performance_correction_to_standard_conditions(
        measured_test, site_conditions
    )
    assert corrected["analysis_scope"] == "COMPLIANT"
    assert corrected["ptc10_valid"] is True
    # Speed ratio is 10000/9500 = 1.0526 -> head scales by speed_ratio^2 ~ 1.108
    assert corrected["head"] > measured_test["head"]
    # Guaranteed efficiency is higher than test due to higher specified Reynolds number
    assert corrected["efficiency"] > measured_test["efficiency"]
    assert corrected["power_kw"] > 0


def test_asme_ptc10_test_validity_rejections():
    """Verify that ASME PTC 10 departure limits reject invalid test points."""
    # Test point with extreme volume ratio deviation (> 5% for Type 2)
    test_data = {"volume_ratio": 3.0, "mach_number": 0.80, "test_type": "Type 2"}
    spec_data = {"volume_ratio": 2.4, "mach_number": 0.80}

    validity = ASME_PTC10_Compliance.check_test_validity(test_data, spec_data)
    assert validity["is_valid"] is False
    assert len(validity["warnings"]) > 0
    assert any("Hacim oranı sapması" in w for w in validity["warnings"])


def test_iso6976_real_gas_fuel_properties():
    """Verify ISO 6976:2016 real gas volumetric heating values and Wobbe Index."""
    engine = ThermoEngine()
    # Typical Russian export natural gas: 95% Methane, 3% Ethane, 1% Propane, 1% Nitrogen
    fuel_comp = {
        "METHANE": 95.0,
        "ETHANE": 3.0,
        "PROPANE": 1.0,
        "NITROGEN": 1.0,
    }
    props = engine.calculate_fuel_gas_properties(fuel_comp, source="iso6976")
    
    assert props["lhv_kj_kg"] > 45000.0
    assert props["hhv_kj_kg"] > props["lhv_kj_kg"]
    
    # Real gas compressibility factor Z0 at 15°C, 1 atm typically 0.997 - 0.999
    assert 0.995 <= props["z_std"] <= 1.000
    
    # Standard volumetric heating value (MJ/Sm³) for natural gas is typically 33 - 42 MJ/Sm³
    assert 32.0 <= props["lhv_mj_sm3"] <= 40.0
    assert 36.0 <= props["hhv_mj_sm3"] <= 44.0
    
    # Wobbe Index for natural gas (H-gas) is typically 48 - 54 MJ/Sm³
    assert 45.0 <= props["wobbe_gross_mj_sm3"] <= 55.0
    assert 40.0 <= props["wobbe_net_mj_sm3"] <= 50.0
    
    # Relative density for methane-rich natural gas is typically 0.57 - 0.65
    assert 0.55 <= props["relative_density"] <= 0.65


def test_equal_work_stage_optimization_integration():
    """Verify that stage_pr_mode='equal_work' optimizes stage pressure ratios when T_in != T_ic."""
    engine = ThermoEngine()
    inputs = {
        "p_in": 1.0,
        "p_in_unit": "bar",
        "p_out": 16.0,
        "p_out_unit": "bar",
        "t_in": 15.0,          # 15°C = 288.15 K
        "t_in_unit": "°C",
        "intercooler_t": 40.0, # 40°C = 313.15 K
        "intercooler_t_unit": "°C",
        "intercooler_dp": 0.02,
        "num_stages": 2,
        "flow": 10.0,
        "flow_unit": "kg/s",
        "gas": "Doğal Gaz",
        "gas_comp": {"METHANE": 90.0, "ETHANE": 10.0},
        "eos_method": "pr",
        "method": "Metot 2 (Endpoint)",
        "poly_eff": 80.0,
        "stage_pr_mode": "equal_work",
        "enable_uncertainty": False,
    }
    
    results = engine.calculate_design_performance(inputs)
    assert results is not None
    staged = results.get("stages", [])
    assert len(staged) == 2
    # Stage 1 and Stage 2 have balanced power distribution
    p1 = staged[0]["power_gas_kw"]
    p2 = staged[1]["power_gas_kw"]
    assert p1 > 0 and p2 > 0
    # Power difference between stages should be minimal (< 10%) with equal work optimization
    diff_pct = abs(p1 - p2) / max(p1, p2) * 100.0
    assert diff_pct < 10.0


def test_compliance_robustness_and_edge_cases():
    """Verify that compliance classes gracefully handle None, zeros, strings, and missing data."""
    from kasp.core.compliance import ASME_PTC10_Compliance, API_617_Compliance

    # 1. API 617 lateral analysis with None, zero mass, strings, and operating speed
    r1 = API_617_Compliance.lateral_critical_speed_analysis(None)
    assert r1["first_critical_speed_rpm"] > 0
    assert r1["separation_margin"] is None

    r2 = API_617_Compliance.lateral_critical_speed_analysis({"mass": 0, "stiffness": 0})
    assert r2["first_critical_speed_rpm"] > 0

    r3 = API_617_Compliance.lateral_critical_speed_analysis({
        "mass": "80.0",
        "stiffness": "2e6",
        "operating_speed_rpm": "4000.0"
    })
    assert r3["first_critical_speed_rpm"] > 0
    # Çalışma hızı verilse bile basitleştirilmiş model API 617 uygunluğu iddia etmemeli
    assert r3["separation_margin"] is None
    assert r3["meets_api"] is None
    assert r3["not_implemented"] is True
    # Nc = 60/(2π)·sqrt(2e6/80) ≈ 1509.8 rpm → |1509.8-4000|/4000 ≈ %62.3
    assert r3["indicative_separation_margin_pct"] == pytest.approx(62.25, abs=0.1)
    assert r1["indicative_separation_margin_pct"] is None

    # 2. API 617 torsional analysis with None
    r4 = API_617_Compliance.torsional_analysis(None)
    assert r4["status"] == "NOT_IMPLEMENTED"

    # 3. ASME PTC 10 uncertainty with None and string values
    assert ASME_PTC10_Compliance.calculate_uncertainty(None, None) == 0.0
    u = ASME_PTC10_Compliance.calculate_uncertainty({"p": "100.0", "t": 350.0}, {"p": "0.01"})
    assert u > 0.0

    # 4. ASME PTC 10 test validity with None
    val = ASME_PTC10_Compliance.check_test_validity(None, None)
    assert "is_valid" in val
    assert val["is_valid"] is True

    # 5. ASME PTC 10 performance correction with None / minimal inputs
    corr = ASME_PTC10_Compliance.performance_correction_to_standard_conditions(None, None)
    assert "head" in corr
    assert "efficiency" in corr
    assert "power_kw" in corr
