"""TDD test suite for thermodynamic phase classification & N+1 operating/standby unit layout."""

from pathlib import Path
import shutil
import subprocess
import pytest

from kasp.core.properties import ThermodynamicSolver
from kasp.core.thermo import ThermoEngine
from kasp.services.calculation_service import execute_design_calculation
from kasp.services.station_service import calculate_station_process_model

REPO_ROOT = Path(__file__).resolve().parent

NATURAL_GAS = {
    "METHANE": 85.0,
    "ETHANE": 7.0,
    "PROPANE": 4.0,
    "NITROGEN": 2.0,
    "CARBONDIOXIDE": 2.0,
}


class TestThermodynamicPhaseClassification:
    def test_coolprop_and_pr_natural_gas_return_gas_phase_not_liquid(self):
        engine = ThermoEngine()
        for eos in ("coolprop", "pr", "srk", "gerg2008"):
            gas_obj = engine._create_gas_object(NATURAL_GAS, eos)
            # Low pressure gas (5 bar, 19 C)
            st_low = engine.thermo_solver.get_properties(5.0e5, 292.15, gas_obj, eos)
            assert st_low.phase == "gas", f"{eos} at 5 bar returned {st_low.phase}"
            assert st_low.raw_props.get("thermo_health") == "HEALTHY"

            # Pipeline natural gas inlet & outlet
            st_in = engine.thermo_solver.get_properties(50.66325e5, 292.15, gas_obj, eos)
            assert st_in.phase == "gas", f"{eos} at 50.66 bar returned {st_in.phase}"
            assert st_in.raw_props.get("thermo_health") == "HEALTHY"

            st_out = engine.thermo_solver.get_properties(75.0e5, 323.06, gas_obj, eos)
            assert st_out.phase == "gas", f"{eos} at 75 bar returned {st_out.phase}"

    def test_real_liquid_dense_supercritical_twophase_and_fallbacks_preserved(self):
        engine = ThermoEngine()

        # Real liquid propane (20 bar, 20 C -> rho ~ 503 kg/m3, Z ~ 0.07)
        g_prop = engine._create_gas_object({"PROPANE": 100.0}, "coolprop")
        st_liq = engine.thermo_solver.get_properties(20.0e5, 293.15, g_prop, "coolprop")
        assert st_liq.phase == "liquid"

        # Dense supercritical CO2 (90 bar, 35 C -> rho ~ 662 kg/m3)
        g_co2 = engine._create_gas_object({"CARBONDIOXIDE": 100.0}, "coolprop")
        st_sc = engine.thermo_solver.get_properties(90.0e5, 308.15, g_co2, "coolprop")
        assert st_sc.phase == "supercritical"

        # Two-phase rich gas under CoolProp
        g_rich = engine._create_gas_object(
            {"METHANE": 70.0, "ETHANE": 15.0, "PROPANE": 10.0, "BUTANE": 5.0},
            "coolprop",
        )
        st_2p = engine.thermo_solver.get_properties(80.0e5, 253.15, g_rich, "coolprop")
        assert st_2p.phase == "two-phase"

        # Fallback markers preserved even at gas Z/density
        assert ThermodynamicSolver._classify_phase(0.95, 10.0, "ideal_fallback") == "ideal_fallback"
        assert ThermodynamicSolver._classify_phase(0.95, 10.0, "z_factor_fallback") == "z_factor_fallback"
        assert ThermodynamicSolver._classify_phase(0.95, 10.0, "ideal") == "ideal"

    def test_design_calculation_reports_gas_phase_for_coolprop(self):
        engine = ThermoEngine()
        res = execute_design_calculation(
            {
                "p_in": 49.65,
                "p_in_unit": "bar(g)",
                "p_out": 75.0,
                "p_out_unit": "bar(a)",
                "t_in": 19.0,
                "t_in_unit": "°C",
                "flow": 1985000.0,
                "flow_unit": "Sm³/h",
                "gas_comp": NATURAL_GAS,
                "eos_model": "coolprop",
                "calc_method": "Metot 5: Huntington-RK45 Diferansiyel",
                "poly_eff": 90.0,
                "mech_eff": 98.0,
                "therm_eff": 35.0,
                "num_units": 1,
                "num_stages": 1,
            },
            engine=engine,
        )
        assert res["phase_in"] == "gas"
        assert res["phase_out"] == "gas"
        assert res["inlet_properties"]["phase"] == "gas"
        assert res["outlet_properties"]["phase"] == "gas"
        assert res["inlet_properties"]["thermo_health"] == "HEALTHY"


class TestNPlusOneUnitsAndDesignSidebarConsolidation:
    def test_n_plus_1_splits_flow_across_operating_units_only(self):
        engine = ThermoEngine()
        # N = 4 operating units -> N+1 means 4 operating + 1 standby = 5 installed
        res = execute_design_calculation(
            {
                "p_in": 49.65,
                "p_in_unit": "bar(g)",
                "p_out": 75.0,
                "p_out_unit": "bar(a)",
                "t_in": 19.0,
                "t_in_unit": "°C",
                "flow": 100.0,
                "flow_unit": "kg/s",
                "gas_comp": NATURAL_GAS,
                "eos_model": "coolprop",
                "calc_method": "Metot 5: Huntington-RK45 Diferansiyel",
                "poly_eff": 85.0,
                "mech_eff": 98.0,
                "therm_eff": 35.0,
                "num_units": 4,
                "num_stages": 1,
            },
            engine=engine,
        )
        assert res["num_units"] == 4
        assert res["operating_units"] == 4
        assert res["standby_units"] == 1
        assert res["installed_units"] == 5
        assert res["mass_flow_total_kgs"] == pytest.approx(100.0, rel=1e-4)
        # Flow must be split across the 4 operating units (25.0 kg/s), NOT 5 (20.0 kg/s)
        assert res["mass_flow_per_unit_kgs"] == pytest.approx(25.0, rel=1e-4)
        assert res["power_shaft_total_kw"] == pytest.approx(res["power_shaft_per_unit_kw"] * 4.0, rel=1e-3)

        station = calculate_station_process_model(
            {
                "flow": 100.0,
                "flow_unit": "kg/s",
                "p_in": 50.66325,
                "p_in_unit": "bar(a)",
                "p_out": 75.0,
                "p_out_unit": "bar(a)",
                "t_in": 19.0,
                "gas_comp": NATURAL_GAS,
                "num_units": 4,
            }
        )
        comp_eq = station["equipment_sizing"]["turbo_compressors"]
        assert comp_eq["operating_count"] == 4
        assert comp_eq["standby_count"] == 1
        assert comp_eq["installed_count"] == 5
        assert "4 Çalışan + 1 Yedek" in comp_eq["configuration"]
        assert comp_eq["flow_per_unit_kgs"] == pytest.approx(25.0, rel=1e-2)

    def test_design_sidebar_merged_stages_into_process_and_removed_duplicate_num_units(self):
        dside = (REPO_ROOT / "kasp" / "web" / "src" / "components" / "designSidebar.js").read_text(encoding="utf-8")
        rview = (REPO_ROOT / "kasp" / "web" / "src" / "components" / "resultsView.js").read_text(encoding="utf-8")
        locales = (REPO_ROOT / "kasp" / "web" / "src" / "i18n" / "locales.js").read_text(encoding="utf-8")

        # Duplicate step 4 accordion & duplicate num_units field removed
        assert "step_stages" not in dside
        assert "inp-step4-num-units" not in dside

        # Stages and intercooling inputs live inside Step 1 (before Step 2 header)
        step1_start = dside.index("<!-- Step 1:")
        step2_start = dside.index("<!-- Step 2:")
        step1_block = dside[step1_start:step2_start]
        assert 'data-field="num_stages"' in step1_block
        assert 'data-field="intercooler_t"' in step1_block
        assert 'data-field="intercooler_dp_pct"' in step1_block
        assert 'data-field="num_units"' in step1_block

        # Dropdown options store operating count N while displaying N+1 (1 Çalışan + 1 Yedek, 4 Çalışan + 1 Yedek, ...)
        assert 'value="1"' in step1_block and "1+1" in step1_block
        assert 'value="4"' in step1_block and "4+1" in step1_block

        # Remaining steps renumbered cleanly 1..5 in locales
        assert "4. Hedef Verimler" in locales
        assert "5. Saha & Çevre Şartları" in locales

        # Results view uses phase formatter & operating+standby metadata
        assert "formatPhaseDisplay" in rview or "phaseBadgeClass" in rview

        node_bin = shutil.which("node")
        if node_bin:
            for rel in (
                "kasp/web/src/components/designSidebar.js",
                "kasp/web/src/components/resultsView.js",
                "kasp/web/src/i18n/locales.js",
                "kasp/web/src/store/projectStore.js",
            ):
                proc = subprocess.run([node_bin, "--check", str(REPO_ROOT / rel)], capture_output=True, text=True)
                assert proc.returncode == 0, f"node --check failed for {rel}: {proc.stderr}"
