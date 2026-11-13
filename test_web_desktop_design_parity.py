"""Web ↔ Desktop design-input parity regression tests.

The web sidebar must start from the same design data as the PyQt desktop
client so that an untouched project produces the same thermodynamic result.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from kasp.core.contracts import get_design_input_defaults, normalize_design_inputs
from kasp.core.thermo import ThermoEngine
from kasp.services.calculation_service import execute_design_calculation


PROJECT_STORE = Path("kasp/web/src/store/projectStore.js")


def _js_defaults_block() -> str:
    source = PROJECT_STORE.read_text(encoding="utf-8")
    marker = "export const DEFAULT_DESIGN_INPUTS = {"
    assert marker in source, "DEFAULT_DESIGN_INPUTS block bulunamadı"
    return source.split(marker, 1)[1].split("\n};", 1)[0]


def _js_scalar(block: str, key: str) -> str:
    match = re.search(rf"\b{re.escape(key)}\s*:\s*([^,\n]+)", block)
    assert match, f"JS varsayılanında '{key}' yok"
    return match.group(1).strip().strip('"')


def _js_number(block: str, key: str) -> float:
    return float(_js_scalar(block, key))


def _js_gas_comp(block: str) -> dict[str, float]:
    gas_block = block.split("gas_comp:", 1)[1].split("}", 1)[0]
    return {
        key: float(value)
        for key, value in re.findall(r"([A-Z0-9_]+)\s*:\s*([0-9.]+)", gas_block)
    }


class _NoTurbineDB:
    """Keep the parity test focused on thermodynamics, not DB contents."""

    def get_all_turbines_full_data(self):
        return []


@pytest.fixture(scope="module")
def engine():
    return ThermoEngine()


def test_web_default_design_inputs_match_desktop_form():
    """Web sidebar defaults must equal the PyQt desktop startup form values."""
    block = _js_defaults_block()

    assert _js_number(block, "p_in") == pytest.approx(49.65)
    assert _js_scalar(block, "p_in_unit") == "bar(g)"
    assert _js_number(block, "t_in") == pytest.approx(19.0)
    assert _js_number(block, "p_out") == pytest.approx(75.0)
    assert _js_number(block, "flow") == pytest.approx(1_985_000.0)
    assert _js_scalar(block, "flow_unit") == "Sm³/h"

    assert _js_scalar(block, "eos_model") == "coolprop"
    assert "Metot 5" in _js_scalar(block, "calc_method")
    assert _js_number(block, "poly_eff") == pytest.approx(90.0)
    assert _js_number(block, "therm_eff") == pytest.approx(35.0)
    assert _js_number(block, "mech_eff") == pytest.approx(98.0)

    assert _js_number(block, "num_units") == pytest.approx(1)
    assert _js_number(block, "num_stages") == pytest.approx(1)
    assert _js_number(block, "intercooler_t") == pytest.approx(40.0)
    assert _js_number(block, "intercooler_dp_pct") == pytest.approx(2.0)

    assert _js_number(block, "ambient_temp") == pytest.approx(15.0)
    assert _js_number(block, "ambient_pressure") == pytest.approx(101.325)
    assert _js_number(block, "altitude") == pytest.approx(0.0)
    assert _js_number(block, "humidity") == pytest.approx(60.0)
    assert _js_scalar(block, "solver_method") == "aj_nr"
    assert _js_scalar(block, "lhv_source") == "kasp"

    assert _js_gas_comp(block) == {
        "METHANE": 85.0,
        "ETHANE": 7.0,
        "PROPANE": 4.0,
        "NITROGEN": 2.0,
        "CARBONDIOXIDE": 2.0,
    }


def test_shared_contract_defaults_match_desktop_startup():
    """Normalization defaults must not silently diverge from the desktop form."""
    defaults = get_design_input_defaults()

    assert float(defaults["p_in"]) == pytest.approx(49.65)
    assert defaults["p_in_unit"] == "bar(g)"
    assert float(defaults["t_in"]) == pytest.approx(19.0)
    assert float(defaults["p_out"]) == pytest.approx(75.0)
    assert float(defaults["flow"]) == pytest.approx(1_985_000.0)
    assert defaults["flow_unit"] == "Sm³/h"
    assert defaults["eos_method"] == "coolprop"
    assert "Metot 5" in defaults["method"]
    assert defaults["poly_eff"] == pytest.approx(90.0)
    assert defaults["num_stages"] == 1
    assert defaults["intercooler_t"] == pytest.approx(40.0)
    assert defaults["ambient_temp"] == pytest.approx(15.0)
    assert defaults["solver_method"] == "aj_nr"
    assert defaults["gas_comp"] == {
        "METHANE": 85.0,
        "ETHANE": 7.0,
        "PROPANE": 4.0,
        "NITROGEN": 2.0,
        "CARBONDIOXIDE": 2.0,
    }


def test_web_service_and_desktop_engine_path_produce_same_thermodynamics(engine):
    """Same normalized inputs → identical core design results on both clients."""
    inputs = {
        "p_in": 49.65,
        "p_in_unit": "bar(g)",
        "t_in": 19.0,
        "t_in_unit": "°C",
        "p_out": 75.0,
        "p_out_unit": "bar(a)",
        "flow": 1_985_000.0,
        "flow_unit": "Sm³/h",
        "gas_comp": {
            "METHANE": 85.0,
            "ETHANE": 7.0,
            "PROPANE": 4.0,
            "NITROGEN": 2.0,
            "CARBONDIOXIDE": 2.0,
        },
        "eos_method": "coolprop",
        "method": "Metot 5: Huntington-RK45 Diferansiyel",
        "poly_eff": 90.0,
        "therm_eff": 35.0,
        "mech_eff": 98.0,
        "num_units": 1,
        "num_stages": 1,
        "intercooler_t": 40.0,
        "intercooler_dp_pct": 2.0,
        "ambient_temp": 15.0,
        "ambient_pressure": 101.325,
        "altitude": 0.0,
        "humidity": 60.0,
        "solver_method": "aj_nr",
        "lhv_source": "kasp",
        "use_consistency_iteration": False,
        "max_consistency_iter": 20,
        "consistency_tolerance": 0.1,
    }

    web_results = execute_design_calculation(dict(inputs), engine=engine, db=_NoTurbineDB())
    desktop_results = engine.calculate_design_performance_with_mode(normalize_design_inputs(dict(inputs)))

    for key in (
        "power_shaft_total_kw",
        "head_kj_kg",
        "actual_poly_efficiency",
        "t_out",
        "compression_ratio",
    ):
        assert web_results.get(key) == pytest.approx(desktop_results.get(key), rel=1e-9, abs=1e-9), key
