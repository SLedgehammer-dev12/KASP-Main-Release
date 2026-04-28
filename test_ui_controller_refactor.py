import os
import sys
from collections import Counter

import pytest
from PyQt5.QtWidgets import QApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("KASP_SKIP_CHANGELOG_DIALOG", "1")

from kasp.ui.main_window import KaspMainWindow


@pytest.fixture(scope="module")
def app():
    qt_app = QApplication.instance()
    if qt_app is None:
        qt_app = QApplication(sys.argv)
    return qt_app


def test_main_window_document_workflow_methods_delegate(app, monkeypatch):
    window = KaspMainWindow()
    calls = []

    try:
        monkeypatch.setattr(
            window.document_workflow,
            "handle_design_report",
            lambda: calls.append("handle_design_report"),
        )
        monkeypatch.setattr(
            window.document_workflow,
            "export_results",
            lambda: calls.append("export_results"),
        )
        monkeypatch.setattr(
            window.document_workflow,
            "save_project",
            lambda: calls.append("save_project"),
        )
        monkeypatch.setattr(
            window.document_workflow,
            "load_project",
            lambda: calls.append("load_project"),
        )
        monkeypatch.setattr(
            window.document_workflow,
            "new_project",
            lambda: calls.append("new_project"),
        )
        monkeypatch.setattr(
            window.document_workflow,
            "handle_performance_report",
            lambda: calls.append("handle_performance_report"),
        )

        window.handle_design_report()
        window.export_results()
        window.save_project()
        window.load_project()
        window.new_project()
        window.handle_performance_report()

        window.generate_report_btn.click()
        window.export_results_btn.click()
        window.save_project_btn.click()
    finally:
        window.close()

    counts = Counter(calls)
    assert counts["handle_design_report"] == 2
    assert counts["export_results"] == 2
    assert counts["save_project"] == 2
    assert counts["load_project"] == 1
    assert counts["new_project"] == 1
    assert counts["handle_performance_report"] == 1


def test_main_window_action_and_performance_methods_delegate(app, monkeypatch):
    window = KaspMainWindow()
    calls = []

    try:
        monkeypatch.setattr(
            window.window_actions,
            "open_library_manager",
            lambda: calls.append(("open_library_manager",)),
        )
        monkeypatch.setattr(
            window.window_actions,
            "clear_engine_cache",
            lambda: calls.append(("clear_engine_cache",)),
        )
        monkeypatch.setattr(
            window.window_actions,
            "show_about_dialog",
            lambda: calls.append(("show_about_dialog",)),
        )
        monkeypatch.setattr(
            window.window_actions,
            "show_examples",
            lambda: calls.append(("show_examples",)),
        )
        monkeypatch.setattr(
            window.window_actions,
            "clear_logs",
            lambda: calls.append(("clear_logs",)),
        )
        monkeypatch.setattr(
            window.window_actions,
            "append_log",
            lambda message: calls.append(("append_log", message)),
        )
        monkeypatch.setattr(
            window.window_actions,
            "filter_logs",
            lambda selected_level: calls.append(("filter_logs", selected_level)),
        )
        monkeypatch.setattr(
            window.performance_workflow,
            "run_evaluation",
            lambda: calls.append(("run_evaluation",)),
        )
        monkeypatch.setattr(
            window.performance_workflow,
            "toggle_driver_inputs",
            lambda: calls.append(("toggle_driver_inputs",)),
        )

        window.open_library_manager()
        window.clear_engine_cache()
        window.show_about_dialog()
        window.show_examples()
        window.clear_logs()
        window.append_log("[INFO] delegated")
        window._filter_logs("INFO")
        window.run_performance_evaluation()
        window._toggle_perf_driver_inputs()
    finally:
        window.close()

    assert ("open_library_manager",) in calls
    assert ("clear_engine_cache",) in calls
    assert ("show_about_dialog",) in calls
    assert ("show_examples",) in calls
    assert ("clear_logs",) in calls
    assert ("append_log", "[INFO] delegated") in calls
    assert ("filter_logs", "INFO") in calls
    assert ("run_evaluation",) in calls
    assert ("toggle_driver_inputs",) in calls


def test_main_window_gas_composition_methods_delegate(app, monkeypatch):
    window = KaspMainWindow()
    calls = []

    try:
        monkeypatch.setattr(
            window.gas_composition_workflow,
            "on_gas_selection_changed",
            lambda gas_name: calls.append(("on_gas_selection_changed", gas_name)),
        )
        monkeypatch.setattr(
            window.gas_composition_workflow,
            "load_standard_gas_composition",
            lambda gas_name: calls.append(("load_standard_gas_composition", gas_name)),
        )
        monkeypatch.setattr(
            window.gas_composition_workflow,
            "add_component_row",
            lambda: calls.append(("add_component_row",)),
        )
        monkeypatch.setattr(
            window.gas_composition_workflow,
            "remove_component_row",
            lambda: calls.append(("remove_component_row",)),
        )
        monkeypatch.setattr(
            window.gas_composition_workflow,
            "update_total_label",
            lambda *args: calls.append(("update_total_label", args)),
        )
        monkeypatch.setattr(
            window.gas_composition_workflow,
            "normalize_composition",
            lambda: calls.append(("normalize_composition",)),
        )
        monkeypatch.setattr(
            window.gas_composition_workflow,
            "get_gas_composition",
            lambda: {"METHANE": 100.0},
        )

        window.on_gas_selection_changed("Air")
        window.load_standard_gas_composition("Air")
        window.add_component_row()
        window.remove_component_row()
        window._update_composition_total_label()
        window.normalize_composition()
        gas_comp = window._get_gas_composition()

        window.add_component_btn.click()
        window.remove_component_btn.click()
        window.normalize_btn.click()
    finally:
        window.close()

    counts = Counter(call[0] for call in calls)
    assert counts["add_component_row"] == 2
    assert counts["remove_component_row"] == 2
    assert counts["normalize_composition"] == 2
    assert ("on_gas_selection_changed", "Air") in calls
    assert ("load_standard_gas_composition", "Air") in calls
    assert any(call[0] == "update_total_label" for call in calls)
    assert gas_comp == {"METHANE": 100.0}


def test_main_window_design_calculation_methods_delegate(app, monkeypatch):
    window = KaspMainWindow()
    calls = []

    try:
        monkeypatch.setattr(
            window.design_calculation_workflow,
            "run",
            lambda: calls.append(("run",)),
        )
        monkeypatch.setattr(
            window.design_calculation_workflow,
            "calculation_finished",
            lambda results, selected_units: calls.append(("calculation_finished", results, selected_units)),
        )
        monkeypatch.setattr(
            window.design_calculation_workflow,
            "calculation_error",
            lambda message: calls.append(("calculation_error", message)),
        )
        monkeypatch.setattr(
            window.design_calculation_workflow,
            "stop",
            lambda: calls.append(("stop",)),
        )
        monkeypatch.setattr(
            window.design_calculation_workflow,
            "update_progress_detailed",
            lambda percentage, message: calls.append(("update_progress_detailed", percentage, message)),
        )
        monkeypatch.setattr(
            window.design_calculation_workflow,
            "update_time_estimate",
            lambda seconds: calls.append(("update_time_estimate", seconds)),
        )
        monkeypatch.setattr(
            window.design_calculation_workflow,
            "calculation_cancelled",
            lambda: calls.append(("calculation_cancelled",)),
        )

        window.run_calculation()
        window.calculate_btn.click()
        window.calculation_finished({"power_unit_kw": 1.0}, [])
        window.calculation_error("boom")
        window.stop_calculation()
        window.stop_btn.setEnabled(True)
        window.stop_btn.click()
        window.update_progress_detailed(25, "step")
        window.update_time_estimate(12)
        window.calculation_cancelled()
    finally:
        window.close()

    counts = Counter(call[0] for call in calls)
    assert counts["run"] == 2
    assert ("calculation_finished", {"power_unit_kw": 1.0}, []) in calls
    assert ("calculation_error", "boom") in calls
    assert counts["stop"] == 2
    assert ("update_progress_detailed", 25, "step") in calls
    assert ("update_time_estimate", 12) in calls
    assert ("calculation_cancelled",) in calls


def test_main_window_design_input_binder_is_used(app, monkeypatch):
    window = KaspMainWindow()
    calls = []

    try:
        monkeypatch.setattr(
            window.design_input_binder,
            "collect",
            lambda: ({"project_name": "Delegated"}, 100.0),
        )
        monkeypatch.setattr(
            window.design_input_binder,
            "apply",
            lambda inputs: calls.append(("apply", inputs)) or {"project_name": "Applied"},
        )
        monkeypatch.setattr(
            window.gas_composition_workflow,
            "update_total_label",
            lambda *args: calls.append(("update_total_label", args)),
        )

        collected = window._get_design_inputs()
        applied = window._populate_ui_from_inputs({"project_name": "Delegated"})
    finally:
        window.close()

    assert collected == {"project_name": "Delegated"}
    assert applied == {"project_name": "Applied"}
    assert ("apply", {"project_name": "Delegated"}) in calls
    assert any(call[0] == "update_total_label" for call in calls)
