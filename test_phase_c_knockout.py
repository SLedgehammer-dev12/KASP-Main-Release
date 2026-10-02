"""
Tests for Phase C: Process Thermodynamics — Intercooler VLE & Liquid Knockout Drum
"""

import math
import pytest
from kasp.core.vle import perform_vle_flash, calculate_wilson_k_values, solve_rachford_rice
from kasp.core.thermo import ThermoEngine


def test_vle_flash_dry_gas():
    """Kuru doğal gazda çiğlenme noktasına ulaşılmadığı için sıvı oluşmamalı (beta=1.0)."""
    comp = {"Methane": 90.0, "Ethane": 7.0, "Propane": 3.0}
    res = perform_vle_flash(p_pa=20e5, t_k=313.15, composition=comp, mass_flow_kgs=10.0)

    assert res["vapor_fraction"] == pytest.approx(1.0, abs=1e-5)
    assert res["liquid_fraction"] == pytest.approx(0.0, abs=1e-5)
    assert res["liquid_knockout_kg_h"] == pytest.approx(0.0, abs=1e-5)
    assert res["liquid_mass_flow_kgs"] == pytest.approx(0.0, abs=1e-5)
    assert res["vapor_mass_flow_kgs"] == pytest.approx(10.0, abs=1e-5)
    assert res["is_two_phase"] is False


def test_vle_flash_wet_gas():
    """Nemli gazda (su içeren) ara soğutucuda su yoğunlaşmalı ve kütle korunmalıdır."""
    comp = {"Methane": 85.0, "Water": 15.0}
    mass_feed = 10.0
    res = perform_vle_flash(p_pa=20e5, t_k=303.15, composition=comp, mass_flow_kgs=mass_feed)

    assert 0.0 < res["vapor_fraction"] < 1.0
    assert 0.0 < res["liquid_fraction"] < 1.0
    assert res["liquid_knockout_kg_h"] > 5000.0  # >5000 kg/h su ayrışmalı
    assert res["is_two_phase"] is True

    # Kütle dengesi analitik korunumu (m_feed = m_v + m_l)
    assert (res["vapor_mass_flow_kgs"] + res["liquid_mass_flow_kgs"]) == pytest.approx(mass_feed, abs=1e-9)

    # Buhar fazı metan yönünden zenginleşmeli (>98% metan)
    assert res["vapor_composition"]["METHANE"] > 98.0
    assert res["vapor_composition"]["WATER"] < 2.0

    # Sıvı fazı su yönünden zenginleşmeli (>90% su)
    assert res["liquid_composition"]["WATER"] > 90.0


def test_vle_flash_heavy_hydrocarbon():
    """Ağır hidrokarbon içeren zengin gazda (C6, C8) yoğuşma gerçekleşmeli."""
    comp = {"Methane": 75.0, "Ethane": 10.0, "Propane": 5.0, "Hexane": 5.0, "Octane": 5.0}
    mass_feed = 12.0
    res = perform_vle_flash(p_pa=25e5, t_k=295.15, composition=comp, mass_flow_kgs=mass_feed)

    assert res["is_two_phase"] is True
    assert res["liquid_knockout_kg_h"] > 1000.0
    # Kütle dengesi korunumu
    assert (res["vapor_mass_flow_kgs"] + res["liquid_mass_flow_kgs"]) == pytest.approx(mass_feed, abs=1e-9)

    # Sıvı fazda ağır hidrokarbonların toplamı belirgin şekilde artmalı
    c6_c8_liquid = res["liquid_composition"].get("HEXANE", 0.0) + res["liquid_composition"].get("OCTANE", 0.0)
    assert c6_c8_liquid > 50.0


def test_multistage_knockout_orchestration():
    """Çok kademeli tasarımda ara soğutucu scrubber drum simülasyonu."""
    engine = ThermoEngine()

    # 1. Kuru gaz 2 kademeli kompresör: Sıvı ayrışması = 0, kademe debileri eşit
    inputs_dry = {
        "p_in": 5.0, "p_in_unit": "bar(a)",
        "p_out": 25.0, "p_out_unit": "bar(a)",
        "t_in": 20.0, "t_in_unit": "°C",
        "flow": 10.0, "flow_unit": "kg/s",
        "num_stages": 2,
        "intercooler_t": 35.0, "intercooler_t_unit": "°C",
        "intercooler_dp_pct": 2.0,
        "gas_comp": {"Methane": 90.0, "Ethane": 7.0, "Propane": 3.0},
        "eos_method": "pr",
    }
    res_dry = engine.calculate_design_performance(inputs_dry)
    assert res_dry["liquid_knockout_total_kg_h"] == 0.0
    assert res_dry["stages"][0]["mass_flow_kgs"] == pytest.approx(10.0, abs=1e-4)
    assert res_dry["stages"][1]["mass_flow_kgs"] == pytest.approx(10.0, abs=1e-4)

    # 2. Islak gaz 2 kademeli kompresör: Ara soğutucuda su ayrışmalı ve kademe 2 debisi düşmeli
    inputs_wet = {
        "p_in": 5.0, "p_in_unit": "bar(a)",
        "p_out": 35.0, "p_out_unit": "bar(a)",
        "t_in": 40.0, "t_in_unit": "°C",
        "flow": 10.0, "flow_unit": "kg/s",
        "num_stages": 2,
        "intercooler_t": 25.0, "intercooler_t_unit": "°C",
        "intercooler_dp_pct": 2.0,
        "gas_comp": {"Methane": 85.0, "Water": 15.0},
        "eos_method": "pr",
    }
    res_wet = engine.calculate_design_performance(inputs_wet)
    assert res_wet["liquid_knockout_total_kg_h"] > 5000.0
    assert res_wet["stages"][0]["mass_flow_kgs"] == pytest.approx(10.0, abs=1e-4)
    assert res_wet["stages"][1]["mass_flow_kgs"] < 9.0  # Kademe 2 kütle debisi düşmeli
    assert any("Knockout Drum aktif" in w for w in res_wet.get("warnings", []))


def test_single_stage_no_intercooler():
    """Tek kademeli kompresörde ara soğutucu olmadığı için sıvı ayrışması sıfır olmalıdır."""
    engine = ThermoEngine()
    inputs = {
        "p_in": 5.0, "p_in_unit": "bar(a)",
        "p_out": 15.0, "p_out_unit": "bar(a)",
        "t_in": 30.0, "t_in_unit": "°C",
        "flow": 8.0, "flow_unit": "kg/s",
        "num_stages": 1,
        "gas_comp": {"Methane": 85.0, "Water": 15.0},
        "eos_method": "pr",
    }
    res = engine.calculate_design_performance(inputs)
    assert res["liquid_knockout_total_kg_h"] == 0.0
    assert len(res["stages"]) == 1
    assert res["stages"][0]["mass_flow_kgs"] == pytest.approx(8.0, abs=1e-4)
