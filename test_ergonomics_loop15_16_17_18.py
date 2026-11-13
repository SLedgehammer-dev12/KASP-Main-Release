"""Ergonomics Loops #15, #16, #17, #18 contract tests:
- Loop #15 (chartsView.js): #btn-charts-reset-zoom and #btn-charts-download-png
- Loop #16 (header.js + main.js): #btn-shortcuts-help and #shortcuts-help-overlay / '?' shortcut
- Loop #17 (projectModal.js): #project-history-search live filter
- Loop #18 (stationTab.js): #station-stale-banner and #btn-station-sync-recalc
- node --check passes on all modified JS modules
"""

from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent


def test_loops_15_16_17_18_ergonomics_contract():
    charts_src = (ROOT / "kasp/web/src/components/chartsView.js").read_text(encoding="utf-8")
    header_src = (ROOT / "kasp/web/src/components/header.js").read_text(encoding="utf-8")
    main_src = (ROOT / "kasp/web/src/main.js").read_text(encoding="utf-8")
    proj_modal_src = (ROOT / "kasp/web/src/components/projectModal.js").read_text(encoding="utf-8")
    station_src = (ROOT / "kasp/web/src/components/stationTab.js").read_text(encoding="utf-8")

    # Loop #15
    assert "btn-charts-reset-zoom" in charts_src
    assert "btn-charts-download-png" in charts_src

    # Loop #16
    assert "btn-shortcuts-help" in header_src
    assert "shortcuts-help-overlay" in main_src

    # Loop #17
    assert "project-history-search" in proj_modal_src

    # Loop #18
    assert "station-stale-banner" in station_src
    assert "btn-station-sync-recalc" in station_src

    for js_rel in (
        "kasp/web/src/components/chartsView.js",
        "kasp/web/src/components/header.js",
        "kasp/web/src/main.js",
        "kasp/web/src/components/projectModal.js",
        "kasp/web/src/components/stationTab.js",
    ):
        chk = subprocess.run(["node", "--check", str(ROOT / js_rel)], capture_output=True, text=True)
        assert chk.returncode == 0, f"node --check failed for {js_rel}: {chk.stderr}"
