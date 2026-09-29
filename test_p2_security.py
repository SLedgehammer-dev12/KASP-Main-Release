"""P2 regression tests: permission enforcement, per-user lockout, recovery key, API hardening."""

import pytest
from fastapi import HTTPException

import kasp.security as sec
from kasp.security import Session


# ── P2-13: action-level authorization ────────────────────────────────────────

class _User:
    def __init__(self, username, role):
        self.username = username
        self.role = role


def test_authorize_allows_unauthenticated_dev_flow():
    Session._current_user = None
    Session._permission_manager = None
    assert Session.authorize("write") is True


def test_authorize_enforces_role_for_logged_in_user():
    Session.login(_User("basic", "user"))
    try:
        assert Session.authorize("read") is True
        assert Session.authorize("export") is True
        assert Session.authorize("write") is False
    finally:
        Session.logout()


def test_authorize_admin_can_write():
    Session.login(_User("root", "admin"))
    try:
        assert Session.authorize("write") is True
        assert Session.authorize("manage_users") is True
    finally:
        Session.logout()


# ── P2-14: per-user lockout isolation ────────────────────────────────────────

def test_lockout_is_per_user(monkeypatch, tmp_path):
    monkeypatch.setattr(sec, "_lockout_file", str(tmp_path / "lockout.json"))
    sec.reset_lockout_state()

    for _ in range(3):
        sec.record_attempt(success=False, username="alice")

    assert sec.check_lockout("alice")[0] is True
    # Bob must not be affected by Alice's failures
    assert sec.check_lockout("bob")[0] is False

    # Resetting Alice only must not touch Bob's state
    sec.reset_lockout_state("alice")
    assert sec.check_lockout("alice")[0] is False


# ── P2-15: API hardening ─────────────────────────────────────────────────────

def test_api_requires_bearer_token(monkeypatch):
    import kasp.api.server as srv

    monkeypatch.setattr(srv, "API_TOKEN", "s3cret")
    with pytest.raises(HTTPException) as no_header:
        srv.require_auth(None)
    assert no_header.value.status_code == 401

    with pytest.raises(HTTPException) as wrong:
        srv.require_auth("Bearer nope")
    assert wrong.value.status_code == 403

    assert srv.require_auth("Bearer s3cret") is None


def test_api_health_reports_real_coolprop_status():
    import asyncio
    import kasp.api.server as srv

    # API disabled by default
    assert srv.API_ENABLED is False
    health_payload = asyncio.run(srv.health())
    assert health_payload["status"] == "healthy"
    assert isinstance(health_payload["coolprop_loaded"], bool)

    constants_payload = asyncio.run(srv.get_constants())
    assert "gases" in constants_payload
    assert "units" in constants_payload
    assert "default_composition" in constants_payload


def test_strict_auth_and_sensitive_actions():
    Session.logout()
    try:
        # Unauthenticated sensitive actions must always be denied
        assert Session.authorize("manage_users") is False
        assert Session.authorize("delete") is False

        # Strict auth blocks unauthenticated write too
        Session.set_strict_auth(True)
        assert Session.authorize("write") is False
    finally:
        Session.logout()


def test_validate_file_path_blocks_traversal_and_unbounded_abs_path(tmp_path):
    from kasp.security import InputValidator

    assert InputValidator.validate_file_path("../secret.txt") is False
    assert InputValidator.validate_file_path("/etc/passwd") is False

    allowed_file = tmp_path / "project.kasp"
    assert InputValidator.validate_file_path(str(allowed_file), allowed_dir=str(tmp_path)) is True
    assert InputValidator.validate_file_path("/etc/passwd", allowed_dir=str(tmp_path)) is False


def test_api_rate_limit_and_sanitized_errors(monkeypatch):
    import asyncio
    import kasp.api.server as srv

    monkeypatch.setattr(srv, "RATE_LIMIT_PER_MIN", 2)
    srv._rate_buckets.clear()

    class _DummyClient:
        host = "127.0.0.1"

    class _DummyRequest:
        client = _DummyClient()

    req = _DummyRequest()
    srv.rate_limit(req)
    srv.rate_limit(req)
    with pytest.raises(HTTPException) as exc_info:
        srv.rate_limit(req)
    assert exc_info.value.status_code == 429

    # Verify sanitized error on invalid design calculation failure
    monkeypatch.setattr(
        srv.engine,
        "calculate_design_performance_with_mode",
        lambda _: (_ for _ in ()).throw(RuntimeError("internal secret path /var/data")),
    )
    valid_inputs = srv.DesignInputs(
        p_in=20.0,
        t_in=30.0,
        p_out=60.0,
        flow=10.0,
        gas_comp={"METHANE": 100.0},
        poly_eff=80.0,
    )
    with pytest.raises(HTTPException) as calc_err:
        asyncio.run(srv.calculate_design(valid_inputs))
    assert calc_err.value.status_code == 400
    assert "internal secret path" not in calc_err.value.detail

