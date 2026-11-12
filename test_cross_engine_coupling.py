"""Cross-Engine Coupling Tests (Konu #1 — Faz 1 TDD).

Tests end-to-end physical and thermodynamic coupling across:
1. Flow conversion (`Sm³/h`, `Sm3/h`, `Nm³/h`, `MMSCFD`, `MMSCMD`) using real mixture MW / EOS standard density instead of hardcoded 0.772 / 0.320 constants.
2. Propagation of `ThermoEngine` outputs (`rho_in`, `z_in`, `z_out`, `Cp`/`Δh`, `mu`, `t_out`) into:
   - `StationService` (`calculate_station_process_model`)
   - `AirCoolerAdapter`
   - `PipeSizingService` (all 15 lines with real EOS `rho`/`mu`/`Z` and real `dp_cyclone`/`dp_filter`/`dp_cooler` nodal pressures)
   - `ControlValveAdapter` (forwarding user's selected `eos_model`)
   - `PSVAdapter` (real discharge state & gas properties)
3. Generation and propagation of engineering warnings (ASV, PCV, TCV, PSV, Air Cooler, Pipe Erosion/Velocity).
"""

from __future__ import annotations

import pytest

from kasp.core.thermo import ThermoEngine
from kasp.integrations.control_valve.adapter import ControlValveAdapter
from kasp.services.calculation_service import (
    execute_design_calculation,
    serialize_turbine_recommendation,
)
from kasp.services.pipe_sizing_service import PipeSizingService
from kasp.services.station_service import calculate_station_process_model


H2_RICH_GAS = {
    "HYDROGEN": 85.0,
    "METHANE": 15.0,
}  # MW ~ 4.12 g/mol (>> 4x lighter than natural gas, Cp ~ 6.5+ kJ/kg.K)

CO2_RICH_GAS = {
    "CARBONDIOXIDE": 80.0,
    "METHANE": 15.0,
    "ETHANE": 5.0,
}  # MW ~ 39.12 g/mol (> 2x heavier than natural gas, Z strongly depressed at high P)

PIPELINE_GAS = {
    "METHANE": 90.0,
    "ETHANE": 5.0,
    "PROPANE": 2.0,
    "NITROGEN": 1.5,
    "CARBONDIOXIDE": 1.5,
}


def _node_map(station_res: dict) -> dict:
    return {n["id"]: n for n in station_res.get("nodes", [])}


class TestRealMWFlowConversion:
    """Verify Sm3/h, Nm3/h, MMSCFD, MMSCMD use real gas MW/EOS instead of 0.772 or 0.320."""

    def test_sm3h_uses_real_mw_not_hardcoded_0772(self):
        engine = ThermoEngine()
        gas_h2 = engine._create_gas_object(H2_RICH_GAS, "pr")
        expected_h2_kgs = engine.convert_flow_to_kgs(500_000.0, "Sm³/h", gas_h2, "pr")

        gas_co2 = engine._create_gas_object(CO2_RICH_GAS, "pr")
        expected_co2_kgs = engine.convert_flow_to_kgs(500_000.0, "Sm³/h", gas_co2, "pr")

        res_h2 = calculate_station_process_model({
            "flow": 500_000.0,
            "flow_unit": "Sm³/h",
            "p_in": 35.0,
            "p_in_unit": "bar(a)",
            "p_out": 65.0,
            "p_out_unit": "bar(a)",
            "t_in": 20.0,
            "gas_comp": H2_RICH_GAS,
            "eos_model": "pr",
            "num_units": 1,
        })
        res_co2 = calculate_station_process_model({
            "flow": 500_000.0,
            "flow_unit": "Sm3/h",
            "p_in": 35.0,
            "p_in_unit": "bar(a)",
            "p_out": 65.0,
            "p_out_unit": "bar(a)",
            "t_in": 20.0,
            "gas_comp": CO2_RICH_GAS,
            "eos_model": "pr",
            "num_units": 1,
        })

        actual_h2_kgs = res_h2["station_summary"]["total_mass_flow_kgs"]
        actual_co2_kgs = res_co2["station_summary"]["total_mass_flow_kgs"]

        # Hardcoded 0.772 would have produced 500_000 * 0.772 / 3600 = 107.22 kg/s for BOTH!
        assert abs(actual_h2_kgs - 107.22) > 50.0
        assert abs(actual_co2_kgs - 107.22) > 100.0
        assert actual_h2_kgs == pytest.approx(expected_h2_kgs, rel=0.02)
        assert actual_co2_kgs == pytest.approx(expected_co2_kgs, rel=0.02)
        assert actual_co2_kgs > actual_h2_kgs * 8.0

    def test_mmscfd_and_nm3h_use_real_mw_not_hardcoded_constants(self):
        engine = ThermoEngine()
        gas_h2 = engine._create_gas_object(H2_RICH_GAS, "pr")
        expected_h2_mmscfd = engine.convert_flow_to_kgs(100.0, "MMSCFD", gas_h2, "pr")
        expected_h2_nm3h = engine.convert_flow_to_kgs(360_000.0, "Nm³/h", gas_h2, "pr")

        gas_co2 = engine._create_gas_object(CO2_RICH_GAS, "pr")
        expected_co2_mmscfd = engine.convert_flow_to_kgs(100.0, "MMSCFD", gas_co2, "pr")

        res_h2 = calculate_station_process_model({
            "flow": 100.0,
            "flow_unit": "MMSCFD",
            "p_in": 40.0,
            "p_in_unit": "bar(a)",
            "p_out": 70.0,
            "p_out_unit": "bar(a)",
            "t_in": 20.0,
            "gas_comp": H2_RICH_GAS,
            "eos_model": "pr",
        })
        res_h2_nm3 = calculate_station_process_model({
            "flow": 360_000.0,
            "flow_unit": "Nm³/h",
            "p_in": 40.0,
            "p_in_unit": "bar(a)",
            "p_out": 70.0,
            "p_out_unit": "bar(a)",
            "t_in": 20.0,
            "gas_comp": H2_RICH_GAS,
            "eos_model": "pr",
        })
        res_co2 = calculate_station_process_model({
            "flow": 100.0,
            "flow_unit": "MMSCFD",
            "p_in": 40.0,
            "p_in_unit": "bar(a)",
            "p_out": 70.0,
            "p_out_unit": "bar(a)",
            "t_in": 20.0,
            "gas_comp": CO2_RICH_GAS,
            "eos_model": "pr",
        })

        # Hardcoded 0.320 would give 32.0 kg/s for MMSCFD and 77.2 kg/s for 360k Nm³/h
        assert res_h2["station_summary"]["total_mass_flow_kgs"] == pytest.approx(expected_h2_mmscfd, rel=0.02)
        assert res_h2_nm3["station_summary"]["total_mass_flow_kgs"] == pytest.approx(expected_h2_nm3h, rel=0.02)
        assert res_co2["station_summary"]["total_mass_flow_kgs"] == pytest.approx(expected_co2_mmscfd, rel=0.02)
        assert abs(res_h2["station_summary"]["total_mass_flow_kgs"] - 32.0) > 20.0


class TestThermoEngineToStationAndCoolerCoupling:
    """Verify StationService and AirCoolerAdapter use real EOS rho_in, Z, Cp/Δh, t_out (no Z=0.89 or Cp=2.45)."""

    def test_station_suction_density_and_cooler_duty_use_real_eos_instead_of_constants(self):
        # High-pressure CO2-rich gas at 55 bar(a), 20°C has Z << 0.89 (around ~0.68-0.75)
        inputs_co2 = {
            "flow": 80.0,
            "flow_unit": "kg/s",
            "p_in": 55.0,
            "p_in_unit": "bar(a)",
            "p_out": 95.0,
            "p_out_unit": "bar(a)",
            "t_in": 20.0,
            "t_in_unit": "°C",
            "gas_comp": CO2_RICH_GAS,
            "eos_model": "pr",
            "num_units": 1,
            "num_stages": 1,
            "poly_eff": 82.0,
            "include_air_cooler_design": True,
        }
        design_co2 = execute_design_calculation(inputs_co2)
        station_co2 = calculate_station_process_model(inputs_co2, design_results=design_co2)

        mw_co2 = station_co2["station_summary"]["gas_mw"]
        fake_rho_089 = (55.0 * 1e5) / (0.89 * (8314.462 / mw_co2) * 293.15)
        actual_rho_suction = station_co2["station_summary"]["suction_density_kgm3"]
        assert actual_rho_suction == pytest.approx(design_co2["rho_in"], rel=0.02)
        assert abs(actual_rho_suction - fake_rho_089) > 5.0

        # Discharge temperature must match ThermoEngine t_out
        nodes_co2 = _node_map(station_co2)
        t_hot_co2 = nodes_co2["N05_COMPRESSOR_DISCHARGE"]["temp_c"]
        assert t_hot_co2 == pytest.approx(design_co2["t_out_c"], abs=0.5)

        # AirCoolerAdapter detailed_design on CO2-rich gas must run with real discharge conditions
        ac_detail_co2 = station_co2["equipment_sizing"]["air_coolers"]["detailed_design"]
        assert ac_detail_co2 is not None
        assert ac_detail_co2["heat_duty_kw"] > 0

        # Now compare H2-rich cooler heat duty vs hardcoded Cp=2.45 kJ/(kg.K):
        # H2-rich gas (85% H2, 15% CH4) has Cp ~ 6.5 - 7.5 kJ/(kg.K), roughly 3x higher than 2.45!
        inputs_h2 = {
            "flow": 40.0,
            "flow_unit": "kg/s",
            "p_in": 30.0,
            "p_in_unit": "bar(a)",
            "p_out": 65.0,
            "p_out_unit": "bar(a)",
            "t_in": 25.0,
            "t_in_unit": "°C",
            "gas_comp": H2_RICH_GAS,
            "eos_model": "pr",
            "num_units": 1,
            "num_stages": 1,
            "poly_eff": 80.0,
            "include_air_cooler_design": True,
        }
        design_h2 = execute_design_calculation(inputs_h2)
        station_h2 = calculate_station_process_model(inputs_h2, design_results=design_h2)
        nodes_h2 = _node_map(station_h2)
        t_hot_h2 = nodes_h2["N05_COMPRESSOR_DISCHARGE"]["temp_c"]
        t_out_h2 = nodes_h2["N07_COOLER_OUTLET"]["temp_c"]
        delta_t_h2 = max(0.0, t_hot_h2 - t_out_h2)
        assert delta_t_h2 > 15.0

        fake_duty_245_mw = (40.0 * 2.45 * delta_t_h2) / 1000.0
        actual_duty_h2_mw = station_h2["station_summary"]["cooler_heat_duty_mw"]
        # Real H2-rich enthalpy drop must be > 2x the hardcoded Cp=2.45 value
        assert actual_duty_h2_mw > fake_duty_245_mw * 2.0
        # If CoolProp PT-flash inside AirCoolerAdapter fails on 85% H2, StationService must surface a warning cleanly
        ac_detail_h2 = station_h2["equipment_sizing"]["air_coolers"]["detailed_design"]
        if ac_detail_h2 is None:
            assert len(station_h2["equipment_sizing"]["air_coolers"]["design_warnings"]) >= 1
            assert any("Hava Soğutucu" in w for w in station_h2["warnings"])

    def test_station_pressure_change_runs_real_thermo_engine_instead_of_k128_fallback(self):
        # Design was computed at PR = 50 -> 60 bar (PR=1.2), then user changes Station P_out to 95 bar (PR=1.9)
        design_inputs = {
            "flow": 50.0,
            "flow_unit": "kg/s",
            "p_in": 50.0,
            "p_in_unit": "bar(a)",
            "p_out": 60.0,
            "p_out_unit": "bar(a)",
            "t_in": 20.0,
            "t_in_unit": "°C",
            "gas_comp": H2_RICH_GAS,
            "eos_model": "pr",
            "num_units": 1,
            "num_stages": 1,
            "poly_eff": 82.0,
        }
        old_design = execute_design_calculation(design_inputs)

        shifted_inputs = dict(design_inputs, p_out=95.0)
        station_shifted = calculate_station_process_model(shifted_inputs, design_results=old_design)

        # Compare against direct ThermoEngine calculation at 50 -> 95 bar
        fresh_engine = ThermoEngine()
        expected_fresh = fresh_engine.calculate_design_performance_with_mode({
            **shifted_inputs,
            "eos_method": "pr",
            "method": "Metot 6: Schultz 3-Üslü Gerçek Gaz",
        })

        # Old hardcoded fallback did head = 115.0 * ln(95/50) = 73.8 kJ/kg -> power ~ 4600 kW,
        # whereas real H2-rich head is > 400 kJ/kg -> power > 20,000 kW!
        actual_power_kw = station_shifted["station_summary"]["total_power_kw"]
        nodes_shifted = _node_map(station_shifted)
        actual_t_hot = nodes_shifted["N05_COMPRESSOR_DISCHARGE"]["temp_c"]

        assert actual_power_kw > 18_000.0
        assert actual_power_kw == pytest.approx(expected_fresh["power_unit_kw"], rel=0.06)
        assert actual_t_hot == pytest.approx(expected_fresh["t_out"], abs=1.5)


class TestPipeSizingRealEOSAndNodalPressures:
    """Verify all 15 station lines receive real EOS rho/mu/Z and real dp_cyclone/dp_filter/dp_cooler."""

    def test_station_piping_15_lines_use_real_eos_properties_and_nodal_dp(self):
        # Use low flow (15 kg/s) so station_service sets dp_cyclone=0.18 (not 0.25) and dp_filter=0.12 (not 0.20)!
        inputs = {
            "flow": 15.0,
            "flow_unit": "kg/s",
            "p_in": 55.0,
            "p_in_unit": "bar(a)",
            "p_out": 90.0,
            "p_out_unit": "bar(a)",
            "t_in": 20.0,
            "t_in_unit": "°C",
            "gas_comp": CO2_RICH_GAS,
            "eos_model": "pr",
            "num_units": 1,
            "num_stages": 1,
            "poly_eff": 84.0,
        }
        station = calculate_station_process_model(inputs)
        nodes = _node_map(station)
        piping = station["station_piping"]
        lines = piping["lines"]

        assert len(lines) == 15

        # At 15 kg/s: dp_cyclone = 0.151 -> post_cyclone = 54.85 (NOT 54.75 from hardcoded -0.25!)
        # dp_filter = 0.167 -> comp_suction = 54.68 (NOT 54.55 from hardcoded -0.25 - 0.20!)
        expected_p_cfs = nodes["N03_CYCLONE_OUTLET"]["pressure_bar"]
        expected_p_comp = nodes["N04_FILTER_OUTLET"]["pressure_bar"]
        expected_p_cooled = nodes["N07_COOLER_OUTLET"]["pressure_bar"]

        assert expected_p_cfs != pytest.approx(54.75, abs=0.02)
        assert expected_p_comp != pytest.approx(54.55, abs=0.02)
        assert lines["filter_branch"]["pressure_bar"] == pytest.approx(expected_p_cfs, abs=0.02)
        assert lines["comp_suction_header"]["pressure_bar"] == pytest.approx(expected_p_comp, abs=0.02)
        assert lines["comp_suction_branch"]["pressure_bar"] == pytest.approx(expected_p_comp, abs=0.02)
        assert lines["cooler_outlet"]["pressure_bar"] == pytest.approx(expected_p_cooled, abs=0.02)
        assert lines["mainline_outlet"]["pressure_bar"] == pytest.approx(expected_p_cooled, abs=0.02)

        # Verify all 15 lines carry real EOS Z-factor & density (not the simplified 1 - (P/120)*0.12 formula)
        engine = ThermoEngine()
        gas_obj = engine._create_gas_object(CO2_RICH_GAS, "pr")
        inlet_state = engine.thermo_solver.get_properties(55.0 * 1e5, 293.15, gas_obj, "pr")

        # Simplified formula at 55 bar gives Z = 0.945; real CO2-rich Z at 55 bar, 20°C is < 0.80!
        assert inlet_state.Z < 0.80
        assert lines["mainline_inlet"]["gas_density_kgm3"] == pytest.approx(inlet_state.density, rel=0.03)
        assert lines["mainline_inlet"].get("z_factor") == pytest.approx(inlet_state.Z, abs=0.02)

        for key, line in lines.items():
            assert line["gas_density_kgm3"] > 0
            assert line["gas_viscosity_pa_s"] > 0
            assert "z_factor" in line and 0.1 < line["z_factor"] < 2.0, f"Missing/invalid z_factor in line {key}"

    def test_pipe_sizing_generates_erosion_or_velocity_warnings_on_extreme_flow(self):
        res = PipeSizingService.size_station_network(
            mass_flow_kgs=4500.0,
            p_in_bar=25.0,
            p_out_bar=50.0,
            t_in_c=35.0,
            t_discharge_c=95.0,
            t_cooled_c=45.0,
            comp_op_count=1,
            cyclone_op_count=2,
            filter_op_count=2,
            cooler_bays_count=4,
            gas_mw=18.2,
            gas_comp=PIPELINE_GAS,
            eos_model="pr",
        )
        assert "warnings" in res
        assert len(res["warnings"]) >= 1
        assert any("hız" in w.lower() or "erozyon" in w.lower() for w in res["warnings"])


class TestControlValveAndPSVEOSAndWarnings:
    """Verify ControlValveAdapter honors eos_model, PSVAdapter couples cleanly, and Station aggregates warnings."""

    def test_control_valve_adapter_uses_selected_eos_model_not_hardcoded_gerg2008(self):
        adapter = ControlValveAdapter()
        base_payload = {
            "service": "gas",
            "mass_flow_kgs": 35.0,
            "p_in_bar": 75.0,
            "p_out_bar": 35.0,
            "t_c": 45.0,
            "composition": CO2_RICH_GAS,
            "path": "ASV",
        }
        res_pr = adapter.calculate({**base_payload, "eos_model": "pr"})
        res_coolprop = adapter.calculate({**base_payload, "eos_model": "coolprop"})

        assert "PR" in res_pr["provenance"]["gas_properties"].upper()
        assert "GERG-2008" not in res_pr["provenance"]["gas_properties"].upper()
        assert "COOLPROP" in res_coolprop["provenance"]["gas_properties"].upper()
        # PR vs CoolProp HEOS produce distinct required Cv on high-pressure CO2-rich gas
        assert res_pr["results"]["required_cv"] != res_coolprop["results"]["required_cv"]

    def test_station_forwards_eos_model_to_control_valves_and_psv_and_aggregates_warnings(self):
        # High flow + high pressure drop forces choked / high-noise / high-capacity valve & pipe warnings
        station = calculate_station_process_model({
            "flow": 2500.0,
            "flow_unit": "kg/s",
            "p_in": 25.0,
            "p_in_unit": "bar(a)",
            "p_out": 95.0,
            "p_out_unit": "bar(a)",
            "t_in": 35.0,
            "t_in_unit": "°C",
            "gas_comp": H2_RICH_GAS,
            "eos_model": "srk",
            "num_units": 1,
            "poly_eff": 78.0,
        })

        eq = station["equipment_sizing"]
        asv = eq["turbo_compressors"]["anti_surge_valve_sizing"]
        pcv = eq["station_recycle"]["pcv_sizing"]
        tcv = eq["air_coolers"]["cooler_bypass_valve_sizing"]
        psv = eq["safety_relief_and_blowdown"]["psv_sizing"]

        assert asv is not None
        assert "SRK" in str(asv.get("gas_properties_eos", "")).upper() or "SRK" in str(asv.get("provenance", {})).upper()
        assert pcv is not None
        assert "SRK" in str(pcv.get("gas_properties_eos", "")).upper() or "SRK" in str(pcv.get("provenance", {})).upper()
        assert tcv is not None
        assert "SRK" in str(tcv.get("gas_properties_eos", "")).upper() or "SRK" in str(tcv.get("provenance", {})).upper()
        assert psv is not None
        assert psv["z_used"] is not None and psv["mw_used"] == pytest.approx(4.12, abs=0.1)
        assert psv["selected_orifice"] in {
            "D", "E", "F", "G", "H", "J", "K", "L", "M", "N", "P", "Q", "R", "T", "Multiple Valves Required"
        }

        # Station must expose aggregated warnings list containing valve/PSV/erosion warnings
        assert "warnings" in station
        assert isinstance(station["warnings"], list)
        assert len(station["warnings"]) >= 2
        assert any("PSV" in w or "ASV" in w or "PCV" in w or "Boru Ağı" in w for w in station["warnings"])


class TestTurbineMarginSerialization:
    """Verify serialize_turbine_recommendation exposes both surge and stonewall (choke) margins."""

    def test_serialize_turbine_recommendation_includes_stonewall_margin(self):
        class DummyRec:
            turbine_name = "TestGT-25"
            model = "TGT-25"
            manufacturer = "OEM"
            type_str = "Industrial"
            iso_power_kw = 25000.0
            available_power_kw = 22500.0
            iso_heat_rate = 9800.0
            site_heat_rate = 10100.0
            power_margin_percent = 12.5
            surge_margin_percent = 18.4
            stonewall_margin_percent = 22.7
            meets_api617_surge = True
            efficiency_rating = "Yüksek"
            selection_score = 88.5
            recommendation_level = "Optimal"

        serialized = serialize_turbine_recommendation(DummyRec(), required_power_kw=20000.0)
        assert serialized["surge_margin_pct"] == pytest.approx(18.4)
        assert serialized["stonewall_margin_pct"] == pytest.approx(22.7)
        assert serialized["meets_api617_surge"] is True
