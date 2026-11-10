"""
Unit and integration tests for embedded ASME B36.10M / API 5L Natural Gas Flow Calc engine.
Tests core hydraulic calculations, Barlow thickness formula, API RP 14E erosion limits,
station network pipe sizing (15 lines), and FastAPI /api/v1/calculations/pipe-sizing endpoint.
"""

import pytest
from fastapi.testclient import TestClient
from kasp.core.pipe_sizing import (
    ASME_B36_10M_DATA,
    PIPE_MATERIALS,
    size_single_pipe,
    calculate_pipe_weight_api5l,
    calculate_erosion_velocity,
    get_sorted_pipes,
    nd_sort_key,
)
from kasp.services.pipe_sizing_service import PipeSizingService
from kasp.api.server import app

client = TestClient(app)


def test_asme_catalog_integrity():
    """Verify that ASME B36.10M catalog contains all standard pipeline sizes from 1/8\" to 80\"."""
    assert len(ASME_B36_10M_DATA) >= 40
    assert '48' in ASME_B36_10M_DATA
    assert '30' in ASME_B36_10M_DATA
    assert '16' in ASME_B36_10M_DATA
    assert ASME_B36_10M_DATA['48']["OD_mm"] == pytest.approx(1219.2, 0.1)


def test_barlow_thickness_and_pipe_selection():
    """Verify Barlow's formula and selection for mainline suction line."""
    result = size_single_pipe(
        flow_kgs=120.0,
        p_bar=45.0,
        t_c=15.0,
        p_design_bar=75.0,
        material="API 5L X70",
        design_factor_F=0.50,
        preferred_nominal="48",
    )
    assert result["nominal_size_in"] == '48"'
    assert result["od_mm"] == pytest.approx(1219.2, 0.1)
    assert result["wall_thickness_mm"] >= result["min_required_thickness_mm"]
    assert result["actual_velocity_ms"] < 15.0
    assert result["erosion_ratio_pct"] < 80.0
    assert "Optimum" in result["velocity_status"]


def test_api_rp_14e_erosion_velocity():
    """Verify API RP 14E erosion limit calculation."""
    rho = 35.0  # kg/m3
    v_e = calculate_erosion_velocity(rho, C_empirical=122.0)
    expected = 122.0 / (35.0 ** 0.5)
    assert v_e == pytest.approx(expected, 0.01)


def test_station_network_15_lines_sizing():
    """Verify that PipeSizingService sizes all 15 process lines with accurate physics."""
    res = PipeSizingService.size_station_network(
        mass_flow_kgs=120.0,
        p_in_bar=45.0,
        p_out_bar=75.0,
        t_in_c=15.0,
        t_discharge_c=82.0,
        t_cooled_c=45.0,
        comp_op_count=4,
        cyclone_op_count=3,
        filter_op_count=3,
        cooler_bays_count=6,
        pipe_material="API 5L X70",
        design_factor_F=0.50,
    )
    assert res["success"] is True
    lines = res["lines"]
    assert len(lines) == 15
    for key, line in lines.items():
        assert "tag" in line
        assert line["od_mm"] > 0
        assert line["wall_thickness_mm"] > 0
        assert line["actual_velocity_ms"] > 0
        assert "velocity_status" in line


def test_station_headers_equal_nominal_size():
    """Suction and discharge station headers must share one commercial NPS."""
    for mass_flow, comp_count in ((12.0, 1), (36.0, 3), (120.0, 4)):
        res = PipeSizingService.size_station_network(
            mass_flow_kgs=mass_flow,
            p_in_bar=20.0,
            p_out_bar=60.0,
            t_in_c=25.0,
            t_discharge_c=84.4,
            t_cooled_c=45.0,
            comp_op_count=comp_count,
            cyclone_op_count=max(1, comp_count),
            filter_op_count=max(1, comp_count),
            cooler_bays_count=max(2, comp_count + 1),
            gas_mw=18.27,
            pipe_material="API 5L X70",
            design_factor_F=0.50,
        )
        suction = res["lines"]["suction_header"]
        discharge = res["lines"]["discharge_header"]

        assert suction["nominal_key"] == discharge["nominal_key"]
        assert suction["od_mm"] == pytest.approx(discharge["od_mm"])
        assert suction["diameter_equalized_to"] == suction["nominal_size_in"]
        assert discharge["diameter_equalized_to"] == suction["nominal_size_in"]
        assert suction["header_pair"] == discharge["header_pair"] == "suction_discharge_common_nps"
        assert discharge["actual_velocity_ms"] <= discharge["max_design_velocity_ms"]
        assert suction["actual_velocity_ms"] <= suction["max_design_velocity_ms"]


def test_compressor_and_cooler_lines_are_sized_by_flow():
    """Compressor nozzles, ASV and cooler branches must follow their own flow."""
    res = PipeSizingService.size_station_network(
        mass_flow_kgs=120.0,
        p_in_bar=20.0,
        p_out_bar=60.0,
        t_in_c=25.0,
        t_discharge_c=84.4,
        t_cooled_c=45.0,
        comp_op_count=4,
        cyclone_op_count=4,
        filter_op_count=4,
        cooler_bays_count=6,
        gas_mw=18.27,
        pipe_material="API 5L X70",
        design_factor_F=0.50,
    )
    lines = res["lines"]

    assert lines["comp_suction_branch"]["flow_kgs"] == pytest.approx(30.0)
    assert lines["comp_discharge_branch"]["flow_kgs"] == pytest.approx(30.0)
    assert lines["anti_surge_loop"]["flow_kgs"] == pytest.approx(30.0 * 0.68)
    assert lines["cooler_bay_risers"]["flow_kgs"] == pytest.approx(120.0 / 6)
    assert lines["cooler_bypass"]["flow_kgs"] == pytest.approx(120.0 * 0.35)
    assert lines["cooler_inlet"]["flow_kgs"] == pytest.approx(120.0)
    assert lines["cooler_outlet"]["flow_kgs"] == pytest.approx(120.0)

    # At equal flow, the 60 bar discharge branch needs a smaller NPS than the
    # 20 bar suction branch; the 68% ASV loop also stays below the branch size.
    assert nd_sort_key(lines["comp_discharge_branch"]["nominal_key"]) < nd_sort_key(
        lines["comp_suction_branch"]["nominal_key"]
    )
    assert nd_sort_key(lines["anti_surge_loop"]["nominal_key"]) <= nd_sort_key(
        lines["comp_suction_branch"]["nominal_key"]
    )
    assert nd_sort_key(lines["cooler_bypass"]["nominal_key"]) < nd_sort_key(
        lines["cooler_inlet"]["nominal_key"]
    )


def test_pipe_sizing_api_endpoint():
    """Verify POST /api/v1/calculations/pipe-sizing with various inputs."""
    payload = {
        "flow": 120.0,
        "flow_unit": "kg/s",
        "pressure_bar": 45.0,
        "temp_c": 15.0,
        "design_pressure_bar": 75.0,
        "pipe_material": "API 5L X70",
        "design_factor_F": 0.50,
        "max_velocity_ms": 15.0,
    }
    resp = client.post("/api/v1/calculations/pipe-sizing", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "nominal_size_in" in data
    assert "od_mm" in data
    assert "wall_thickness_mm" in data
    assert "actual_velocity_ms" in data
    assert "velocity_status" in data
