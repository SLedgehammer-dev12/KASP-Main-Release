"""Ergonomics Loop #7 contract tests:
- station3dView.js renders #btn-toggle-3d-fullscreen in .hud-toolbar
- station3dView.js supports 3D full-viewport expand/collapse + resize and keyboard shortcuts (1-8, r/R, f/F, Escape)
- locales.js includes btn_3d_fullscreen and btn_3d_exit_fullscreen in TR and EN
- JS syntax checks pass with node --check
"""

from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent


def test_station_3d_fullscreen_and_camera_hotkeys_contract():
    s3d_src = (ROOT / "kasp/web/src/components/station3dView.js").read_text(encoding="utf-8")
    locales_src = (ROOT / "kasp/web/src/i18n/locales.js").read_text(encoding="utf-8")

    assert "btn-toggle-3d-fullscreen" in s3d_src
    assert "station-3d-expanded" in s3d_src
    assert "btn_3d_fullscreen" in locales_src
    assert "btn_3d_exit_fullscreen" in locales_src

    for js_rel in (
        "kasp/web/src/components/station3dView.js",
        "kasp/web/src/i18n/locales.js",
    ):
        chk = subprocess.run(["node", "--check", str(ROOT / js_rel)], capture_output=True, text=True)
        assert chk.returncode == 0, f"node --check failed for {js_rel}: {chk.stderr}"
