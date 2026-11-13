"""TDD contracts for Ergonomics Loop #1: stale-results awareness, sticky action bar,
accordion expand/collapse all, and global keyboard shortcuts.
"""

import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent


def test_project_store_tracks_stale_results_signature():
    store_text = (REPO_ROOT / "kasp" / "web" / "src" / "store" / "projectStore.js").read_text(encoding="utf-8")
    assert "computeInputsSignature" in store_text
    assert "isResultsStale" in store_text
    assert "lastCalculatedSignature" in store_text


def test_design_sidebar_sticky_footer_and_expand_collapse_all():
    sidebar_text = (REPO_ROOT / "kasp" / "web" / "src" / "components" / "designSidebar.js").read_text(encoding="utf-8")
    assert "btn-toggle-all-steps" in sidebar_text
    assert "position: sticky" in sidebar_text
    assert "isResultsStale" in sidebar_text
    assert "Ctrl+Enter" in sidebar_text or "⌘/Ctrl+Enter" in sidebar_text


def test_results_view_renders_stale_results_banner_with_recalculate():
    results_text = (REPO_ROOT / "kasp" / "web" / "src" / "components" / "resultsView.js").read_text(encoding="utf-8")
    assert "stale-results-banner" in results_text
    assert "btn-recalculate-stale" in results_text
    assert "proj.isResultsStale" in results_text


def test_main_js_global_keyboard_shortcuts_and_syntax():
    main_path = REPO_ROOT / "kasp" / "web" / "src" / "main.js"
    main_text = main_path.read_text(encoding="utf-8")
    assert "btn-run-calculation" in main_text
    assert "btn-save-project" in main_text
    assert "ctrlKey" in main_text and "metaKey" in main_text

    locales_text = (REPO_ROOT / "kasp" / "web" / "src" / "i18n" / "locales.js").read_text(encoding="utf-8")
    for key in ("stale_results_title", "stale_results_cta", "steps_expand_all", "steps_collapse_all"):
        assert locales_text.count(f"{key}:") >= 2, f"Missing TR/EN i18n key: {key}"

    node_bin = shutil.which("node")
    if node_bin:
        for rel in (
            "kasp/web/src/store/projectStore.js",
            "kasp/web/src/components/designSidebar.js",
            "kasp/web/src/components/resultsView.js",
            "kasp/web/src/main.js",
            "kasp/web/src/i18n/locales.js",
        ):
            proc = subprocess.run([node_bin, "--check", str(REPO_ROOT / rel)], capture_output=True, text=True)
            assert proc.returncode == 0, f"node --check failed for {rel}: {proc.stderr}"
