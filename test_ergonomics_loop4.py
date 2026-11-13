"""TDD contracts for Ergonomics Loop #4: unsaved changes indicator in header,
projectStore dirty tracking, and beforeunload tab-close protection.
"""

import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent


def test_unsaved_changes_tracking_header_indicator_and_beforeunload():
    store_text = (REPO_ROOT / "kasp" / "web" / "src" / "store" / "projectStore.js").read_text(encoding="utf-8")
    header_text = (REPO_ROOT / "kasp" / "web" / "src" / "components" / "header.js").read_text(encoding="utf-8")
    main_text = (REPO_ROOT / "kasp" / "web" / "src" / "main.js").read_text(encoding="utf-8")
    locales_text = (REPO_ROOT / "kasp" / "web" / "src" / "i18n" / "locales.js").read_text(encoding="utf-8")

    assert "hasUnsavedChanges" in store_text
    assert "markProjectSaved" in store_text

    assert "unsaved-indicator" in header_text
    assert "markProjectSaved" in header_text

    assert "beforeunload" in main_text
    assert "hasUnsavedChanges" in main_text

    assert locales_text.count("unsaved_changes:") >= 2

    node_bin = shutil.which("node")
    if node_bin:
        for rel in (
            "kasp/web/src/store/projectStore.js",
            "kasp/web/src/components/header.js",
            "kasp/web/src/main.js",
            "kasp/web/src/i18n/locales.js",
        ):
            proc = subprocess.run([node_bin, "--check", str(REPO_ROOT / rel)], capture_output=True, text=True)
            assert proc.returncode == 0, f"node --check failed for {rel}: {proc.stderr}"
