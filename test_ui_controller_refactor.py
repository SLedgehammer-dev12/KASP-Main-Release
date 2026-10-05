import os
import sys
from collections import Counter

import pytest
from PyQt5.QtWidgets import QApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("KASP_SKIP_CHANGELOG_DIALOG", "1")

from kasp.ui.main_window import KaspMainWindow
from kasp.ui.window_actions_workflow import build_examples_dialog_text


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


def test_examples_dialog_contains_actionable_scenarios():
    text = build_examples_dialog_text()

    assert "Dogal gaz kompresor tasarimi" in text
    assert "Saha performans degerlendirmesi" in text
    assert "ASME PTC 22" in text


def test_performance_tab_contains_site_correction_inputs(app):
    window = KaspMainWindow()
    try:
        for attr in [
            "perf_standard_combo",
            "perf_p1_unit_combo",
            "perf_t1_unit_combo",
            "perf_p2_unit_combo",
            "perf_t2_unit_combo",
            "perf_flow_unit_combo",
            "perf_ambient_temp_edit",
            "perf_ambient_temp_unit_combo",
            "perf_ambient_pressure_edit",
            "perf_ambient_pressure_unit_combo",
            "perf_humidity_edit",
            "perf_altitude_edit",
            "perf_inlet_loss_edit",
            "perf_inlet_loss_unit_combo",
            "perf_exhaust_loss_edit",
            "perf_exhaust_loss_unit_combo",
            "perf_manual_power_factor_edit",
            "perf_manual_heat_rate_factor_edit",
            "perf_res_corrected",
        ]:
            assert hasattr(window, attr)

        standards = [window.perf_standard_combo.itemText(i) for i in range(window.perf_standard_combo.count())]
        assert standards == ["ASME PTC 10", "ASME PTC 22", "ISO 2314"]
        assert "API 617" not in standards
        flow_units = [window.perf_flow_unit_combo.itemText(i) for i in range(window.perf_flow_unit_combo.count())]
        assert "kg/s" in flow_units
        assert "Sm³/h" in flow_units
    finally:
        window.close()


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


def test_main_window_close_event_with_running_thread(app, monkeypatch):
    """Verify closeEvent asks confirmation and ignores event if rejected, or cleans up threads if confirmed."""
    from PyQt5.QtGui import QCloseEvent
    from PyQt5.QtWidgets import QMessageBox

    window = KaspMainWindow()
    cleanup_calls = []

    monkeypatch.setattr(window, "_cleanup_worker_thread", lambda: cleanup_calls.append("worker"))
    monkeypatch.setattr(window, "_cleanup_shootout_thread", lambda: cleanup_calls.append("shootout"))

    class FakeRunningThread:
        def isRunning(self): return True
        def quit(self): pass
        def wait(self, *args): pass

    window.worker_thread = FakeRunningThread()

    # Case 1: User says NO to exit -> event ignored, no cleanup
    monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.No)
    event = QCloseEvent()
    window.closeEvent(event)
    assert not event.isAccepted()
    assert cleanup_calls == []

    # Case 2: User says YES to exit -> threads cleaned up, event accepted
    monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)
    event2 = QCloseEvent()
    window.closeEvent(event2)
    assert "worker" in cleanup_calls
    assert "shootout" in cleanup_calls
    assert event2.isAccepted()


def test_main_window_shootout_concurrent_guard(app, monkeypatch):
    """Verify _run_eos_shootout and _run_method_shootout reject concurrent execution when already running."""
    from PyQt5.QtWidgets import QMessageBox

    window = KaspMainWindow()
    window.last_design_inputs = {"p_in": 1.0}

    class FakeRunningThread:
        def isRunning(self): return True

    window._shootout_thread = FakeRunningThread()
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: warnings.append(args[1]))

    window._run_eos_shootout()
    assert len(warnings) == 1

    window._run_method_shootout()
    assert len(warnings) == 2


def test_populate_detailed_tables_with_minimal_results(app):
    """Verify populate_detailed_tables does not crash when results dictionary has missing keys."""
    window = KaspMainWindow()
    try:
        presenter = window.design_results_presenter
        # Minimal results dict with missing fuel, power, and thermo properties
        minimal_results = {
            "power_gas_per_unit_kw": 500.0,
            # 'inlet_properties', 'outlet_properties', 'lhv', 'hhv', 'fuel_total_kgh' omitted
        }
        presenter.populate_detailed_tables(minimal_results)

        # Check that tables were populated safely
        assert window.power_table.rowCount() == 4
        assert window.fuel_table.rowCount() == 3
        assert window.fuel_table.item(0, 1).text() == "-"
        assert window.fuel_table.item(1, 1).text() == "-"
        assert window.fuel_table.item(2, 1).text() == "-"
        assert window.thermo_table.rowCount() == 10
    finally:
        window.close()


def test_build_design_summary_text_with_empty_dictionaries():
    """Verify build_design_summary_text and build_consistency_info_html handle empty or partial dicts safely."""
    from kasp.ui.design_results_workflow import build_consistency_info_html, build_design_summary_text

    # None and empty tests
    assert build_consistency_info_html(None) is None
    assert build_consistency_info_html({}) is None

    # Partial consistency results
    partial_consistency = {
        "consistency_mode": True,
        "consistency_converged": True,
        # missing poly_eff_target, poly_eff_converged, actual_poly_efficiency, etc.
    }
    html = build_consistency_info_html(partial_consistency)
    assert html is not None
    assert "Tutarlı (Self-Consistent)" in html

    summary_text = build_design_summary_text({}, partial_consistency)
    assert "Tutarlı (Self-Consistent)" in summary_text
    assert "İsimsiz Proje" in summary_text



class _FakeLabel:
    def __init__(self):
        self.text = None

    def setText(self, value):
        self.text = value


class _FakeRadio:
    def __init__(self, checked):
        self._checked = checked

    def isChecked(self):
        return self._checked


def _make_fake_perf_window(turb_eff_checked):
    from types import SimpleNamespace

    names = (
        "perf_res_poly_eff", "perf_res_isen_eff", "perf_res_head", "perf_res_power_gas",
        "perf_res_power_shaft", "perf_res_corrected", "perf_res_fuel_lbl", "perf_res_fuel_or_eff",
    )
    window = SimpleNamespace(**{name: _FakeLabel() for name in names})
    window.radio_turb_eff = _FakeRadio(turb_eff_checked)
    return window


@pytest.mark.parametrize("turb_eff_checked", [True, False])
def test_performance_results_presenter_handles_partial_results(turb_eff_checked):
    """Eksik / None / NaN sonuclarda presenter cokmemeli, '—' gostermeli."""
    from kasp.ui.performance_workflow import PerformanceResultsPresenter

    window = _make_fake_perf_window(turb_eff_checked)
    presenter = PerformanceResultsPresenter(window)
    presenter.apply({"poly_eff": 81.234, "isen_eff": None, "gas_power_kw": float("nan")})

    assert window.perf_res_poly_eff.text == "%81.23"
    assert window.perf_res_isen_eff.text == "—"
    assert window.perf_res_head.text == "—"
    assert window.perf_res_power_gas.text == "—"
    assert window.perf_res_power_shaft.text == "Motor: — | Saft: —"
    assert window.perf_res_fuel_or_eff.text == "—"

    # None sonuc sozlugu da guvenli olmali
    presenter.apply(None)
    assert window.perf_res_poly_eff.text == "—"


def test_build_performance_report_inputs_with_missing_keys():
    """flow_kgs / p1_pa / p2_pa / site_correction_inputs eksikken KeyError olmamali."""
    from kasp.ui.performance_workflow import build_performance_report_inputs

    report = build_performance_report_inputs({}, {}, {})
    assert report["flow_kgs"] == 0.0
    assert report["p1_pa"] == 0.0
    assert report["p2_pa"] == 0.0
    assert report["site_correction_inputs"] == {}
    assert report["unit_name"] == "Performans Testi"

    report2 = build_performance_report_inputs(None, {"flow_kgs": "12.5", "site_correction_inputs": None}, None)
    assert report2["flow_kgs"] == 12.5
    assert report2["site_correction_inputs"] == {}
