import pytest
from kasp.services.chart_data_builder import build_turbine_radar_data, build_all_chart_payloads


def test_build_turbine_radar_data_none_surge_and_margins():
    """Verify build_turbine_radar_data handles units with None margins without TypeError."""
    units = [
        {
            "model": "Centaur 40",
            "power_margin_pct": None,
            "surge_margin_pct": None,
            "selection_score": None,
        },
        {
            "model": "Taurus 60",
            "power_margin_pct": "12.0",
            "surge_margin_pct": "14.5",
            "selection_score": "88.0",
        },
    ]
    radar = build_turbine_radar_data(units)
    assert "series" in radar
    assert len(radar["series"]) == 2
    assert len(radar["series"][0]["values"]) == 5
    assert all(isinstance(v, (int, float)) for v in radar["series"][0]["values"])
