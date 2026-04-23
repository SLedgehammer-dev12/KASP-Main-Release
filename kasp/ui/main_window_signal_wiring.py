"""Signal wiring helpers for the KASP main window."""

from __future__ import annotations


def coerce_slider_text_value(text, minimum, maximum, *, scale=10):
    try:
        value = float(text)
    except (TypeError, ValueError):
        return minimum / scale
    return max(minimum / scale, min(maximum / scale, value))


def format_slider_text(slider_value, *, scale=10):
    return f"{slider_value / scale:.1f}"


class MainWindowSignalController:
    def __init__(self, window):
        self.window = window

    def _sync_slider_from_edit(self, edit, slider):
        clamped_value = coerce_slider_text_value(edit.text(), slider.minimum(), slider.maximum())
        slider.setValue(int(clamped_value * 10))
        edit.setText(f"{clamped_value:.1f}")

    def _sync_edit_from_slider(self, edit, slider_value):
        edit.setText(format_slider_text(slider_value))

    def connect_signals(self):
        window = self.window

        window.poly_eff_slider.valueChanged.connect(
            lambda value: self._sync_edit_from_slider(window.poly_eff_edit, value)
        )
        window.therm_eff_slider.valueChanged.connect(
            lambda value: self._sync_edit_from_slider(window.therm_eff_edit, value)
        )
        window.mech_eff_slider.valueChanged.connect(
            lambda value: self._sync_edit_from_slider(window.mech_eff_edit, value)
        )

        window.poly_eff_edit.editingFinished.connect(
            lambda: self._sync_slider_from_edit(window.poly_eff_edit, window.poly_eff_slider)
        )
        window.therm_eff_edit.editingFinished.connect(
            lambda: self._sync_slider_from_edit(window.therm_eff_edit, window.therm_eff_slider)
        )
        window.mech_eff_edit.editingFinished.connect(
            lambda: self._sync_slider_from_edit(window.mech_eff_edit, window.mech_eff_slider)
        )

        window.calculate_btn.clicked.connect(window.run_calculation)
        window.stop_btn.clicked.connect(window.stop_calculation)
        window.add_component_btn.clicked.connect(window.add_component_row)
        window.remove_component_btn.clicked.connect(window.remove_component_row)
        window.normalize_btn.clicked.connect(window.normalize_composition)
        window.refresh_graph_btn.clicked.connect(window.refresh_current_graph)
        window.save_graph_btn.clicked.connect(window.save_current_graph)

        window.composition_table.itemChanged.connect(window._update_composition_total_label)
        window.composition_table.model().rowsInserted.connect(window._update_composition_total_label)
        window.composition_table.model().rowsRemoved.connect(window._update_composition_total_label)
        window.graph_combo.currentTextChanged.connect(window.refresh_current_graph)

        window.turbine_table.itemSelectionChanged.connect(window.on_turbine_selection_changed)

        window.generate_report_btn.clicked.connect(window.handle_design_report)
        window.export_results_btn.clicked.connect(window.export_results)
