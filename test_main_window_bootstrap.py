from types import SimpleNamespace

from kasp.ui.main_window_bootstrap import build_gas_component_maps, initialize_window_state


def test_build_gas_component_maps_exposes_expected_lookup_pairs():
    gas_map, common_display, reverse_map = build_gas_component_maps()

    assert gas_map["METHANE"] == "Methane (CH₄)"
    assert gas_map["AIR"] == "Air"
    assert reverse_map["Nitrogen (N₂)"] == "NITROGEN"
    assert common_display == sorted(common_display)


def test_initialize_window_state_resets_cached_runtime_attributes():
    window = SimpleNamespace(
        last_design_inputs={"old": True},
        last_design_results_raw={"old": True},
        last_selected_units=[1],
        last_perf_inputs={"old": True},
        last_perf_results={"old": True},
        last_report_data={"old": True},
        worker_thread=object(),
        worker=object(),
    )

    initialize_window_state(window)

    assert window.last_design_inputs is None
    assert window.last_design_results_raw is None
    assert window.last_selected_units is None
    assert window.last_perf_inputs is None
    assert window.last_perf_results is None
    assert window.last_report_data == {}
    assert window.worker_thread is None
    assert window.worker is None
