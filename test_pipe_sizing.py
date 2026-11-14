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
    assert len(lines) == 21
    assert "cyclone_outlet_branch" in lines
    assert "filter_outlet_branch" in lines
    assert "unit_discharge_header" in lines
    assert "cooler_bay_inlet_header" in lines
    assert "cooler_bay_outlet_header" in lines
    assert "cooler_bay_outlet_risers" in lines
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
    assert lines["cooler_bay_inlet_header"]["flow_kgs"] == pytest.approx(120.0 / 6)
    assert lines["cooler_bay_outlet_header"]["flow_kgs"] == pytest.approx(120.0 / 6)
    assert lines["cooler_bay_outlet_risers"]["flow_kgs"] == pytest.approx(120.0 / 6)
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


def test_compressible_multisegment_hydraulic_engine_and_empirical_crosscheck():
    """Verify multi-segment compressible Darcy-Weisbach ΔP & Weymouth/Panhandle empirical cross-checks."""
    from kasp.core.station_piping_compliance import calculate_compressible_pipe_dp

    res_short = calculate_compressible_pipe_dp(
        mass_flow_kgs=120.0,
        p_in_bar=45.0,
        t_c=15.0,
        id_mm=660.4,
        equiv_length_m=120.0,
        gas_mw=18.2,
    )
    res_long = calculate_compressible_pipe_dp(
        mass_flow_kgs=120.0,
        p_in_bar=45.0,
        t_c=15.0,
        id_mm=660.4,
        equiv_length_m=1200.0,
        gas_mw=18.2,
    )
    assert res_short["method"] == "compressible_darcy_weisbach_20seg"
    assert res_short["dp_total_bar"] > 0.0
    assert res_long["dp_total_bar"] > res_short["dp_total_bar"] * 9.0
    assert res_long["velocity_out_ms"] > res_long["velocity_in_ms"]
    assert 0.0 < res_short["mach_max"] < 0.25
    assert res_short["choked"] is False
    emp = res_short["empirical_dp_bar"]
    assert emp["weymouth"] > 0.0
    assert emp["panhandle_a"] > 0.0
    assert emp["panhandle_b"] > 0.0


def test_spec_4500_piping_compliance_checks_dp_stress_and_acoustics():
    """Verify Spec 4-NGTL 0-CS-M-002-4500 §5.1 suction/discharge ΔP, B31.3/B31.8 stress & acoustic checks."""
    res_ok = PipeSizingService.size_station_network(
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
        dp_cyclone_bar=0.85,
        dp_filter_bar=0.75,
        dp_cooler_bar=0.40,
        suction_equiv_length_m=120.0,
        discharge_equiv_length_m=150.0,
    )
    comp = res_ok.get("spec_4500_compliance")
    assert isinstance(comp, dict)
    assert comp["spec_ref"] == "4-NGTL 0-CS-M-002-4500 §5.1"

    # Suction ΔP excludes MFS/CFS (which together exceed 1.5 bar here, while piping alone stays <= 1.0 bar)
    suct = comp["suction_piping"]
    assert suct["equiv_length_m"] == pytest.approx(120.0)
    assert suct["limit_bar"] == pytest.approx(1.0)
    assert suct["dp_piping_bar"] <= 1.0
    assert suct["dp_excluded_scrubber_bar"] == pytest.approx(1.60, 0.01)
    assert suct["compliant"] is True

    # Discharge ΔP excludes Gas Cooler (0.40 bar) and remains <= 0.5 bar at 150 m equiv length
    disch = comp["discharge_piping"]
    assert disch["equiv_length_m"] == pytest.approx(150.0)
    assert disch["limit_bar"] == pytest.approx(0.5)
    assert disch["dp_piping_bar"] <= 0.5
    assert disch["dp_excluded_cooler_bar"] == pytest.approx(0.40, 0.01)
    assert disch["compliant"] is True

    # Velocity <= 20 m/s, B31.3/B31.8 stress, and acoustic/pulsation sections present & compliant
    assert comp["velocity_check"]["limit_ms"] == pytest.approx(20.0)
    assert comp["velocity_check"]["compliant"] is True
    assert comp["stress_b313_b318"]["compliant"] is True
    assert comp["stress_b313_b318"]["b318_max_hoop_pct_smys"] <= 50.0
    assert comp["stress_b313_b318"]["b313_allowable_stress_mpa"] > 0.0
    assert comp["stress_b313_b318"]["recommended_support_span_m"] > 0.0
    assert comp["acoustic_pulsation"]["compliant"] is True
    assert comp["acoustic_pulsation"]["max_mach"] < 0.30
    assert comp["overall_compliant"] is True

    # Extreme equivalent pipe lengths must trigger Spec 4500 §5.1 ΔP non-compliance + warnings
    res_fail = PipeSizingService.size_station_network(
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
        dp_cyclone_bar=0.25,
        dp_filter_bar=0.20,
        dp_cooler_bar=0.40,
        suction_equiv_length_m=15000.0,
        discharge_equiv_length_m=12000.0,
    )
    comp_fail = res_fail["spec_4500_compliance"]
    assert comp_fail["suction_piping"]["dp_piping_bar"] > 1.0
    assert comp_fail["suction_piping"]["compliant"] is False
    assert comp_fail["discharge_piping"]["dp_piping_bar"] > 0.5
    assert comp_fail["discharge_piping"]["compliant"] is False
    assert comp_fail["overall_compliant"] is False
    assert any("1.0 bar" in w or "§5.1" in w for w in res_fail["warnings"])
    assert any("0.5 bar" in w or "§5.1" in w for w in res_fail["warnings"])
