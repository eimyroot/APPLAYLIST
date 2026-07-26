from types import SimpleNamespace

import pytest

from core.transition.contracts import DimensionName, TransitionClass, TransitionProfile
from core.transition.engine import assess_transition
from core.transition.profiles import weights_for


def track(
    track_id: str,
    *,
    bpm: float | None = 128.0,
    bpm_confidence: float | None = 0.9,
    camelot: str | None = "8A",
    key_confidence: float | None = 0.9,
    energy: float | None = 0.6,
    energy_confidence: float | None = 0.8,
    percussive_ratio: float | None = 0.7,
    percussive_confidence: float | None = 0.75,
    harmonic_ratio: float | None = 0.4,
):
    return SimpleNamespace(
        track_id=track_id,
        bpm=bpm,
        bpm_confidence=bpm_confidence,
        camelot=camelot,
        key_confidence=key_confidence,
        energy=energy,
        energy_confidence=energy_confidence,
        percussive_ratio=percussive_ratio,
        percussive_confidence=percussive_confidence,
        harmonic_ratio=harmonic_ratio,
    )


def by_name(result, name: DimensionName):
    return next(d for d in result.analysis.dimensions if d.name is name)


def test_assessment_is_deterministic_and_linked() -> None:
    a = track("a")
    b = track("b", bpm=129.0, energy=0.68)
    results = [assess_transition(a, b) for _ in range(100)]
    assert all(result == results[0] for result in results)
    result = results[0]
    assert result.assessment_id
    assert result.analysis.analysis_id
    assert result.recommendation.assessment_id == result.assessment_id
    assert result.explanation.assessment_id == result.assessment_id


def test_unknown_data_reduces_confidence_not_score_to_zero() -> None:
    result = assess_transition(
        track(
            "a",
            camelot=None,
            percussive_ratio=None,
            harmonic_ratio=None,
        ),
        track(
            "b",
            camelot=None,
            percussive_ratio=None,
            harmonic_ratio=None,
        ),
    )
    assert result.analysis.overall_score > 0.0
    assert result.recommendation.classification in {
        TransitionClass.UNKNOWN,
        TransitionClass.POSSIBLE,
    }
    assert result.recommendation.preview_required is True


def test_bass_is_unavailable_even_when_harmonic_ratio_exists() -> None:
    result = assess_transition(track("a"), track("b"))
    bass = by_name(result, DimensionName.BASS_COLLISION)
    assert bass.unavailable is True
    assert bass.confidence == 0.0
    assert bass.evidence_codes == ("BASS_ACTIVITY_UNAVAILABLE",)
    assert "BASS_WHOLE_TRACK_PROXY" not in bass.evidence_codes


def test_no_precise_phrase_recommendation_without_phrase_evidence() -> None:
    result = assess_transition(track("a"), track("b"))
    phrase = by_name(result, DimensionName.PHRASE)
    assert phrase.unavailable is True
    assert result.recommendation.overlap_beats is None
    assert result.recommendation.strategy_code != "phrase_aligned_blend"
    assert "set_transition_points_by_ear" in result.recommendation.instructions


def test_missing_measurement_confidence_is_not_fabricated() -> None:
    result = assess_transition(
        track(
            "a",
            bpm_confidence=None,
            key_confidence=None,
            energy_confidence=None,
            percussive_confidence=None,
        ),
        track(
            "b",
            bpm_confidence=None,
            key_confidence=None,
            energy_confidence=None,
            percussive_confidence=None,
        ),
    )
    for name in {
        DimensionName.TEMPO,
        DimensionName.TONAL,
        DimensionName.ENERGY,
        DimensionName.RHYTHM,
    }:
        dimension = by_name(result, name)
        assert dimension.unavailable is True
        assert dimension.confidence == 0.0


def test_strategy_fit_does_not_inflate_coverage() -> None:
    result = assess_transition(
        track("a", bpm_confidence=None),
        track("b", bpm_confidence=None),
        profile=TransitionProfile.CREATIVE_TENSION,
    )
    assert all(d.name is not DimensionName.STRATEGY_FIT for d in result.analysis.dimensions)
    weights = weights_for(TransitionProfile.CREATIVE_TENSION)
    expected = (
        weights[DimensionName.ENERGY]
        + weights[DimensionName.RHYTHM]
        + weights[DimensionName.TONAL]
    )
    assert result.analysis.evidence_coverage == pytest.approx(expected)
    assert result.recommendation.classification is TransitionClass.UNKNOWN


def test_creative_profile_does_not_reject_distant_key() -> None:
    result = assess_transition(
        track("a", camelot="8A"),
        track("b", camelot="2B"),
        profile=TransitionProfile.CREATIVE_TENSION,
    )
    assert result.analysis.overall_score > 0.0
    assert result.recommendation.strategy_code
    assert result.recommendation.overlap_beats is None
