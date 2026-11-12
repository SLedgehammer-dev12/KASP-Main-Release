"""TDD Regression Suite for Konu #2: ASME PTC-10 Performance Coupling & PDF Contract."""

import io
import pytest

from kasp.core.thermo import ThermoEngine
from kasp.services.calculation_service import execute_design_calculation
from kasp.services.performance_service import (
    evaluate_field_performance,
    evaluate_ptc10_performance,
)
from kasp.utils.reporting import REPORTLAB_LOADED, ReportGenerator


@pytest.fixture(scope="module")
def shared_engine():
    return ThermoEngine()


def test_volumetric_and_actual_flow_units_use_real_eos_density(shared_engine):
    """Sm³/h, MMSCFD, MMSCMD ve m³/h birimleri 1:1 kg/s sayılmaz; gerçek EOS yoğunluğu kullanılır."""
    base_field = {
        "p_in": 30.0,
        "p_in_unit": "bar(a)",
        "p_out": 75.0,
        "p_out_unit": "bar(a)",
        "t_in": 25.0,
        "t_in_unit": "°C",
        "t_out": 115.0,
        "t_out_unit": "°C",
        "flow": 180000.0,
        "flow_unit": "Sm³/h",
        "eos_model": "pr",
    }

    res_ch4 = evaluate_field_performance(
        {**base_field, "gas_comp": {"METHANE": 100.0}},
        engine=shared_engine,
    )
    res_co2 = evaluate_field_performance(
        {**base_field, "gas_comp": {"CARBONDIOXIDE": 95.0, "METHANE": 5.0}},
        engine=shared_engine,
    )

    # 180,000 Sm³/h CH4 ~ 33.9 kg/s (shaft power ~ 3-6 MW, asla GW mertebesinde değil!)
    assert 25.0 < res_ch4["flow_kgs"] < 45.0
    assert 1000.0 < res_ch4["shaft_power_kw"] < 15000.0

    # CO2 karışımı (~42.85 g/mol) aynı Sm³/h debide >2.4x daha yüksek kütlesel debi üretmelidir
    assert res_co2["flow_kgs"] > res_ch4["flow_kgs"] * 2.3

    # Gerçek emiş hacimsel debisi (m³/h = ACMH) P_in, T_in gerçek yoğunluğu ile çevrilir
    res_acmh = evaluate_field_performance(
        {
            **base_field,
            "gas_comp": {"METHANE": 100.0},
            "flow": 3600.0,
            "flow_unit": "m³/h",
        },
        engine=shared_engine,
    )
    # 30 bar(a), 25°C CH4 rho_in ~ 20-23 kg/m³ -> 3600 m³/h = 1 m³/s -> ~20-23 kg/s
    assert 18.0 < res_acmh["flow_kgs"] < 26.0


def test_default_driver_mode_uses_turbine_efficiency_without_bogus_1kgh_fuel(shared_engine):
    """Varsayılan PTC-10 değerlendirmesi 1.0 kg/h sabit yakıt yerine turb_eff kullanır."""
    field_data = {
        "p_in": 25.0,
        "p_in_unit": "bar(a)",
        "p_out": 65.0,
        "p_out_unit": "bar(a)",
        "t_in": 25.0,
        "t_in_unit": "°C",
        "t_out": 112.0,
        "t_out_unit": "°C",
        "flow": 20.0,
        "flow_unit": "kg/s",
        "gas_comp": {"METHANE": 92.0, "ETHANE": 8.0},
        "eos_model": "pr",
        "therm_eff": 36.0,
    }
    res = evaluate_ptc10_performance(field_data, engine=shared_engine)

    assert res["fuel_cons_kg_h"] > 100.0
    assert res["turb_eff"] == pytest.approx(36.0, rel=1e-2)
    assert res["actual_heat_rate"] > 8000.0
    assert not any("türbin verimi fiziksel sınırlar dışında" in w.lower() for w in res.get("warnings", []))

    # Ölçülü saha yakıt debisi (fuel_flow_kgh) verildiğinde gerçek ölçülü yakıt moduna geçer
    measured_fuel = res["fuel_cons_kg_h"] * 1.08
    res_measured = evaluate_ptc10_performance(
        {**field_data, "fuel_flow_kgh": measured_fuel},
        engine=shared_engine,
    )
    assert res_measured["fuel_cons_kg_h"] == pytest.approx(measured_fuel, rel=1e-4)
    assert res_measured["turb_eff"] < 36.0


def test_eos_model_and_unit_normalized_design_comparison(shared_engine):
    """eos_model iletilir ve farklı saha birimleri (bar(g), kg/h) tasarım noktasıyla ortak birimde kıyaslanır."""
    design_inputs = {
        "p_in": 25.0,
        "p_in_unit": "bar(a)",
        "p_out": 60.0,
        "p_out_unit": "bar(a)",
        "t_in": 25.0,
        "t_in_unit": "°C",
        "flow": 15.0,
        "flow_unit": "kg/s",
        "gas_comp": {"METHANE": 85.0, "ETHANE": 10.0, "PROPANE": 5.0},
        "poly_eff": 80.0,
        "mech_eff": 98.0,
        "therm_eff": 35.0,
        "num_stages": 1,
        "eos_model": "pr",
        "calc_method": "Metot 6: Schultz 3-Üslü Gerçek Gaz",
    }
    design_res = execute_design_calculation(design_inputs, engine=shared_engine)

    # Aynı fiziksel noktayı bar(g) ve kg/h cinsinden saha verisi olarak verelim
    field_same_point = {
        "p_in": 25.0 - 1.01325,
        "p_in_unit": "bar(g)",
        "p_out": 60.0 - 1.01325,
        "p_out_unit": "bar(g)",
        "t_in": 25.0,
        "t_in_unit": "°C",
        "t_out": design_res["t_out_c"],
        "t_out_unit": "°C",
        "flow": 15.0 * 3600.0,
        "flow_unit": "kg/h",
        "gas_comp": design_inputs["gas_comp"],
        "eos_model": "pr",
        "mech_eff": 98.0,
        "therm_eff": 35.0,
    }
    perf_same = evaluate_field_performance(field_same_point, design_res, engine=shared_engine)

    assert len(perf_same["comparison"]) == 6
    by_name = {row["parameter"]: row for row in perf_same["comparison"]}
    assert abs(by_name["Giriş Basıncı"]["deviation_pct"]) < 0.2
    assert abs(by_name["Çıkış Basıncı"]["deviation_pct"]) < 0.2
    assert abs(by_name["Gaz Debisi"]["deviation_pct"]) < 0.2
    assert abs(by_name["Mil Gücü"]["deviation_pct"]) < 1.5
    assert by_name["Giriş Basıncı"]["status"] == "OK"
    assert by_name["Gaz Debisi"]["status"] == "OK"

    # eos_model farkı (PR vs SRK, ayrıca 'rk' -> 'srk' güvenli alias eşlemesi) gerçek termodinamik fark üretmelidir
    perf_srk = evaluate_field_performance(
        {**field_same_point, "eos_model": "srk"},
        design_res,
        engine=shared_engine,
    )
    perf_rk_alias = evaluate_field_performance(
        {**field_same_point, "eos_model": "rk"},
        design_res,
        engine=shared_engine,
    )
    assert perf_srk["eos_model"] == "srk"
    assert perf_rk_alias["eos_model"] == "srk"
    assert perf_same["eos_model"] == "pr"
    assert perf_srk["poly_head_kj_kg"] != pytest.approx(perf_same["poly_head_kj_kg"], rel=1e-4)


@pytest.mark.skipif(not REPORTLAB_LOADED, reason="ReportLab yüklü değil")
def test_performance_report_contract_populates_deviations_and_builds_pdf(shared_engine):
    """Bozulmuş saha performansında reporting.py sapma alanları != 0 olur ve geçerli PDF üretilir."""
    design_inputs = {
        "p_in": 30.0,
        "p_in_unit": "bar(a)",
        "p_out": 75.0,
        "p_out_unit": "bar(a)",
        "t_in": 25.0,
        "t_in_unit": "°C",
        "flow": 20.0,
        "flow_unit": "kg/s",
        "gas_comp": {"METHANE": 90.0, "ETHANE": 10.0},
        "poly_eff": 82.0,
        "mech_eff": 98.0,
        "therm_eff": 35.0,
        "num_stages": 1,
        "eos_model": "pr",
        "calc_method": "Metot 6: Schultz 3-Üslü Gerçek Gaz",
    }
    design_res = execute_design_calculation(design_inputs, engine=shared_engine)

    # Çıkış sıcaklığını tasarımın +25°C üzerine çıkar -> verim düşer, mil gücü artar (>%5 KRİTİK sapma)
    degraded_field = {
        "project_name": "PTC10 Test İstasyonu",
        "p_in": 30.0,
        "p_in_unit": "bar(a)",
        "p_out": 75.0,
        "p_out_unit": "bar(a)",
        "t_in": 25.0,
        "t_in_unit": "°C",
        "t_out": design_res["t_out_c"] + 25.0,
        "t_out_unit": "°C",
        "flow": 20.0,
        "flow_unit": "kg/s",
        "gas_comp": design_inputs["gas_comp"],
        "eos_model": "pr",
        "mech_eff": 98.0,
        "therm_eff": 35.0,
    }
    perf_deg = evaluate_field_performance(degraded_field, design_res, engine=shared_engine)

    expected_design_poly_pct = (
        design_res["actual_poly_efficiency"] * 100.0
        if design_res["actual_poly_efficiency"] <= 1.0
        else design_res["actual_poly_efficiency"]
    )
    assert perf_deg["design_poly_eff"] == pytest.approx(expected_design_poly_pct, rel=1e-2)
    assert perf_deg["deviation_poly_eff"] < -5.0
    assert perf_deg["deviation_power"] > 5.0
    assert perf_deg["performance_status"]["status"] in {"KRİTİK", "KRITIK", "DİKKAT", "DIKKAT"}

    buf = io.BytesIO()
    gen = ReportGenerator(buf, shared_engine)
    assert gen.generate_performance_report(degraded_field, perf_deg) is True
    pdf_bytes = buf.getvalue()
    assert pdf_bytes.startswith(b"%PDF-")
    assert len(pdf_bytes) > 1500


def test_api_v1_performance_endpoint_and_pdf_streaming():
    """POST /api/v1/calculations/performance (test_data= uyumu + 422 doğrulama) ve /reports/performance-pdf testi."""
    from fastapi.testclient import TestClient
    from kasp.api.server import app

    client = TestClient(app)

    # 1. Geçersiz sıfır debi -> HTTP 500 traceback yerine HTTP 422 döner
    bad_resp = client.post(
        "/api/v1/calculations/performance",
        json={
            "field_data": {
                "p_in": 25.0,
                "p_in_unit": "bar(a)",
                "p_out": 60.0,
                "p_out_unit": "bar(a)",
                "t_in": 25.0,
                "t_in_unit": "°C",
                "t_out": 105.0,
                "t_out_unit": "°C",
                "flow": 0.0,
                "flow_unit": "kg/s",
                "gas_comp": {"METHANE": 100.0},
            }
        },
    )
    assert bad_resp.status_code == 422

    # 2. Geçerli saha testi -> HTTP 200 ve tam ASME PTC-10 çıktısı
    good_field = {
        "project_name": "API PTC10 Testi",
        "p_in": 25.0,
        "p_in_unit": "bar(a)",
        "p_out": 65.0,
        "p_out_unit": "bar(a)",
        "t_in": 24.0,
        "t_in_unit": "°C",
        "t_out": 115.0,
        "t_out_unit": "°C",
        "flow": 180000.0,
        "flow_unit": "Sm³/h",
        "gas_comp": {"METHANE": 92.0, "ETHANE": 8.0},
        "eos_model": "pr",
        "therm_eff": 35.0,
    }
    resp = client.post(
        "/api/v1/calculations/performance",
        json={"field_data": good_field, "design_point": None},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["comparison"]) == 6
    assert body["fuel_cons_kg_h"] > 50.0
    assert "performance_status" in body

    if REPORTLAB_LOADED:
        pdf_resp = client.post(
            "/api/v1/reports/performance-pdf",
            json={"inputs": good_field, "results": body, "filename": "ptc10_test.pdf"},
        )
        assert pdf_resp.status_code == 200
        assert pdf_resp.headers["content-type"] == "application/pdf"
        assert pdf_resp.content.startswith(b"%PDF-")


def test_multistage_section_by_section_ptc10_stage_index(shared_engine):
    """Çok kademeli ara soğutuculu tasarımda stage_index=0 adyabatik Kademe 1 kesitini 2. Yasa ihlali olmadan doğrular."""
    design_inputs = {
        "p_in": 20.0,
        "p_in_unit": "bar(a)",
        "p_out": 60.0,
        "p_out_unit": "bar(a)",
        "t_in": 25.0,
        "t_in_unit": "°C",
        "flow": 12.0,
        "flow_unit": "kg/s",
        "gas_comp": {"METHANE": 90.0, "ETHANE": 10.0},
        "poly_eff": 80.0,
        "mech_eff": 98.0,
        "therm_eff": 35.0,
        "num_stages": 2,
        "intercooler_t": 35.0,
        "eos_model": "pr",
        "calc_method": "Metot 6: Schultz 3-Üslü Gerçek Gaz",
    }
    design_res = execute_design_calculation(design_inputs, engine=shared_engine)
    stg0 = design_res["stages"][0]

    field_stg0 = {
        "p_in": stg0["p_in_bar"],
        "p_in_unit": "bar(a)",
        "p_out": stg0["p_out_bar"],
        "p_out_unit": "bar(a)",
        "t_in": stg0["t_in_c"],
        "t_in_unit": "°C",
        "t_out": stg0["t_out_c"],
        "t_out_unit": "°C",
        "flow": 12.0,
        "flow_unit": "kg/s",
        "gas_comp": design_inputs["gas_comp"],
        "eos_model": "pr",
        "mech_eff": 98.0,
        "therm_eff": 35.0,
        "stage_index": 0,
    }
    perf_stg0 = evaluate_field_performance(field_stg0, design_res, engine=shared_engine)
    assert 70.0 < perf_stg0["poly_eff"] < 90.0
    assert not any("fiziksel sınırlar dışında" in w.lower() for w in perf_stg0.get("warnings", []))
    assert abs(perf_stg0["deviation_poly_eff"]) < 1.5
    assert abs(perf_stg0["deviation_power"]) < 2.0
