"""
Tests for the new 3-stage isentropic temperature root-finding solvers and fallback comparison benchmarking system.
"""

import pytest
import time
from kasp.core.properties import ThermodynamicSolver
from kasp.core.mixture import GasMixtureBuilder
from kasp.core.aerodynamics import (
    CompressorAerodynamics,
    reset_fallback_comparisons,
    get_fallback_comparisons,
    set_current_stage,
    get_current_stage,
)

def test_three_solvers_execution():
    """Verify that all three solvers run correctly and return reasonable results."""
    solver = ThermodynamicSolver()
    
    # Define a simple mixture
    gas_comp = {"METHANE": 1.0}
    normalized = GasMixtureBuilder.validate_and_normalize(gas_comp)
    gas_obj = GasMixtureBuilder.build_thermo_data(normalized)
    
    p_in = 1.0e6   # 10 bar
    t_in = 300.0   # 300 K
    p_out = 3.0e6  # 300 bar
    
    state_in = solver.get_properties(p_in, t_in, gas_obj, "pr")
    
    # 1. Test Finite Difference NR
    t_fd, iter_fd, res_fd = CompressorAerodynamics.calculate_isentropic_temp_fd_nr(
        state_in, p_out, solver, gas_obj, "pr"
    )
    assert 300.0 < t_fd < 600.0
    assert iter_fd >= 1
    assert res_fd is not None
    
    # 2. Test Analytical Jacobian NR
    t_aj, iter_aj, res_aj = CompressorAerodynamics.calculate_isentropic_temp_aj_nr(
        state_in, p_out, solver, gas_obj, "pr"
    )
    assert 300.0 < t_aj < 600.0
    assert iter_aj >= 1
    assert res_aj is not None
    
    # 3. Test Brent's Method
    t_brent, iter_brent, res_brent = CompressorAerodynamics.calculate_isentropic_temp_brent(
        state_in, p_out, solver, gas_obj, "pr"
    )
    assert 300.0 < t_brent < 600.0
    assert iter_brent >= 1
    assert res_brent is not None
    
    # The temperatures should be very close to each other
    assert abs(t_fd - t_aj) < 5.0
    assert abs(t_fd - t_brent) < 5.0


def test_fallback_comparison_runner_and_storage():
    """Verify that the benchmarking runner executes all solvers, profiles them, and stores results in thread-local storage."""
    solver = ThermodynamicSolver()
    
    gas_comp = {"METHANE": 0.9, "ETHANE": 0.1}
    normalized = GasMixtureBuilder.validate_and_normalize(gas_comp)
    gas_obj = GasMixtureBuilder.build_thermo_data(normalized)
    
    p_in = 2.0e6   # 20 bar
    t_in = 310.0   # 310 K
    p_out = 5.0e6  # 50 bar
    
    state_in = solver.get_properties(p_in, t_in, gas_obj, "pr")
    
    # Reset thread-local storage
    reset_fallback_comparisons()
    set_current_stage("Kademe 1")
    
    # Run fallback comparison
    t_result = CompressorAerodynamics.calculate_isentropic_temp_fallback(
        state_in, p_out, solver, gas_obj, "pr"
    )
    
    assert 310.0 < t_result < 600.0
    
    # Check thread-local comparisons list
    comparisons = get_fallback_comparisons()
    assert len(comparisons) == 1
    
    comp = comparisons[0]
    assert comp["stage"] == "Kademe 1"
    assert len(comp["methods"]) == 3
    
    method_names = [m["name"] for m in comp["methods"]]
    assert "Sonlu Farklar NR (FD-NR)" in method_names
    assert "Analitik Jacobian NR (AJ-NR)" in method_names
    assert "Brent Metodu (Brent)" in method_names
    
    for method in comp["methods"]:
        assert 300.0 < method["temp_k"] < 600.0
        assert method["iterations"] >= 1
        assert method["residual"] >= 0.0
        assert method["time_ms"] >= 0.0


def test_brent_solver_high_pr_convergence():
    """Verify that calculate_isentropic_temp_brent converges accurately at high pressure ratios and never collapses to t_in."""
    solver = ThermodynamicSolver()
    gas_comp = {"METHANE": 0.85, "ETHANE": 0.10, "PROPANE": 0.05}
    normalized = GasMixtureBuilder.validate_and_normalize(gas_comp)
    gas_obj = GasMixtureBuilder.build_thermo_data(normalized)

    p_in = 1.0e6   # 10 bar
    t_in = 300.0   # 300 K
    p_out = 8.0e6  # 80 bar (PR = 8.0)

    state_in = solver.get_properties(p_in, t_in, gas_obj, "pr")
    t_brent, iters, residual = CompressorAerodynamics.calculate_isentropic_temp_brent(
        state_in, p_out, solver, gas_obj, "pr"
    )

    # Must be physically well above t_in (compression heating)
    assert t_brent > t_in + 50.0
    assert 400.0 < t_brent < 600.0
    # Must converge with low entropy residual
    assert residual < 1.0
    assert iters >= 1


def test_auto_solver_bypasses_redundant_comparisons():
    """Verify that in 'auto' mode with active run tracking, redundant fallback benchmarking is bypassed."""
    solver = ThermodynamicSolver()
    solver.begin_run_tracking("auto")
    
    gas_comp = {"METHANE": 0.9, "ETHANE": 0.1}
    normalized = GasMixtureBuilder.validate_and_normalize(gas_comp)
    gas_obj = GasMixtureBuilder.build_thermo_data(normalized)
    
    p_in = 2.0e6
    t_in = 310.0
    p_out = 5.0e6
    
    state_in = solver.get_properties(p_in, t_in, gas_obj, "pr")
    
    reset_fallback_comparisons()
    set_current_stage("Kademe 1")
    
    t_result = CompressorAerodynamics.calculate_isentropic_temp_fallback(
        state_in, p_out, solver, gas_obj, "pr"
    )
    assert 310.0 < t_result < 600.0
    # Auto mode should NOT run the 3-solver shootout comparison
    comparisons = get_fallback_comparisons()
    assert len(comparisons) == 0


def test_benchmark_solver_executes_comparisons():
    """Verify that in 'benchmark' mode with active run tracking, the 3-solver comparison is executed."""
    solver = ThermodynamicSolver()
    solver.begin_run_tracking("benchmark")
    
    gas_comp = {"METHANE": 0.9, "ETHANE": 0.1}
    normalized = GasMixtureBuilder.validate_and_normalize(gas_comp)
    gas_obj = GasMixtureBuilder.build_thermo_data(normalized)
    
    p_in = 2.0e6
    t_in = 310.0
    p_out = 5.0e6
    
    state_in = solver.get_properties(p_in, t_in, gas_obj, "pr")
    
    reset_fallback_comparisons()
    set_current_stage("Kademe 1")
    
    t_result = CompressorAerodynamics.calculate_isentropic_temp_fallback(
        state_in, p_out, solver, gas_obj, "pr"
    )
    assert 310.0 < t_result < 600.0
    # Benchmark mode MUST run the 3-solver shootout comparison
    comparisons = get_fallback_comparisons()
    assert len(comparisons) == 1
    assert len(comparisons[0]["methods"]) == 3


def test_aerodynamic_calculation_guards():
    """Verify that CompressorAerodynamics methods safely handle zero, negative, None,
    and non-numeric inputs without throwing unhandled exceptions."""
    solver = ThermodynamicSolver()
    gas_comp = {"METHANE": 1.0}
    normalized = GasMixtureBuilder.validate_and_normalize(gas_comp)
    gas_obj = GasMixtureBuilder.build_thermo_data(normalized)

    # 1. calculate_polytropic_exponent_integral guards
    # Zero or negative inlet pressure
    n1, k1, diag1 = CompressorAerodynamics.calculate_polytropic_exponent_integral(
        0.0, 300.0, 10.0e5, 0.8, solver, gas_obj, "pr"
    )
    assert k1 == 1.3
    assert diag1["steps_used"] == 0

    # Zero or negative outlet pressure
    n2, k2, diag2 = CompressorAerodynamics.calculate_polytropic_exponent_integral(
        10.0e5, 300.0, 0.0, 0.8, solver, gas_obj, "pr"
    )
    assert k2 == 1.3
    assert diag2["steps_used"] == 0

    # Equal inlet and outlet pressure (p_in == p_out)
    n3, k3, diag3 = CompressorAerodynamics.calculate_polytropic_exponent_integral(
        10.0e5, 300.0, 10.0e5, 0.8, solver, gas_obj, "pr"
    )
    assert k3 > 1.0
    assert diag3["steps_used"] == 0

    # None or non-numeric inputs
    n4, k4, diag4 = CompressorAerodynamics.calculate_polytropic_exponent_integral(
        None, "invalid", 10.0e5, None, solver, gas_obj, "pr"
    )
    assert k4 == 1.3

    # 2. _calculate_z_average_logarithmic guards
    assert CompressorAerodynamics._calculate_z_average_logarithmic(None, 1.0) == 1.0
    assert CompressorAerodynamics._calculate_z_average_logarithmic(0.0, 0.9) == 1.0
    assert CompressorAerodynamics._calculate_z_average_logarithmic(-0.5, -0.5) == 1.0
    assert abs(CompressorAerodynamics._calculate_z_average_logarithmic(0.9, 0.9) - 0.9) < 1e-6
    z_log = CompressorAerodynamics._calculate_z_average_logarithmic(0.8, 1.2)
    assert 0.8 < z_log < 1.2

    # 3. calculate_mechanical_loss guards
    loss_none = CompressorAerodynamics.calculate_mechanical_loss(None, None)
    assert loss_none >= 10.0
    loss_str = CompressorAerodynamics.calculate_mechanical_loss("invalid", "invalid")
    assert loss_str >= 10.0
    loss_valid = CompressorAerodynamics.calculate_mechanical_loss(1.5, 5000.0)
    assert 10.0 <= loss_valid <= 500.0

    # 4. calculate_thermal_efficiency guards
    assert CompressorAerodynamics.calculate_thermal_efficiency(None) == 0.0
    assert CompressorAerodynamics.calculate_thermal_efficiency("invalid") == 0.0
    assert CompressorAerodynamics.calculate_thermal_efficiency(0.0) == 0.0
    assert CompressorAerodynamics.calculate_thermal_efficiency(-1000.0) == 0.0
    assert 0.35 < CompressorAerodynamics.calculate_thermal_efficiency(9000.0) < 0.45



