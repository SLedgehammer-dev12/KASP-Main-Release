import numpy as np
import pytest
from PyQt5.QtWidgets import QApplication

_app = QApplication.instance() or QApplication([])

from kasp.core.thermo import ThermoEngine
from kasp.utils.graphs import GraphGenerator

@pytest.fixture
def graph_gen():
    engine = ThermoEngine()
    return GraphGenerator(engine)

def test_pv_diagram_with_array_head_kj_kg(graph_gen):
    inputs = {
        "p_in": 2.0,
        "p_in_unit": "bar",
        "p_out": 6.0,
        "p_out_unit": "bar",
        "t_in": 25.0,
        "t_in_unit": "°C",
        "poly_eff": 82.0,
    }
    composition = {"methane": 1.0}
    eos = "pr"

    # Multi-stage array
    results_array = {
        "t_out": 95.0,
        "head_kj_kg": np.array([75.0, 85.0]),
    }
    canvas1 = graph_gen.create_pv_diagram(inputs, results_array, composition, eos)
    assert canvas1 is not None, "create_pv_diagram should succeed with numpy array head_kj_kg"

    # List
    results_list = {
        "t_out": 95.0,
        "head_kj_kg": [75.0, 85.0],
    }
    canvas2 = graph_gen.create_pv_diagram(inputs, results_list, composition, eos)
    assert canvas2 is not None, "create_pv_diagram should succeed with list head_kj_kg"

    # 1D single-element array
    results_1d = {
        "t_out": 95.0,
        "head_kj_kg": np.array([160.0]),
    }
    canvas3 = graph_gen.create_pv_diagram(inputs, results_1d, composition, eos)
    assert canvas3 is not None, "create_pv_diagram should succeed with 1D single-element array"

    # None
    results_none = {
        "t_out": 95.0,
        "head_kj_kg": None,
    }
    canvas4 = graph_gen.create_pv_diagram(inputs, results_none, composition, eos)
    assert canvas4 is not None, "create_pv_diagram should succeed with None head_kj_kg"

def test_ts_diagram_robustness(graph_gen):
    inputs = {
        "p_in": "2.0",
        "p_in_unit": "bar",
        "p_out": "6.0",
        "p_out_unit": "bar",
        "t_in": "25.0",
        "t_in_unit": "°C",
        "poly_eff": "82.0",
    }
    composition = {"methane": 1.0}
    eos = "pr"
    results = {
        "t_out": "95.0",
        "head_kj_kg": "160.0",
    }
    canvas = graph_gen.create_ts_diagram(inputs, results, composition, eos)
    assert canvas is not None, "create_ts_diagram should succeed with string numeric inputs"
