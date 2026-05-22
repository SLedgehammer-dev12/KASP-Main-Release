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
