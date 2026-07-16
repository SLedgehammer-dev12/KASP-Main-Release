import pytest
from kasp.core.settings import EngineSettings


class TestEngineSettings:
    def test_scoring_weights_sum_to_one(self):
        w = (EngineSettings.SCORE_WEIGHT_POWER + EngineSettings.SCORE_WEIGHT_EFFICIENCY +
             EngineSettings.SCORE_WEIGHT_SURGE)
        assert abs(w - 1.0) < 0.01

    def test_all_constants_defined(self):
        for attr in ['FALLBACK_LHV_KJ_KG', 'DEFAULT_ISENTROPIC_K_FALLBACK',
                      'IDEAL_GAS_FALLBACK_CP_BASE', 'MECHANICAL_LOSS_COEFF',
                      'MECHANICAL_LOSS_EXPONENT', 'MECHANICAL_LOSS_MIN_KW']:
            assert hasattr(EngineSettings, attr), f"Missing: {attr}"

    def test_binary_interaction_params_is_dict(self):
        assert isinstance(EngineSettings.BINARY_INTERACTION_PARAMS, dict)

    def test_api617_margins_positive(self):
        assert EngineSettings.API617_MIN_SURGE_MARGIN > 0
        assert EngineSettings.API617_MIN_STONEWALL_MARGIN > 0


class TestReleaseMetadata:
    def test_version_is_string(self):
        from release_metadata import RELEASE_VERSION, RELEASE_FULL_VERSION, RELEASE_BUILD_HASH
        assert isinstance(RELEASE_VERSION, str)
        assert len(RELEASE_VERSION) > 0
        assert "+" in RELEASE_FULL_VERSION or RELEASE_BUILD_HASH != "unknown"
        assert len(RELEASE_BUILD_HASH) > 0
