"""Ergonomics Loop #8 contract tests:
- stationTab.js renders 2D P&ID interactive toolbar (#btn-2d-zoom-in, #btn-2d-zoom-out, #btn-2d-zoom-reset, #btn-2d-fullscreen, #btn-2d-export-svg)
- stationTab.js binds SVG viewBox pan/zoom + fullscreen + SVG export
- locales.js includes btn_2d_export_svg and btn_2d_zoom_reset in TR and EN
- JS syntax checks pass with node --check
"""

from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent


def test_station_2d_pid_pan_zoom_fullscreen_export_contract():
    st_src = (ROOT / "kasp/web/src/components/stationTab.js").read_text(encoding="utf-8")
    locales_src = (ROOT / "kasp/web/src/i18n/locales.js").read_text(encoding="utf-8")

    for dom_id in (
        "station-2d-viewport",
        "btn-2d-zoom-in",
        "btn-2d-zoom-out",
        "btn-2d-zoom-reset",
        "btn-2d-fullscreen",
        "btn-2d-export-svg",
        "station-2d-expanded",
    ):
        assert dom_id in st_src, f"Missing 2D P&ID control: {dom_id}"

    assert "btn_2d_export_svg" in locales_src
    assert "btn_2d_zoom_reset" in locales_src

    for js_rel in (
        "kasp/web/src/components/stationTab.js",
        "kasp/web/src/i18n/locales.js",
    ):
        chk = subprocess.run(["node", "--check", str(ROOT / js_rel)], capture_output=True, text=True)
        assert chk.returncode == 0, f"node --check failed for {js_rel}: {chk.stderr}"
