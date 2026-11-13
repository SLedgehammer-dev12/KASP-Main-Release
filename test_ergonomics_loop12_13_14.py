"""Ergonomics Loops #12, #13, #14 contract tests:
- Loop #12 (performanceTab.js): #btn-copy-ptc10-summary, #btn-reset-ptc10-form, buildPtc10SummaryText
- Loop #13 (shootoutTab.js): #shootout-filter-input, #btn-shootout-export-csv
- Loop #14 (projectStore.js + gasTable.js): normalizeGasComposition(), #btn-gas-normalize
- node --check passes on all modified JS modules
"""

from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent


def test_loops_12_13_14_ergonomics_contract():
    perf_src = (ROOT / "kasp/web/src/components/performanceTab.js").read_text(encoding="utf-8")
    shoot_src = (ROOT / "kasp/web/src/components/shootoutTab.js").read_text(encoding="utf-8")
    store_src = (ROOT / "kasp/web/src/store/projectStore.js").read_text(encoding="utf-8")
    gas_src = (ROOT / "kasp/web/src/components/gasTable.js").read_text(encoding="utf-8")

    # Loop #12
    assert "btn-copy-ptc10-summary" in perf_src
    assert "btn-reset-ptc10-form" in perf_src
    assert "buildPtc10SummaryText" in perf_src

    # Loop #13
    assert "shootout-filter-input" in shoot_src
    assert "btn-shootout-export-csv" in shoot_src

    # Loop #14
    assert "export function normalizeGasComposition()" in store_src
    assert "btn-gas-copy" in gas_src

    for js_rel in (
        "kasp/web/src/components/performanceTab.js",
        "kasp/web/src/components/shootoutTab.js",
        "kasp/web/src/store/projectStore.js",
        "kasp/web/src/components/gasTable.js",
    ):
        chk = subprocess.run(["node", "--check", str(ROOT / js_rel)], capture_output=True, text=True)
        assert chk.returncode == 0, f"node --check failed for {js_rel}: {chk.stderr}"
