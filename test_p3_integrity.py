"""P3 regression tests: reporting/UI integrity and uncertainty honesty."""

import math

import pytest


# ── P3-19: head unit Btu/lb + cache clearing + graph filename ────────────────

def test_head_btu_lb_conversion():
    from kasp.core.thermo_support import _convert_head_value

    btu = _convert_head_value(2.326, "kJ/kg", "Btu/lb")
    assert btu == pytest.approx(1.0, rel=1e-3)
    assert _convert_head_value(1.0, "Btu/lb", "kJ/kg") == pytest.approx(2.326, rel=1e-3)


def test_engine_clear_cache_exists_and_empties_cache():
    from kasp.core.thermo import ThermoEngine

    engine = ThermoEngine()
    engine.clear_cache()
    assert engine.thermo_solver.get_cache_stats()["size"] == 0


def test_graph_save_name_has_single_extension():
    from kasp.ui.graph_workflow import graph_save_default_name

    name = graph_save_default_name("My Project", "ts_diagram", "png")
    assert name.endswith(".png")
    assert not name.endswith(".png.png")


# ── P3-21: uncertainty honesty ───────────────────────────────────────────────

def test_uncertainty_marks_sensitivity_failures():
    from kasp.core.uncertainty import UncertaintyAnalyzer

    analyzer = UncertaintyAnalyzer()

    def calc(inputs):
        # Sadece temel noktada calisir; pertürbe edilmis noktalarda hata verir
        if abs(inputs["p_in"] - 10.0) > 1e-9:
            raise ValueError("perturbation failed")
        return {"polytropic_efficiency": 0.85}

    result = analyzer.analyze_uncertainty(
        {"p_in": 10.0, "p_out": 20.0, "t_in": 300.0, "flow": 5.0},
        {
            "p_in": "pressure_transducer_high",
            "p_out": "pressure_transducer_high",
            "t_in": "temperature_rtd_pt100",
            "flow": "flow_orifice",
        },
        calc,
        "polytropic_efficiency",
    )

    assert result["sensitivity_failures"]
    assert result["fully_compliant"] is False
    # %FS basinc olcumleri tam olcek bilinmeden varsayim olarak isaretlenir
    assert "p_in" in result["full_scale_assumptions"]


def test_uncertainty_payload_reports_non_compliance():
    from kasp.core.thermo_design_support import build_uncertainty_payload

    payload = build_uncertainty_payload(
        {
            "combined_uncertainty": 0.01,
            "expanded_uncertainty": 0.02,
            "breakdown_percent": {"p_in": 100.0},
            "sensitivity_failures": ["flow"],
            "full_scale_assumptions": ["p_in"],
            "model_uncertainty_included": False,
            "fully_compliant": False,
        },
        0.85,
    )
    assert payload["asme_ptc10_compliant"] is False
    assert payload["compliance_reasons"]


# ── P3-20: graph generation headless + wrap ──────────────────────────────────

def test_headless_canvas_factory_and_wrap():
    pytest.importorskip("PyQt5", reason="PyQt5 required")
    from PyQt5.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])

    import logging

    from kasp.utils import graphs

    graphs._render_ctx.headless = True
    try:
        headless = graphs._new_canvas(4, 3)
        assert isinstance(headless, graphs.HeadlessCanvas)
        assert headless.fig is not None
    finally:
        graphs._render_ctx.headless = False

    gm = graphs.GraphManager.__new__(graphs.GraphManager)
    gm.logger = logging.getLogger("test-graph-wrap")
    wrapped = gm.wrap_headless_graphs({"demo": headless})
    assert "demo" in wrapped
    assert isinstance(wrapped["demo"], graphs.MplCanvas)


def test_graph_generation_without_p_out_unit():
    """Verify diagrams render successfully even when p_out_unit is omitted from inputs."""
    pytest.importorskip("PyQt5", reason="PyQt5 required")
    from PyQt5.QtWidgets import QApplication
    _app = QApplication.instance() or QApplication([])

    from kasp.core.thermo import ThermoEngine
    from kasp.utils.graphs import GraphGenerator

    engine = ThermoEngine()
    gen = GraphGenerator(engine)
    inputs = {
        "p_in": 2.0,
        "p_in_unit": "bar",
        "p_out": 6.0,
        # p_out_unit intentionally omitted
        "t_in": 25.0,
        "t_in_unit": "°C",
        "poly_eff": 82.0,
    }
    results = {
        "t_out": 95.0,
        "head_kj_kg": 150.0,
    }
    composition = {"methane": 1.0}
    eos = "pr"

    ts_canvas = gen.create_ts_diagram(inputs, results, composition, eos)
    assert ts_canvas is not None

    pv_canvas = gen.create_pv_diagram(inputs, results, composition, eos)
    assert pv_canvas is not None

    hs_canvas = gen.create_hs_mollier_diagram(inputs, results, composition, eos)
    assert hs_canvas is not None

    kz_canvas = gen.create_kz_pressure_path(inputs, composition, eos)
    assert kz_canvas is not None


def test_unit_system_alias_and_case_tolerance():
    """Verify UnitSystem gracefully converts industrial aliases and case variations."""
    from kasp.core.units import UnitSystem

    # Pressure conversions
    assert UnitSystem.convert_pressure(200.0, "kpa", "bar") == pytest.approx(2.0, rel=1e-3)
    assert UnitSystem.convert_pressure(0.2, "mpa", "bar") == pytest.approx(2.0, rel=1e-3)
    assert UnitSystem.convert_pressure(2.0, "bar ", "bar") == pytest.approx(2.0, rel=1e-3)
    assert UnitSystem.convert_pressure(2.0, "barg", "Pa") == pytest.approx(301325.0, rel=1e-3)
    assert UnitSystem.convert_pressure(2.0, "bar_g", "Pa") == pytest.approx(301325.0, rel=1e-3)
    assert UnitSystem.convert_pressure(2.0, "kg/cm2", "Pa") == pytest.approx(196133.0, rel=1e-3)

    # Temperature conversions
    assert UnitSystem.convert_temperature(25.0, "degC", "K") == pytest.approx(298.15, rel=1e-3)
    assert UnitSystem.convert_temperature(25.0, "C", "K") == pytest.approx(298.15, rel=1e-3)
    assert UnitSystem.convert_temperature(25.0, " celsius ", "°C") == pytest.approx(25.0, rel=1e-3)
    assert UnitSystem.convert_temperature(77.0, "degF", "K") == pytest.approx(298.15, rel=1e-3)
    assert UnitSystem.convert_temperature(77.0, "F", "K") == pytest.approx(298.15, rel=1e-3)
    assert UnitSystem.convert_temperature(300.0, "k", "K") == pytest.approx(300.0, rel=1e-3)

    # Validation methods
    assert UnitSystem.validate_pressure_value(2.0, "barg") is True
    assert UnitSystem.validate_temperature_value(25.0, "degC") is True



