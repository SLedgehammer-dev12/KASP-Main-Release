"""Regression contract for selectable units in the 3D station parameter bar.

The station panel keeps canonical SI/IP values internally (kg/s, bar(a), °C)
and converts only at the display boundary, exactly like the design sidebar.
"""

from pathlib import Path


STATION_TAB = Path("kasp/web/src/components/stationTab.js")


def test_station_live_parameters_expose_design_style_unit_selectors():
    source = STATION_TAB.read_text(encoding="utf-8")

    for selector_id in (
        "select-param-flow-unit",
        "select-param-pin-unit",
        "select-param-pout-unit",
    ):
        assert f'id="{selector_id}"' in source, f"Eksik birim seçici: {selector_id}"

    for unit in ("kg/s", "Sm³/h", "Nm³/h", "kg/h", "MMSCFD", "MMSCMD"):
        assert f'"{unit}"' in source, f"Debi birimi eksik: {unit}"
    for unit in ("bar(a)", "bar(g)", "kPa", "psi"):
        assert f'"{unit}"' in source, f"Basınç birimi eksik: {unit}"


def test_station_pout_defaults_to_bar_gauge():
    source = STATION_TAB.read_text(encoding="utf-8")

    # Station panel defaults P_out to bar(g); a saved non-bar(a) unit still wins.
    assert "initialPoutUnit" in source
    assert 'projectPoutUnit !== "bar(a)"' in source
    assert ': "bar(g)"' in source


def test_station_api_payload_stays_in_canonical_units():
    source = STATION_TAB.read_text(encoding="utf-8")

    # Display units are converted back before the station model is called.
    assert 'flow_unit: "kg/s"' in source
    assert 'p_in_unit: "bar(a)"' in source
    assert 'p_out_unit: "bar(a)"' in source
    assert "stationFlowToKgs" in source
    assert "stationPressureToBarA" in source
