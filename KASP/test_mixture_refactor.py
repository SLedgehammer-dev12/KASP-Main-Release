import pytest

from kasp.core.exceptions import FluidPropertyError
from kasp.core.mixture import GasMixtureBuilder


def test_validate_and_normalize_rejects_zero_total_composition():
    with pytest.raises(FluidPropertyError, match="pozitif"):
        GasMixtureBuilder.validate_and_normalize({"METHANE": 0.0, "ETHANE": 0.0})


def test_validate_and_normalize_rejects_non_numeric_percentages():
    with pytest.raises(FluidPropertyError, match="Gecersiz"):
        GasMixtureBuilder.validate_and_normalize({"METHANE": "abc"})


def test_validate_and_normalize_merges_aliases_before_normalizing():
    composition = GasMixtureBuilder.validate_and_normalize({"CO2": 40.0, "CARBONDIOXIDE": 60.0})

    assert composition == {"CARBONDIOXIDE": pytest.approx(1.0)}


def test_build_thermo_data_uses_shared_mixture_mw_calculation():
    composition = GasMixtureBuilder.validate_and_normalize({"METHANE": 50.0, "NITROGEN": 50.0})
    data = GasMixtureBuilder.build_thermo_data(composition)

    assert data["MW"] == pytest.approx(GasMixtureBuilder.calculate_mixture_mw(composition))
    assert data["ids"] == ["methane", "nitrogen"]
    assert data["mol_fractions"] == [pytest.approx(0.5), pytest.approx(0.5)]
