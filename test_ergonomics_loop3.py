"""TDD contracts for Ergonomics Loop #3: eliminate Plotly title/legend overlap
on Design & Charts tabs via a clean shared layout helper.
"""

import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent


def test_results_and_charts_views_prevent_plotly_title_legend_overlap():
    results_text = (REPO_ROOT / "kasp" / "web" / "src" / "components" / "resultsView.js").read_text(encoding="utf-8")
    charts_text = (REPO_ROOT / "kasp" / "web" / "src" / "components" / "chartsView.js").read_text(encoding="utf-8")

    assert "buildResultsPlotlyLayout" in results_text
    assert "title: undefined" in results_text
    assert "yanchor: \"bottom\"" in results_text

    assert "title: undefined" in charts_text
    assert "margin:" in charts_text

    node_bin = shutil.which("node")
    if node_bin:
        for rel in (
            "kasp/web/src/components/resultsView.js",
            "kasp/web/src/components/chartsView.js",
        ):
            proc = subprocess.run([node_bin, "--check", str(REPO_ROOT / rel)], capture_output=True, text=True)
            assert proc.returncode == 0, f"node --check failed for {rel}: {proc.stderr}"
