import pytest
from kasp.services.chart_data_builder import (
    build_ts_chart_data,
    build_pv_chart_data,
    build_hs_chart_data,
    build_power_sankey_data,
    build_kz_path_data,
    build_stage_overview_data,
    build_all_chart_payloads,
)


def test_chart_builder_none_inputs_and_results():
    """Verify all chart builder functions handle None inputs and results gracefully."""
    ts = build_ts_chart_data(None, None)
    assert isinstance(ts, dict)
    assert "actual_path" in ts

    pv = build_pv_chart_data(None, None)
    assert isinstance(pv, dict)
    assert "polytropic_path" in pv

    hs = build_hs_chart_data(None, None)
    assert isinstance(hs, dict)
    assert "actual_path" in hs

    sankey = build_power_sankey_data(None, None)
    assert isinstance(sankey, dict)
    assert "nodes" in sankey

    kz = build_kz_path_data(None, None)
    assert isinstance(kz, dict)
    assert "prs" in kz

    stages = build_stage_overview_data(None, None)
    assert isinstance(stages, dict)
    assert "labels" in stages

    all_payloads = build_all_chart_payloads(None, None)
    assert isinstance(all_payloads, dict)
    assert "ts_diagram" in all_payloads
    assert "pv_diagram" in all_payloads


def test_pv_chart_zero_and_negative_pressure():
    """Verify build_pv_chart_data does not raise ZeroDivisionError on p_in <= 0 or p_out <= 0."""
    pv1 = build_pv_chart_data({"p_in": 0.0, "p_out": 0.0}, {})
    assert isinstance(pv1, dict)
    assert len(pv1["polytropic_path"]["p"]) > 0

    pv2 = build_pv_chart_data({"p_in": -5.0, "p_out": -1.0}, {})
    assert isinstance(pv2, dict)
    assert len(pv2["polytropic_path"]["p"]) > 0


def test_stage_overview_malformed_stages():
    """Verify build_stage_overview_data handles stages with None and string entries."""
    malformed_results = {
        "stages": [
            None,
            {},
            {"p_in": "invalid", "t_out": None, "power_gas_kw": "bad_kw"}
        ]
    }
    overview = build_stage_overview_data({}, malformed_results)
    assert isinstance(overview, dict)
    assert len(overview["labels"]) == 3
