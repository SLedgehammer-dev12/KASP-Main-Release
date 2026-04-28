import sys
from types import SimpleNamespace

import pytest
from PyQt5.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

from kasp.ui.main_window import KaspMainWindow
from kasp.ui.design_results_workflow import DesignResultsPresenter


@pytest.fixture(scope="module")
def app():
    qt_app = QApplication.instance()
    if qt_app is None:
        qt_app = QApplication(sys.argv)
    return qt_app


def test_main_window_results_methods_delegate_to_presenters(app, monkeypatch):
    window = KaspMainWindow()
    calls = []

    try:
        monkeypatch.setattr(
            window.design_results_presenter,
            "apply_results",
            lambda results, selected_units: calls.append(("apply_results", results, selected_units)),
        )
        monkeypatch.setattr(
            window.design_results_presenter,
            "update_single_result_unit",
            lambda key, unit: calls.append(("update_single_result_unit", key, unit)),
        )
        monkeypatch.setattr(
            window.design_results_presenter,
            "populate_turbine_table",
            lambda selected_units: calls.append(("populate_turbine_table", selected_units)),
        )
        monkeypatch.setattr(
            window.design_results_presenter,
            "populate_detailed_tables",
            lambda results: calls.append(("populate_detailed_tables", results)),
        )
        monkeypatch.setattr(
            window.design_results_presenter,
            "refresh_current_graph",
            lambda: calls.append(("refresh_current_graph",)),
        )
        monkeypatch.setattr(
            window.design_results_presenter,
            "apply_selected_turbine_selection",
            lambda selected_rows, selected_units: calls.append(
                ("apply_selected_turbine_selection", selected_rows, selected_units)
            ),
        )
        monkeypatch.setattr(
            window.design_results_presenter,
            "serialize_selected_units",
            lambda selected_units: calls.append(("serialize_selected_units", selected_units)) or [{"unit": "GT"}],
        )
        monkeypatch.setattr(
            window.graph_workflow,
            "save_current_graph",
            lambda: calls.append(("save_current_graph",)),
        )

        window._update_results_ui({"compression_ratio": 1.5}, [])
        window._update_single_result_unit("power_unit_kw", "MW")
        window._populate_turbine_table([])
        window._populate_detailed_tables({"compression_ratio": 1.5})
        window.on_turbine_selection_changed()
        window.refresh_current_graph()
        window.save_current_graph()
        serialized_units = window._serialize_selected_units([{"unit": "GT"}])
    finally:
        window.close()

    assert ("apply_results", {"compression_ratio": 1.5}, []) in calls
    assert ("update_single_result_unit", "power_unit_kw", "MW") in calls
    assert ("populate_turbine_table", []) in calls
    assert ("populate_detailed_tables", {"compression_ratio": 1.5}) in calls
    assert any(call[0] == "apply_selected_turbine_selection" for call in calls)
    assert ("refresh_current_graph",) in calls
    assert ("save_current_graph",) in calls
    assert ("serialize_selected_units", [{"unit": "GT"}]) in calls
    assert serialized_units == [{"unit": "GT"}]


def test_refresh_current_graph_readds_canvas_and_draws(app):
    graph_widget = QWidget()
    graph_layout = QVBoxLayout(graph_widget)
    default_label = QLabel("default")
    graph_layout.addWidget(default_label)

    class DummyCanvas(QLabel):
        def __init__(self):
            super().__init__("canvas")
            self.drawn = False

        def draw_idle(self):
            self.drawn = True

    canvas = DummyCanvas()
    window = SimpleNamespace(
        graph_combo=SimpleNamespace(currentText=lambda: "T-s Diyagramı"),
        graph_layout=graph_layout,
        graph_widget=graph_widget,
        default_graph_label=default_label,
        last_design_results_raw={"ok": True},
    )
    presenter = DesignResultsPresenter(
        window,
        engine=None,
        graph_manager=SimpleNamespace(current_graphs={"ts_diagram": canvas}),
    )

    presenter.refresh_current_graph()

    assert graph_layout.indexOf(canvas) >= 0
    assert canvas.drawn is True
    assert default_label.isVisible() is False
