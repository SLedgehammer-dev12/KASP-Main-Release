"""Regression tests for separated PSV (API 520/526) & ESD (IEC 60534) sizing,
Ultrasonic Flow Meter (FT-401 AGA-9), and 3D valve interactive input forms.
"""

from pathlib import Path
import pytest

from kasp.services.station_service import calculate_station_process_model


BASE_INPUTS = {
    "p_in": 49.65,
    "p_in_unit": "bar(g)",
    "p_out": 75.0,
    "p_out_unit": "bar(a)",
    "t_in": 19.0,
    "t_in_unit": "°C",
    "flow": 1_985_000.0,
    "flow_unit": "Sm³/h",
    "gas_comp": {
        "METHANE": 85.0,
        "ETHANE": 7.0,
        "PROPANE": 4.0,
        "NITROGEN": 2.0,
        "CARBONDIOXIDE": 2.0,
    },
    "eos_model": "coolprop",
    "calc_method": "Metot 5: Huntington-RK45 Diferansiyel",
    "num_units": 1,
}


@pytest.fixture(scope="module")
def station_with_user_safety_inputs():
    inputs = dict(BASE_INPUTS)
    inputs.update(
        {
            "psv_set_pressure_bar": 85.0,
            "psv_overpressure_pct": 10.0,
            "psv_back_pressure_bar": 1.05,
            "psv_valve_type": "balanced_bellows",
            "psv_count": 3,
            "psv_duty_count": 2,
            "esd_count": 3,
            "esd_duty_count": 2,
            "esd_allowable_dp_bar": 0.35,
            "esd_valve_type": "full_bore_ball",
        }
    )
    return calculate_station_process_model(inputs)


def test_psv_sizing_uses_station_gas_inputs_and_user_overrides(station_with_user_safety_inputs):
    safety = station_with_user_safety_inputs["equipment_sizing"]["safety_relief_and_blowdown"]
    sizing = safety["psv_sizing"]
    auto = safety["auto_inputs"]

    assert sizing is not None
    assert sizing["required_area_sqin"] > 0
    assert sizing["required_area_total_sqin"] == pytest.approx(sizing["required_area_sqin"] * 2, rel=1e-3)
    assert sizing["required_diameter_in"] > 0
    assert sizing["recommended_duty_count"] >= 1
    assert "API 520" in sizing["standard"]

    # Program-provided thermodynamic inputs are automatically populated
    assert auto["eos_model"] == "coolprop"
    assert auto["mw"] > 16.0
    assert auto["p_upstream_bar"] == pytest.approx(75.0)
    assert auto["mass_flow_total_kgs"] > 400.0
    assert "METHANE" in auto["gas_comp"]

    assert safety["psv_set_pressure_bar"] == pytest.approx(85.0)
    assert safety["psv_count"] == 3
    assert safety["psv_duty_count"] == 2
    assert safety["psv_valve_type"] == "balanced_bellows"
    assert safety["missing_inputs"] == []


def test_esd_sizing_separates_duty_count_and_calculates_diameter(station_with_user_safety_inputs):
    esd = station_with_user_safety_inputs["equipment_sizing"]["esd_sizing"]
    suction = esd["suction"]
    discharge = esd["discharge"]
    auto = esd["auto_inputs"]

    assert esd["esd_count"] == 3
    assert esd["esd_duty_count"] == 2
    assert auto["discharge_p_in_bar"] > 70.0
    assert auto["mass_flow_total_kgs"] > 400.0

    for valve in (suction, discharge):
        assert valve["duty_count"] == 2
        assert valve["flow_per_valve_kgs"] == pytest.approx(auto["mass_flow_total_kgs"] / 2.0, rel=1e-2)
        assert valve["required_cv"] > 0
        assert valve["required_cv_total"] == pytest.approx(valve["required_cv"] * 2.0, rel=1e-2)
        assert valve["calculated_size_in"] > 0
        assert valve["selected_dn_mm"] >= valve["line_dn_mm"]
        assert valve["selected_size_in"] >= valve["line_size_in"]
        assert "IEC 60534" in (valve["standard"] or "")

    assert esd["allowable_dp_bar"] == pytest.approx(0.35)
    assert esd["missing_inputs"] == []


def test_ultrasonic_flow_meter_is_sized_on_discharge_header(station_with_user_safety_inputs):
    usm = station_with_user_safety_inputs["equipment_sizing"]["ultrasonic_meter"]

    assert usm["tag"] == "FT-401"
    assert "AGA" in usm["meter_type"]
    assert usm["mass_flow_kgs"] > 400.0
    assert usm["actual_volumetric_flow_m3h"] > 1000.0
    assert usm["speed_of_sound_ms"] > 300.0
    assert usm["gas_velocity_ms"] > 1.0


def test_3d_scene_includes_bypass_kickers_risers_usm_and_interactive_hud():
    source = Path("kasp/web/src/components/station3dView.js").read_text(encoding="utf-8")

    for token in (
        "pig_bypass",
        "pig_kicker_receiver",
        "pig_kicker_launcher",
        "ultrasonic_meter",
        "btn-hud-calc-psv",
        "btn-hud-calc-esd",
        "hud-psv-count",
        "hud-esd-count",
    ):
        assert token in source, f"3D sahnede eksik bileşen: {token}"
