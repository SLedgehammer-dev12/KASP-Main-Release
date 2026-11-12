"""TDD Suite for Konu #4:
- F02: Turbine thermal efficiency (therm_eff), ISO 2314 site conditions (ambient_temp, altitude, humidity),
  driver_thermal_efficiency_pct, and per-turbine site_thermal_efficiency_pct.
- F12: Project history & .kasp export/import full-state persistence (selected_units, charts, warnings,
  modules, station_data) + Desktop <-> Web input key synchronization.
- F10: Design PDF report Web key compatibility (eos_model, calc_method, ambient_temp/t_amb, mixed pressure units).
- F11: Multi-sheet Excel report design KPIs, stage table, matched turbines, and design warnings.
"""

from __future__ import annotations

import io
import json
import os
import tempfile

import openpyxl
import pytest
from fastapi.testclient import TestClient

from kasp.api.server import app
from kasp.data.database import UnitDatabase
from kasp.security import hash_password
from kasp.utils.project_manager import ProjectManager
from kasp.utils.reporting import REPORTLAB_LOADED


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="module")
def auth_headers(client):
    db = UnitDatabase()
    admin_pw = "AdminPass123!"
    existing = db.get_user_by_username("konu4_admin")
    if not existing:
        db.create_user(
            username="konu4_admin",
            password_hash=hash_password(admin_pw),
            role="admin",
            full_name="Konu 4 Admin",
            email="konu4@kasp.local",
        )
    else:
        db.update_user(existing["id"], password_hash=hash_password(admin_pw), role="admin")
    db.reset_auth_lockout("konu4_admin")

    resp = client.post("/api/v1/auth/login", json={"username": "konu4_admin", "password": admin_pw})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    return {
        "Authorization": f"Bearer {body['token']}",
        "X-CSRF-Token": body["csrf_token"],
    }


def _base_design_payload(**overrides):
    payload = {
        "project_name": "Konu 4 Entegrasyon Testi",
        "p_in": 20.0,
        "p_in_unit": "bar(a)",
        "p_out": 60.0,
        "p_out_unit": "bar(a)",
        "t_in": 25.0,
        "t_in_unit": "°C",
        "flow": 15.0,
        "flow_unit": "kg/s",
        "gas_comp": {
            "METHANE": 88.0,
            "ETHANE": 7.0,
            "PROPANE": 3.0,
            "NITROGEN": 1.0,
            "CARBONDIOXIDE": 1.0,
        },
        "eos_model": "pr",
        "calc_method": "Metot 6: Schultz 3-Üslü Gerçek Gaz",
        "poly_eff": 82.0,
        "mech_eff": 98.0,
        "therm_eff": 35.0,
        "num_units": 1,
        "num_stages": 2,
        "intercooler_t": 35.0,
        "intercooler_dp_pct": 2.0,
    }
    payload.update(overrides)
    return payload


def test_design_api_turbine_efficiency_and_site_derating(client):
    """F02: therm_eff yakıt/heat-rate'i ölçekler; driver_thermal_efficiency_pct ve site derating döner."""
    resp_iso = client.post(
        "/api/v1/calculations/design",
        json=_base_design_payload(therm_eff=35.0, ambient_temp=15.0, altitude=0.0, humidity=60.0),
    )
    assert resp_iso.status_code == 200, resp_iso.text
    data_iso = resp_iso.json()
    res_iso = data_iso["results"]
    units_iso = data_iso["selected_units"]

    resp_hot = client.post(
        "/api/v1/calculations/design",
        json=_base_design_payload(therm_eff=42.0, ambient_temp=40.0, altitude=1200.0, humidity=40.0),
    )
    assert resp_hot.status_code == 200, resp_hot.text
    data_hot = resp_hot.json()
    res_hot = data_hot["results"]
    units_hot = data_hot["selected_units"]

    # 1. Gerçek sürücü ısıl verimi sonuç sözlüğünde yer almalı (sabit 36.5% yerine)
    assert res_iso.get("driver_thermal_efficiency_pct") == pytest.approx(35.0, rel=1e-3)
    assert res_hot.get("driver_thermal_efficiency_pct") == pytest.approx(42.0, rel=1e-3)

    # 2. Heat rate ve kütlesel yakıt tüketimi therm_eff ile ters orantılı ölçeklenmeli (35 / 42)
    expected_ratio = 35.0 / 42.0
    assert (res_hot["heat_rate"] / res_iso["heat_rate"]) == pytest.approx(expected_ratio, rel=1e-4)
    assert (res_hot["fuel_unit_kgh"] / res_iso["fuel_unit_kgh"]) == pytest.approx(expected_ratio, rel=1e-4)
    assert res_hot["heat_rate"] == pytest.approx(3600.0 / 0.42, rel=1e-3)

    # 3. Türbin listesinde site_thermal_efficiency_pct alanı bulunmalı ve ISO 2314 saha güç düşümü çalışmalı
    assert len(units_iso) > 0 and len(units_hot) > 0
    top_iso = units_iso[0]
    assert top_iso.get("site_thermal_efficiency_pct") is not None
    if top_iso.get("site_heat_rate_kj_kwh", 0) > 0:
        assert top_iso["site_thermal_efficiency_pct"] == pytest.approx(
            360000.0 / top_iso["site_heat_rate_kj_kwh"], abs=0.15
        )

    # Aynı türbin modeli için 40°C / 1200 m saha gücü, 15°C / 0 m gücünden belirgin düşük olmalı
    iso_by_name = {u["name"]: u for u in units_iso}
    hot_by_name = {u["name"]: u for u in units_hot}
    shared_models = set(iso_by_name).intersection(hot_by_name)
    if shared_models:
        model_name = next(iter(shared_models))
        assert hot_by_name[model_name]["site_power_kw"] < iso_by_name[model_name]["site_power_kw"] * 0.90
    else:
        assert units_hot[0]["site_power_kw"] < units_hot[0]["iso_power_kw"] * 0.92

    # 4. t_amb eski anahtarı gönderildiğinde de ambient_temp'e eşlenmeli
    resp_legacy_tamb = client.post(
        "/api/v1/calculations/design",
        json=_base_design_payload(t_amb=38.0),
    )
    assert resp_legacy_tamb.status_code == 200, resp_legacy_tamb.text
    assert resp_legacy_tamb.json()["inputs"]["ambient_temp"] == pytest.approx(38.0)


def test_project_history_and_kasp_roundtrip_preserve_units_charts_warnings_and_site_inputs(client, auth_headers):
    """F12: Kaydet/Yükle ve .kasp Dışa/İçe Aktar selected_units, charts, warnings, therm_eff ve saha verilerini korur."""
    inputs = _base_design_payload(
        project_name="Tam Durum Kalıcılık Projesi",
        therm_eff=41.5,
        ambient_temp=34.0,
        altitude=850.0,
        custom_kij={"METHANE:CARBONDIOXIDE": 0.105},
    )
    results = {
        "power_shaft_per_unit_kw": 4820.0,
        "power_motor_per_unit_kw": 4918.4,
        "power_unit_kw": 5115.1,
        "fuel_unit_kgh": 910.5,
        "heat_rate": 8674.7,
        "driver_thermal_efficiency_pct": 41.5,
        "stages": [{"stage": 1, "p_in_bar": 20.0, "p_out_bar": 35.0, "t_in_c": 25.0, "t_out_c": 78.2, "power_kw": 2410.0}],
    }
    selected_units = [
        {
            "name": "Solar Mars 100",
            "model": "Mars 100",
            "manufacturer": "Solar Turbines",
            "site_power_kw": 8950.0,
            "iso_power_kw": 10690.0,
            "site_heat_rate_kj_kwh": 10980.0,
            "site_thermal_efficiency_pct": 32.79,
            "power_margin_pct": 82.0,
        }
    ]
    charts = {
        "operating_envelope": {"operating_point": {"q_acmh": 26500.0, "surge_margin_pct": 24.5}},
        "ambient_derating": {"design_ambient_c": 34.0, "traces": [{"name": "Mars 100"}]},
    }
    warnings = ["Ağır hidrokarbon çiğlenme noktası kontrol edilmeli."]
    modules = {"psv": {"results": {"Selected_Orifice_Letter": "J", "Required_Area_sqin": 1.12}}}
    station_data = {"station_summary": {"total_power_mw": 5.12, "pressure_ratio": 3.0}}

    # 1. Veritabanı geçmişine kaydet -> tekil ve liste sorgularında tüm ekleri geri al
    save_resp = client.post(
        "/api/v1/projects",
        headers=auth_headers,
        json={
            "project_name": inputs["project_name"],
            "calculation_type": "Design",
            "inputs": inputs,
            "results": results,
            "selected_units": selected_units,
            "charts": charts,
            "warnings": warnings,
            "modules": modules,
            "station_data": station_data,
            "notes": "Konu 4 testi",
        },
    )
    assert save_resp.status_code == 200, save_resp.text
    proj_id = save_resp.json()["id"]

    get_resp = client.get(f"/api/v1/projects/{proj_id}", headers=auth_headers)
    assert get_resp.status_code == 200, get_resp.text
    loaded = get_resp.json()
    assert loaded["inputs"]["therm_eff"] == pytest.approx(41.5)
    assert loaded["inputs"]["ambient_temp"] == pytest.approx(34.0)
    assert loaded["inputs"]["altitude"] == pytest.approx(850.0)
    assert loaded["selected_units"] == selected_units
    assert loaded["charts"] == charts
    assert loaded["warnings"] == warnings
    assert loaded["modules"] == modules
    assert loaded["station_data"] == station_data

    list_resp = client.get("/api/v1/projects?limit=10", headers=auth_headers)
    assert list_resp.status_code == 200
    listed = next(item for item in list_resp.json() if item["id"] == proj_id)
    assert listed["selected_units"] == selected_units
    assert listed["charts"] == charts
    assert listed["warnings"] == warnings

    # 2. .kasp dışa aktar -> içe aktar round-trip
    exp_resp = client.post(
        "/api/v1/projects/export-kasp",
        headers=auth_headers,
        json={
            "project_name": "konu4_roundtrip",
            "inputs": inputs,
            "results": results,
            "selected_units": selected_units,
            "charts": charts,
            "warnings": warnings,
            "modules": modules,
            "station_data": station_data,
        },
    )
    assert exp_resp.status_code == 200, exp_resp.text

    imp_resp = client.post(
        "/api/v1/projects/import-kasp",
        headers=auth_headers,
        files={"file": ("konu4_roundtrip.kasp", exp_resp.content, "application/json")},
    )
    assert imp_resp.status_code == 200, imp_resp.text
    imp = imp_resp.json()
    assert imp["inputs"]["therm_eff"] == pytest.approx(41.5)
    assert imp["inputs"]["ambient_temp"] == pytest.approx(34.0)
    assert imp["inputs"]["altitude"] == pytest.approx(850.0)
    assert imp["inputs"]["custom_kij"] == {"METHANE:CARBONDIOXIDE": 0.105}
    assert imp["selected_units"] == selected_units
    assert imp["charts"] == charts
    assert imp["warnings"] == warnings
    assert imp["modules"]["psv"]["results"] == modules["psv"]["results"]
    assert imp["station_data"] == station_data


def test_project_manager_desktop_web_bidirectional_key_sync_and_legacy_eos_migration():
    """F12: Masaüstü <-> Web girdi anahtarları çift yönlü eşitlenir; eski rk/bwrs EOS'ları göç ettirilir."""
    pm = ProjectManager()
    with tempfile.TemporaryDirectory() as tmpdir:
        # Web tarzı girdi ile kayıt -> Masaüstü de eos_method ve method anahtarlarını görür
        web_path = os.path.join(tmpdir, "web_origin.kasp")
        ok, _ = pm.save_project(
            web_path,
            {
                "project_name": "Web Kaynaklı",
                "eos_model": "gerg2008",
                "calc_method": "Metot 5: Huntington-RK45 Diferansiyel",
                "t_amb": 32.5,
                "therm_eff": 39.0,
                "altitude": 600,
                "custom_kij": {"METHANE:ETHANE": 0.003},
            },
            results={"power_unit_kw": 3200.0},
            selected_units=[{"name": "NovaLT12"}],
            charts={"ambient_derating": {"traces": []}},
            warnings=["Test uyarısı"],
        )
        assert ok
        ok_load, loaded_inp, loaded_res = pm.load_project(web_path)
        assert ok_load
        assert loaded_inp["eos_method"] == "gerg2008"
        assert loaded_inp["eos_model"] == "gerg2008"
        assert loaded_inp["method"] == "Metot 5: Huntington-RK45 Diferansiyel"
        assert loaded_inp["calc_method"] == "Metot 5: Huntington-RK45 Diferansiyel"
        assert loaded_inp["ambient_temp"] == pytest.approx(32.5)
        assert loaded_inp["therm_eff"] == pytest.approx(39.0)
        assert loaded_inp["altitude"] == 600
        assert loaded_inp["custom_kij"] == {"METHANE:ETHANE": 0.003}
        assert loaded_res["selected_units"] == [{"name": "NovaLT12"}]
        assert loaded_res["charts"] == {"ambient_derating": {"traces": []}}
        assert loaded_res["warnings"] == ["Test uyarısı"]

        # Eski şemalı rk / bwrs EOS içeren proje migrasyonu
        migrated = pm._migrate_project_schema(
            {
                "schema_version": "3.0",
                "inputs": {"project_name": "Eski RK", "eos_method": "rk", "method": "Metot 6: Schultz 3-Üslü Gerçek Gaz"},
                "results": None,
            }
        )
        assert migrated["inputs"]["eos_method"] == "srk"
        assert migrated["inputs"]["eos_model"] == "srk"
        assert migrated["inputs"]["calc_method"] == "Metot 6: Schultz 3-Üslü Gerçek Gaz"

        # Boş sonuç (results=None) davranışı bozulmamalı
        empty_path = os.path.join(tmpdir, "empty.kasp")
        ok_empty, _ = pm.save_project(empty_path, {"project_name": "Boş"}, None)
        assert ok_empty
        _, _, empty_res = pm.load_project(empty_path)
        assert empty_res is None


@pytest.mark.skipif(not REPORTLAB_LOADED, reason="ReportLab yüklü değil")
def test_pdf_report_web_keys_eos_method_ambient_and_mixed_pressure_units(client, monkeypatch):
    """F10: Web anahtarlarıyla üretilen PDF raporu sahte Fallback etiketi basmaz; metot, ortam T ve basınç birimlerini korur."""
    import kasp.utils.reporting as reporting_mod

    captured_tables = []
    orig_build = reporting_mod.SimpleDocTemplate.build

    def _spy_build(self, flowables, *args, **kwargs):
        for item in flowables:
            if hasattr(item, "_cellvalues"):
                captured_tables.append(item._cellvalues)
        return orig_build(self, flowables, *args, **kwargs)

    monkeypatch.setattr(reporting_mod.SimpleDocTemplate, "build", _spy_build)

    web_inputs = {
        "project_name": "Web PDF Rapor Testi",
        "p_in": 48.0,
        "p_in_unit": "bar(g)",
        "p_out": 75.0,
        "p_out_unit": "bar(a)",
        "t_in": 22.0,
        "t_in_unit": "°C",
        "flow": 18.0,
        "flow_unit": "kg/s",
        "gas_comp": {"METHANE": 92.0, "ETHANE": 8.0},
        "eos_model": "pr",
        "calc_method": "Metot 6: Schultz 3-Üslü Gerçek Gaz",
        "poly_eff": 82.0,
        "mech_eff": 98.0,
        "therm_eff": 41.0,
        "ambient_temp": 33.0,
        "altitude": 900.0,
    }
    web_results = {
        "effective_eos": "pr",
        "t_out": 84.5,
        "compression_ratio": 1.53,
        "actual_poly_efficiency": 0.82,
        "power_gas_per_unit_kw": 1850.0,
        "power_shaft_per_unit_kw": 1890.0,
        "power_motor_per_unit_kw": 1928.6,
        "power_unit_kw": 2005.7,
        "power_unit_total_kw": 2005.7,
        "fuel_unit_kgh": 350.2,
        "fuel_total_kgh": 350.2,
        "mass_flow_per_unit_kgs": 18.0,
        "mass_flow_total_kgs": 18.0,
        "inlet_vol_flow_acmh_per_unit": 1900.0,
        "heat_rate": 8780.5,
        "lhv": 48200.0,
        "hhv": 53400.0,
        "num_units": 1,
    }

    resp = client.post(
        "/api/v1/reports/pdf",
        json={"inputs": web_inputs, "results": web_results, "selected_units": []},
    )
    assert resp.status_code == 200, resp.text
    assert resp.content.startswith(b"%PDF-")

    flat_cells = [
        str(cell)
        for table in captured_tables
        for row in table
        for cell in row
    ]
    joined = " | ".join(flat_cells)
    assert "Peng-Robinson" in joined
    assert "CoolProp -> Peng-Robinson (Fallback)" not in joined
    assert "Metot 6: Schultz 3-Üslü Gerçek Gaz" in joined
    assert "33.0" in joined
    assert "41.0" in joined
    assert "bar(g)" in joined and "bar(a)" in joined


def test_excel_report_includes_design_kpis_stages_turbines_and_design_warnings(client):
    """F11: Excel raporu mevcut modül sayfalarını bozmadan Tasarım, Türbinler ve tasarım uyarılarını içerir."""
    payload = {
        "inputs": _base_design_payload(project_name="Excel Tam Rapor", therm_eff=40.0, ambient_temp=30.0),
        "results": {
            "power_gas_per_unit_kw": 4100.0,
            "power_shaft_per_unit_kw": 4160.0,
            "power_motor_per_unit_kw": 4244.9,
            "power_unit_kw": 4414.7,
            "power_unit_total_kw": 4414.7,
            "head_kj_kg": 274.5,
            "compression_ratio": 3.0,
            "t_out": 86.4,
            "actual_poly_efficiency": 0.82,
            "driver_thermal_efficiency_pct": 40.0,
            "heat_rate": 9000.0,
            "fuel_unit_kgh": 785.4,
            "fuel_total_kgh": 785.4,
            "lhv": 48620.0,
            "stages": [
                {
                    "stage": 1,
                    "p_in_bar": 20.0,
                    "p_out_bar": 34.64,
                    "t_in_c": 25.0,
                    "t_out_c": 79.1,
                    "head_kj_kg": 138.2,
                    "power_kw": 2073.0,
                    "actual_poly_eff": 0.82,
                },
                {
                    "stage": 2,
                    "p_in_bar": 33.95,
                    "p_out_bar": 60.0,
                    "t_in_c": 35.0,
                    "t_out_c": 86.4,
                    "head_kj_kg": 136.3,
                    "power_kw": 2027.0,
                    "actual_poly_eff": 0.82,
                },
            ],
            "warnings": ["Tasarım faz zarfı kontrol uyarısı."],
        },
        "selected_units": [
            {
                "name": "Solar Centaur 50",
                "model": "Centaur 50",
                "manufacturer": "Solar Turbines",
                "type": "Industrial",
                "iso_power_kw": 4600.0,
                "site_power_kw": 4380.0,
                "site_heat_rate_kj_kwh": 12200.0,
                "site_thermal_efficiency_pct": 29.51,
                "power_margin_pct": 3.2,
                "selection_score": 91.4,
            }
        ],
        "warnings": ["Girdi doğrulama uyarısı: yüksek sıkıştırma oranı."],
        "modules": {
            "psv": {"results": {"Selected_Orifice_Letter": "H", "Required_Area_sqin": 0.72}, "warnings": ["PSV uyarısı."]},
            "api5l": {"results": {"recommendation": {"nominal_size_in": 16, "material_grade": "X65"}}},
            "air_cooler": {"results": {"heat_duty_kw": 1450.0}},
            "control_valve": {"results": {"service": "ASV", "required_cv": 120.0}},
        },
        "station_data": {"station_summary": {"total_power_mw": 4.41, "pressure_ratio": 3.0}},
    }

    resp = client.post("/api/v1/reports/modules-excel", json=payload)
    assert resp.status_code == 200, resp.text
    wb = openpyxl.load_workbook(io.BytesIO(resp.content))
    names = set(wb.sheetnames)

    # Mevcut sözleşme sayfaları korunmalı
    assert {"Özet", "PSV", "API5L", "AirCooler", "KontrolVanasi", "Istasyon", "Uyarılar"}.issubset(names)
    # Yeni Tasarım ve Türbinler sayfaları eklenmeli
    assert "Tasarım" in names
    assert "Türbinler" in names

    design_values = " | ".join(
        str(cell)
        for row in wb["Tasarım"].iter_rows(values_only=True)
        for cell in row
        if cell is not None
    )
    assert "4160" in design_values
    assert "785.4" in design_values
    assert "40" in design_values

    turbine_values = " | ".join(
        str(cell)
        for row in wb["Türbinler"].iter_rows(values_only=True)
        for cell in row
        if cell is not None
    )
    assert "Centaur 50" in turbine_values
    assert "4380" in turbine_values

    warning_values = " | ".join(
        str(cell)
        for row in wb["Uyarılar"].iter_rows(values_only=True)
        for cell in row
        if cell is not None
    )
    assert "PSV uyarısı." in warning_values
    assert "Tasarım faz zarfı kontrol uyarısı." in warning_values
    assert "Girdi doğrulama uyarısı: yüksek sıkıştırma oranı." in warning_values
