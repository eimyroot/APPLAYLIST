from __future__ import annotations

from core.transition.contracts import DimensionName, TransitionProfile

PROFILE_WEIGHTS: dict[TransitionProfile, dict[DimensionName, float]] = {
    TransitionProfile.BALANCED: {
        DimensionName.PHRASE: 0.20,
        DimensionName.ENERGY: 0.17,
        DimensionName.RHYTHM: 0.17,
        DimensionName.TONAL: 0.15,
        DimensionName.TEMPO: 0.13,
        DimensionName.BASS_COLLISION: 0.10,
        DimensionName.VOCAL_COLLISION: 0.08,
    },
    TransitionProfile.LONG_MELODIC_OVERLAP: {
        DimensionName.PHRASE: 0.22,
        DimensionName.ENERGY: 0.14,
        DimensionName.RHYTHM: 0.12,
        DimensionName.TONAL: 0.25,
        DimensionName.TEMPO: 0.09,
        DimensionName.BASS_COLLISION: 0.10,
        DimensionName.VOCAL_COLLISION: 0.08,
    },
    TransitionProfile.SHORT_PERCUSSION: {
        DimensionName.PHRASE: 0.18,
        DimensionName.ENERGY: 0.19,
        DimensionName.RHYTHM: 0.24,
        DimensionName.TONAL: 0.10,
        DimensionName.TEMPO: 0.15,
        DimensionName.BASS_COLLISION: 0.09,
        DimensionName.VOCAL_COLLISION: 0.05,
    },
    TransitionProfile.CREATIVE_TENSION: {
        DimensionName.PHRASE: 0.20,
        DimensionName.ENERGY: 0.20,
        DimensionName.RHYTHM: 0.19,
        DimensionName.TONAL: 0.12,
        DimensionName.TEMPO: 0.11,
        DimensionName.BASS_COLLISION: 0.11,
        DimensionName.VOCAL_COLLISION: 0.07,
    },
}


ANALYSIS_DIMENSIONS = frozenset(
    {
        DimensionName.PHRASE,
        DimensionName.ENERGY,
        DimensionName.RHYTHM,
        DimensionName.TONAL,
        DimensionName.TEMPO,
        DimensionName.BASS_COLLISION,
        DimensionName.VOCAL_COLLISION,
    }
)


def weights_for(profile: TransitionProfile) -> dict[DimensionName, float]:
    weights = dict(PROFILE_WEIGHTS[profile])
    if set(weights) != ANALYSIS_DIMENSIONS:
        raise RuntimeError(f"transition profile dimensions are incomplete: {profile}")
    if abs(sum(weights.values()) - 1.0) > 1e-9:
        raise RuntimeError(f"transition profile weights do not sum to 1: {profile}")
    tonal_weight = weights[DimensionName.TONAL]
    if not 0.10 <= tonal_weight <= 0.25:
        raise RuntimeError(f"tonal weight outside product invariant: {tonal_weight}")
    return weights
