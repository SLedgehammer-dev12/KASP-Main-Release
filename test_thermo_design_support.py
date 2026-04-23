import pytest

from kasp.core.thermo_design_support import (
    ENGINE_VERSION,
    build_design_results_payload,
    build_stage_result,
    build_uncertainty_measurements,
    build_uncertainty_payload,
    compute_stage_pressure_ratio,
    select_design_method_key,
)


def test_compute_stage_pressure_ratio_and_method_selection_remain_stable():
    assert compute_stage_pressure_ratio(9.0, 0.0, 2) == pytest.approx(3.0)
    assert compute_stage_pressure_ratio(9.0, 0.02, 3) > 2.0
    assert select_design_method_key("Metot 1: Ortalama Özellikler") == "average"
    assert select_design_method_key("Metot 2: Uç Nokta") == "endpoint"
    assert select_design_method_key("Metot 3: Artımlı Basınç") == "incremental"
    assert select_design_method_key("Metot 4: Doğrudan H-S") == "direct_hs"


def test_build_stage_result_keeps_backward_compatible_keys():
    stage = build_stage_result(
        stage=1,
        p_in=100000.0,
        t_in=300.0,
        p_out=200000.0,
        t_out=360.0,
        head_kj_kg=120.0,
        poly_eff_design=0.82,
        poly_eff_diagnostic=0.8,
        power_gas_kw=950.0,
        delta_h_kj_kg=150.0,
        z_avg=0.94,
        method_history={"iteration": [0, 1]},
    )

    assert stage["poly_eff"] == 0.82
    assert stage["poly_eff_diagnostic"] == 0.8
    assert stage["method_history"]["iteration"] == [0, 1]


def test_build_design_results_payload_and_uncertainty_helpers_preserve_contract():
    staged_results = [
        {"delta_h_kj_kg": 150.0, "poly_eff_diagnostic": 0.8},
        {"delta_h_kj_kg": 170.0, "poly_eff_diagnostic": 0.79},
    ]
    results = build_design_results_payload(
        p_in_pa=100000.0,
        t_in_k=300.0,
        p_out_pa=400000.0,
        final_t_out_k=380.0,
        total_poly_head_kj_kg=256.0,
        poly_eff_tgt=0.82,
        total_stage_gas_power_kw=1900.0,
        total_shaft_kw=2000.0,
        motor_kw=2050.0,
        unit_kw=2132.0,
        mech_loss_kw=100.0,
        fuel_kgh=420.0,
        mass_flow_per_unit=12.0,
        inlet_acmh=48000.0,
        num_units=2,
        total_mass_flow_kgs=24.0,
        heat_rate=11000.0,
        lhv=47000.0,
        hhv=52000.0,
        inlet_properties={"Z": 0.95},
        outlet_properties={"Z": 0.91},
        num_stages=2,
        staged_results=staged_results,
        method="Metot 1",
    )

    assert results["t_out"] == pytest.approx(106.85)
    assert results["actual_poly_efficiency"] == pytest.approx(256.0 / 320.0)
    assert results["power_unit_total_kw"] == pytest.approx(4264.0)
    assert results["engine_version"] == ENGINE_VERSION

    measurements = build_uncertainty_measurements({"p_in": "1.1", "p_out": "4.2", "t_in": "25", "flow": "12.5"})
    payload = build_uncertainty_payload(
        {
            "combined_uncertainty": 0.012,
            "expanded_uncertainty": 0.024,
            "breakdown_percent": {"flow": 40.0},
        },
        0.801,
    )

    assert measurements == {"p_in": 1.1, "p_out": 4.2, "t_in": 25.0, "flow": 12.5}
    assert payload["polytropic_efficiency"]["value"] == 0.801
    assert payload["asme_ptc10_compliant"] is True
