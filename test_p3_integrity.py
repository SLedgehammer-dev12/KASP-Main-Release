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

