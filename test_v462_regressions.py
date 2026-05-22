import sys
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout

import pytest
from PyQt5.QtWidgets import QApplication

from kasp.core.thermo import ThermoEngine
from kasp.ui.main_window import KaspMainWindow


@pytest.fixture(scope="module")
def app():
    qt_app = QApplication.instance()
    if qt_app is None:
        qt_app = QApplication(sys.argv)
    return qt_app


def test_eos_combo_exposes_all_supported_methods(app):
    window = KaspMainWindow()
    try:
        labels = [
            window.eos_method_combo.itemText(index)
            for index in range(window.eos_method_combo.count())
        ]
    finally:
        window.close()

    assert any("CoolProp" in label for label in labels)
    thermo_available = pytest.importorskip("thermo", reason="PR/SRK options require thermo package")
    assert thermo_available is not None
    assert any("Peng-Robinson" in label for label in labels)
    assert any("SRK" in label for label in labels)


def test_design_calculation_returns_without_hanging():
    engine = ThermoEngine()
    inputs = {
        "p_in": 49.65,
        "p_in_unit": "bar(g)",
        "t_in": 19.0,
        "t_in_unit": "°C",
        "p_out": 75.0,
        "p_out_unit": "bar(a)",
        "flow": 1985000.0,
        "flow_unit": "Sm³/h",
        "num_units": 1,
        "gas_comp": {
            "METHANE": 85.0,
            "ETHANE": 4.9928,
            "PROPANE": 2.0019,
            "BUTANE": 0.5672,
            "ISOBUTANE": 0.2225,
            "ISOPENTANE": 0.0169,
            "PENTANE": 0.0104,
            "CARBONDIOXIDE": 1.1641,
            "NITROGEN": 4.6635,
            "HEXANE": 0.0285,
        },
        "eos_method": "coolprop",
        "method": "Metot 1: Ortalama Özellikler",
        "poly_eff": 90.0,
        "therm_eff": 35.0,
        "mech_eff": 98.0,
        "use_consistency_iteration": False,
        "method_max_iter": 25,
    }

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(engine.calculate_design_performance, inputs)
        try:
            results = future.result(timeout=20)
        except FutureTimeout as exc:
            raise AssertionError("Design calculation entered an unexpected long-running loop.") from exc

    assert results["t_out"] > inputs["t_in"]
    assert results["power_shaft_total_kw"] > 0
