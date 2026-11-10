import pytest
from kasp.core.thermo import ThermoEngine
from kasp.core.contracts import get_design_input_defaults

def test_complex_8comp_coolprop_method_convergence():
    engine = ThermoEngine()
    inputs = get_design_input_defaults()
    inputs["eos_method"] = "coolprop"
    inputs["method"] = "Metot 1: Ortalama Özellikler"
    inputs["p_in"] = "50.66"
    inputs["p_in_unit"] = "bar(a)"
    inputs["p_out"] = "75.0"
    inputs["p_out_unit"] = "bar(a)"
    inputs["t_in"] = "19.0"
    inputs["t_in_unit"] = "°C"
    # 8-component natural gas mixture
    inputs["gas_comp"] = {
        "METHANE": 85.0,
        "ETHANE": 5.0,
        "PROPANE": 3.0,
        "BUTANE": 1.5,
        "ISOBUTANE": 1.5,
        "PENTANE": 1.0,
        "CARBONDIOXIDE": 1.5,
        "NITROGEN": 1.5,
    }

    # Run design performance
    results = engine.calculate_design_performance(inputs)
    assert results is not None
    stage = results["stages"][0]
    history = stage.get("method_history", {})

    # The calculation MUST converge cleanly, not be aborted with max_iterations
    assert history.get("converged") is True, f"Calculation failed to converge: {history.get('termination_reason')}"
    assert history.get("termination_reason") == "converged"
