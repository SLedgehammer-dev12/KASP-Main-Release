"""Integration Tests for KASP Web API v1.

Verifies all REST endpoints: Auth, RBAC, Metadata, Gas & kij matrix, Calculations,
Equipment CRUD, In-Memory PDF streaming, Project import/export, Shootout jobs, and Logs.
"""

import io
import json
import pytest
from fastapi.testclient import TestClient

from kasp.api.auth import session_store
from kasp.api.server import app
from kasp.core.user_manager import UserManager
from kasp.data.database import UnitDatabase
from kasp.security import hash_password


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="module")
def auth_tokens(client):
    """Seed test admin and test user in DB, and log in to get session headers."""
    db = UnitDatabase()
    user_mgr = UserManager(db)

    # Ensure admin exists
    admin_pw = "AdminPass123!"
    existing_admin = db.get_user_by_username("test_admin")
    if not existing_admin:
        db.create_user(
            username="test_admin",
            password_hash=hash_password(admin_pw),
            role="admin",
            full_name="Test Administrator",
            email="admin@kasp.local",
        )
    else:
        db.update_user(existing_admin["id"], password_hash=hash_password(admin_pw), role="admin")

    # Reset any lockout
    db.reset_auth_lockout("test_admin")

    # Login as admin
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": "test_admin", "password": admin_pw},
    )
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    data = resp.json()
    token = data["token"]
    csrf = data["csrf_token"]
    cookie_header = resp.headers.get("set-cookie", "")

    headers = {
        "Authorization": f"Bearer {token}",
        "X-CSRF-Token": csrf,
    }
    return {"token": token, "csrf": csrf, "headers": headers, "user": data["user"]}


def test_metadata_constants(client):
    """Check constants and system metadata."""
    resp = client.get("/api/v1/meta/constants")
    assert resp.status_code == 200
    data = resp.json()
    assert "version" in data
    assert "gases" in data
    assert len(data["gases"]) >= 19
    assert "units" in data


def test_metadata_presets(client):
    """Check 4 engineering presets."""
    resp = client.get("/api/v1/meta/presets")
    assert resp.status_code == 200
    presets = resp.json()
    assert len(presets) == 4
    keys = [p.get("id") or p.get("key") for p in presets]
    assert "natural_gas" in keys
    assert "lng_boiloff" in keys
    assert "co2_injection" in keys
    assert "hydrogen_blend" in keys


def test_metadata_gases(client):
    """Check 19 standard gases catalog."""
    resp = client.get("/api/v1/thermo/gases")
    assert resp.status_code == 200
    gases = resp.json()
    assert len(gases) >= 17
    symbols = [g.get("id") or g.get("symbol") for g in gases]
    assert "METHANE" in symbols
    assert "HYDROGEN" in symbols
    assert "CARBONDIOXIDE" in symbols


def test_thermo_recommendations(client):
    """Check smart EOS and Method recommendations."""
    payload = {
        "gas_comp": {"METHANE": 85.0, "ETHANE": 10.0, "PROPANE": 5.0},
        "pressure_ratio": 4.5,
    }
    resp = client.post("/api/v1/thermo/recommendations", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "recommended_eos" in data
    assert "recommended_method" in data
    assert "reason" in data


def test_thermo_kij_matrix_generator(client):
    """Check N x N kij matrix generation and override."""
    payload = {
        "gas_comp": {"METHANE": 80.0, "CARBONDIOXIDE": 20.0},
        "custom_kij": {"METHANE:CARBONDIOXIDE": 0.095},
    }
    resp = client.post("/api/v1/thermo/kij-matrix", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "matrix" in data
    assert len(data["matrix"]) == 2
    assert "components" in data
    assert len(data["components"]) == 2
    assert "sources" in data
    assert data["has_overrides"] is True
    # Verify override took effect at (0, 1) or (1, 0)
    assert data["matrix"][0][1] == 0.095 or data["matrix"][1][0] == 0.095
    assert data["sources"][0][1] == "user_override" or data["sources"][1][0] == "user_override"


def test_auth_login_and_me(client, auth_tokens):
    """Check login token verification and me endpoint."""
    headers = auth_tokens["headers"]
    resp = client.get("/api/v1/auth/me", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["user"]["username"] == "test_admin"
    assert "csrf_token" in data


def test_auth_lockout_enforcement(client):
    """Verify that repeated invalid attempts trigger 429 Too Many Requests."""
    bad_user = "lockout_tester"
    db = UnitDatabase()
    db.reset_auth_lockout(bad_user)

    for _ in range(3):
        client.post("/api/v1/auth/login", json={"username": bad_user, "password": "WrongPassword1!"})

    resp = client.post("/api/v1/auth/login", json={"username": bad_user, "password": "WrongPassword1!"})
    assert resp.status_code == 429
    assert "kilitlendi" in resp.json()["detail"].lower()
    db.reset_auth_lockout(bad_user)


def test_equipment_turbines_crud(client, auth_tokens):
    """Check full turbine catalog listing and CRUD operations."""
    headers = auth_tokens["headers"]

    # 1. List
    resp = client.get("/api/v1/equipment/turbines")
    assert resp.status_code == 200
    turbines = resp.json()
    assert len(turbines) >= 146

    # 2. Add
    new_t = {
        "manufacturer": "KASP-Test",
        "model": "KASP-T1000",
        "type": "Industrial",
        "iso_power_kw": 25000.0,
        "iso_heat_rate_kj_kwh": 9500.0,
        "max_pressure_ratio": 15.0,
        "min_flow_kgs": 5.0,
        "max_flow_kgs": 250.0,
    }
    resp_add = client.post("/api/v1/equipment/turbines", json=new_t, headers=headers)
    assert resp_add.status_code in (200, 400)  # 400 if already exists

    # Find created
    resp_list = client.get("/api/v1/equipment/turbines")
    created = [t for t in resp_list.json() if t["model"] == "KASP-T1000"]
    if created:
        t_id = created[0]["id"]
        # 3. Update
        resp_up = client.put(f"/api/v1/equipment/turbines/{t_id}", json={"iso_power_kw": 26000.0}, headers=headers)
        assert resp_up.status_code == 200

        # 4. Delete
        resp_del = client.delete(f"/api/v1/equipment/turbines/{t_id}", headers=headers)
        assert resp_del.status_code == 200


def test_calculation_design_and_charts(client):
    """Verify comprehensive design calculation endpoint and chart payload generation."""
    payload = {
        "project_name": "Test Web Projesi",
        "p_in": 20.0,
        "p_in_unit": "bar(a)",
        "p_out": 60.0,
        "p_out_unit": "bar(a)",
        "t_in": 25.0,
        "t_in_unit": "°C",
        "flow": 15.0,
        "flow_unit": "kg/s",
        "gas_comp": {"METHANE": 90.0, "ETHANE": 10.0},
        "poly_eff": 82.0,
        "num_stages": 2,
        "intercooler_t": 35.0,
        "eos_model": "coolprop",
        "calc_method": "Metot 1: Ortalama Özellikler",
        "theme": "light",
    }
    resp = client.post("/api/v1/calculations/design", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "results" in data
    assert "selected_units" in data
    assert len(data["selected_units"]) > 0
    assert "charts" in data
    charts = data["charts"]
    assert "ts_diagram" in charts
    assert "pv_diagram" in charts
    assert "hs_mollier" in charts
    assert "power_sankey" in charts
    assert "kz_path" in charts
    assert "stage_overview" in charts
    assert "turbine_radar" in charts
    assert "architecture_svg" in charts
    assert "<svg" in charts["architecture_svg"]


def test_in_memory_pdf_streaming(client, auth_tokens):
    """Verify in-memory PDF generation streaming directly via BytesIO."""
    headers = auth_tokens["headers"]

    calc_payload = {
        "p_in": 20.0,
        "p_in_unit": "bar(a)",
        "p_out": 50.0,
        "p_out_unit": "bar(a)",
        "t_in": 20.0,
        "t_in_unit": "°C",
        "flow": 10.0,
        "flow_unit": "kg/s",
        "gas_comp": {"METHANE": 100.0},
        "poly_eff": 80.0,
        "num_stages": 2,
        "eos_model": "coolprop",
        "calc_method": "Metot 1: Ortalama Özellikler",
    }
    calc_resp = client.post("/api/v1/calculations/design", json=calc_payload)
    assert calc_resp.status_code == 200
    calc_data = calc_resp.json()

    pdf_req = {
        "inputs": calc_data["inputs"],
        "results": calc_data["results"],
        "selected_units": calc_data["selected_units"],
        "modules": {
            "psv": {"results": {"Required_Area_sqin": 1.47, "Selected_Orifice_Letter": "K"}},
            "api5l": {"results": {"recommendation": {"nominal_size_in": "48\"", "required_thickness_mm": 20.32, "is_sufficient": True}}},
        },
        "station_data": {"station_summary": {"total_mass_flow_kgs": 10.0, "pressure_ratio": 2.5, "total_power_mw": 1.2}},
        "filename": "test_tasarim_raporu.pdf",
    }
    resp = client.post("/api/v1/reports/pdf", json=pdf_req, headers=headers)
    assert resp.status_code == 200
    assert resp.headers.get("content-type") == "application/pdf"
    content = resp.content
    assert len(content) > 50000  # Multi-page PDF with embedded charts
    assert content.startswith(b"%PDF-")


def test_project_history_and_kasp_export(client, auth_tokens):
    """Verify saving to calculation history and exporting .kasp project."""
    headers = auth_tokens["headers"]

    # 1. Save project
    modules = {"psv": {"results": {"Required_Area_sqin": 1.47}, "warnings": []}}
    station_data = {"station_summary": {"total_mass_flow_kgs": 12.0}}
    save_req = {
        "project_name": "KASP Entegrasyon Projesi",
        "calculation_type": "Design",
        "inputs": {"p_in": 15.0, "p_out": 45.0, "gas_comp": {"METHANE": 100.0}},
        "results": {"power_total_kw": 1250.0},
        "modules": modules,
        "station_data": station_data,
        "notes": "Otomatik entegrasyon testi notu",
    }
    resp_save = client.post("/api/v1/projects", json=save_req, headers=headers)
    assert resp_save.status_code == 200
    proj_id = resp_save.json()["id"]

    # 2. List projects
    resp_list = client.get("/api/v1/projects", headers=headers)
    assert resp_list.status_code == 200
    items = resp_list.json()
    saved = next(p for p in items if p["id"] == proj_id)
    # List responses are lightweight; full results come from the detail endpoint.
    assert saved["results"] is None
    detail_resp = client.get(f"/api/v1/projects/{proj_id}", headers=headers)
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["results"]["module_results"]["psv"]["results"]["Required_Area_sqin"] == 1.47
    assert detail["results"]["station_data"]["station_summary"]["total_mass_flow_kgs"] == 12.0

    # Opt-in legacy behaviour remains available for API consumers.
    full_list_resp = client.get("/api/v1/projects?include_results=true", headers=headers)
    assert full_list_resp.status_code == 200
    full_saved = next(p for p in full_list_resp.json() if p["id"] == proj_id)
    assert full_saved["results"]["module_results"]["psv"]["results"]["Required_Area_sqin"] == 1.47

    # 3. Export .kasp
    export_req = {
        "project_name": "KASP Entegrasyon Projesi",
        "inputs": save_req["inputs"],
        "results": save_req["results"],
        "modules": modules,
        "station_data": station_data,
    }
    resp_exp = client.post("/api/v1/projects/export-kasp", json=export_req, headers=headers)
    assert resp_exp.status_code == 200
    kasp_json = resp_exp.json()
    assert kasp_json["schema_version"] == "4.1"
    assert "timestamp" in kasp_json
    assert kasp_json["inputs"]["p_in"] == 15.0
    assert kasp_json["modules"]["psv"]["results"]["Required_Area_sqin"] == 1.47
    assert kasp_json["station_data"]["station_summary"]["total_mass_flow_kgs"] == 12.0

    # 3b. Import .kasp
    import io
    import json as _json

    file_bytes = _json.dumps(kasp_json).encode("utf-8")
    resp_imp = client.post(
        "/api/v1/projects/import-kasp",
        files={"file": ("entegrasyon.kasp", io.BytesIO(file_bytes), "application/json")},
        headers=headers,
    )
    assert resp_imp.status_code == 200
    imported = resp_imp.json()
    assert imported["modules"]["psv"]["results"]["Required_Area_sqin"] == 1.47
    assert imported["station_data"]["station_summary"]["total_mass_flow_kgs"] == 12.0

    # 4. Delete project
    resp_del = client.delete(f"/api/v1/projects/{proj_id}", headers=headers)
    assert resp_del.status_code == 200


def test_module_excel_and_json_exports(client, auth_tokens):
    headers = auth_tokens["headers"]
    modules = {"psv": {"results": {"Required_Area_sqin": 1.47}, "warnings": []}}
    station_data = {"station_summary": {"total_mass_flow_kgs": 12.0}}
    payload = {
        "inputs": {"project_name": "Modül Export Testi", "p_in": 20.0, "gas_comp": {"METHANE": 100.0}},
        "results": {"t_out": 84.4},
        "modules": modules,
        "station_data": station_data,
    }

    resp_xlsx = client.post("/api/v1/reports/modules-excel", json=payload, headers=headers)
    assert resp_xlsx.status_code == 200
    assert resp_xlsx.content[:2] == b"PK"
    assert "spreadsheetml" in resp_xlsx.headers.get("content-type", "")

    resp_json = client.post("/api/v1/projects/export-results-json", json=payload, headers=headers)
    assert resp_json.status_code == 200
    exported = resp_json.json()
    assert exported["modules"]["psv"]["results"]["Required_Area_sqin"] == 1.47
    assert exported["station_data"]["station_summary"]["total_mass_flow_kgs"] == 12.0


def test_shootout_job_lifecycle(client):
    """Verify asynchronous shootout job submission and status polling."""
    payload = {
        "inputs": {
            "p_in": 20.0,
            "p_in_unit": "bar(a)",
            "p_out": 50.0,
            "p_out_unit": "bar(a)",
            "t_in": 20.0,
            "t_in_unit": "°C",
            "flow": 8.0,
            "flow_unit": "kg/s",
            "gas_comp": {"METHANE": 100.0},
            "poly_eff": 80.0,
        },
        "eos_list": ["coolprop", "pr"],
        "method_list": ["Metot 1: Ortalama Özellikler"],
    }
    resp = client.post("/api/v1/jobs/shootout", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    job_id = data["job_id"]
    assert data["total_runs"] == 2

    # Poll status
    status_resp = client.get(f"/api/v1/jobs/{job_id}/status")
    assert status_resp.status_code == 200
    st = status_resp.json()
    assert st["status"] in ("queued", "running", "completed")


def test_system_logs(client):
    """Verify logs retrieval from memory ring buffer."""
    resp = client.get("/api/v1/logs?limit=50")
    assert resp.status_code == 200
    logs = resp.json()
    assert isinstance(logs, list)
