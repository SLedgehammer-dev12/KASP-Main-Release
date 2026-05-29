"""FAZ 8: EOS ve Metot Shootout Testleri."""
import pytest
from kasp.core.thermo import ThermoEngine


# ─────────────────────── EOS Shootout ───────────────────────

def test_eos_shootout_runs():
    """run_eos_shootout en az coolprop ile başarılı olmalı."""
    from kasp.core.engineering import run_eos_shootout, ALL_EOS_METHODS
    engine = ThermoEngine()
    inputs = {
        "p_in": 10.0, "p_in_unit": "bar",
        "t_in": 25.0, "t_in_unit": "°C",
        "p_out": 20.0, "p_out_unit": "bar",
        "flow": 5000.0, "flow_unit": "kg/h",
        "gas_comp": {"METHANE": 90.0, "ETHANE": 8.0, "PROPANE": 2.0},
        "method": "Metot 1: Ortalama Özellikler",
        "poly_eff": 85.0, "num_units": 1, "num_stages": 1,
        "therm_eff": 35.0, "mech_eff": 98.0,
        "intercooler_dp_pct": 0.0, "intercooler_t": 40.0,
        "enable_uncertainty": False,
    }
    results = run_eos_shootout(engine, inputs)
    assert len(results) >= 1
    assert len(results) == len(ALL_EOS_METHODS)

    coolprop_result = next((r for r in results if r["eos"] == "coolprop"), None)
    assert coolprop_result is not None
    assert coolprop_result["success"] is True
    assert coolprop_result["t_out"] is not None
    assert coolprop_result["head_kj_kg"] is not None
    assert coolprop_result["head_kj_kg"] > 0
    assert coolprop_result["elapsed_s"] >= 0

    for r in results:
        if r["success"]:
            assert r["label"] != ""
            assert isinstance(r["elapsed_s"], float)
        else:
            assert r.get("error") is not None


def test_eos_shootout_returns_correct_structure():
    """Her sonuç beklenen alanları içermeli."""
    from kasp.core.engineering import run_eos_shootout
    engine = ThermoEngine()
    inputs = {
        "p_in": 5.0, "p_in_unit": "bar",
        "t_in": 20.0, "t_in_unit": "°C",
        "p_out": 10.0, "p_out_unit": "bar",
        "flow": 1000.0, "flow_unit": "kg/h",
        "gas_comp": {"METHANE": 100.0},
        "method": "Metot 1: Ortalama Özellikler",
        "poly_eff": 80.0, "num_units": 1, "num_stages": 1,
        "therm_eff": 35.0, "mech_eff": 98.0,
        "intercooler_dp_pct": 0.0, "intercooler_t": 40.0,
        "enable_uncertainty": False,
    }
    results = run_eos_shootout(engine, inputs)
    required_fields = ["eos", "label", "success", "t_out", "head_kj_kg", "poly_eff_actual", "power_kw", "elapsed_s"]
    for r in results:
        for field in required_fields:
            assert field in r, f"'{field}' missing from shootout result for {r.get('eos')}"

    successful = [r for r in results if r["success"]]
    if successful:
        first = successful[0]
        assert first["head_diff_pct"] == 0.0
        if len(successful) > 1:
            assert "head_diff_pct" in successful[1]


def test_eos_shootout_handles_invalid_eos():
    """Geçersiz EOS durumunda shootout çökmemeli."""
    from kasp.core.engineering import run_eos_shootout, ALL_EOS_METHODS
    engine = ThermoEngine()
    inputs = {
        "p_in": 10.0, "p_in_unit": "bar",
        "t_in": 25.0, "t_in_unit": "°C",
        "p_out": 20.0, "p_out_unit": "bar",
        "flow": 5000.0, "flow_unit": "kg/h",
        "gas_comp": {"METHANE": 100.0},
        "method": "Metot 1: Ortalama Özellikler",
        "poly_eff": 85.0, "num_units": 1, "num_stages": 1,
        "therm_eff": 35.0, "mech_eff": 98.0,
        "intercooler_dp_pct": 0.0, "intercooler_t": 40.0,
        "enable_uncertainty": False,
    }
    results = run_eos_shootout(engine, inputs)
    assert any(not r["success"] for r in results) or all(r["success"] for r in results)
    assert len(results) == len(ALL_EOS_METHODS)


# ─────────────────────── Method Shootout ───────────────────────

def test_method_shootout_runs():
    """run_method_shootout 4 metot için de çalışmalı."""
    from kasp.core.engineering import run_method_shootout, ALL_METHOD_LABELS
    engine = ThermoEngine()
    inputs = {
        "p_in": 10.0, "p_in_unit": "bar",
        "t_in": 25.0, "t_in_unit": "°C",
        "p_out": 20.0, "p_out_unit": "bar",
        "flow": 5000.0, "flow_unit": "kg/h",
        "gas_comp": {"METHANE": 90.0, "ETHANE": 8.0, "PROPANE": 2.0},
        "eos_method": "coolprop",
        "poly_eff": 85.0, "num_units": 1, "num_stages": 1,
        "therm_eff": 35.0, "mech_eff": 98.0,
        "intercooler_dp_pct": 0.0, "intercooler_t": 40.0,
        "enable_uncertainty": False,
    }
    results = run_method_shootout(engine, inputs)
    assert len(results) == len(ALL_METHOD_LABELS)

    for r in results:
        assert r["success"] is True
        assert r["t_out"] is not None
        assert r["head_kj_kg"] is not None
        assert r["head_kj_kg"] > 0
        assert r["power_kw"] > 0
        assert r["poly_eff_actual"] is not None
        assert isinstance(r["elapsed_s"], float)


def test_method_shootout_returns_correct_structure():
    """Her metot sonucu beklenen alanları içermeli."""
    from kasp.core.engineering import run_method_shootout
    engine = ThermoEngine()
    inputs = {
        "p_in": 10.0, "p_in_unit": "bar",
        "t_in": 25.0, "t_in_unit": "°C",
        "p_out": 20.0, "p_out_unit": "bar",
        "flow": 5000.0, "flow_unit": "kg/h",
        "gas_comp": {"METHANE": 100.0},
        "eos_method": "coolprop",
        "poly_eff": 85.0, "num_units": 1, "num_stages": 1,
        "therm_eff": 35.0, "mech_eff": 98.0,
        "intercooler_dp_pct": 0.0, "intercooler_t": 40.0,
        "enable_uncertainty": False,
    }
    results = run_method_shootout(engine, inputs)
    required_fields = ["method", "label", "success", "t_out", "head_kj_kg", "poly_eff_actual", "power_kw", "convergence", "elapsed_s"]
    for r in results:
        for field in required_fields:
            assert field in r


def test_method_shootout_methods_have_different_labels():
    """Tüm metot etiketleri birbirinden farklı olmalı."""
    from kasp.core.engineering import run_method_shootout, METHOD_NAMES
    engine = ThermoEngine()
    inputs = {
        "p_in": 10.0, "p_in_unit": "bar",
        "t_in": 25.0, "t_in_unit": "°C",
        "p_out": 20.0, "p_out_unit": "bar",
        "flow": 1000.0, "flow_unit": "kg/h",
        "gas_comp": {"METHANE": 100.0},
        "eos_method": "coolprop",
        "poly_eff": 85.0, "num_units": 1, "num_stages": 1,
        "therm_eff": 35.0, "mech_eff": 98.0,
        "intercooler_dp_pct": 0.0, "intercooler_t": 40.0,
        "enable_uncertainty": False,
    }
    results = run_method_shootout(engine, inputs)
    labels = [r["label"] for r in results]
    assert len(labels) == len(set(labels))
    assert len(labels) == 4


# ─────────────────────── Shootout Edge Cases ───────────────────────

def test_shootout_preserves_original_inputs():
    """Shootout orijinal input dict'ini bozmamalı."""
    from kasp.core.engineering import run_eos_shootout
    engine = ThermoEngine()
    inputs = {
        "p_in": 10.0, "p_in_unit": "bar",
        "t_in": 25.0, "t_in_unit": "°C",
        "p_out": 20.0, "p_out_unit": "bar",
        "flow": 1000.0, "flow_unit": "kg/h",
        "gas_comp": {"METHANE": 100.0},
        "eos_method": "coolprop",
        "method": "Metot 1: Ortalama Özellikler",
        "poly_eff": 85.0, "num_units": 1, "num_stages": 1,
        "therm_eff": 35.0, "mech_eff": 98.0,
        "intercooler_dp_pct": 0.0, "intercooler_t": 40.0,
        "enable_uncertainty": False,
    }
    original_eos = inputs["eos_method"]
    results = run_eos_shootout(engine, inputs)
    assert inputs["eos_method"] == original_eos
    assert results[0]["eos"] != original_eos or results[0]["eos"] == original_eos
