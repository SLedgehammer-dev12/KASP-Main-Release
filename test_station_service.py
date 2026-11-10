"""Tests for Compressor Station Process Modeling Service and API Endpoint."""

import pytest
from kasp.services.station_service import calculate_station_process_model


def test_station_process_model_default_inputs():
    inputs = {
        "flow": 60.0,
        "flow_unit": "kg/s",
        "p_in": 25.0,
        "p_in_unit": "bar(a)",
        "p_out": 75.0,
        "p_out_unit": "bar(a)",
        "t_in": 20.0,
        "gas_comp": {"CH4": 0.92, "C2H6": 0.05, "CO2": 0.03},
    }

    res = calculate_station_process_model(inputs)
    assert res["success"] is True
    
    summary = res["station_summary"]
    assert summary["total_mass_flow_kgs"] == 60.0
    assert summary["pressure_ratio"] == 3.0
    assert summary["volumetric_flow_mmscmd"] > 0
    assert summary["cooler_heat_duty_mw"] > 0

    equip = res["equipment_sizing"]
    # 60 kg/s / 22 kg/s per cyclone = 3 operating + 1 spare = 4
    assert equip["cyclones"]["operating_count"] >= 2
    assert equip["cyclones"]["installed_count"] >= 3

    # Cartridge filters
    assert equip["cartridge_filters"]["operating_count"] >= 2
    assert equip["cartridge_filters"]["installed_count"] >= 3

    # Turbo-compressor trains & building
    assert equip["turbo_compressors"]["operating_count"] >= 1
    assert equip["compressor_building"]["area_m2"] > 100

    # Anti-surge & Recycle
    assert equip["turbo_compressors"]["anti_surge_valve_size_in"] >= 8
    assert equip["station_recycle"]["max_recirculation_capacity_kgs"] > 0

    # Coolers & Relief
    assert equip["air_coolers"]["bay_count"] >= 2
    assert equip["safety_relief_and_blowdown"]["psv_count"] == 2
    assert equip["safety_relief_and_blowdown"]["psv_set_pressure_bar"] > 75.0

    # Nodes & Pipe flows
    assert len(res["nodes"]) >= 8
    assert "main_suction" in res["pipe_flows"]
    assert "anti_surge_loop" in res["pipe_flows"]
    assert "station_recycle" in res["pipe_flows"]


def test_station_api_endpoint():
    from fastapi.testclient import TestClient
    from kasp.api.server import app

    client = TestClient(app)
    payload = {
        "inputs": {
            "flow": 45.0,
            "flow_unit": "kg/s",
            "p_in": 20.0,
            "p_in_unit": "bar(a)",
            "p_out": 60.0,
            "p_out_unit": "bar(a)",
            "t_in": 15.0,
        }
    }

    response = client.post("/api/v1/calculations/station", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "station_summary" in data
    assert "equipment_sizing" in data


def test_station_accepts_web_gas_keys_and_mass_flow():
    """Web sends METHANE/CARBONDIOXIDE keys and an explicit kg/s mass_flow."""
    inputs = {
        "flow": 12.0,
        "flow_unit": "Sm³/h",  # deliberately different from mass_flow
        "mass_flow": 30.0,
        "p_in": 20.0,
        "p_in_unit": "bar(a)",
        "p_out": 60.0,
        "p_out_unit": "bar(a)",
        "t_in": 25.0,
        "t_in_unit": "°C",
        "gas_comp": {
            "METHANE": 88.0,
            "ETHANE": 7.0,
            "PROPANE": 3.0,
            "NITROGEN": 1.0,
            "CARBONDIOXIDE": 1.0,
        },
    }
    res = calculate_station_process_model(inputs)
    assert res["station_summary"]["total_mass_flow_kgs"] == 30.0
    # Natural gas mixture MW must be ~18.2 g/mol, not the 16.04 fallback.
    assert res["station_summary"]["gas_mw"] > 17.0


def test_station_converts_gauge_pressure_and_temperature_units():
    inputs = {
        "flow": 30.0,
        "flow_unit": "kg/s",
        "p_in": 20.0,
        "p_in_unit": "bar(g)",
        "p_out": 60.0,
        "p_out_unit": "bar(g)",
        "t_in": 298.15,
        "t_in_unit": "K",
        "gas_comp": {"METHANE": 90.0, "ETHANE": 10.0},
    }
    res = calculate_station_process_model(inputs)
    assert res["station_summary"]["suction_pressure_bar"] == pytest.approx(21.01, abs=0.02)
    assert res["station_summary"]["discharge_pressure_bar"] == pytest.approx(61.01, abs=0.02)
    assert res["nodes"][0]["temp_c"] == pytest.approx(25.0, abs=0.1)


def test_station_uses_real_design_results():
    inputs = {
        "flow": 12.0,
        "flow_unit": "kg/s",
        "mass_flow": 12.0,
        "p_in": 20.0,
        "p_in_unit": "bar(a)",
        "p_out": 60.0,
        "p_out_unit": "bar(a)",
        "t_in": 25.0,
        "gas_comp": {"METHANE": 90.0, "ETHANE": 10.0},
    }
    design = {
        "power_shaft_per_unit_kw": 2999.0,
        "t_out_c": 111.0,
        "head_kj_kg": 222.0,
        "mass_flow_per_unit_kgs": 12.0,
        "mass_flow_total_kgs": 12.0,
        "num_units": 1,
        "compression_ratio": 3.0,
        "actual_poly_efficiency": 0.80,
    }
    res = calculate_station_process_model(inputs, design_results=design)
    assert res["station_summary"]["total_power_mw"] == pytest.approx(3.0, abs=0.01)
    assert res["nodes"][4]["temp_c"] == pytest.approx(111.0, abs=0.1)
