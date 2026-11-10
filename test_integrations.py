"""Integration module tests: PSV, API 5L and pipe hydraulics."""

import pytest
from fastapi.testclient import TestClient

from kasp.api.server import app
from kasp.integrations.registry import calculate_module, list_modules

client = TestClient(app)

COMPOSITION = {
    "METHANE": 88.0,
    "ETHANE": 7.0,
    "PROPANE": 3.0,
    "NITROGEN": 1.0,
    "CARBONDIOXIDE": 1.0,
}


def test_module_registry_lists_station_modules():
    ids = {m["id"] for m in list_modules()}
    assert {"psv", "api5l", "pipe_hydraulics"}.issubset(ids)


def test_api5l_botas_vs_asme_recommendation():
    result = calculate_module(
        "api5l",
        {
            "diameter_in": "48",
            "material_grade": "X65",
            "design_pressure_bar": 75.0,
            "design_factor_f": 0.50,
            "location_type": "Station",
            "standard_code": "BOTAŞ",
            "psl_level": "PSL2",
            "compare_standards": True,
        },
    )
    rec = result["results"]["recommendation"]
    assert rec["standard"] == "BOTAŞ"
    assert rec["required_thickness_mm"] > 0
    assert rec["selected_nominal_thickness_mm"] >= rec["required_thickness_mm"]
    assert rec["botas_standard_thickness_mm"] > 0
    assert rec["is_sufficient"] is True
    assert "BOTAŞ" in result["results"]["comparison"]


def test_pipe_hydraulics_total_pressure_drop():
    result = calculate_module(
        "pipe_hydraulics",
        {
            "flow_kgs": 12.0,
            "pressure_bar": 45.0,
            "temp_c": 25.0,
            "composition": COMPOSITION,
            "length_m": 500.0,
            "fitting_k_total": 3.5,
            "elevation_m": 10.0,
            "material": "API 5L X70",
            "design_factor_F": 0.50,
        },
    )
    rec = result["results"]["recommendation"]
    detail = result["results"]["detail"]
    assert rec["nominal_size_in"]
    assert rec["pressure_drop_bar_total"] > 0
    assert detail["pressure_drop_friction_bar"] > 0
    assert detail["pressure_drop_fittings_bar"] > 0
    assert detail["pressure_drop_elevation_bar"] > 0
    assert rec["outlet_pressure_bar"] < 45.0


def test_psv_gas_sizing():
    result = calculate_module(
        "psv",
        {
            "service": "gas",
            "p1_bar": 82.5,
            "p2_bar": 1.01325,
            "t_c": 84.4,
            "mass_flow_kgs": 12.0,
            "composition": COMPOSITION,
            "valve_type": "conventional",
        },
    )
    assert result["success"] is True
    assert result["results"]["Required_Area_sqin"] > 0
    assert result["results"]["Selected_Orifice_Letter"]
    assert result["results"]["Result_Meta"]["Standard"].startswith("API 520")


def test_air_cooler_detailed_design():
    result = calculate_module(
        "air_cooler",
        {
            "composition": COMPOSITION,
            "mass_flow_kgs": 12.0,
            "p_in_bar": 60.0,
            "p_out_bar": 59.6,
            "t_in_c": 84.4,
            "t_out_c": 45.0,
            "air_in_c": 15.0,
            "air_out_c": 35.0,
            "auto_size": True,
        },
    )
    r = result["results"]
    assert r["heat_duty_kw"] > 0
    assert r["required_area_m2"] > 0
    assert r["actual_area_m2"] >= r["required_area_m2"] * 0.95
    assert r["fan_power_kw"] > 0
    assert r["geometry"]["tubes_per_row"] >= 24


def test_control_valve_gas_sizing():
    result = calculate_module(
        "control_valve",
        {
            "service": "gas",
            "composition": COMPOSITION,
            "mass_flow_kgs": 12.0,
            "p_in_bar": 60.0,
            "p_out_bar": 20.0,
            "t_c": 84.4,
        },
    )
    r = result["results"]
    assert r["required_cv"] > 0
    assert r["valve_dn_mm"] > 0
    assert r["valve_inch"]
    assert 0.0 <= r["opening_percent"] <= 110.0


def test_project_manager_roundtrip_with_modules(tmp_path):
    from kasp.utils.project_manager import ProjectManager

    modules = {"psv": {"results": {"Required_Area_sqin": 1.47}, "warnings": []}}
    station = {"station_summary": {"total_mass_flow_kgs": 12.0}}
    path = tmp_path / "module_project.kasp"
    pm = ProjectManager()
    assert pm.save_project(path, {"project_name": "Modül Testi"}, {"t_out": 84.4}, modules=modules, station_data=station)
    ok, inputs, results = pm.load_project(path)
    assert ok
    assert inputs["project_name"] == "Modül Testi"
    assert results["module_results"]["psv"]["results"]["Required_Area_sqin"] == 1.47
    assert results["station_data"]["station_summary"]["total_mass_flow_kgs"] == 12.0


def test_module_workbook_contains_sheets():
    from openpyxl import load_workbook
    from kasp.services.module_report_service import build_module_workbook

    modules = {
        "psv": {"results": {"Required_Area_sqin": 1.47, "Selected_Orifice_Letter": "K"}},
        "api5l": {"results": {"recommendation": {"nominal_size_in": "48\"", "required_thickness_mm": 20.32}}},
        "air_cooler": {"results": {"heat_duty_kw": 1038.0, "required_area_m2": 1370.0}},
        "control_valve": {"results": {"service": "gas", "required_cv": 41.7, "valve_inch": "2\""}},
    }
    station = {
        "station_summary": {"total_mass_flow_kgs": 12.0, "pressure_ratio": 3.0},
        "station_piping": {"pipe_standard": "BOTAŞ", "psl_level": "PSL2", "lines": {}},
    }
    buffer = build_module_workbook({"project_name": "Test"}, {"t_out": 84.4}, modules, station)
    workbook = load_workbook(buffer)
    names = set(workbook.sheetnames)
    assert {"Özet", "PSV", "API5L", "AirCooler", "KontrolVanasi", "Istasyon"}.issubset(names)


def test_module_schema_migration():
    from kasp.integrations.schema import (
        MODULE_SCHEMA_VERSION,
        migrate_module_payload,
        migrate_modules_payload,
    )

    legacy = migrate_module_payload("psv", {"Required_Area_sqin": 1.47})
    assert legacy["schema_version"] == MODULE_SCHEMA_VERSION
    assert legacy["results"]["Required_Area_sqin"] == 1.47

    future = migrate_module_payload(
        "psv",
        {"schema_version": "99.0", "results": {"x": 1}, "warnings": []},
    )
    assert future["schema_version"] == "99.0"
    assert any("yeni" in str(w).lower() for w in future["warnings"])

    migrated = migrate_modules_payload({"api5l": {"results": {"recommendation": {"x": 1}}}})
    assert migrated["api5l"]["schema_version"] == MODULE_SCHEMA_VERSION


def test_project_schema_migrates_legacy_modules(tmp_path):
    from kasp.utils.project_manager import ProjectManager

    project = {
        "schema_version": ProjectManager.VERSION,
        "inputs": {"project_name": "Legacy Modül"},
        "results": {"module_results": {"psv": {"Required_Area_sqin": 1.47}}},
        "modules": {"psv": {"Required_Area_sqin": 1.47}},
    }
    migrated = ProjectManager()._migrate_project_schema(project)
    assert migrated["modules"]["psv"]["schema_version"] == "1.0"
    assert migrated["results"]["module_results"]["psv"]["schema_version"] == "1.0"


def test_pdf_report_includes_modules():
    import io
    from kasp.core.thermo import ThermoEngine
    from kasp.services.calculation_service import execute_design_calculation
    from kasp.utils.reporting import ReportGenerator

    inputs = {
        "p_in": 20.0,
        "p_in_unit": "bar(a)",
        "p_out": 60.0,
        "p_out_unit": "bar(a)",
        "t_in": 25.0,
        "t_in_unit": "°C",
        "flow": 12.0,
        "flow_unit": "kg/s",
        "gas_comp": COMPOSITION,
        "eos_model": "pr",
        "calc_method": "Metot 6: Schultz 3-Üslü Gerçek Gaz",
        "poly_eff": 82.0,
        "num_units": 1,
        "num_stages": 2,
        "intercooler_t": 35.0,
        "mech_eff": 98.0,
    }
    results = execute_design_calculation(inputs)
    results["module_results"] = {
        "psv": {"results": {"Required_Area_sqin": 1.47, "Selected_Orifice_Letter": "K"}},
        "api5l": {"results": {"recommendation": {"nominal_size_in": "48\"", "required_thickness_mm": 20.32, "is_sufficient": True}}},
        "air_cooler": {"results": {"heat_duty_kw": 1038.0, "required_area_m2": 1370.0, "actual_area_m2": 1486.0}},
    }
    results["station_data"] = {"station_summary": {"total_mass_flow_kgs": 12.0, "pressure_ratio": 3.0, "total_power_mw": 2.44}}
    buffer = io.BytesIO()
    ReportGenerator(buffer, ThermoEngine()).generate_design_report(inputs, results, [], None)
    pdf = buffer.getvalue()
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 20000


def test_station_uses_api5l_psv_and_control_valves():
    from kasp.services.station_service import calculate_station_process_model

    res = calculate_station_process_model(
        {
            "flow": 12.0,
            "flow_unit": "kg/s",
            "p_in": 20.0,
            "p_in_unit": "bar(a)",
            "p_out": 60.0,
            "p_out_unit": "bar(a)",
            "t_in": 25.0,
            "gas_comp": COMPOSITION,
            "pipe_standard": "BOTAŞ",
            "psl_level": "PSL2",
        }
    )
    eq = res["equipment_sizing"]
    assert eq["safety_relief_and_blowdown"]["psv_sizing"]["required_area_sqin"] > 0
    assert eq["turbo_compressors"]["anti_surge_valve_sizing"]["required_cv"] > 0
    assert eq["station_recycle"]["pcv_sizing"]["required_cv"] > 0
    assert eq["air_coolers"]["cooler_bypass_valve_sizing"]["required_cv"] > 0
    line = res["station_piping"]["lines"]["suction_header"]
    assert line["standard_recommendation"]["standard"] == "BOTAŞ"
    assert line["standard_recommendation"]["required_thickness_mm"] > 0


def test_modules_api_endpoint():
    response = client.get("/api/v1/modules")
    assert response.status_code == 200
    assert any(m["id"] == "api5l" for m in response.json()["modules"])

    response = client.post(
        "/api/v1/modules/pipe_hydraulics/calculate",
        json={
            "payload": {
                "flow_kgs": 12.0,
                "pressure_bar": 20.0,
                "temp_c": 25.0,
                "composition": COMPOSITION,
                "length_m": 100.0,
            }
        },
    )
    assert response.status_code == 200
    assert response.json()["results"]["recommendation"]["nominal_size_in"]


def test_air_cooler_api_endpoint():
    response = client.post(
        "/api/v1/modules/air_cooler/calculate",
        json={
            "payload": {
                "composition": COMPOSITION,
                "mass_flow_kgs": 12.0,
                "p_in_bar": 60.0,
                "p_out_bar": 59.6,
                "t_in_c": 84.4,
                "t_out_c": 45.0,
                "auto_size": False,
                "geometry": {"tubes_per_row": 40},
            }
        },
    )
    assert response.status_code == 200
    assert response.json()["results"]["heat_duty_kw"] > 0
