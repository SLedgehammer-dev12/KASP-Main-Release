import logging
import pytest
from kasp.core.thermo import ThermoEngine
from kasp.core.contracts import get_design_input_defaults

def test_gas_comp_normalization_only_warns_once_per_calculation(caplog):
    engine = ThermoEngine()
    inputs = get_design_input_defaults()
    inputs["eos_method"] = "pr"
    inputs["method"] = "Metot 1: Ortalama Özellikler"
    inputs["num_stages"] = 2
    inputs["intercooler_dp_pct"] = 2.0
    # Gas composition summing to 98.67% (unnormalized)
    inputs["gas_comp"] = {
        "METHANE": 85.0,
        "ETHANE": 5.0,
        "PROPANE": 4.0,
        "NITROGEN": 4.67,
    }

    with caplog.at_level(logging.WARNING):
        results = engine.calculate_design_performance(inputs)

    assert results is not None

    # Count how many times the normalization warning was emitted
    norm_warnings = [
        r.message for r in caplog.records
        if "Normalize ediliyor" in r.message
    ]

    # Before fix: emitted multiple times (3-5 times) for a multi-stage calculation
    # Target: Should be emitted at most ONCE
    assert len(norm_warnings) == 1, (
        f"Normalization warning emitted {len(norm_warnings)} times, expected exactly 1! "
        f"Warnings: {norm_warnings}"
    )
