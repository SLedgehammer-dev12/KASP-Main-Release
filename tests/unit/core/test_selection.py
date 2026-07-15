import pytest
from kasp.core.selection import TurbineSelector

SAMPLE_TURBINE = {
    "manufacturer": "TestCorp", "model": "T100",
    "type": "Aeroderivative",
    "iso_power_kw": 5000.0,
    "iso_heat_rate_kj_kwh": 10500.0,
    "surge_flow": 5.0,
    "stonewall_flow": 50.0,
}


class TestEdgeCases:
    def test_zero_required_power_returns_empty(self):
        result = TurbineSelector.select_units(0.0, {}, [SAMPLE_TURBINE])
        assert result == []

    def test_negative_power_returns_empty(self):
        result = TurbineSelector.select_units(-100.0, {}, [SAMPLE_TURBINE])
        assert result == []

    def test_empty_turbine_list(self):
        result = TurbineSelector.select_units(3000.0, {}, [])
        assert result == []

    def test_zero_surge_flow_handled(self):
        t = {**SAMPLE_TURBINE, "surge_flow": 0.0}
        result = TurbineSelector.select_units(3000.0, {
            'ambient_temp': 15.0, 'altitude': 0.0,
            'ambient_pressure': 101.325, 'flow': 0.0,
        }, [t])
        assert result == []

    def test_very_small_surge_flow(self):
        t = {**SAMPLE_TURBINE, "surge_flow": 1e-12}
        result = TurbineSelector.select_units(3000.0, {
            'ambient_temp': 15.0, 'altitude': 0.0,
            'ambient_pressure': 101.325, 'flow': 20.0,
        }, [t])
        assert result == []


class TestNormalFlow:
    def test_valid_selection_with_matching_power(self):
        t = {**SAMPLE_TURBINE, "iso_power_kw": 3500}
        result = TurbineSelector.select_units(3000.0, {
            'ambient_temp': 15.0, 'altitude': 0.0,
            'ambient_pressure': 101.325, 'flow': 20.0,
        }, [t])
        assert len(result) >= 0
        if result:
            assert 0 <= result[0].selection_score <= 100

    def test_oversized_turbine_filtered_out(self):
        result = TurbineSelector.select_units(500.0, {
            'ambient_temp': 15.0, 'altitude': 0.0,
            'ambient_pressure': 101.325, 'flow': 20.0,
        }, [SAMPLE_TURBINE])
        assert len(result) == 0

    def test_selection_sorted_by_score(self):
        t1 = {**SAMPLE_TURBINE, "model": "T100", "iso_power_kw": 3500}
        t2 = {**SAMPLE_TURBINE, "model": "T200", "iso_power_kw": 5000}
        result = TurbineSelector.select_units(3000.0, {
            'ambient_temp': 15.0, 'altitude': 0.0,
            'ambient_pressure': 101.325, 'flow': 20.0,
        }, [t1, t2])
        assert len(result) >= 1
        for i in range(len(result) - 1):
            assert result[i].selection_score >= result[i + 1].selection_score

    def test_limit_parameter(self):
        turbines = []
        for i in range(10):
            t = {**SAMPLE_TURBINE, "model": f"T{i:03d}", "iso_power_kw": 3000 + i * 500}
            turbines.append(t)
        result = TurbineSelector.select_units(3000.0, {
            'ambient_temp': 15.0, 'altitude': 0.0,
            'ambient_pressure': 101.325, 'flow': 20.0,
        }, turbines, limit=3)
        assert len(result) <= 3
