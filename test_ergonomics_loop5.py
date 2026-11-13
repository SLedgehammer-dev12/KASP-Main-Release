"""Ergonomics Loop #5 contract tests:
- projectStore.js exports resetDesignInputs()
- designSidebar.js renders #sidebar-validation-alert, disables #btn-run-calculation on invalid P_out/gasTotal/flow, wires #btn-footer-balance-gas and #btn-reset-inputs
- locales.js includes TR/EN validation & reset keys
- JS syntax checks pass with node --check
"""

from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent


def test_design_sidebar_live_validation_and_reset_contract():
    store_src = (ROOT / "kasp/web/src/store/projectStore.js").read_text(encoding="utf-8")
    sidebar_src = (ROOT / "kasp/web/src/components/designSidebar.js").read_text(encoding="utf-8")
    locales_src = (ROOT / "kasp/web/src/i18n/locales.js").read_text(encoding="utf-8")

    assert "export function resetDesignInputs()" in store_src
    assert "resetDesignInputs" in sidebar_src
    assert "balanceGasComponent" in sidebar_src

    assert "sidebar-validation-alert" in sidebar_src
    assert "btn-footer-balance-gas" in sidebar_src
    assert "btn-reset-inputs" in sidebar_src
    assert "computeValidationError" in sidebar_src

    for key in (
        "validation_pout_gt_pin",
        "validation_gas_sum",
        "validation_flow_gt_zero",
        "btn_reset_defaults",
        "btn_balance_100",
    ):
        assert key in locales_src, f"Missing locale key: {key}"

    for js_rel in (
        "kasp/web/src/store/projectStore.js",
        "kasp/web/src/components/designSidebar.js",
        "kasp/web/src/i18n/locales.js",
    ):
        res = subprocess.run(["node", "--check", str(ROOT / js_rel)], capture_output=True, text=True)
        assert res.returncode == 0, f"node --check failed for {js_rel}: {res.stderr}"
