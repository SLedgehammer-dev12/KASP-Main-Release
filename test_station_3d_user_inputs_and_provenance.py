"""
TDD Suite — Web 3D Station User Inputs, Header Equalization, Cooler/ESD/PSV Coupling & Parameter Provenance Matrix.

Covers:
1. User-configurable maximum gas velocity (`max_velocity_ms`, default 20.0 m/s) in minimum pipe diameter sizing
   and per-line acceptable commercial diameters (`acceptable_nominals`).
2. Governing maximum header diameter rule across all non-equipment-connection headers:
   Station Suction Header (`suction_header`), Station Discharge Header (`discharge_header`),
   Unit Suction Header (`comp_suction_header`), and Unit Discharge Header (`unit_discharge_header`).
3. Exact coupling of Compressor Outlet Temperature -> Gas Cooler Inlet Temperature, plus user inputs for
   Gas Cooler Air Temperature (`cooler_air_temp_c`) and Max Gas Outlet Temperature (`cooler_max_outlet_temp_c`).
4. ESD / BDV blowdown valve sizing from user-entered High-Pressure Piping Volume (`esd_hp_volume_m3` @ `p_out`)
   and Low-Pressure Piping Volume (`esd_lp_volume_m3` @ `p_in`).
5. Atmospheric pressure (`ambient_pressure` / `altitude`) and ambient temperature (`ambient_temp`) from Design Tab
   coupled into both ESD and PSV valve diameter calculations.
6. Comprehensive Parameter Provenance / Data Source Matrix (`parameter_sources`) classifying every equipment and
   piping parameter into `design_tab`, `station_3d_calc`, `user_input`, or `fixed_default`.
"""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import pytest
from fastapi.testclient import TestClient

from kasp.api.server import app
from kasp.core.pipe_sizing import nd_sort_key, size_single_pipe
from kasp.services.calculation_service import execute_design_calculation
from kasp.services.pipe_sizing_service import PipeSizingService
from kasp.services.station_service import calculate_station_process_model

REPO_ROOT = Path(__file__).resolve().parent
client = TestClient(app)

NATURAL_GAS = {
    "METHANE": 88.0,
    "ETHANE": 6.0,
    "PROPANE": 3.0,
    "NITROGEN": 1.5,
    "CARBONDIOXIDE": 1.5,
}


class TestPipeMaxVelocityAndAcceptableDiameters:
    """Verify default 20 m/s velocity limit, user velocity overrides, and per-line acceptable diameters."""

    def test_default_max_velocity_is_20_ms_and_exposes_acceptable_nominals(self):
        single = size_single_pipe(
            flow_kgs=85.0,
            p_bar=45.0,
            t_c=20.0,
            p_design_bar=75.0,
            material="API 5L X70",
            design_factor_F=0.50,
        )
        assert single["max_design_velocity_ms"] == pytest.approx(20.0)
        assert single["actual_velocity_ms"] <= 20.0
        assert "acceptable_nominals" in single
        assert isinstance(single["acceptable_nominals"], list)
        assert len(single["acceptable_nominals"]) >= 2
        assert single["nominal_size_in"] in single["acceptable_nominals"]
        assert single["velocity_min_nominal_in"] == single["nominal_size_in"]

    def test_user_max_velocity_changes_minimum_pipe_diameter_in_station_network(self):
        base_kwargs = dict(
            mass_flow_kgs=140.0,
            p_in_bar=35.0,
            p_out_bar=75.0,
            t_in_c=20.0,
            t_discharge_c=85.0,
            t_cooled_c=45.0,
            comp_op_count=3,
            cyclone_op_count=3,
            filter_op_count=3,
            cooler_bays_count=4,
            gas_comp=NATURAL_GAS,
            eos_model="pr",
        )
        res_default = PipeSizingService.size_station_network(**base_kwargs)
        res_strict = PipeSizingService.size_station_network(**base_kwargs, max_velocity_ms=8.0)
        res_relaxed = PipeSizingService.size_station_network(**base_kwargs, max_velocity_ms=24.0)

        assert res_default["max_velocity_ms"] == pytest.approx(20.0)
        assert res_strict["max_velocity_ms"] == pytest.approx(8.0)
        assert res_relaxed["max_velocity_ms"] == pytest.approx(24.0)

        # Strict 8 m/s limit must yield larger commercial diameter than relaxed 24 m/s limit
        for key in ("suction_header", "comp_suction_branch", "cooler_inlet"):
            nd_strict = nd_sort_key(res_strict["lines"][key]["nominal_key"])
            nd_relaxed = nd_sort_key(res_relaxed["lines"][key]["nominal_key"])
            assert nd_strict > nd_relaxed, f"{key} did not grow when max_velocity_ms tightened 24 -> 8 m/s"
            assert res_strict["lines"][key]["actual_velocity_ms"] <= 8.05

        # Every line exposes acceptable diameters according to velocity limit
        for key, line in res_default["lines"].items():
            assert isinstance(line.get("acceptable_nominals"), list) and len(line["acceptable_nominals"]) >= 1, key
            assert line.get("velocity_min_nominal_in"), key
            assert line.get("individual_nominal_size_in"), key
            assert line.get("acceptable_diameters_summary"), key


class TestAllHeadersGoverningMaxDiameter:
    """Verify Station Suction, Station Discharge, Unit Suction, and Unit Discharge headers share max NPS."""

    def test_four_headers_take_largest_calculated_nps_excluding_equipment_branches(self):
        # Case A: Low suction pressure (22 bar) vs high discharge pressure (78 bar) -> Unit Suction Header governs
        res_suct_gov = PipeSizingService.size_station_network(
            mass_flow_kgs=120.0,
            p_in_bar=22.0,
            p_out_bar=78.0,
            t_in_c=25.0,
            t_discharge_c=90.0,
            t_cooled_c=42.0,
            comp_op_count=3,
            cyclone_op_count=3,
            filter_op_count=3,
            cooler_bays_count=4,
            dp_cyclone_bar=0.25,
            dp_filter_bar=0.25,
            dp_cooler_bar=0.45,
            max_velocity_ms=20.0,
            gas_comp=NATURAL_GAS,
            eos_model="pr",
        )
        lines_a = res_suct_gov["lines"]
        header_keys = ("suction_header", "comp_suction_header", "unit_discharge_header", "discharge_header")
        for hk in header_keys:
            assert hk in lines_a, f"Missing header line {hk}"

        common_key_a = lines_a["suction_header"]["nominal_key"]
        for hk in header_keys:
            assert lines_a[hk]["nominal_key"] == common_key_a
            assert lines_a[hk]["od_mm"] == pytest.approx(lines_a["suction_header"]["od_mm"])
            # Individual pre-equalization acceptable size is preserved for info!
            assert lines_a[hk]["individual_nominal_size_in"] in lines_a[hk]["acceptable_nominals"]

        # Discharge individual minimum size at 78 bar is smaller than suction at 22 bar, proving equalization raised it
        assert nd_sort_key(lines_a["discharge_header"]["individual_nominal_key"]) < nd_sort_key(common_key_a)

        # Equipment connection piping is NOT forced to the common header diameter
        for eq_branch in ("cyclone_branch", "cyclone_outlet_branch", "filter_branch", "filter_outlet_branch", "comp_suction_branch", "comp_discharge_branch", "cooler_bay_risers", "cooler_bypass"):
            assert nd_sort_key(lines_a[eq_branch]["nominal_key"]) < nd_sort_key(common_key_a)

        # Case B: Low PR (55 -> 58 bar) with very hot compressor outlet (145°C) vs cold suction (5°C)
        # Here hot Unit Discharge Header has lower density / higher volumetric flow than cold Suction Header -> Unit Discharge Header governs!
        res_disch_gov = PipeSizingService.size_station_network(
            mass_flow_kgs=160.0,
            p_in_bar=55.0,
            p_out_bar=58.0,
            t_in_c=5.0,
            t_discharge_c=145.0,
            t_cooled_c=35.0,
            comp_op_count=3,
            cyclone_op_count=3,
            filter_op_count=3,
            cooler_bays_count=4,
            dp_cyclone_bar=0.10,
            dp_filter_bar=0.10,
            dp_cooler_bar=0.30,
            max_velocity_ms=18.0,
            gas_comp=NATURAL_GAS,
            eos_model="pr",
        )
        lines_b = res_disch_gov["lines"]
        max_indiv_b = max(
            (lines_b[hk]["individual_nominal_key"] for hk in header_keys),
            key=nd_sort_key,
        )
        assert lines_b["unit_discharge_header"]["individual_nominal_key"] == max_indiv_b
        for hk in header_keys:
            assert lines_b[hk]["nominal_key"] == max_indiv_b


class TestCompressorToGasCoolerCouplingAndUserInputs:
    """Verify Compressor Outlet Temp == Gas Cooler Inlet Temp and user Air Temp / Max Gas Outlet Temp."""

    def test_compressor_outlet_temp_is_gas_cooler_inlet_temp_and_cooler_user_inputs_work(self):
        design_inputs = {
            "flow": 90.0,
            "flow_unit": "kg/s",
            "p_in": 40.0,
            "p_in_unit": "bar(a)",
            "p_out": 76.0,
            "p_out_unit": "bar(a)",
            "t_in": 22.0,
            "t_in_unit": "°C",
            "gas_comp": NATURAL_GAS,
            "eos_model": "pr",
            "num_units": 2,
            "num_stages": 1,
            "poly_eff": 82.0,
            "ambient_temp": 18.0,
            "ambient_pressure": 101.325,
        }
        design_res = execute_design_calculation(design_inputs)

        st_cool_38 = calculate_station_process_model(
            {
                **design_inputs,
                "cooler_air_temp_c": 20.0,
                "cooler_max_outlet_temp_c": 38.0,
                "include_air_cooler_design": True,
            },
            design_results=design_res,
        )
        ac_38 = st_cool_38["equipment_sizing"]["air_coolers"]
        nodes_38 = {n["id"]: n for n in st_cool_38["nodes"]}

        # Exact verification: Compressor outlet temp == Gas cooler inlet temp
        assert ac_38["inlet_temp_c"] == pytest.approx(design_res["t_out_c"], abs=0.15)
        assert nodes_38["N05_COMPRESSOR_DISCHARGE"]["temp_c"] == pytest.approx(ac_38["inlet_temp_c"], abs=0.05)
        assert nodes_38["N06_DISCHARGE_HEADER"]["temp_c"] == pytest.approx(ac_38["inlet_temp_c"], abs=0.05)
        assert st_cool_38["station_piping"]["lines"]["unit_discharge_header"]["temp_c"] == pytest.approx(
            ac_38["inlet_temp_c"], abs=0.15
        )
        assert ac_38["outlet_temp_c"] == pytest.approx(38.0, abs=0.1)
        assert ac_38["air_inlet_temp_c"] == pytest.approx(20.0, abs=0.1)
        assert nodes_38["N07_COOLER_OUTLET"]["temp_c"] == pytest.approx(38.0, abs=0.1)
        assert st_cool_38["station_piping"]["lines"]["discharge_header"]["temp_c"] == pytest.approx(38.0, abs=0.1)

        # Raising max outlet temp (38 -> 50°C) reduces cooler heat duty; raising air temp (20 -> 34°C at 38°C outlet) shrinks LMTD & increases bays/area
        st_cool_50 = calculate_station_process_model(
            {
                **design_inputs,
                "cooler_air_temp_c": 20.0,
                "cooler_max_outlet_temp_c": 50.0,
            },
            design_results=design_res,
        )
        assert st_cool_50["station_summary"]["cooler_heat_duty_mw"] < st_cool_38["station_summary"]["cooler_heat_duty_mw"]
        assert st_cool_50["equipment_sizing"]["air_coolers"]["outlet_temp_c"] == pytest.approx(50.0, abs=0.1)

        st_hot_air = calculate_station_process_model(
            {
                **design_inputs,
                "cooler_air_temp_c": 33.0,
                "cooler_max_outlet_temp_c": 38.0,
                "include_air_cooler_design": True,
            },
            design_results=design_res,
        )
        ac_hot_air = st_hot_air["equipment_sizing"]["air_coolers"]
        assert ac_hot_air["lmtd_c"] < ac_38["lmtd_c"]
        assert ac_hot_air["bay_count"] >= ac_38["bay_count"]

        # Impossible approach check (air_temp = 42°C, max_outlet = 40°C) triggers warning & clamps above air_temp
        st_impossible = calculate_station_process_model(
            {
                **design_inputs,
                "cooler_air_temp_c": 42.0,
                "cooler_max_outlet_temp_c": 40.0,
            },
            design_results=design_res,
        )
        assert st_impossible["equipment_sizing"]["air_coolers"]["outlet_temp_c"] > 42.0
        assert any("soğutucu" in w.lower() for w in st_impossible["warnings"])


class TestESDVolumesAndDesignAtmosphericCoupling:
    """Verify ESD HP/LP piping volumes and Design Tab atmospheric P & T coupling into ESD & PSV."""

    def test_esd_sizing_responds_to_hp_and_lp_piping_volumes_and_pressures(self):
        base = {
            "flow": 80.0,
            "flow_unit": "kg/s",
            "p_in": 32.0,
            "p_in_unit": "bar(a)",
            "p_out": 76.0,
            "p_out_unit": "bar(a)",
            "t_in": 18.0,
            "t_in_unit": "°C",
            "gas_comp": NATURAL_GAS,
            "eos_model": "pr",
            "ambient_temp": 15.0,
            "ambient_pressure": 101.325,
            "bdv_depressurization_time_min": 15.0,
        }
        res_small = calculate_station_process_model({
            **base,
            "esd_hp_volume_m3": 25.0,
            "esd_lp_volume_m3": 20.0,
        })
        res_large_hp = calculate_station_process_model({
            **base,
            "esd_hp_volume_m3": 150.0,
            "esd_lp_volume_m3": 20.0,
        })
        res_large_lp = calculate_station_process_model({
            **base,
            "esd_hp_volume_m3": 25.0,
            "esd_lp_volume_m3": 140.0,
        })

        esd_s = res_small["equipment_sizing"]["esd_sizing"]
        esd_hp = res_large_hp["equipment_sizing"]["esd_sizing"]
        esd_lp = res_large_lp["equipment_sizing"]["esd_sizing"]

        # HP upstream pressure is compressor outlet (76 bar), LP upstream pressure is compressor inlet (32 bar)
        assert esd_s["discharge"]["upstream_pressure_bar"] == pytest.approx(76.0, abs=0.05)
        assert esd_s["suction"]["upstream_pressure_bar"] == pytest.approx(32.0, abs=0.05)
        assert esd_s["discharge"]["piping_volume_m3"] == pytest.approx(25.0)
        assert esd_s["suction"]["piping_volume_m3"] == pytest.approx(20.0)

        # Increasing HP volume 6x increases HP blowdown flow & Cv while LP stays constant
        assert esd_hp["discharge"]["blowdown_mass_flow_total_kgs"] > esd_s["discharge"]["blowdown_mass_flow_total_kgs"] * 5.0
        assert esd_hp["discharge"]["required_cv"] > esd_s["discharge"]["required_cv"] * 5.0
        assert esd_hp["suction"]["required_cv"] == pytest.approx(esd_s["suction"]["required_cv"], rel=1e-4)

        # Increasing LP volume 7x increases LP blowdown flow & Cv while HP stays constant
        assert esd_lp["suction"]["blowdown_mass_flow_total_kgs"] > esd_s["suction"]["blowdown_mass_flow_total_kgs"] * 6.0
        assert esd_lp["suction"]["required_cv"] > esd_s["suction"]["required_cv"] * 6.0
        assert esd_lp["discharge"]["required_cv"] == pytest.approx(esd_s["discharge"]["required_cv"], rel=1e-4)

    def test_design_tab_atmospheric_pressure_and_temp_couple_into_esd_and_psv(self):
        sea_level = calculate_station_process_model({
            "flow": 95.0,
            "flow_unit": "kg/s",
            "p_in": 40.0,
            "p_in_unit": "bar(a)",
            "p_out": 75.0,
            "p_out_unit": "bar(a)",
            "t_in": 20.0,
            "gas_comp": NATURAL_GAS,
            "eos_model": "pr",
            "ambient_pressure": 101.325,  # 1.01325 bar(a)
            "ambient_temp": 10.0,
            "esd_hp_volume_m3": 80.0,
            "esd_lp_volume_m3": 60.0,
        })
        high_alt_hot = calculate_station_process_model({
            "flow": 95.0,
            "flow_unit": "kg/s",
            "p_in": 40.0,
            "p_in_unit": "bar(a)",
            "p_out": 75.0,
            "p_out_unit": "bar(a)",
            "t_in": 20.0,
            "gas_comp": NATURAL_GAS,
            "eos_model": "pr",
            "ambient_pressure": 82.0,  # 0.820 bar(a) (~1750m site)
            "ambient_temp": 42.0,
            "esd_hp_volume_m3": 80.0,
            "esd_lp_volume_m3": 60.0,
        })

        assert sea_level["station_summary"]["ambient_pressure_bar"] == pytest.approx(1.01325, abs=0.002)
        assert sea_level["station_summary"]["ambient_temp_c"] == pytest.approx(10.0, abs=0.05)
        assert high_alt_hot["station_summary"]["ambient_pressure_bar"] == pytest.approx(0.82, abs=0.002)
        assert high_alt_hot["station_summary"]["ambient_temp_c"] == pytest.approx(42.0, abs=0.05)

        psv_sea = sea_level["equipment_sizing"]["safety_relief_and_blowdown"]
        psv_alt = high_alt_hot["equipment_sizing"]["safety_relief_and_blowdown"]
        esd_sea = sea_level["equipment_sizing"]["esd_sizing"]
        esd_alt = high_alt_hot["equipment_sizing"]["esd_sizing"]

        # PSV atmospheric pressure & ambient temp come from Design Tab
        assert psv_sea["psv_back_pressure_bar"] == pytest.approx(1.01325, abs=0.002)
        assert psv_alt["psv_back_pressure_bar"] == pytest.approx(0.82, abs=0.002)
        assert psv_sea["auto_inputs"]["p_atm_bar"] == pytest.approx(1.01325, abs=0.002)
        assert psv_alt["auto_inputs"]["p_atm_bar"] == pytest.approx(0.82, abs=0.002)
        assert psv_sea["auto_inputs"]["ambient_temp_c"] == pytest.approx(10.0, abs=0.05)
        assert psv_alt["auto_inputs"]["ambient_temp_c"] == pytest.approx(42.0, abs=0.05)
        assert psv_sea["psv_sizing"]["vent_exit_velocity_ms"] != pytest.approx(
            psv_alt["psv_sizing"]["vent_exit_velocity_ms"], rel=1e-3
        )

        # ESD downstream atmospheric pressure & ambient temp come from Design Tab and change required Cv
        assert esd_sea["auto_inputs"]["p_atm_bar"] == pytest.approx(1.01325, abs=0.002)
        assert esd_alt["auto_inputs"]["p_atm_bar"] == pytest.approx(0.82, abs=0.002)
        assert esd_sea["auto_inputs"]["ambient_temp_c"] == pytest.approx(10.0, abs=0.05)
        assert esd_alt["auto_inputs"]["ambient_temp_c"] == pytest.approx(42.0, abs=0.05)
        assert esd_sea["discharge"]["required_cv"] != pytest.approx(esd_alt["discharge"]["required_cv"], rel=1e-3)
        assert esd_sea["suction"]["required_cv"] != pytest.approx(esd_alt["suction"]["required_cv"], rel=1e-3)


class TestParameterProvenanceMatrixAndWebSyntax:
    """Verify full parameter provenance registry (`parameter_sources`) and valid JS modules."""

    def test_station_exposes_complete_parameter_provenance_matrix(self):
        res_default = calculate_station_process_model({
            "flow": 75.0,
            "flow_unit": "kg/s",
            "p_in": 35.0,
            "p_in_unit": "bar(a)",
            "p_out": 72.0,
            "p_out_unit": "bar(a)",
            "t_in": 19.0,
            "gas_comp": NATURAL_GAS,
            "ambient_pressure": 100.5,
            "ambient_temp": 17.5,
        })
        ps = res_default.get("parameter_sources")
        assert isinstance(ps, dict)
        assert {"design_tab", "station_3d_calc", "user_input", "fixed_default"}.issubset(set(ps["categories"].keys()))

        checks = ps["coupling_checks"]
        assert checks["compressor_outlet_equals_cooler_inlet"]["verified"] is True
        assert checks["headers_equalized_to_max_nps"]["verified"] is True
        assert checks["esd_uses_design_atm_and_volumes"]["verified"] is True
        assert checks["psv_uses_design_atm_and_temp"]["verified"] is True

        expected_equip = {
            "pig_traps",
            "cyclones",
            "cartridge_filters",
            "turbo_compressors",
            "compressor_building",
            "air_coolers",
            "station_recycle",
            "safety_relief_psv",
            "esd_blowdown_valves",
            "ultrasonic_meter",
            "condensate_system",
        }
        assert expected_equip.issubset({item["key"] for item in ps["equipment"]})
        assert len(ps["piping"]) == len(res_default["station_piping"]["lines"])

        # When user explicitly enters 3D overrides, provenance dynamically flips to `user_input`
        res_user = calculate_station_process_model({
            "flow": 75.0,
            "flow_unit": "kg/s",
            "p_in": 35.0,
            "p_in_unit": "bar(a)",
            "p_out": 72.0,
            "p_out_unit": "bar(a)",
            "t_in": 19.0,
            "gas_comp": NATURAL_GAS,
            "ambient_pressure": 100.5,
            "ambient_temp": 17.5,
            "max_velocity_ms": 17.5,
            "cooler_air_temp_c": 26.0,
            "cooler_max_outlet_temp_c": 41.0,
            "esd_hp_volume_m3": 95.0,
            "esd_lp_volume_m3": 65.0,
        })
        ps_user = res_user["parameter_sources"]
        equip_by_key = {item["key"]: {p["param"]: p["source"] for p in item["parameters"]} for item in ps_user["equipment"]}
        assert equip_by_key["air_coolers"]["cooler_air_temp_c"] == "user_input"
        assert equip_by_key["air_coolers"]["cooler_max_outlet_temp_c"] == "user_input"
        assert equip_by_key["esd_blowdown_valves"]["esd_hp_volume_m3"] == "user_input"
        assert equip_by_key["esd_blowdown_valves"]["esd_lp_volume_m3"] == "user_input"
        assert equip_by_key["esd_blowdown_valves"]["ambient_pressure_bar"] == "design_tab"
        assert equip_by_key["safety_relief_psv"]["ambient_pressure_bar"] == "design_tab"

    def test_web_js_syntax_and_new_ui_controls_present(self):
        js_files = [
            REPO_ROOT / "kasp" / "web" / "src" / "components" / "designSidebar.js",
            REPO_ROOT / "kasp" / "web" / "src" / "components" / "stationTab.js",
            REPO_ROOT / "kasp" / "web" / "src" / "components" / "station3dView.js",
            REPO_ROOT / "kasp" / "web" / "src" / "store" / "projectStore.js",
            REPO_ROOT / "kasp" / "web" / "src" / "i18n" / "locales.js",
        ]
        stab = (REPO_ROOT / "kasp" / "web" / "src" / "components" / "stationTab.js").read_text(encoding="utf-8")
        s3d = (REPO_ROOT / "kasp" / "web" / "src" / "components" / "station3dView.js").read_text(encoding="utf-8")
        dside = (REPO_ROOT / "kasp" / "web" / "src" / "components" / "designSidebar.js").read_text(encoding="utf-8")

        assert "ambient_pressure" in dside
        assert "max_velocity_ms" in stab
        assert "cooler_air_temp_c" in stab
        assert "cooler_max_outlet_temp_c" in stab
        assert "esd_hp_volume_m3" in stab
        assert "esd_lp_volume_m3" in stab
        assert "parameter_sources" in stab
        assert "unit_discharge_header" in s3d
        assert "acceptable_nominals" in stab or "acceptable_diameters_summary" in stab

        node_bin = shutil.which("node")
        if node_bin:
            for f in js_files + [
                REPO_ROOT / "kasp" / "web" / "src" / "api" / "client.js",
                REPO_ROOT / "kasp" / "web" / "src" / "components" / "resultsView.js",
            ]:
                proc = subprocess.run([node_bin, "--check", str(f)], capture_output=True, text=True)
                assert proc.returncode == 0, f"node --check failed for {f}: {proc.stderr}"

    def test_pressure_ratio_and_design_inputs_support_ambient_pressure(self):
        from kasp.services.validation_service import validate_pressure_ratio, validate_design_inputs

        # Standard atmospheric pressure (101.325 kPa)
        ok1, pr1, _, _ = validate_pressure_ratio(40.0, "bar(g)", 80.0, "bar(g)", 1, ambient_pressure_pa=101325.0)
        assert ok1 is True
        # (80 + 1.01325) / (40 + 1.01325) = 81.01325 / 41.01325 ~= 1.9753
        assert pr1 == pytest.approx(81.01325 / 41.01325, rel=1e-3)

        # High altitude site (80 kPa = 0.8 bar)
        ok2, pr2, _, _ = validate_pressure_ratio(40.0, "bar(g)", 80.0, "bar(g)", 1, ambient_pressure_pa=80000.0)
        assert ok2 is True
        # (80 + 0.8) / (40 + 0.8) = 80.8 / 40.8 ~= 1.9804
        assert pr2 == pytest.approx(80.8 / 40.8, rel=1e-3)

        # Full validation with ambient pressure in kPa
        val = validate_design_inputs({
            "p_in": 49.65,
            "p_in_unit": "bar(g)",
            "p_out": 75.0,
            "p_out_unit": "bar(a)",
            "t_in": 19.0,
            "t_in_unit": "°C",
            "flow": 1985000.0,
            "flow_unit": "Sm³/h",
            "gas_comp": {"METHANE": 85.0, "ETHANE": 7.0, "PROPANE": 4.0, "NITROGEN": 2.0, "CARBONDIOXIDE": 2.0},
            "num_stages": 1,
            "ambient_pressure": 95.0,
            "altitude": 500,
        })
        assert val["is_valid"] is True
        assert len(val["errors"]) == 0

    def test_station_3d_cooler_bays_have_dedicated_inlet_and_outlet_headers(self):
        s3d = (REPO_ROOT / "kasp" / "web" / "src" / "components" / "station3dView.js").read_text(encoding="utf-8")
        assert 'lineKey: "cooler_bay_inlet_header"' in s3d
        assert 'lineKey: "cooler_bay_outlet_header"' in s3d
        assert 'lineKey: "cooler_bay_outlet_risers"' in s3d
        assert "pLines.cooler_bay_inlet_header" in s3d
        assert "pLines.cooler_bay_outlet_header" in s3d
        assert "pLines.cooler_bay_outlet_risers" in s3d
        assert "coolerBayInletHdrLine.od_mm" in s3d
        assert "coolerBayOutletHdrLine.od_mm" in s3d
        assert "for (let b = 0; b < numCoolerBays; b++)" in s3d
        assert "bayInletHdrY" in s3d and "bayOutletHdrY" in s3d
        assert "new THREE.Vector3(bayInletX, bayInletHdrY, bayInletHeaderZ)" in s3d
        assert "new THREE.Vector3(bayOutletX, bayOutletHdrY, bayOutletHeaderZ)" in s3d

    def test_pipe_sizing_divides_flow_per_bay_for_bay_headers_and_risers(self):
        from kasp.services.pipe_sizing_service import PipeSizingService

        net = PipeSizingService.size_station_network(
            mass_flow_kgs=400.0,
            p_in_bar=50.0,
            p_out_bar=75.0,
            t_in_c=19.0,
            t_discharge_c=60.0,
            t_cooled_c=45.0,
            comp_op_count=4,
            cyclone_op_count=6,
            filter_op_count=6,
            cooler_bays_count=4,
        )
        lines = net["lines"]
        # Main cooler manifolds carry total station flow
        assert lines["cooler_inlet"]["flow_kgs"] == pytest.approx(400.0)
        assert lines["cooler_outlet"]["flow_kgs"] == pytest.approx(400.0)
        # Per-bay risers and per-bay inlet/outlet headers carry mass_flow / bay_count
        for key in (
            "cooler_bay_risers",
            "cooler_bay_inlet_header",
            "cooler_bay_outlet_header",
            "cooler_bay_outlet_risers",
        ):
            assert lines[key]["flow_kgs"] == pytest.approx(100.0)
            assert lines[key]["od_mm"] < lines["cooler_inlet"]["od_mm"]
        # Hot vs cold conditions preserved on bay inlet vs bay outlet headers
        assert lines["cooler_bay_inlet_header"]["temp_c"] == pytest.approx(60.0)
        assert lines["cooler_bay_outlet_header"]["temp_c"] == pytest.approx(45.0)
        assert lines["cooler_bay_outlet_risers"]["temp_c"] == pytest.approx(45.0)

    def test_pipe_sizing_separates_cyclone_and_filter_inlet_outlet_lines(self):
        from kasp.services.pipe_sizing_service import PipeSizingService

        net = PipeSizingService.size_station_network(
            mass_flow_kgs=180.0,
            p_in_bar=45.0,
            p_out_bar=75.0,
            t_in_c=20.0,
            t_discharge_c=75.0,
            t_cooled_c=45.0,
            comp_op_count=3,
            cyclone_op_count=3,
            filter_op_count=3,
            cooler_bays_count=4,
            dp_cyclone_bar=0.45,
            dp_filter_bar=0.35,
            max_velocity_ms=20.0,
        )
        lines = net["lines"]
        assert len(lines) == 21
        assert lines["cyclone_branch"]["pressure_bar"] == pytest.approx(45.0)
        assert lines["cyclone_outlet_branch"]["pressure_bar"] == pytest.approx(44.55)
        assert lines["filter_branch"]["pressure_bar"] == pytest.approx(44.55)
        assert lines["filter_outlet_branch"]["pressure_bar"] == pytest.approx(44.20)
        for key in ("cyclone_branch", "cyclone_outlet_branch", "filter_branch", "filter_outlet_branch"):
            assert lines[key]["flow_kgs"] == pytest.approx(60.0)
            assert lines[key]["meets_min_velocity_diameter"] is True
            assert lines[key]["velocity_min_nominal_in"]
            assert lines[key]["diameter_source"] == "station_3d_calc"

    def test_cyclone_and_filter_user_diameters_and_min_velocity_check(self):
        from kasp.services.station_service import calculate_station_process_model

        base_inputs = {
            "p_in": 45.0,
            "p_in_unit": "bar(a)",
            "p_out": 75.0,
            "p_out_unit": "bar(a)",
            "t_in": 20.0,
            "t_in_unit": "°C",
            "flow": 180.0,
            "flow_unit": "kg/s",
            "cyclone_op_count": 3,
            "filter_op_count": 3,
            "gas_comp": NATURAL_GAS,
            "eos_model": "pr",
            "max_velocity_ms": 15.0,
        }

        # 1. Compliant oversized user selection
        ok_res = calculate_station_process_model({
            **base_inputs,
            "cyclone_inlet_pipe_size": '24"',
            "cyclone_outlet_pipe_size": "20",
            "filter_inlet_pipe_size": "20",
            "filter_outlet_pipe_size": '18"',
        })
        ok_lines = ok_res["station_piping"]["lines"]
        assert ok_lines["cyclone_branch"]["nominal_size_in"] == '24"'
        assert ok_lines["cyclone_outlet_branch"]["nominal_size_in"] == '20"'
        assert ok_lines["filter_branch"]["nominal_size_in"] == '20"'
        assert ok_lines["filter_outlet_branch"]["nominal_size_in"] == '18"'
        assert ok_lines["cyclone_branch"]["diameter_source"] == "user_input"
        assert ok_lines["cyclone_outlet_branch"]["diameter_source"] == "user_input"
        assert ok_lines["filter_branch"]["diameter_source"] == "user_input"
        assert ok_lines["filter_outlet_branch"]["diameter_source"] == "user_input"
        assert ok_lines["cyclone_branch"]["meets_min_velocity_diameter"] is True

        eq_cyc = ok_res["equipment_sizing"]["cyclones"]
        eq_flt = ok_res["equipment_sizing"]["cartridge_filters"]
        assert eq_cyc["inlet_pipe_size"] == '24"'
        assert eq_cyc["outlet_pipe_size"] == '20"'
        assert eq_cyc["inlet_min_diameter_ok"] is True
        assert eq_cyc["outlet_min_diameter_ok"] is True
        assert eq_flt["inlet_pipe_size"] == '20"'
        assert eq_flt["outlet_pipe_size"] == '18"'
        assert eq_flt["inlet_min_diameter_ok"] is True
        assert eq_flt["outlet_min_diameter_ok"] is True

        # 2. Undersized user diameter triggers minimum-diameter check failure against max_velocity_ms
        low_res = calculate_station_process_model({
            **base_inputs,
            "cyclone_inlet_pipe_size": "4",
            "filter_outlet_pipe_size": "4",
        })
        low_lines = low_res["station_piping"]["lines"]
        cyc_in = low_lines["cyclone_branch"]
        flt_out = low_lines["filter_outlet_branch"]
        assert cyc_in["nominal_size_in"] == '4"'
        assert cyc_in["actual_velocity_ms"] > 15.0
        assert cyc_in["meets_min_velocity_diameter"] is False
        assert nd_sort_key(cyc_in["velocity_min_key"]) > nd_sort_key("4")
        assert flt_out["nominal_size_in"] == '4"'
        assert flt_out["meets_min_velocity_diameter"] is False
        assert low_res["equipment_sizing"]["cyclones"]["inlet_min_diameter_ok"] is False
        assert low_res["equipment_sizing"]["cartridge_filters"]["outlet_min_diameter_ok"] is False
        warnings_blob = "\n".join(low_res["station_piping"]["warnings"])
        assert "L-103" in warnings_blob and cyc_in["velocity_min_nominal_in"] in warnings_blob
        assert "L-104A" in warnings_blob and flt_out["velocity_min_nominal_in"] in warnings_blob

    def test_web_3d_and_ui_have_cyclone_and_filter_inlet_outlet_pipe_controls(self):
        tab_src = (REPO_ROOT / "kasp" / "web" / "src" / "components" / "stationTab.js").read_text(encoding="utf-8")
        s3d_src = (REPO_ROOT / "kasp" / "web" / "src" / "components" / "station3dView.js").read_text(encoding="utf-8")
        for sel_id in (
            "select-param-cyc-in",
            "select-param-cyc-out",
            "select-param-flt-in",
            "select-param-flt-out",
        ):
            assert sel_id in tab_src, f"Missing UI pipe diameter selector #{sel_id}"
        for key in (
            "cyclone_inlet_pipe_size",
            "cyclone_outlet_pipe_size",
            "filter_inlet_pipe_size",
            "filter_outlet_pipe_size",
        ):
            assert key in tab_src
        assert 'lineKey: "cyclone_outlet_branch"' in s3d_src
        assert 'lineKey: "filter_outlet_branch"' in s3d_src
        assert "rCycloneInlet" in s3d_src and "rCycloneOutlet" in s3d_src
        assert "rFilterInlet" in s3d_src and "rFilterOutlet" in s3d_src

    def test_station_3d_cfs_elevated_above_headers_with_equal_diameter_ball_valves_and_wide_spacing(self):
        s3d = (REPO_ROOT / "kasp" / "web" / "src" / "components" / "station3dView.js").read_text(encoding="utf-8")

        # Elevated CFS vessels above CFS inlet/outlet header level + dedicated inlet & outlet headers
        assert "cfsHeaderY" in s3d and "cfsVesselY" in s3d
        assert "cfsInletHeaderZ" in s3d and "cfsOutletHeaderZ" in s3d
        assert "cfsPitchX" in s3d

        # Inside the CFS per-filter loop, both inlet and outlet ball valves use exact branch pipe radii
        cfs_loop_start = s3d.index("for (let i = 0; i < numFilters; i++)")
        cfs_loop_end = s3d.index("registerClickable(cfsGroup", cfs_loop_start)
        cfs_block = s3d[cfs_loop_start:cfs_loop_end]
        assert "createValveStation(" in cfs_block
        assert "rFilterInlet" in cfs_block
        assert "rFilterOutlet" in cfs_block
        inlet_valve_matches = [line for line in cfs_block.splitlines() if "createValveStation(" in line and "rFilterInlet" in line]
        outlet_valve_matches = [line for line in cfs_block.splitlines() if "createValveStation(" in line and "rFilterOutlet" in line]
        assert inlet_valve_matches, "CFS per-filter inlet ball valve must use exact rFilterInlet pipe radius"
        assert outlet_valve_matches, "CFS per-filter outlet ball valve must use exact rFilterOutlet pipe radius"
        assert "rotationY: Math.PI / 2" in "\n".join(inlet_valve_matches)
        assert "rotationY: Math.PI / 2" in "\n".join(outlet_valve_matches)

        # Expanded equipment spacing constants
        assert "const compPitch = 58" in s3d
        assert "frontSuctionZ" in s3d and "frontRecycleZ" in s3d and "frontDischargeZ" in s3d

    def test_station_3d_compressors_start_from_cooler_side_and_grow_westward(self):
        s3d = (REPO_ROOT / "kasp" / "web" / "src" / "components" / "station3dView.js").read_text(encoding="utf-8")

        # Compressors must anchor near Gas Cooler (coolerX0) and step westward (- i * compPitch) toward PIG traps
        assert "compStartX - i * compPitch" in s3d
        assert "compStartX - Math.max(0, numComps - 1) * compPitch" in s3d
        assert "compStartX - (cutawayUnitIdx - 1) * compPitch" in s3d
        assert "coolerX0" in s3d.split("const compStartX")[1].splitlines()[0]
        assert "const westLoopRoadX" in s3d

    def test_station_3d_has_station_recycle_control_valve_with_block_valves_and_canopy(self):
        s3d = (REPO_ROOT / "kasp" / "web" / "src" / "components" / "station3dView.js").read_text(encoding="utf-8")

        # Spec 4-NGTL 0-CS-M-002-4500 Sec 5.8 Station Recycle Valve downstream of Gas Cooler -> filtered suction
        assert "stationRecycleTakeoffX" in s3d
        assert "stationRecycleValveX" in s3d
        assert "stationRecycleZ" in s3d
        assert "stationRecycleCanopy" in s3d
        # Must branch downstream of Gas Cooler on dischargeReturnZ and return to filtered suction spine at cfsOutletTieX
        skid_start = s3d.index("stationRecycleTakeoffX")
        skid_end = s3d.index("registerClickable(stationRecycleSkid", skid_start)
        skid_block = s3d[skid_start:skid_end]
        assert "dischargeReturnZ" in skid_block
        assert "cfsOutletTieX" in skid_block
        assert skid_block.count("createValveStation(") >= 3, (
            "Station Recycle skid must include control valve + 2 flanking block valves"
        )
        assert "lineKey: \"station_recycle\"" in skid_block
        assert "equipKey: \"station_recycle\"" in skid_block

    def test_station_service_accepts_equiv_pipe_lengths_and_exposes_spec_4500_compliance_and_ui(self):
        from kasp.services.station_service import calculate_station_process_model

        res = calculate_station_process_model({
            "flow": 95.0,
            "flow_unit": "kg/s",
            "p_in": 40.0,
            "p_in_unit": "bar(a)",
            "p_out": 74.0,
            "p_out_unit": "bar(a)",
            "t_in": 20.0,
            "gas_comp": NATURAL_GAS,
            "suction_equiv_length_m": 220.0,
            "discharge_equiv_length_m": 280.0,
        })
        comp = res["station_piping"].get("spec_4500_compliance")
        assert isinstance(comp, dict)
        assert comp["suction_piping"]["equiv_length_m"] == pytest.approx(220.0)
        assert comp["discharge_piping"]["equiv_length_m"] == pytest.approx(280.0)

        ps = res["parameter_sources"]
        assert "spec_4500_piping_compliance" in ps["coupling_checks"]
        equip_by_key = {item["key"]: {p["param"]: p["source"] for p in item["parameters"]} for item in ps["equipment"]}
        assert "spec_4500_piping_compliance" in equip_by_key
        assert equip_by_key["spec_4500_piping_compliance"]["suction_equiv_length_m"] == "user_input"
        assert equip_by_key["spec_4500_piping_compliance"]["discharge_equiv_length_m"] == "user_input"

        stab = (REPO_ROOT / "kasp" / "web" / "src" / "components" / "stationTab.js").read_text(encoding="utf-8")
        assert "suction_equiv_length_m" in stab
        assert "discharge_equiv_length_m" in stab
        assert "input-param-suct-len" in stab
        assert "input-param-disch-len" in stab
        assert "spec_4500_compliance" in stab

    def test_station_3d_mfs_dynamic_provenance_blow_flask_dual_bottles_and_heat_tracing(self):
        from kasp.services.station_service import calculate_station_process_model

        res = calculate_station_process_model({
            "flow": 84.0,
            "flow_unit": "kg/s",
            "p_in": 32.0,
            "p_in_unit": "bar(a)",
            "p_out": 70.0,
            "p_out_unit": "bar(a)",
            "t_in": 18.0,
            "gas_comp": NATURAL_GAS,
        })
        ps = res["parameter_sources"]
        equip_by_key = {item["key"]: item["parameters"] for item in ps["equipment"]}
        cyc_params = {p["param"]: p for p in equip_by_key["cyclones"]}
        # Dynamic sizing must NOT claim fixed 22.0 kg/s default capacity
        assert cyc_params["unit_cap_cyclone_kgs"]["value"] == pytest.approx(42.0, abs=0.1)
        assert cyc_params["unit_cap_cyclone_kgs"]["source"] == "station_3d_calc"
        assert "efficiency_spec" in cyc_params
        assert "heat_tracing_min_c" in cyc_params

        s3d = (REPO_ROOT / "kasp" / "web" / "src" / "components" / "station3dView.js").read_text(encoding="utf-8")
        stab = (REPO_ROOT / "kasp" / "web" / "src" / "components" / "stationTab.js").read_text(encoding="utf-8")
        td = (REPO_ROOT / "kasp" / "web" / "src" / "components" / "equipmentTeardown.js").read_text(encoding="utf-8")

        assert "blowFlask" in s3d
        assert "levelBottle" in s3d
        assert "heatTrace" in s3d
        assert "8 µm" in s3d and "400 mbar" in s3d and "700 mbar" in s3d and "1.6 mm" in s3d
        assert "8 µm" in stab and "Blow-Flask" in stab and "2 °C" in stab
        assert "8 µm" in td and "Blow-Flask" in td and "corrosion_allowance_mm" in td and "mm CA" in td

    def test_station_3d_cfs_dynamic_provenance_qoc_davit_blow_flask_and_specs(self):
        from kasp.services.station_service import calculate_station_process_model

        res = calculate_station_process_model({
            "flow": 84.0,
            "flow_unit": "kg/s",
            "p_in": 32.0,
            "p_in_unit": "bar(a)",
            "p_out": 70.0,
            "p_out_unit": "bar(a)",
            "t_in": 18.0,
            "gas_comp": NATURAL_GAS,
        })
        ps = res["parameter_sources"]
        equip_by_key = {item["key"]: item["parameters"] for item in ps["equipment"]}
        flt_params = {p["param"]: p for p in equip_by_key["cartridge_filters"]}
        assert flt_params["unit_cap_filter_kgs"]["value"] == pytest.approx(42.0, abs=0.1)
        assert flt_params["unit_cap_filter_kgs"]["source"] == "station_3d_calc"
        assert "efficiency_spec" in flt_params
        assert "heat_tracing_min_c" in flt_params

        s3d = (REPO_ROOT / "kasp" / "web" / "src" / "components" / "station3dView.js").read_text(encoding="utf-8")
        stab = (REPO_ROOT / "kasp" / "web" / "src" / "components" / "stationTab.js").read_text(encoding="utf-8")
        td = (REPO_ROOT / "kasp" / "web" / "src" / "components" / "equipmentTeardown.js").read_text(encoding="utf-8")

        assert "cfsBlowFlask" in s3d
        assert "qocDavit" in s3d
        assert "140 mbar" in s3d and "300 mbar" in s3d and "3 µm" in s3d
        assert "select-param-filters" in stab
        assert "QOC" in stab and "140 mbar" in stab and "300 mbar" in stab
        assert "QOC" in td and "140" in td and "300" in td and "Davit" in td

    def test_station_3d_turbo_compressor_auxiliaries_fuel_dgs_lube_and_provenance(self):
        from kasp.services.station_service import calculate_station_process_model

        res = calculate_station_process_model({
            "flow": 90.0,
            "flow_unit": "kg/s",
            "p_in": 35.0,
            "p_in_unit": "bar(a)",
            "p_out": 75.0,
            "p_out_unit": "bar(a)",
            "t_in": 20.0,
            "gas_comp": NATURAL_GAS,
        })
        ps = res["parameter_sources"]
        equip_by_key = {item["key"]: item["parameters"] for item in ps["equipment"]}
        assert "fuel_gas" in equip_by_key
        tc_params = {p["param"]: p for p in equip_by_key["turbo_compressors"]}
        assert "dgs_spec" in tc_params
        assert "lube_oil_spec" in tc_params
        assert "unit_valves_spec" in tc_params
        assert "air_intake_spec" in tc_params

        s3d = (REPO_ROOT / "kasp" / "web" / "src" / "components" / "station3dView.js").read_text(encoding="utf-8")
        stab = (REPO_ROOT / "kasp" / "web" / "src" / "components" / "stationTab.js").read_text(encoding="utf-8")

        # 3D models & HUD reflect temporary strainer, dual unit valves, DGS skid, fuel gas pre-cooler skid, lube oil cooler
        assert "tempStrainer" in s3d
        assert "dgsPanel" in s3d
        assert "lubeCooler" in s3d
        assert "fuelGasSkid" in s3d
        assert "0.195" not in s3d
        assert "10 µm" in s3d and "1 µm" in s3d
        assert "fuel_gas_system" in s3d

        # 2D SVG & Inspector replace hardcoded 0.195 factor with live ISO 6976 & Item 4 auxiliaries
        assert "0.195" not in stab
        assert "fuel_gas_system" in stab
        assert "dry_gas_seal" in stab
        assert "lube_oil_system" in stab

    def test_station_3d_cooler_dynamic_dp_tcv_and_utilities_ui(self):
        from kasp.services.station_service import calculate_station_process_model

        res = calculate_station_process_model({
            "flow": 95.0,
            "flow_unit": "kg/s",
            "p_in": 38.0,
            "p_in_unit": "bar(a)",
            "p_out": 76.0,
            "p_out_unit": "bar(a)",
            "t_in": 20.0,
            "gas_comp": NATURAL_GAS,
        })
        ps = res["parameter_sources"]
        equip_by_key = {item["key"]: item["parameters"] for item in ps["equipment"]}
        assert "station_utilities" in equip_by_key
        ac_params = {p["param"]: p for p in equip_by_key["air_coolers"]}
        assert ac_params["pressure_drop_bar"]["source"] == "station_3d_calc"

        s3d = (REPO_ROOT / "kasp" / "web" / "src" / "components" / "station3dView.js").read_text(encoding="utf-8")
        stab = (REPO_ROOT / "kasp" / "web" / "src" / "components" / "stationTab.js").read_text(encoding="utf-8")

        assert "Forced-Draft" in stab
        assert "Induced-Draft" not in stab
        assert "station_utilities" in s3d
        assert "station_utilities" in stab
        assert "Gas-over-Oil" in s3d and "Fail-Open" in s3d
        assert "utilityGasSkid" in s3d or "airReceiverTank" in s3d

    def test_station_3d_recycle_pigging_condensate_5250_and_fire_water_ui(self):
        from kasp.services.station_service import calculate_station_process_model

        res = calculate_station_process_model({
            "flow": 95.0,
            "flow_unit": "kg/s",
            "p_in": 38.0,
            "p_in_unit": "bar(a)",
            "p_out": 76.0,
            "p_out_unit": "bar(a)",
            "t_in": 20.0,
            "gas_comp": NATURAL_GAS,
        })
        equip_by_key = {item["key"]: item["parameters"] for item in res["parameter_sources"]["equipment"]}
        assert "pigging" in equip_by_key
        assert "fire_water" in equip_by_key
        cond_params = {p["param"]: p for p in equip_by_key["condensate_system"]}
        assert "spec_5250_pump" in cond_params

        s3d = (REPO_ROOT / "kasp" / "web" / "src" / "components" / "station3dView.js").read_text(encoding="utf-8")
        stab = (REPO_ROOT / "kasp" / "web" / "src" / "components" / "stationTab.js").read_text(encoding="utf-8")

        assert "DIN 6608" in s3d and ("300 m³" in s3d or "300} m³" in s3d)
        assert "DIN 6608" in stab and ("300 m³" in stab or "300} m³" in stab)
        assert 'key === "fire_water"' in s3d and 'key === "fire_water"' in stab
        assert "0.5–4.0 barg" in s3d or "0.5-4.0 barg" in s3d

    def test_station_3d_and_2d_expose_4500_valves_loading_and_bypass(self):
        s3d = (REPO_ROOT / "kasp" / "web" / "src" / "components" / "station3dView.js").read_text(encoding="utf-8")
        stab = (REPO_ROOT / "kasp" / "web" / "src" / "components" / "stationTab.js").read_text(encoding="utf-8")

        for key in (
            "station_suction_valve",
            "station_discharge_valve",
            "mainline_block_valve",
            "station_loading_line",
            "station_bypass_valve",
        ):
            assert f'"{key}"' in s3d, f"{key} missing in station3dView.js"
            assert f'data-equip-key="{key}"' in stab, f"{key} missing in 2D SVG in stationTab.js"
            assert f'key === "{key}"' in stab, f"{key} inspector missing in stationTab.js"
        assert 'data-equip-key="ultrasonic_meter"' in stab






