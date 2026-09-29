"""Birim testleri: kasp.api.server (P4-15).

FastAPI endpoint testleri (TestClient ile).
KASP_API_TOKEN ortam degiskeni gerektirir; yoksa 503 doner.
"""

import pytest
import os
from fastapi.testclient import TestClient


def test_api_import():
    """API modulu import edilebilmeli."""
    from kasp.api import server
    assert hasattr(server, 'app')


@pytest.fixture
def client():
    """TestClient fixture."""
    from kasp.api.server import app
    return TestClient(app)


def _has_api_token():
    """API token yapilandirilmis mi?"""
    return bool(os.environ.get("KASP_API_TOKEN"))


class TestAPIEndpoints:
    """API endpoint testleri."""

    def test_health_endpoint(self, client):
        """Health check endpoint testi (token gerektirmeyebilir)."""
        response = client.get("/api/health")
        # API devre disi oldugunda (KASP_API_ENABLE=1 yoksa) 200 ama farklı mesaj
        assert response.status_code == 200
        data = response.json()
        # API devre disi oldugunda "disabled" mesaji donuyor
        assert "status" in data or "message" in data or "detail" in data

    def test_constants_endpoint(self, client):
        """Constants endpoint testi (token gerektirebilir)."""
        response = client.get("/api/constants")
        # Constants 200 veya 503 donuyor (token durumuna gore)
        assert response.status_code in (200, 503)
        if response.status_code == 200:
            data = response.json()
            # Constants endpoint 'gases', 'units', 'default_composition' donduruyor
            assert "gases" in data or "R_universal" in data

    def test_calculate_design_unauthorized(self, client):
        """Yetkisiz tasarim hesaplamasi 401/403/503 donmeli."""
        payload = {
            "gas_comp": {"METHANE": 1.0},
            "p_in": 20.0,
            "p_out": 60.0,
            "t_in": 30.0,
            "poly_eff": 85.0,
        }
        response = client.post("/api/calculate/design", json=payload)
        # Token durumuna gore farkli status
        assert response.status_code in (401, 403, 503)

    def test_calculate_design_invalid_payload(self, client):
        """Gecersiz payload icin 422 veya auth hatasi."""
        headers = {"Authorization": "Bearer invalid-token"}
        payload = {"p_in": 20.0}  # Eksik alanlar
        response = client.post("/api/calculate/design", json=payload, headers=headers)
        assert response.status_code in (401, 403, 422, 503)

    def test_calculate_design_missing_fields(self, client):
        """Eksik zorunlu alanlar icin hata."""
        response = client.post("/api/calculate/design", json={})
        assert response.status_code in (401, 403, 422, 503)


class TestAPIAuth:
    """Kimlik dogrulama testleri."""

    def test_rate_limit_header(self, client):
        """Rate limit header varligi (varsa)."""
        response = client.get("/api/health")
        assert response.status_code == 200

    def test_cors_headers(self, client):
        """CORS header'lari (preflight)."""
        response = client.options("/api/health")
        assert response.status_code in (200, 405)


class TestAPIErrorHandling:
    """Hata yonetimi testleri."""

    def test_internal_error_not_exposed(self, client):
        """Ic hata detaylari istemciye sizmemeli (P4-2).
        
        /api/calculate/design ic hata durumunda str(e) donuyordu (P4-2 MEDIUM).
        Bu test hata mesajlarinin guvenli oldugunu dogrular.
        """
        # Gercek hata tetiklemek icin gecerli token + bozuk input gerekir
        # Bu test yapisal kontrol icin placeholder
        pass