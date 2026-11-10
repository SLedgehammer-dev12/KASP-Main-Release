import pytest
from kasp.core.thermo_support import _convert_fuel_flow, _convert_heating_value, _convert_heat_rate_value
from kasp.core.models import ThermodynamicState


class MockThermoSolver:
    def get_properties(self, p, t, gas_obj, eos):
        return ThermodynamicState(
            P=p, T=t, H=0.0, S=0.0, Z=0.99, k=1.3, MW=16.04,
            Cp=2000.0, Cv=1500.0, density=0.80, phase="gas"
        )


def test_fuel_flow_bidirectional_standard_volume():
    """Verify fuel flow conversion works bidirectionally between Sm3/h and kg/h."""
    mock_solver = MockThermoSolver()
    gas_obj = {"mock": True}

    # 1. Forward: 80.0 kg/h -> Sm3/h (density = 0.80 kg/m3 => 100.0 Sm3/h)
    vol_flow = _convert_fuel_flow(
        80.0, "kg/h", "Sm3/h",
        gas_obj=gas_obj, eos_method="pr", thermo_solver=mock_solver
    )
    assert vol_flow == pytest.approx(100.0, rel=1e-3)

    # 2. Backward: 100.0 Sm3/h -> kg/h (density = 0.80 kg/m3 => 80.0 kg/h)
    mass_flow = _convert_fuel_flow(
        100.0, "Sm3/h", "kg/h",
        gas_obj=gas_obj, eos_method="pr", thermo_solver=mock_solver
    )
    assert mass_flow == pytest.approx(80.0, rel=1e-3)

    # 3. Identity passthrough
    assert _convert_fuel_flow(50.0, "Sm3/h", "Sm3/h") == 50.0


def test_heating_value_and_heat_rate_unit_aliases():
    """Verify Btu/lb and Btu/hp.hr aliases work without UnitConversionError."""
    # Btu/lb alias for Btu/lbm
    val_kj = _convert_heating_value(1000.0, "Btu/lb", "kJ/kg")
    assert val_kj == pytest.approx(2326.0, rel=1e-3)
    val_back = _convert_heating_value(val_kj, "kJ/kg", "Btu/lb")
    assert val_back == pytest.approx(1000.0, rel=1e-3)

    # Btu/hp.hr alias for Btu/hp-hr
    hr_kj = _convert_heat_rate_value(10000.0, "Btu/hp.hr", "kJ/kWh")
    assert hr_kj > 0
    hr_back = _convert_heat_rate_value(hr_kj, "kJ/kWh", "Btu/hp.hr")
    assert hr_back == pytest.approx(10000.0, rel=1e-3)
