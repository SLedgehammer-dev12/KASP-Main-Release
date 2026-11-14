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


def test_station_mfs_dynamic_sizing_and_spec_5260_4500_compliance():
    """Verify MFS defaults to PFD 2+1 (%50), sizes dynamically without 22 kg/s cap, and fulfills 5260 & 4500 §5.2."""
    res_auto_60 = calculate_station_process_model({
        "flow": 60.0,
        "flow_unit": "kg/s",
        "p_in": 35.0,
        "p_in_unit": "bar(a)",
        "p_out": 75.0,
        "p_out_unit": "bar(a)",
        "t_in": 20.0,
        "ambient_temp": -5.0,
        "gas_comp": {"METHANE": 92.0, "ETHANE": 5.0, "CARBONDIOXIDE": 3.0},
    })
    cyc = res_auto_60["equipment_sizing"]["cyclones"]
    # PFD / Özel Şartname §4.8.2: 3 units total (2 operating + 1 standby, %50 station capacity each)
    assert cyc["operating_count"] == 2
    assert cyc["standby_count"] == 1
    assert cyc["installed_count"] == 3
    assert cyc["unit_capacity_pct"] == pytest.approx(50.0, abs=0.1)
    assert cyc["flow_per_unit_kgs"] == pytest.approx(30.0, abs=0.1)
    assert cyc["unit_design_capacity_kgs"] == pytest.approx(30.0, abs=0.1)
    assert cyc["efficiency_8um_pct"] == pytest.approx(100.0)
    assert cyc["efficiency_4um_pct"] == pytest.approx(90.0)
    assert cyc["max_clean_dp_bar"] == pytest.approx(0.400)
    assert cyc["dirty_alarm_dp_bar"] == pytest.approx(0.700)
    assert 0.05 < cyc["pressure_drop_bar"] <= 0.400
    assert cyc["corrosion_allowance_mm"] == pytest.approx(1.6)
    assert cyc["head_type"] == "Spherical Fixed"
    assert cyc["internal_bolts_material"] == "Stainless Steel"
    assert cyc["design_code"] == "ASME BPVC Sec. VIII & IX"
    assert cyc["has_manway"] is True
    assert cyc["vessel_diameter_mm"] > 508

    # Blow-flask + dual instrument bottles + dump tank >= 15x + >= 2°C heat tracing (4500 §5.2)
    bf = cyc["blow_flask"]
    assert bf["orientation"] == "horizontal"
    assert bf["located_below_barrel"] is True
    assert bf["dump_volume_m3"] > 0
    assert bf["diameter_mm"] > 0 and bf["length_mm"] > bf["diameter_mm"]

    lvl = cyc["level_instrumentation"]
    assert lvl["bottles_count"] == 2
    assert lvl["online_isolatable"] is True

    dump = cyc["dump_system"]
    assert dump["atmospheric_cyclone_with_flame_arrestor"] is True
    assert dump["inter_separator_purge_line"] is True
    assert dump["min_dump_tank_volume_m3"] >= max(3.0, 15.0 * bf["dump_volume_m3"]) - 1e-6
    assert res_auto_60["equipment_sizing"]["condensate_system"]["collection_tank_volume_m3"] >= dump["min_dump_tank_volume_m3"]

    ht = cyc["heat_tracing"]
    assert ht["insulated"] is True
    assert ht["electrical_traced"] is True
    assert ht["min_temp_c"] == pytest.approx(2.0)
    assert ht["freeze_risk_active"] is True  # ambient_temp = -5 °C < 2 °C
    assert any("heat tracing" in w.lower() or "2 °c" in w.lower() for w in cyc["design_warnings"])

    # Dynamic scaling when flow doubles (still PFD 2+1 by default) OR when user picks 4+1
    res_auto_120 = calculate_station_process_model({
        "flow": 120.0,
        "flow_unit": "kg/s",
        "p_in": 35.0,
        "p_in_unit": "bar(a)",
        "p_out": 75.0,
        "p_out_unit": "bar(a)",
        "t_in": 20.0,
        "gas_comp": {"METHANE": 92.0, "ETHANE": 5.0, "CARBONDIOXIDE": 3.0},
    })
    cyc_120 = res_auto_120["equipment_sizing"]["cyclones"]
    assert cyc_120["operating_count"] == 2
    assert cyc_120["installed_count"] == 3
    assert cyc_120["flow_per_unit_kgs"] == pytest.approx(60.0, abs=0.1)
    assert cyc_120["vessel_diameter_mm"] >= cyc["vessel_diameter_mm"]
    assert cyc_120["internal_cyclone_elements"] > cyc["internal_cyclone_elements"]

    res_user_4 = calculate_station_process_model({
        "flow": 120.0,
        "flow_unit": "kg/s",
        "p_in": 35.0,
        "p_in_unit": "bar(a)",
        "p_out": 75.0,
        "p_out_unit": "bar(a)",
        "t_in": 20.0,
        "cyclone_op_count": 4,
        "gas_comp": {"METHANE": 92.0, "ETHANE": 5.0, "CARBONDIOXIDE": 3.0},
    })
    cyc_u4 = res_user_4["equipment_sizing"]["cyclones"]
    assert cyc_u4["operating_count"] == 4
    assert cyc_u4["installed_count"] == 5
    assert cyc_u4["unit_capacity_pct"] == pytest.approx(25.0, abs=0.1)
    assert cyc_u4["flow_per_unit_kgs"] == pytest.approx(30.0, abs=0.1)
    assert cyc_u4["internal_cyclone_elements"] < cyc_120["internal_cyclone_elements"]

    # High-flow Adapazarı nominal load (180 kg/s @ 45 bar, PFD 2+1) must stay <= 400 mbar clean ΔP
    res_180 = calculate_station_process_model({
        "flow": 180.0,
        "flow_unit": "kg/s",
        "p_in": 45.0,
        "p_in_unit": "bar(a)",
        "p_out": 75.0,
        "p_out_unit": "bar(a)",
        "t_in": 15.0,
        "gas_comp": {"METHANE": 94.0, "ETHANE": 4.0, "CARBONDIOXIDE": 2.0},
    })
    cyc_180 = res_180["equipment_sizing"]["cyclones"]
    assert cyc_180["operating_count"] == 2
    assert cyc_180["installed_count"] == 3
    assert cyc_180["flow_per_unit_kgs"] == pytest.approx(90.0, abs=0.1)
    assert cyc_180["pressure_drop_bar"] <= 0.400
    assert cyc_180["internal_cyclone_elements"] > 36


def test_station_cfs_dynamic_sizing_and_spec_5210_ozel_compliance():
    """Verify CFS defaults to PFD 2+1 (%50), eliminates fixed 18 kg/s cap, and meets Spec 5210 & Ozel §4.8.2."""
    res_60 = calculate_station_process_model({
        "flow": 60.0,
        "flow_unit": "kg/s",
        "p_in": 35.0,
        "p_in_unit": "bar(a)",
        "p_out": 75.0,
        "p_out_unit": "bar(a)",
        "t_in": 20.0,
        "ambient_temp": -5.0,
        "gas_comp": {"METHANE": 92.0, "ETHANE": 5.0, "CARBONDIOXIDE": 3.0},
    })
    flt = res_60["equipment_sizing"]["cartridge_filters"]
    assert flt["operating_count"] == 2
    assert flt["standby_count"] == 1
    assert flt["installed_count"] == 3
    assert flt["unit_capacity_pct"] == pytest.approx(50.0, abs=0.1)
    assert flt["flow_per_unit_kgs"] == pytest.approx(30.0, abs=0.1)
    assert flt["unit_design_capacity_kgs"] == pytest.approx(30.0, abs=0.1)
    assert flt["efficiency_solid_3um_pct"] == pytest.approx(99.8)
    assert flt["max_clean_dp_bar"] == pytest.approx(0.140)
    assert flt["dirty_changeout_dp_bar"] == pytest.approx(0.300)
    assert flt["element_burst_pressure_bar"] == pytest.approx(3.0)
    assert 0.03 <= flt["clean_dp_bar"] <= 0.140
    assert "QOC" in flt["closure_type"] and "Davit" in flt["closure_type"]
    assert "ASME" in flt["design_code"] and "CE" in flt["design_code"]
    assert flt["hydro_test_factor"] == pytest.approx(1.5)
    assert "NR 80" in flt["noise_limit"]
    assert "3 set" in flt["spare_sets_required"]

    bf = flt["blow_flask"]
    assert bf["orientation"] == "horizontal"
    assert bf["located_below_barrel"] is True
    assert bf["diameter_mm"] > 0 and bf["length_mm"] > bf["diameter_mm"]

    ht = flt["heat_tracing"]
    assert ht["insulated"] is True
    assert ht["insulation_brackets_factory_installed"] is True
    assert ht["self_regulating"] is True
    assert ht["min_temp_c"] == pytest.approx(2.0)
    assert ht["freeze_risk_active"] is True
    assert any("2 °C" in w or "heat tracing" in w.lower() for w in flt["design_warnings"])

    # High-flow PFD 2+1 (180 kg/s @ 45 bar) stays <= 140 mbar clean ΔP & user 4+1 reduces unit flow
    res_180 = calculate_station_process_model({
        "flow": 180.0,
        "flow_unit": "kg/s",
        "p_in": 45.0,
        "p_in_unit": "bar(a)",
        "p_out": 75.0,
        "p_out_unit": "bar(a)",
        "t_in": 15.0,
        "gas_comp": {"METHANE": 94.0, "ETHANE": 4.0, "CARBONDIOXIDE": 2.0},
    })
    flt_180 = res_180["equipment_sizing"]["cartridge_filters"]
    assert flt_180["operating_count"] == 2
    assert flt_180["installed_count"] == 3
    assert flt_180["flow_per_unit_kgs"] == pytest.approx(90.0, abs=0.1)
    assert flt_180["clean_dp_bar"] <= 0.140
    assert flt_180["cartridge_elements_count"] > flt["cartridge_elements_count"]

    res_u4 = calculate_station_process_model({
        "flow": 180.0,
        "flow_unit": "kg/s",
        "p_in": 45.0,
        "p_in_unit": "bar(a)",
        "p_out": 75.0,
        "p_out_unit": "bar(a)",
        "t_in": 15.0,
        "filter_op_count": 4,
        "gas_comp": {"METHANE": 94.0, "ETHANE": 4.0, "CARBONDIOXIDE": 2.0},
    })
    flt_u4 = res_u4["equipment_sizing"]["cartridge_filters"]
    assert flt_u4["operating_count"] == 4
    assert flt_u4["installed_count"] == 5
    assert flt_u4["unit_capacity_pct"] == pytest.approx(25.0, abs=0.1)
    assert flt_u4["flow_per_unit_kgs"] == pytest.approx(45.0, abs=0.1)
    assert flt_u4["cartridge_elements_count"] < flt_180["cartridge_elements_count"]


def test_station_turbo_compressor_auxiliaries_and_spec_4500_ozel_compliance():
    """Verify Turbo-Compressor Item 4 specs: dynamic trains, ISO 6976 fuel gas, DGS, lube oil, dual unit valves & strainer."""
    res_base = calculate_station_process_model({
        "flow": 90.0,
        "flow_unit": "kg/s",
        "p_in": 35.0,
        "p_in_unit": "bar(a)",
        "p_out": 75.0,
        "p_out_unit": "bar(a)",
        "t_in": 20.0,
        "poly_eff": 86.0,
        "therm_eff": 36.0,
        "ambient_temp": 15.0,
        "gas_comp": {"METHANE": 92.0, "ETHANE": 5.0, "CARBONDIOXIDE": 3.0},
    })
    tc = res_base["equipment_sizing"]["turbo_compressors"]
    bldg = res_base["equipment_sizing"]["compressor_building"]
    fg_root = res_base["equipment_sizing"]["fuel_gas"]

    # 1. Dynamic train sizing (not hardcoded 35 kg/s cap): adapts to actual power & head, user override respected
    assert tc["operating_count"] >= 1
    assert tc["standby_count"] == 1
    assert tc["installed_count"] == tc["operating_count"] + 1
    assert bldg["crane_capacity_tons"] >= 15.0

    # 2. Unit Valves & Temporary Startup Strainer (Spec 4500 §5.5-5.8 & Özel §4.8)
    uv = tc["unit_valves_and_strainer"]
    assert uv["suction_series_valves_count"] == 2
    assert uv["discharge_series_valves_count"] == 2
    assert uv["motor_actuator_stroke_max_s"] <= 30.0
    assert uv["temporary_startup_strainer"] is True
    assert uv["reducers_adjacent_to_nozzles"] is True
    assert uv["discharge_non_slam_check_valve"] is True
    assert uv["asv_downstream_check_and_shutoff"] is True
    assert uv["purge_volume_changes"] >= 7 and uv["purge_min_time_s"] >= 15.0
    assert uv["vent_max_time_s"] <= 60.0

    # 3. Dry Gas Seal (Spec 4500 §6.5 & Özel §6.1.2)
    dgs = tc["dry_gas_seal"]
    assert "API 692" in dgs["standard"]
    assert dgs["filtration_rating_um"] == pytest.approx(1.0)
    assert dgs["duplex_redundant"] is True
    assert "PDCV" in dgs["control_mode"]
    assert dgs["seal_gas_heater_included"] is True
    assert "Carbon" in dgs["separation_seal"] or "Karbon" in dgs["separation_seal"]
    assert "2 set" in dgs["spare_sets_required"]

    # 4. Fuel Gas System with real ISO 6976 LHV & Pre-Cooler Take-Off (Spec 4500 §8.1-8.5 & Özel §4.8.5)
    fg = tc["fuel_gas_system"]
    assert fg_root["takeoff_downstream_of_main_filters"] is True
    assert fg_root["takeoff_upstream_of_gas_cooler"] is True
    assert fg["thermal_efficiency_pct"] == pytest.approx(36.0)
    assert fg["lhv_kj_kg"] > 40000.0
    assert fg["fuel_per_unit_kgh"] > 0.0 and fg["fuel_per_unit_sm3h"] > 0.0
    assert fg["design_fuel_per_unit_kgh"] == pytest.approx(fg["fuel_per_unit_kgh"] * 1.20, rel=1e-2)
    assert fg["separator_filtration_um"] == pytest.approx(1.0)
    assert fg["separator_heat_tracing_min_c"] == pytest.approx(2.0)
    assert "20" in fg["heat_exchanger_outlet_c"]
    assert "316" in fg["pipe_material"]
    assert "2 set" in fg["spare_sets_required"]

    # Heavy hydrocarbon gas has different mass LHV -> different fuel consumption even at identical shaft power
    res_heavy = calculate_station_process_model({
        "flow": 90.0,
        "flow_unit": "kg/s",
        "p_in": 35.0,
        "p_in_unit": "bar(a)",
        "p_out": 75.0,
        "p_out_unit": "bar(a)",
        "t_in": 20.0,
        "poly_eff": 86.0,
        "therm_eff": 36.0,
        "gas_comp": {"METHANE": 75.0, "PROPANE": 15.0, "NITROGEN": 10.0},
    })
    assert res_heavy["equipment_sizing"]["turbo_compressors"]["fuel_gas_system"]["lhv_kj_kg"] < fg["lhv_kj_kg"]

    # 5. Lube Oil System (Spec 4500 §6.7 & Özel §6.1.1.3)
    lo = tc["lube_oil_system"]
    assert lo["flow_lpm_per_unit"] > 50.0
    assert lo["reservoir_min_retention_min"] == pytest.approx(5.0)
    assert lo["reservoir_min_working_volume_l"] == pytest.approx(lo["flow_lpm_per_unit"] * 5.0, rel=1e-2)
    assert lo["reservoir_min_surface_area_cm2"] == pytest.approx(lo["flow_lpm_per_unit"] * 51.0, rel=1e-2)
    assert lo["filter_nominal_um"] == pytest.approx(10.0)
    assert lo["duplex_online_replaceable"] is True
    assert lo["aerial_cooler_fans"] == 2
    assert lo["aerial_cooler_3way_bypass"] is True
    assert lo["ups_dc_emergency_pump"] is True
    assert lo["magnetic_chip_detectors"] is True
    assert "2 set" in lo["spare_sets_required"]

    # 6. Combustion Air Intake, Noise & High Suction Overload Warnings (Spec 4500 §6.4 & Özel §4.8, §6.1.1.4)
    ai = tc["air_intake_and_enclosure"]
    assert ai["air_intake_clean_dp_max_mbar"] == pytest.approx(8.0)
    assert ai["air_intake_dirty_dp_mbar"] == pytest.approx(7.5)
    assert ai["air_intake_trip_dp_mbar"] == pytest.approx(12.5)
    assert ai["exhaust_max_dp_mbar"] == pytest.approx(10.0)
    assert ai["exhaust_max_surface_temp_c"] == pytest.approx(55.0)
    assert ai["enclosure_max_temp_c"] == pytest.approx(80.0)
    assert ai["enclosure_ventilation_ups"] is True

    # High suction pressure (67 bar -> 65-70 bar regime) + low poly_eff (<85%) trigger explicit Spec warnings
    res_high_p = calculate_station_process_model({
        "flow": 90.0,
        "flow_unit": "kg/s",
        "p_in": 67.0,
        "p_in_unit": "bar(a)",
        "p_out": 85.0,
        "p_out_unit": "bar(a)",
        "t_in": 20.0,
        "poly_eff": 82.0,
        "gas_comp": {"METHANE": 92.0, "ETHANE": 5.0, "CARBONDIOXIDE": 3.0},
    })
    tc_warns = res_high_p["equipment_sizing"]["turbo_compressors"]["design_warnings"]
    assert any("65" in w or "overload" in w.lower() or "tork" in w.lower() for w in tc_warns)
    assert any("85" in w and "verim" in w.lower() for w in tc_warns)


def test_station_gas_cooler_dynamic_dp_5234_and_utilities_compliance():
    """Verify dynamic Fin-Fan ΔP, Spec 5234/4500 §5.14/Özel §4.8.4, TCV, and Station Utilities (§7, §9, §10, §11)."""
    from kasp.services.station_service import calculate_station_process_model

    base = {
        "flow": 90.0,
        "flow_unit": "kg/s",
        "p_in": 40.0,
        "p_in_unit": "bar(a)",
        "p_out": 76.0,
        "p_out_unit": "bar(a)",
        "t_in": 20.0,
        "ambient_temp": 15.0,
        "gas_comp": {"METHANE": 85.0, "ETHANE": 7.0, "PROPANE": 3.0, "NITROGEN": 3.0, "CARBONDIOXIDE": 2.0},
    }
    res = calculate_station_process_model(base)
    res_high_flow = calculate_station_process_model({**base, "flow": 360.0, "cooler_bays_count": 2})

    ac = res["equipment_sizing"]["air_coolers"]
    ac_hi = res_high_flow["equipment_sizing"]["air_coolers"]
    # Dynamic Fin-Fan gas-side ΔP responds to flow/bay sizing instead of staying fixed 0.40
    assert 0.05 <= ac["pressure_drop_bar"] <= 0.85
    assert ac_hi["pressure_drop_bar"] > ac["pressure_drop_bar"]
    assert ac["tube_bundle"]["tube_wall_bwg"] == "12 BWG"
    assert ac["tube_bundle"]["allowable_dp_bar"] == pytest.approx(0.50)

    # Spec 5234 & Özel §4.8.4 mechanical/fan/TCV contract
    assert "Forced-Draft" in ac["draft_type"]
    assert ac["fan_blades_min"] == 4
    assert ac["max_fan_tip_speed_ms"] == pytest.approx(50.0)
    assert ac["fan_motor_max_kw"] == pytest.approx(29.8)
    assert ac["noise_limit_150m_dba"] == pytest.approx(55.0)
    assert ac["design_reference_ambient_c"] == pytest.approx(40.0)
    assert ac["max_design_gas_outlet_c"] == pytest.approx(45.0)
    assert "IEEE 519" in ac["vfd_drive_spec"]
    assert "95" in ac["vfd_drive_spec"]
    assert "Murphy" in ac["vibration_switches"] or "titreşim" in ac["vibration_switches"].lower()
    assert "panjur" in ac["louver_and_sunshade"].lower() and "2.0 mm" in ac["louver_and_sunshade"]
    assert "ON/OFF" in ac["tcv_control_spec"]
    assert "Gas-over-Oil" in ac["tcv_control_spec"]
    assert "Fail-Open" in ac["tcv_control_spec"]

    # Exceeding Spec 40°C ambient / 45°C gas outlet triggers explicit warnings
    res_hot = calculate_station_process_model({
        **base,
        "cooler_air_temp_c": 42.0,
        "cooler_max_outlet_temp_c": 48.0,
    })
    assert any("40" in w and "45" in w or "40" in w for w in res_hot["warnings"])

    # Station Utilities (§7 Power Gas, §9/Özel §4.8.6 Utility Gas, §10/Özel §4.8.7 Compressed Air, §11 Heating, §5.9-5.13)
    util = res["equipment_sizing"]["station_utilities"]
    pg = util["power_gas"]
    assert pg["design_pressure_bar"] >= 75.0
    assert pg["methanol_dehydrator"]["included"] is True
    assert pg["methanol_dehydrator"]["hammerschmidt_depression_c"] >= 10.0

    ug = util["utility_gas"]
    assert ug["min_skid_capacity_sm3h"] == pytest.approx(1485.0)
    assert ug["calculated_demand_sm3h"] >= 1485.0
    assert "Soğutucu Giriş" in ug["takeoff_location"] or "Cooler" in ug["takeoff_location"]
    assert ug["odorizer_included"] is True
    assert ug["electric_heater_external_mcc"] is True
    assert ug["preheat_dewpoint_margin_c"] >= 10.0
    assert "PE" in ug["underground_distribution_material"]

    ca = util["compressed_air"]
    assert ca["dewpoint_c"] == pytest.approx(-40.0)
    assert ca["high_dewpoint_alarm_c"] == pytest.approx(-20.0)
    assert ca["receiver_volume_m3"] >= 25.0
    assert ca["holdup_time_min"] >= 10.0
    assert "304" in ca["piping_material"]
    assert "1+1" in ca["compressor_configuration"]

    hg = util["heating_glycol"]
    assert "90/70" in hg["medium"]
    assert "50/%50" in hg["medium"] or "50/50" in hg["medium"]
    assert "2 × %70" in hg["boilers"]
    assert "3 × %50" in hg["pumps"]

    res_winter = calculate_station_process_model({**base, "ambient_temp": -15.0})
    assert res_winter["equipment_sizing"]["station_utilities"]["heating_glycol"]["heat_load_kw"] > hg["heat_load_kw"]

    sb = util["safety_and_bypass"]
    assert sb["usm_4500"]["paths_min"] >= 4
    assert sb["psv_4500"]["min_distance_from_buildings_m"] == pytest.approx(35.0)
    assert sb["psv_4500"]["dual_outlet_flanged"] is True
    assert sb["bdv_4500"]["target_pressure_barg"] == pytest.approx(1.0)
    assert sb["bdv_4500"]["max_blowdown_time_s"] == pytest.approx(60.0)
    assert sb["bdv_4500"]["esd_60s_compliant"] is False  # default 15 dk exceeds 60s
    res_fast_bdv = calculate_station_process_model({**base, "bdv_depressurization_time_min": 1.0})
    assert res_fast_bdv["equipment_sizing"]["station_utilities"]["safety_and_bypass"]["bdv_4500"]["esd_60s_compliant"] is True
    assert "4500 §5.12" in sb["loading_line"]
    assert "4500 §5.13" in sb["station_bypass_check"]


def test_station_recycle_pigging_condensate_5250_and_fire_water_compliance():
    """Verify Items 6, 9, 10 & 11b: Recycle NRV/PowerGas, PIG 0.5-4 barg/Loading/Bypass, Condensate 5250, Fire Water 300m3."""
    from kasp.services.station_service import calculate_station_process_model

    res = calculate_station_process_model({
        "flow": 90.0,
        "flow_unit": "kg/s",
        "p_in": 40.0,
        "p_in_unit": "bar(a)",
        "p_out": 76.0,
        "p_out_unit": "bar(a)",
        "t_in": 20.0,
        "gas_comp": {"METHANE": 85.0, "ETHANE": 7.0, "PROPANE": 3.0, "NITROGEN": 3.0, "CARBONDIOXIDE": 2.0},
    })
    eq = res["equipment_sizing"]

    # Item 6: Station Recycle NRV + Power-Gas Actuator Bottle + Note 13 separation
    rec = eq["station_recycle"]
    assert rec["inline_check_valve_nrv"] is True
    assert rec["power_gas_actuator_bottle"]["dedicated_bottle"] is True
    assert "316" in rec["power_gas_actuator_bottle"]["tubing_material"]
    assert rec["note13_purge_rack_separated"] is True

    # Item 9: PIG Traps 0.5-4 barg ΔP interlock + Gas-over-Oil + Scraper-barred tee + Loading + Bypass
    pig = eq["pigging"]
    assert "0.5" in pig["dp_interlock_barg"] and "4" in pig["dp_interlock_barg"]
    assert "Gas-over-Oil" in pig["side_valves"] and "Fail-Closed" in pig["side_valves"]
    assert "Gas-over-Oil" in pig["mainline_block_valve"] and "Fail-Open" in pig["mainline_block_valve"]
    assert pig["scraper_barred_tees"] is True
    assert "4500 §5.12" in pig["loading_line"]
    assert "4500 §5.13" in pig["station_bypass_check"]

    # Item 10: Condensate System Spec 5250 (DIN 6608 / St37, 15x blow-flask, 10 m3/h @ 5m Ex-proof pump, 2 bar test)
    cond = eq["condensate_system"]
    assert "DIN 6608" in cond["design_standard"] and "St37" in cond["design_standard"]
    assert cond["spec_5250_base_tank_m3"] == pytest.approx(5.0)  # > 100,000 Sm3/h
    assert cond["pump_flow_m3h"] == pytest.approx(10.0)
    assert cond["pump_head_m"] == pytest.approx(5.0)
    assert cond["pump_motor_kw"] == pytest.approx(4.0)
    assert cond["hydrostatic_test_bar"] == pytest.approx(2.0)
    assert cond["min_15x_blowflask_m3"] >= 3.0
    assert cond["collection_tank_volume_m3"] >= max(cond["spec_5250_base_tank_m3"], cond["min_15x_blowflask_m3"])

    # Item 11b: Fire Water 300 m3 + NFPA 20 + HVAC
    util = eq["station_utilities"]
    assert util["fire_water"]["tank_volume_m3"] == pytest.approx(300.0)
    assert "NFPA 20" in util["fire_water"]["pumps"]
    assert "CO2" in util["fire_water"]["turbine_enclosure_suppression"]
    assert "Ex-Proof" in util["hvac"]["control_building"]


def test_spec_4500_and_ozel_station_valves_loading_bypass_psv_condensate_compliance():
    """Verify Spec 4500 §5.2/5.4/5.9-5.13 & Ozel §5.3-5.4 first-class valve/equipment models."""
    res = calculate_station_process_model({
        "flow": 120.0,
        "flow_unit": "kg/s",
        "p_in": 45.0,
        "p_in_unit": "bar(a)",
        "p_out": 75.0,
        "p_out_unit": "bar(a)",
        "t_in": 20.0,
        "gas_comp": {"METHANE": 94.0, "ETHANE": 4.0, "CARBONDIOXIDE": 2.0},
    })
    eq = res["equipment_sizing"]

    # 1. Station Suction & Discharge Side Valves (4500 §5.4 + Ozel §5.4)
    sv_in = eq["station_suction_valve"]
    sv_out = eq["station_discharge_valve"]
    assert sv_in["tag"] == "SV-IN"
    assert sv_out["tag"] == "SV-OUT"
    assert "API 6D QSL 2" in sv_in["standard"]
    assert "Fail-Closed" in sv_in["fail_action"] and "Fail-Closed" in sv_out["fail_action"]
    assert "0.5–4.0 barg" in sv_in["dp_interlock"]
    assert "1500" in sv_in["body_vent_class"]

    # 2. Mainline Block Valve (4500 §5.4 + Ozel §5.4)
    mlbv = eq["mainline_block_valve"]
    assert mlbv["tag"] == "MLBV-101"
    assert "Fail-Open" in mlbv["fail_action"]
    assert "0.5–4.0 barg" in mlbv["dp_interlock"]

    # 3. Station Loading Line & Valves around SV-IN (4500 §5.12 + Ozel §5.4)
    load = eq["station_loading_line"]
    assert load["installed_around"] == "station_suction_valve"
    assert "Küresel" in load["upstream_valve"] or "Ball" in load["upstream_valve"]
    assert "Globe" in load["downstream_valve"] and "Limit Switch" in load["downstream_valve"]
    assert load["remote_control_ozel_5_4"] is True

    # 4. Station By-Pass Line & Non-Slam Check Valve (4500 §5.13)
    bp = eq["station_bypass_valve"]
    assert "Non-Slam" in bp["valve_type"]
    assert "USM" in bp["tie_in_location"] and "Soğutucu" in bp["tie_in_location"]

    # 5. PSV 2" Pilot Supply + Pulsation Snubber + Field Test Connection (4500 §5.10 + Ozel §5.4)
    psv = eq["safety_relief_and_blowdown"]
    assert '2"' in psv["psv_pilot_supply"] and "Snubber" in psv["psv_pilot_supply"]
    assert "Field Test Connection" in psv["psv_pilot_supply"]
    assert "Lubricated" in psv["bdv_valve_type"] and "Plug" in psv["bdv_valve_type"]

    # 6. Atmospheric Cyclone + Flame Arrestor + Manual Purge (4500 §5.2)
    cond = eq["condensate_system"]
    assert "Flame Arrestor" in cond["atmospheric_cyclone_separator"]







