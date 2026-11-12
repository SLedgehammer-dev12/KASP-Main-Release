"""Contract tests for the shared harness / skill layer.

The same files are read by OpenCode, Antigravity and ACP-compatible clients.
These tests keep the single-source promise honest: valid frontmatter, unique
feature IDs, a wired manifest and a runnable stdlib verification CLI.
"""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SKILLS_DIR = ROOT / ".agents" / "skills"
VERIFY_SCRIPT = SKILLS_DIR / "kasp-verify" / "scripts" / "kasp_verify.py"


def _load_verify_module():
    spec = importlib.util.spec_from_file_location("kasp_verify", VERIFY_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_skill_frontmatter_contract():
    verify = _load_verify_module()
    results = verify.lint_skills()

    assert results, "no skills discovered"
    invalid = [item for item in results if item["status"] != "ok"]
    assert invalid == [], f"invalid skills: {invalid}"

    names = {item["name"] for item in results}
    assert {
        "kasp-verify",
        "kasp-api-contracts",
        "kasp-frontend",
        "kasp-local-stack",
        "kasp-harness-interop",
    }.issubset(names)


def test_skills_are_portable():
    offenders = []
    for skill_file in SKILLS_DIR.glob("*/SKILL.md"):
        text = skill_file.read_text(encoding="utf-8")
        if "/Users/" in text or "C:\\Users\\" in text:
            offenders.append(str(skill_file.relative_to(ROOT)))
    assert offenders == [], f"skills contain absolute user paths: {offenders}"


def test_feature_registry_is_unique_and_complete():
    data = json.loads((SKILLS_DIR / "kasp-verify" / "references" / "features.json").read_text(encoding="utf-8"))
    ids = [item["id"] for item in data]
    assert len(ids) == len(set(ids))
    assert all(item.get("expected") and item.get("entrypoint") for item in data)
    assert any(item["area"] == "station-3d" for item in data)


def test_harness_manifest_wires_both_harnesses():
    manifest = json.loads((ROOT / ".agents" / "harness.json").read_text(encoding="utf-8"))

    assert manifest["skillRoot"] == ".agents/skills"
    assert manifest["harnesses"]["opencode"]["native"] is True
    assert manifest["harnesses"]["antigravity"]["native"] is True
    assert "opencode" in manifest["harnesses"]["openhands-acp"]["agentCommand"]

    opencode = json.loads((ROOT / ".opencode" / "opencode.json").read_text(encoding="utf-8"))
    assert ".agents/skills" in opencode["skills"]["paths"]


def test_root_agents_md_documents_the_contract():
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for needle in ("OpenCode", "Antigravity", "ACP", ".agents/skills", "kasp-verify"):
        assert needle in text, f"AGENTS.md missing {needle!r}"


def test_verify_cli_selftest_passes():
    result = subprocess.run(
        [sys.executable, str(VERIFY_SCRIPT), "selftest"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["checks"]
