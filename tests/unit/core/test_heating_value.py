import pytest
from kasp.core.heating_value import calculate as calc_heating


class TestHeatingValue:
    def test_pure_methane_kasp(self):
        lhv, hhv = calc_heating({'METHANE': 100.0}, 'kasp')
        assert lhv > 0, f"LHV must be positive: {lhv}"
        assert hhv > lhv, f"HHV must exceed LHV: {hhv} vs {lhv}"

    def test_pure_methane_iso6976(self):
        lhv, hhv = calc_heating({'METHANE': 100.0}, 'iso6976')
        assert 45_000 < lhv < 55_000, f"ISO 6976 LHV out of range: {lhv}"
        assert 48_000 < hhv < 60_000, f"ISO 6976 HHV out of range: {hhv}"

    def test_mixture_weighted(self):
        lhv_mix, hhv_mix = calc_heating(
            {'METHANE': 50.0, 'ETHANE': 50.0}, 'iso6976'
        )
        lhv_ch4, _ = calc_heating({'METHANE': 100.0}, 'iso6976')
        lhv_c2, _ = calc_heating({'ETHANE': 100.0}, 'iso6976')
        assert min(lhv_ch4, lhv_c2) < lhv_mix < max(lhv_ch4, lhv_c2)

    def test_empty_composition_rejected(self):
        with pytest.raises(Exception):
            calc_heating({}, 'kasp')

    def test_inert_only_returns_zero(self):
        lhv, hhv = calc_heating({'NITROGEN': 100.0}, 'kasp')
        assert lhv == 0.0

    def test_all_sources_positive(self):
        for source in ['kasp', 'iso6976', 'thermo']:
            lhv, hhv = calc_heating({'METHANE': 100.0}, source)
            assert lhv > 0, f"{source}: LHV = {lhv}"
