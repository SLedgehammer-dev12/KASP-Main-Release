"""P4 regression tests: updater platform handling, SSOT version, reentrant run tracking."""

import sys

import pytest


# ── P4-22: platform-aware asset selection ────────────────────────────────────

def test_pick_default_asset_is_platform_aware(monkeypatch):
    from kasp.utils import updater as up

    release = up.ReleaseInfo(
        tag_name="v9.9.9",
        name="v9.9.9",
        body="",
        html_url="",
        published_at="",
        prerelease=False,
        draft=False,
        assets=(
            up.ReleaseAsset("app-win.exe", "https://x/app.exe", 1, "application/octet-stream"),
            up.ReleaseAsset("app-mac.dmg", "https://x/app.dmg", 1, "application/octet-stream"),
        ),
    )

    monkeypatch.setattr(sys, "platform", "win32")
    assert up.pick_default_asset(release).name == "app-win.exe"

    monkeypatch.setattr(sys, "platform", "darwin")
    assert up.pick_default_asset(release).name == "app-mac.dmg"


# ── P4-24: SSOT engine version reflects 6 methods ────────────────────────────

def test_engine_version_reports_six_methods():
    from kasp.core.thermo_design_support import ENGINE_VERSION

    assert "6-Method" in ENGINE_VERSION


# ── P4-25: nested run tracking restores outer context ────────────────────────

def test_nested_run_tracking_preserves_outer_summary():
    from kasp.core.models import ThermodynamicState
    from kasp.core.properties import ThermodynamicSolver

    solver = ThermodynamicSolver()
    solver.begin_run_tracking("auto")          # outer
    solver.begin_run_tracking("auto")          # inner (e.g. uncertainty perturbation)
    solver.end_run_tracking()                   # inner completes

    state = ThermodynamicState(
        P=1e5, T=300.0, H=0.0, S=0.0, Z=1.0, k=1.4, MW=28.0,
        Cp=1000.0, Cv=700.0, density=1.0, phase="gas",
        raw_props={"fallback": True},
    )
    solver._record_run_tracking(1e5, 300.0, "pr", state)

    summary = solver.end_run_tracking()
    assert summary["fallback_used"] is True
    assert summary["fallback_call_count"] == 1
