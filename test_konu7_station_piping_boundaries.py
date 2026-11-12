"""
Konu #7 TDD Suite — Station Piping Naming, Hierarchy, Main-Header Continuity & 3D Battery-Limit Boundaries.

Verifies:
1. Station Suction Header (`L-102` + `L-105`) is a continuous equalized main-header spine
   from Inlet Pig Receiver (`PIG-R`) to the end of the Turbo-Compressor Suction Header.
2. Station Discharge Header (`L-109`) is a continuous equalized main-header spine
   from the start of the Turbo-Compressor Discharge Header to Outlet Pig Launcher (`PIG-L`).
3. Equipment piping (MFS `L-103`, CFS `L-104`, TC suction/discharge branches `L-106`/`L-107`,
   ASV/Recycle `L-108`/`L-110`, Gas Cooler `L-111`..`L-114`) connects to the main headers
   via explicit `parent_header` and `from_boundary -> to_boundary` battery limits.
4. `station3dView.js` & `stationTab.js` expose 3D pipe naming, boundary markers, direct pipe
   telemetry inspection, auditable `lineKey`/`fromBoundary`/`toBoundary` routes, and valid JS syntax.
"""

from pathlib import Path
import shutil
import subprocess
import pytest
from fastapi.testclient import TestClient

from kasp.api.server import app
from kasp.core.pipe_sizing import nd_sort_key
from kasp.services.pipe_sizing_service import PipeSizingService
from kasp.services.station_service import calculate_station_process_model

REPO_ROOT = Path(__file__).resolve().parent
client = TestClient(app)


def test_station_suction_and_discharge_main_headers_boundaries_and_continuity():
    """Station Suction Header (L-102 + L-105) and Station Discharge Header (L-109) share one main NPS and span PIG-R..TC and TC..PIG-L."""
    for mass_flow, comp_count in ((12.0, 1), (60.0, 3), (180.0, 4)):
        res = PipeSizingService.size_station_network(
            mass_flow_kgs=mass_flow,
            p_in_bar=30.0,
            p_out_bar=75.0,
            t_in_c=20.0,
            t_discharge_c=88.0,
            t_cooled_c=42.0,
            comp_op_count=comp_count,
            cyclone_op_count=max(1, comp_count),
            filter_op_count=max(1, comp_count),
            cooler_bays_count=max(2, comp_count + 1),
            dp_cyclone_bar=0.25,
            dp_filter_bar=0.20,
            dp_cooler_bar=0.40,
            gas_mw=18.2,
            pipe_material="API 5L X70",
            design_factor_F=0.50,
        )
        assert res["success"] is True
        arch = res.get("piping_architecture")
        assert isinstance(arch, dict)
        assert "station_suction_header" in arch["main_headers"]
        assert "station_discharge_header" in arch["main_headers"]
        assert len(arch.get("naming_limitations", [])) >= 3

        suct_arch = arch["main_headers"]["station_suction_header"]
        disch_arch = arch["main_headers"]["station_discharge_header"]
        assert "PIG-R" in suct_arch["from_boundary"]
        assert "TC" in suct_arch["to_boundary"] or "Kompresör" in suct_arch["to_boundary"]
        assert "TC" in disch_arch["from_boundary"] or "Kompresör" in disch_arch["from_boundary"]
        assert "PIG-L" in disch_arch["to_boundary"]

        lines = res["lines"]
        suct = lines["suction_header"]
        comp_suct = lines["comp_suction_header"]
        disch = lines["discharge_header"]

        # Main spine NPS & OD continuity across Suction Header (L-102 & L-105) and Discharge Header (L-109)
        assert suct["nominal_key"] == comp_suct["nominal_key"] == disch["nominal_key"]
        assert suct["od_mm"] == pytest.approx(comp_suct["od_mm"])
        assert suct["od_mm"] == pytest.approx(disch["od_mm"])
        assert suct["header_pair"] == comp_suct["header_pair"] == disch["header_pair"] == "suction_discharge_common_nps"

        # Pressure drop across MFS + CFS is preserved on L-105 even after common-NPS equalization
        assert comp_suct["pressure_bar"] == pytest.approx(30.0 - 0.25 - 0.20, abs=0.02)

        assert suct["hierarchy_level"] == "main_header"
        assert comp_suct["hierarchy_level"] == "main_header"
        assert disch["hierarchy_level"] == "main_header"
        assert suct["parent_header"] == "station_suction_header"
        assert comp_suct["parent_header"] == "station_suction_header"
        assert disch["parent_header"] == "station_discharge_header"

        # End-to-end boundary strings on main headers
        assert "PIG-R" in suct["from_boundary"]
        assert "TC" in comp_suct["to_boundary"] or "Kompresör" in comp_suct["to_boundary"]
        assert "TC" in disch["from_boundary"] or "Kompresör" in disch["from_boundary"]
        assert "PIG-L" in disch["to_boundary"]


def test_equipment_piping_connects_to_main_headers_with_explicit_boundaries():
    """All 15 lines carry explicit hierarchy, parent header, and start/end battery limits."""
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
    )
    lines = res["lines"]
    assert len(lines) == 15

    for key, line in lines.items():
        assert line.get("hierarchy_level"), f"{key} missing hierarchy_level"
        assert line.get("hierarchy_label"), f"{key} missing hierarchy_label"
        assert line.get("from_boundary"), f"{key} missing from_boundary"
        assert line.get("to_boundary"), f"{key} missing to_boundary"
        assert "➔" in line.get("boundary_summary", ""), f"{key} missing boundary_summary arrow"
        assert "parent_header" in line, f"{key} missing parent_header key"

    # Mainline transmission boundaries outside Pig Traps
    assert lines["mainline_inlet"]["hierarchy_level"] == "mainline_tie_in"
    assert "PIG-R" in lines["mainline_inlet"]["to_boundary"]
    assert lines["mainline_outlet"]["hierarchy_level"] == "mainline_tie_in"
    assert "PIG-L" in lines["mainline_outlet"]["from_boundary"]

    # Suction-side equipment connects to Station Suction Header
    for eq_key in ("cyclone_branch", "filter_branch", "comp_suction_branch"):
        assert lines[eq_key]["parent_header"] == "station_suction_header"
        assert lines[eq_key]["hierarchy_level"] == "equipment_branch"

    # Discharge-side equipment connects to Station Discharge Header
    for eq_key in ("comp_discharge_branch", "cooler_inlet", "cooler_bay_risers", "cooler_bypass", "cooler_outlet"):
        assert lines[eq_key]["parent_header"] == "station_discharge_header"
        assert lines[eq_key]["hierarchy_level"] in ("equipment_header", "equipment_branch")

    # Recycle & ASV bridge Discharge -> Suction protection/recirculation
    for rec_key in ("anti_surge_loop", "station_recycle"):
        assert lines[rec_key]["parent_header"] == "station_suction_and_discharge_headers"
        assert lines[rec_key]["hierarchy_level"] == "recycle_control"

    # Equipment branches remain smaller/equal to main headers per hydraulic flow split
    assert nd_sort_key(lines["comp_discharge_branch"]["nominal_key"]) <= nd_sort_key(
        lines["discharge_header"]["nominal_key"]
    )
    assert nd_sort_key(lines["cooler_bay_risers"]["nominal_key"]) < nd_sort_key(
        lines["discharge_header"]["nominal_key"]
    )


def test_station_api_returns_piping_architecture_and_line_boundaries():
    """FastAPI /api/v1/calculations/station exposes piping_architecture and per-line battery limits."""
    payload = {
        "inputs": {
            "flow": 90.0,
            "flow_unit": "kg/s",
            "p_in": 40.0,
            "p_in_unit": "bar(a)",
            "p_out": 72.0,
            "p_out_unit": "bar(a)",
            "t_in": 18.0,
        }
    }
    resp = client.post("/api/v1/calculations/station", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    piping = data["station_piping"]
    assert "piping_architecture" in piping
    assert piping["piping_architecture"]["main_headers"]["station_suction_header"]["nominal_size_in"] == (
        piping["lines"]["suction_header"]["nominal_size_in"]
    )
    assert piping["piping_architecture"]["main_headers"]["station_discharge_header"]["nominal_size_in"] == (
        piping["lines"]["discharge_header"]["nominal_size_in"]
    )
    assert "PIG-L" in piping["lines"]["discharge_header"]["to_boundary"]


def test_station_3d_view_and_tab_pipe_naming_and_syntax():
    """station3dView.js and stationTab.js expose 3D pipe labels, boundaries, direct pipe HUD, and pass node --check."""
    s3d_path = REPO_ROOT / "kasp" / "web" / "src" / "components" / "station3dView.js"
    stab_path = REPO_ROOT / "kasp" / "web" / "src" / "components" / "stationTab.js"
    s3d_text = s3d_path.read_text(encoding="utf-8")
    stab_text = stab_path.read_text(encoding="utf-8")

    # 3D header labels, boundary plaques, toolbar toggle, direct pipe telemetry & audit fields
    assert "STATION SUCTION HEADER" in s3d_text
    assert "STATION DISCHARGE HEADER" in s3d_text
    assert "btn-toggle-pipe-labels" in s3d_text
    assert "buildPipeTelemetryHtml" in s3d_text
    assert "inspectPipe" in s3d_text
    assert "fromBoundary" in s3d_text
    assert "toBoundary" in s3d_text
    assert "hierarchyLevel" in s3d_text

    # stationTab.js renders accessible boundary columns and piping architecture summary
    assert 'scope="col"' in stab_text
    assert 'scope="row"' in stab_text
    assert "boundary_summary" in stab_text
    assert "piping_architecture" in stab_text

    node_bin = shutil.which("node")
    if node_bin:
        for js_file in (s3d_path, stab_path):
            proc = subprocess.run([node_bin, "--check", str(js_file)], capture_output=True, text=True)
            assert proc.returncode == 0, f"node --check failed for {js_file}: {proc.stderr}"
