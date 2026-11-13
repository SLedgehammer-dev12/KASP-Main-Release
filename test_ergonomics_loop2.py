"""TDD contracts for Ergonomics Loop #2: Turbine Selection Table search,
OEM filter, sorting, show-all toggle, and accessible table container.
"""

import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent


def test_results_view_turbine_table_toolbar_and_accessibility():
    results_text = (REPO_ROOT / "kasp" / "web" / "src" / "components" / "resultsView.js").read_text(encoding="utf-8")
    for token in (
        "turbine-search-input",
        "turbine-oem-filter",
        "turbine-sort-select",
        "btn-turbine-show-all",
        "btn-turbine-clear-filters",
        "filterAndSortTurbines",
        'tabindex="0"',
        'role="region"',
        'scope="col"',
    ):
        assert token in results_text, f"Missing token in resultsView.js: {token}"


def test_locales_and_syntax_for_turbine_toolbar():
    locales_text = (REPO_ROOT / "kasp" / "web" / "src" / "i18n" / "locales.js").read_text(encoding="utf-8")
    for key in (
        "turbine_search_placeholder",
        "turbine_all_oems",
        "turbine_show_all",
        "turbine_show_top20",
    ):
        assert locales_text.count(f"{key}:") >= 2, f"Missing TR/EN i18n key: {key}"

    node_bin = shutil.which("node")
    if node_bin:
        for rel in (
            "kasp/web/src/components/resultsView.js",
            "kasp/web/src/i18n/locales.js",
        ):
            proc = subprocess.run([node_bin, "--check", str(REPO_ROOT / rel)], capture_output=True, text=True)
            assert proc.returncode == 0, f"node --check failed for {rel}: {proc.stderr}"
