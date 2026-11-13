"""Ergonomics Loops #9, #10, #11 contract tests (2D P&ID enhancements):
- Loop #9: #pid-zoom-badge, #select-2d-focus-equip (smooth focus on PIG-R/Siklon/Filtre/Kompresor/Cooler/PSV/PIG-L), and +/-/0 keyboard zoom shortcuts
- Loop #10: #btn-2d-toggle-tags (pid-hide-tags class) and de-overlapped 2D header labels
- Loop #11: #btn-2d-export-png (HiDPI 2x canvas rasterization to kasp_station_pid.png)
"""

from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent


def test_station_2d_loops_9_10_11_contract():
    st_src = (ROOT / "kasp/web/src/components/stationTab.js").read_text(encoding="utf-8")
    locales_src = (ROOT / "kasp/web/src/i18n/locales.js").read_text(encoding="utf-8")

    # Loop #9
    assert "pid-zoom-badge" in st_src
    assert "select-2d-focus-equip" in st_src
    assert "STATION_2D_FOCUS_ZONES" in st_src

    # Loop #10
    assert "btn-2d-toggle-tags" in st_src
    assert "pid-hide-tags" in st_src

    # Loop #11
    assert "btn-2d-export-png" in st_src
    assert "kasp_station_pid.png" in st_src

    for key in ("btn_2d_export_png", "btn_2d_tags", "select_2d_focus"):
        assert key in locales_src, f"Missing locale key: {key}"

    for js_rel in ("kasp/web/src/components/stationTab.js", "kasp/web/src/i18n/locales.js"):
        chk = subprocess.run(["node", "--check", str(ROOT / js_rel)], capture_output=True, text=True)
        assert chk.returncode == 0, f"node --check failed for {js_rel}: {chk.stderr}"
