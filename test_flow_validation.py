import math
import logging
import pytest
from kasp.core.exceptions import UnitConversionError
from kasp.core.thermo_support import convert_flow_to_kgs

class _MockSolver:
    def infer_mw_g_mol(self, gas_obj):
        return 16.04

    def get_properties(self, p, t, gas_obj, eos):
        class _State:
            density = 0.717
            MW = 16.04
        return _State()

@pytest.fixture
def solver():
    return _MockSolver()

def test_flow_conversion_rejects_negative_value(solver):
    with pytest.raises(UnitConversionError, match="pozitif"):
        convert_flow_to_kgs(
            -10.0,
            "kg/s",
            {},
            "pr",
            thermo_solver=solver,
            logger=logging.getLogger("test"),
            std_press_pa=101325.0,
            standard_temp_k=288.15,
            normal_temp_k=273.15,
        )

def test_flow_conversion_rejects_zero_value(solver):
    with pytest.raises(UnitConversionError, match="pozitif"):
        convert_flow_to_kgs(
            0.0,
            "Sm³/h",
            {},
            "pr",
            thermo_solver=solver,
            logger=logging.getLogger("test"),
            std_press_pa=101325.0,
            standard_temp_k=288.15,
            normal_temp_k=273.15,
        )

def test_flow_conversion_rejects_nan_and_inf(solver):
    for bad_val in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(UnitConversionError):
            convert_flow_to_kgs(
                bad_val,
                "kg/h",
                {},
                "pr",
                thermo_solver=solver,
                logger=logging.getLogger("test"),
                std_press_pa=101325.0,
                standard_temp_k=288.15,
                normal_temp_k=273.15,
            )

def test_flow_conversion_accepts_valid_positive_values(solver):
    res = convert_flow_to_kgs(
        3600.0,
        "kg/h",
        {},
        "pr",
        thermo_solver=solver,
        logger=logging.getLogger("test"),
        std_press_pa=101325.0,
        standard_temp_k=288.15,
        normal_temp_k=273.15,
    )
    assert math.isclose(res, 1.0, rel_tol=1e-5)
