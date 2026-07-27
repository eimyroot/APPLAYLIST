from types import MappingProxyType

import pytest

from core.transition.contracts import (
    DimensionAssessment,
    DimensionName,
    TransitionClass,
    TransitionProfile,
    UserDecisionType,
)
from core.transition.profiles import ANALYSIS_DIMENSIONS, PROFILE_WEIGHTS, weights_for


@pytest.mark.parametrize("profile", list(TransitionProfile))
def test_profile_weights_are_normalized(profile: TransitionProfile) -> None:
    weights = weights_for(profile)
    assert set(weights) == ANALYSIS_DIMENSIONS
    assert DimensionName.STRATEGY_FIT not in weights
    assert sum(weights.values()) == pytest.approx(1.0)
    assert 0.10 <= weights[DimensionName.TONAL] <= 0.25


def test_declared_profiles_are_all_valid() -> None:
    assert set(PROFILE_WEIGHTS) == set(TransitionProfile)


def test_dimension_details_are_deeply_read_only() -> None:
    details = {"delta": 1.0}
    dimension = DimensionAssessment(
        name=DimensionName.TEMPO,
        score=80.0,
        confidence=0.9,
        weight=0.1,
        contribution=8.0,
        evidence_codes=("TEMPO_SHIFT_FEASIBLE",),
        details=details,
    )
    details["delta"] = 99.0
    assert dimension.details == {"delta": 1.0}
    assert isinstance(dimension.details, MappingProxyType)
    with pytest.raises(TypeError):
        dimension.details["delta"] = 2.0


def test_dimension_rejects_inconsistent_contribution() -> None:
    with pytest.raises(ValueError, match="contribution"):
        DimensionAssessment(
            name=DimensionName.TEMPO,
            score=80.0,
            confidence=0.9,
            weight=0.1,
            contribution=7.0,
            evidence_codes=("TEMPO_SHIFT_FEASIBLE",),
        )

def test_string_enum_text_representation_remains_legacy_compatible() -> None:
    assert str(TransitionClass.SAFE) == "TransitionClass.SAFE"
    assert str(TransitionProfile.BALANCED) == "TransitionProfile.BALANCED"
    assert str(DimensionName.TEMPO) == "DimensionName.TEMPO"
    assert str(UserDecisionType.ACCEPT) == "UserDecisionType.ACCEPT"
