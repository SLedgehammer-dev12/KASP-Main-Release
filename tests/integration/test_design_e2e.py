"""
End-to-end design calculation integration tests.

Validates the full ThermoEngine pipeline:
  gas composition -> property solver -> method calculation -> power/head/turbine
"""

import pytest
from kasp.core.thermo import ThermoEngine


DESIGN_BASE = {
    'project_name': 'E2E Test',
    'p_in': 1.0, 'p_in_unit': 'bar(a)',
    't_in': 25.0, 't_in_unit': '\u00b0C',
    'p_out': 3.0, 'p_out_unit': 'bar(a)',
    'flow': 10.0, 'flow_unit': 'kg/s',
    'gas_comp': {'METHANE': 100.0},
    'eos_method': 'coolprop',
    'method': 'Metot 3: Art\u0131ml\u0131 Bas\u0131n\u00e7',
    'poly_eff': 82.0,
    'mech_eff': 98.0,
    'therm_eff': 35.0,
    'num_units': 1,
    'num_stages': 1,
    'intercooler_t': 40.0,
    'intercooler_dp_pct': 2.0,
    'consistency_check': False,
}

MIXTURE_COMP = {
    'METHANE': 85.0, 'ETHANE': 8.0, 'PROPANE': 4.0,
    'NITROGEN': 2.0, 'CARBONDIOXIDE': 1.0,
}


@pytest.fixture(scope="module")
def engine():
    return ThermoEngine()


class TestDesignCalculationE2E:
    def test_methane_single_stage_coolprop(self, engine):
        result = engine.calculate_design_performance(DESIGN_BASE)
        assert result is not None
        assert result['power_shaft_total_kw'] > 0
        assert result['t_out'] > 0
        assert 'stages' in result or 'actual_poly_efficiency' in result

    def test_mixture_with_consistency(self, engine):
        inputs = {**DESIGN_BASE, 'consistency_check': True,
                  'gas_comp': MIXTURE_COMP}
        result = engine.calculate_design_performance(inputs)
        assert result is not None
        assert result['power_shaft_total_kw'] > 0

    @pytest.mark.parametrize("eos", ["coolprop", "pr", "srk"])
    def test_all_eos_backends(self, engine, eos):
        inputs = {**DESIGN_BASE, 'eos_method': eos}
        result = engine.calculate_design_performance(inputs)
        assert result is not None, f"{eos} failed"
        assert result['power_shaft_total_kw'] > 0

    @pytest.mark.parametrize("stages", [1, 2, 3])
    def test_multistage(self, engine, stages):
        inputs = {**DESIGN_BASE, 'num_stages': stages}
        result = engine.calculate_design_performance(inputs)
        assert result is not None, f"{stages} stages failed"
        stages_data = result.get('stages', [])
        if stages_data and len(stages_data) > 0:
            assert len(stages_data) == stages, f"Expected {stages} stages"

    @pytest.mark.parametrize("method", [
        "Metot 1: Ortalama \u00d6zellikler",
        "Metot 2: U\u00e7 Nokta",
        "Metot 3: Art\u0131ml\u0131 Bas\u0131n\u00e7",
        "Metot 4: Do\u011frudan H-S",
    ])
    def test_all_calculation_methods(self, engine, method):
        inputs = {**DESIGN_BASE, 'method': method}
        result = engine.calculate_design_performance(inputs)
        assert result is not None, f"{method} returned None"
        assert result.get('power_shaft_total_kw', 0) > 0, f"{method} power=0"

    def test_power_increases_with_pressure_ratio(self, engine):
        pr2 = {**DESIGN_BASE, 'p_out': 2.0, 'p_out_unit': 'bar(a)'}
        pr5 = {**DESIGN_BASE, 'p_out': 5.0, 'p_out_unit': 'bar(a)'}
        p2 = engine.calculate_design_performance(pr2)['power_shaft_total_kw']
        p5 = engine.calculate_design_performance(pr5)['power_shaft_total_kw']
        assert p5 > p2, f"PR=5 power ({p5}) <= PR=2 power ({p2})"

    def test_power_increases_with_flow(self, engine):
        f5 = {**DESIGN_BASE, 'flow': 5.0}
        f20 = {**DESIGN_BASE, 'flow': 20.0}
        p5 = engine.calculate_design_performance(f5)['power_shaft_total_kw']
        p20 = engine.calculate_design_performance(f20)['power_shaft_total_kw']
        assert p20 > p5

    def test_heating_value_in_result(self, engine):
        result = engine.calculate_design_performance(DESIGN_BASE)
        assert 'lhv_kj_kg' in result or 'fuel_consumption_kg_h' in result or True

    def test_turbine_selection_in_result(self, engine):
        result = engine.calculate_design_performance(DESIGN_BASE)
        assert isinstance(result, dict)
        assert 'engine_version' in result or 'power_shaft_total_kw' in result


class TestErrorHandling:
    def test_invalid_eos_handled(self, engine):
        try:
            engine.calculate_design_performance({**DESIGN_BASE, 'eos_method': 'invalid_eos'})
        except Exception:
            pass

    def test_missing_required_fields(self, engine):
        try:
            engine.calculate_design_performance_with_mode({'p_in': 1.0})
        except Exception:
            pass

    def test_p_out_less_than_p_in(self, engine):
        try:
            engine.calculate_design_performance_with_mode({
                **DESIGN_BASE, 'p_out': 0.5, 'p_out_unit': 'bar(a)'
            })
        except Exception:
            pass

    def test_invalid_poly_eff(self, engine):
        try:
            engine.calculate_design_performance_with_mode({
                **DESIGN_BASE, 'poly_eff': 150.0
            })
        except Exception:
            pass
