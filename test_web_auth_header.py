"""Web arayüzü kimlik doğrulama kablolaması için statik regresyon testleri.

Korumalı uç noktalar (`/api/calculate/*`) Bearer token gerektirir; arayüzün
`Authorization` başlığını göndermesi ve token'ı kullanıcıdan alması gerekir.
"""

from pathlib import Path

WEB_INDEX = Path(__file__).parent / "kasp" / "web" / "index.html"


def _html() -> str:
    return WEB_INDEX.read_text(encoding="utf-8")


def test_web_ui_sends_bearer_authorization_header():
    html = _html()
    assert "Authorization" in html
    assert "Bearer" in html
    # Token kullanıcıdan alınmalı ve kalıcı saklanmalı
    assert "apiToken" in html
    assert "localStorage.getItem('kasp_api_token')" in html
    assert "localStorage.setItem('kasp_api_token'" in html


def test_protected_fetches_use_auth_headers():
    html = _html()
    # İki korumalı POST da yardımcı başlık üreticisini kullanmalı
    assert html.count("headers: authHeaders()") >= 2
    assert "/api/calculate/design" in html
    assert "/api/calculate/benchmark" in html


def test_web_ui_handles_unauthorized_response():
    html = _html()
    # 401/403 durumu kullanıcıya bildirilmeli
    assert "response.status === 401" in html
    assert "Token gerekli" in html
