"""pytest wrapper for textbook/reference verification scripts (P4-14).

These tests adapt the standalone verify_*.py scripts to pytest format,
providing independent textbook/NIST reference validation for thermodynamic
calculations. They are marked as 'reference' and 'slow' so they can be
run selectively with: pytest -m "reference and slow"
"""

import math
import pytest
from kasp.core.thermo import ThermoEngine


# ============================================================
# TEXTBOOK COMPRESSOR POWER VERIFICATION
# ============================================================

def test_textbook_compressor_power():
    """Textbook formula verification for compressor gas power (P4-14).
    
    Reference: P = [n/(n-1)] * (Z_avg * R * T1) * [(P2/P1)^((n-1)/n) - 1] * (m_dot / poly_eff)
    Using natural gas mixture (Methane 90%, Ethane 5%, Propane 5%).
    """
    mass_flow_kgh = 50000.0
    mass_flow_kgs = mass_flow_kgh / 3600.0
    
    P1 = 20.0
    P2 = 60.0
    PR = P2 / P1
    
    T1_C = 30.0
    T1_K = T1_C + 273.15
    
    poly_eff = 0.85
    
    MW = 18.1 / 1000.0
    R_universal = 8.314462
    R_specific = R_universal / MW / 1000.0
    
    k = 1.3
    n_over_n_minus_1 = (k / (k - 1)) * poly_eff
    n_minus_1_over_n = 1.0 / n_over_n_minus_1
    
    Z1 = 0.95
    Z2 = 0.88
    Z_avg = (Z1 + Z2) / 2.0
    
    H_p = Z_avg * R_specific * T1_K * n_over_n_minus_1 * (math.pow(PR, n_minus_1_over_n) - 1)
    gas_power = mass_flow_kgs * H_p / poly_eff
    
    assert 13.8 <= mass_flow_kgs <= 13.9
    assert 0.45 <= R_specific <= 0.47
    assert 0.90 <= Z_avg <= 0.93
    assert 160.0 <= H_p <= 185.0
    assert 2600.0 <= gas_power <= 3000.0


# ============================================================
# INDEPENDENT COOLPROP VERIFICATION (NIST reference)
# ============================================================

@pytest.mark.slow
def test_independent_coolprop_verification():
    """Independent CoolProp verification against textbook formulas (P4-14).
    
    Uses pure CoolProp HEOS for methane/ethane/propane mixture.
    Validates isentropic and polytropic head/power calculations.
    """
    pytest.importorskip("CoolProp")
    import CoolProp.CoolProp as CP
    
    gas = "HEOS::Methane[0.9]&Ethane[0.05]&Propane[0.05]"
    
    p1 = 2000000.0
    t1 = 303.15
    
    h1 = CP.PropsSI('Hmass', 'P', p1, 'T', t1, gas)
    s1 = CP.PropsSI('Smass', 'P', p1, 'T', t1, gas)
    z1 = CP.PropsSI('Z', 'P', p1, 'T', t1, gas)
    
    p2 = 6000000.0
    try:
        h2_is = CP.PropsSI('Hmass', 'P', p2, 'Smass', s1, gas)
    except ValueError:
        lo, hi = t1, t1 * 2.0
        for _ in range(45):
            mid = 0.5 * (lo + hi)
            if CP.PropsSI('Smass', 'P', p2, 'T', mid, gas) < s1:
                lo = mid
            else:
                hi = mid
        t2_is = 0.5 * (lo + hi)
        h2_is = CP.PropsSI('Hmass', 'P', p2, 'T', t2_is, gas)
    else:
        t2_is = CP.PropsSI('T', 'P', p2, 'Smass', s1, gas)
    
    mass_flow = 50000.0 / 3600.0
    
    head_is = (h2_is - h1) / 1000.0
    power_is = mass_flow * head_is
    
    assert 150.0 <= head_is <= 190.0
    assert power_is > 0
    
    # Polytropic work verification (target 85% eff)
    poly_eff_target = 0.85
    t2_guess = t2_is + 20
    for _ in range(50):
        h2_act = CP.PropsSI('Hmass', 'P', p2, 'T', t2_guess, gas)
        z2_act = CP.PropsSI('Z', 'P', p2, 'T', t2_guess, gas)
        
        try:
            z_avg = (z2_act - z1) / math.log(z2_act / z1)
        except ValueError:
            z_avg = (z2_act + z1) / 2.0
        
        n_over_n_minus_1 = math.log(p2 / p1) / math.log(t2_guess / t1)
        sigma = 1.0 / n_over_n_minus_1
        
        R_real = CP.PropsSI('gas_constant', 'P', p1, 'T', t1, gas) / CP.PropsSI('molar_mass', 'P', p1, 'T', t1, gas)
        head_poly = (z_avg * R_real * t1 * (1.0 / sigma) * (math.pow(p2 / p1, sigma) - 1.0)) / 1000.0
        
        calc_eff = head_poly / ((h2_act - h1) / 1000.0)
        t2_guess += 10.0 * (calc_eff - poly_eff_target)
    
    actual_power = mass_flow * head_poly / poly_eff_target
    
    assert 155.0 <= head_poly <= 195.0
    assert 2500.0 <= actual_power <= 3200.0
    assert t2_guess > t1


# ============================================================
# EOS METHOD COMPARISON (CoolProp vs PR vs SRK)
# ============================================================

@pytest.mark.slow
@pytest.mark.parametrize("eos", ["coolprop", "pr", "srk"])
def test_eos_method_comparison(eos):
    """Compare EOS methods against basic sanity checks (P4-14).
    
    Validates that all three EOS methods produce physically reasonable
    results for a standard natural gas compression case.
    """
    engine = ThermoEngine()
    
    base_inputs = {
        'gas_comp': {
            'METHANE': 0.98,
            'ETHANE': 0.015,
            'NITROGEN': 0.005
        },
        'ambient_pressure_pa': 101325.0,
        'p_in': 50.66325,
        'p_in_unit': 'bar',
        't_in': 19.0,
        't_in_unit': '°C',
        'p_out': 75.0,
        'p_out_unit': 'bar',
        'flow': 1985000.0,
        'flow_unit': 'Sm³/h',
        'poly_eff': 90.0,
        'mech_eff': 98.0,
        'num_units': 1,
        'num_stages': 1,
        'eos_method': eos,
    }
    
    results = engine.calculate_design_performance(base_inputs)
    
    head = results.get('head_kj_kg', 0)
    p_gas = results.get('power_gas_per_unit_kw', 0)
    p_shaft = results.get('power_shaft_per_unit_kw', 0)
    p_unit = results.get('power_unit_kw', 0)
    t_out = results.get('t_out', 0)
    
    assert head > 0, f"{eos}: Expected positive head, got {head}"
    assert p_gas > 0, f"{eos}: Expected positive gas power, got {p_gas}"
    assert p_shaft >= p_gas, f"{eos}: shaft power >= gas power failed"
    assert p_unit >= p_shaft, f"{eos}: unit power >= shaft power failed"
    assert t_out > base_inputs['t_in'], f"{eos}: outlet temperature > inlet failed"


# ============================================================
# STABILITY TEST (single-stage methane)
# ============================================================

@pytest.mark.slow
def test_thermo_stability_methane():
    """Basic thermodynamic stability test for pure methane (P4-14)."""
    engine = ThermoEngine()
    
    inputs = {
        'gas_comp': {'METHANE': 1.0},
        'eos_method': 'coolprop',
        'ambient_pressure_pa': 101325.0,
        'p_in': 20.0,
        'p_in_unit': 'bar',
        't_in': 30.0,
        't_in_unit': '°C',
        'p_out': 60.0,
        'p_out_unit': 'bar',
        'flow': 50000.0,
        'flow_unit': 'kg/h',
        'poly_eff': 85.0,
        'mech_eff': 98.0,
    }
    
    results = engine.calculate_design_performance(inputs)
    
    assert results['mass_flow_per_unit_kgs'] > 0
    assert results['head_kj_kg'] > 0
    assert results['power_gas_per_unit_kw'] > 0
    assert results['power_shaft_per_unit_kw'] > results['power_gas_per_unit_kw']
    assert results['power_unit_kw'] > results['power_shaft_per_unit_kw']