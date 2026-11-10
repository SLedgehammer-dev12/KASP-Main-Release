import pytest
from kasp.core.thermo_support import _convert_head_value, convert_result_value
from kasp.core.exceptions import UnitConversionError


def test_head_conversion_identity():
    """Identity conversions (same from and to unit) must return exact value without exception."""
    assert _convert_head_value(150.0, "kJ/kg", "kJ/kg") == 150.0
    assert _convert_head_value(50000.0, "ft-lbf/lbm", "ft-lbf/lbm") == 50000.0
    assert _convert_head_value(64.5, "Btu/lb", "Btu/lb") == 64.5
    assert _convert_head_value(1200.0, "m", "m") == 1200.0


def test_head_conversion_cross_imperial():
    """Converting between ft-lbf/lbm and Btu/lb must work seamlessly via canonical base."""
    # 1 Btu = 778.169 ft-lbf approx -> 1 Btu/lb approx 778.169 ft-lbf/lbm
    # via kJ/kg: 1 kJ/kg = 334.55256555 ft-lbf/lbm and 0.4299226139 Btu/lb
    val_ft = 778.169
    val_btu = _convert_head_value(val_ft, "ft-lbf/lbm", "Btu/lb")
    assert val_btu == pytest.approx(1.0, rel=1e-3)

    back_ft = _convert_head_value(val_btu, "Btu/lb", "ft-lbf/lbm")
    assert back_ft == pytest.approx(val_ft, rel=1e-5)


def test_head_conversion_metric_meters():
    """Converting between kJ/kg and meters of fluid column (m) using g = 9.80665 m/s^2."""
    # 1 kJ/kg = 1000 J/kg / 9.80665 m/s^2 = 101.97162 m
    val_kj_kg = 10.0
    val_m = _convert_head_value(val_kj_kg, "kJ/kg", "m")
    assert val_m == pytest.approx(1019.7162, rel=1e-4)

    back_kj = _convert_head_value(val_m, "m", "kJ/kg")
    assert back_kj == pytest.approx(val_kj_kg, rel=1e-5)

    # meters to ft-lbf/lbm
    val_ft = _convert_head_value(val_m, "m", "ft-lbf/lbm")
    assert val_ft == pytest.approx(10.0 * 334.55256555, rel=1e-4)


def test_head_conversion_unsupported_unit():
    """Unsupported unit names must raise UnitConversionError."""
    with pytest.raises(UnitConversionError):
        _convert_head_value(100.0, "invalid_unit", "kJ/kg")

    with pytest.raises(UnitConversionError):
        _convert_head_value(100.0, "kJ/kg", "invalid_unit")
