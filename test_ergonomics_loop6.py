"""Ergonomics Loop #6 contract tests:
- resultsView.js exports buildResultsSummaryText(proj)
- resultsView.js renders #btn-copy-results-summary next to #btn-goto-station-3d with clipboard copy + toast feedback
- locales.js includes btn_copy_summary and btn_copied_summary in TR and EN
- JS syntax checks pass with node --check
"""

from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent


def test_results_view_one_click_summary_copy_contract():
    results_src = (ROOT / "kasp/web/src/components/resultsView.js").read_text(encoding="utf-8")
    locales_src = (ROOT / "kasp/web/src/i18n/locales.js").read_text(encoding="utf-8")

    assert "export function buildResultsSummaryText(" in results_src
    assert "btn-copy-results-summary" in results_src
    assert "navigator.clipboard" in results_src
    assert "btn_copy_summary" in locales_src
    assert "btn_copied_summary" in locales_src

    # Verify buildResultsSummaryText works cleanly via node -e
    node_probe = r'''
globalThis.localStorage = { getItem: () => "", setItem: () => {}, removeItem: () => {} };
const { buildResultsSummaryText } = await import("./kasp/web/src/components/resultsView.js");
const text = buildResultsSummaryText({
  inputs: {
    project_name: "Adapazari CS",
    p_in: 49.65, p_in_unit: "bar(g)",
    p_out: 75, p_out_unit: "bar(a)",
    t_in: 19, t_in_unit: "°C",
    flow: 1985000, flow_unit: "Sm³/h",
    eos_model: "coolprop", calc_method: "Metot 6"
  },
  results: {
    pressure_ratio: 1.48,
    total_shaft_power_kw: 14250.5,
    polytropic_head_kj_kg: 52.3,
    t_out_c: 54.2,
    z_avg: 0.892
  },
  selectedUnits: [{ manufacturer: "Solar", model: "Titan 250", site_power_kw: 21500, power_margin_pct: 50.9 }]
});
if (!text.includes("Adapazari CS") || !text.includes("14250.5") || !text.includes("Titan 250")) {
  throw new Error("Summary text missing expected fields: " + text);
}
'''
    res = subprocess.run(["node", "--input-type=module", "-e", node_probe], cwd=str(ROOT), capture_output=True, text=True)
    assert res.returncode == 0, f"node summary probe failed: {res.stderr}"

    for js_rel in (
        "kasp/web/src/components/resultsView.js",
        "kasp/web/src/i18n/locales.js",
    ):
        chk = subprocess.run(["node", "--check", str(ROOT / js_rel)], capture_output=True, text=True)
        assert chk.returncode == 0, f"node --check failed for {js_rel}: {chk.stderr}"
