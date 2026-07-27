from __future__ import annotations

from typing import Any

from core.transition.contracts import DimensionAssessment, DimensionName
from core.transition.tonal import assess_tonal_relation


def _value(track: Any, name: str) -> Any:
    if isinstance(track, dict):
        return track.get(name)
    return getattr(track, name, None)


def _identifier(track: Any) -> str:
    return str(_value(track, "track_id") or _value(track, "id") or "unknown")


def _confidence_adjust(raw_score: float, confidence: float) -> float:
    return 50.0 + confidence * (raw_score - 50.0)


def _pair_confidence(a: Any, b: Any, *names: str) -> float | None:
    for name in names:
        value_a = _value(a, name)
        value_b = _value(b, name)
        if value_a is not None and value_b is not None:
            return min(
                max(0.0, min(1.0, float(value_a))),
                max(0.0, min(1.0, float(value_b))),
            )
    return None


def unavailable(
    name: DimensionName,
    weight: float,
    code: str,
    *,
    details: dict[str, Any] | None = None,
    risk_codes: tuple[str, ...] = ("PREVIEW_REQUIRED",),
) -> DimensionAssessment:
    return DimensionAssessment(
        name=name,
        score=50.0,
        confidence=0.0,
        weight=weight,
        contribution=50.0 * weight,
        evidence_codes=(code,),
        risk_codes=risk_codes,
        unavailable=True,
        details=details or {},
    )


def assess_tonal(a: Any, b: Any, weight: float) -> DimensionAssessment:
    result = assess_tonal_relation(
        _value(a, "camelot") or _value(a, "key"),
        _value(b, "camelot") or _value(b, "key"),
        confidence_a=_value(a, "key_confidence"),
        confidence_b=_value(b, "key_confidence"),
    )
    details = {"relation": result.relation.value, "distance": result.distance}
    if result.relation.value == "unknown":
        return unavailable(
            DimensionName.TONAL,
            weight,
            "KEY_ANALYSIS_UNAVAILABLE",
            details=details,
        )
    if result.confidence == 0.0:
        return unavailable(
            DimensionName.TONAL,
            weight,
            "KEY_CONFIDENCE_UNAVAILABLE",
            details=details,
            risk_codes=result.risk_codes or ("PREVIEW_REQUIRED",),
        )

    effective = _confidence_adjust(result.score, result.confidence)
    return DimensionAssessment(
        name=DimensionName.TONAL,
        score=effective,
        confidence=result.confidence,
        weight=weight,
        contribution=effective * weight,
        evidence_codes=result.evidence_codes,
        risk_codes=result.risk_codes,
        details=details,
    )


def assess_tempo(a: Any, b: Any, weight: float) -> DimensionAssessment:
    bpm_a = _value(a, "bpm")
    bpm_b = _value(b, "bpm")
    if bpm_a is None or bpm_b is None:
        return unavailable(DimensionName.TEMPO, weight, "TEMPO_ANALYSIS_UNAVAILABLE")

    bpm_a = float(bpm_a)
    bpm_b = float(bpm_b)
    candidates = [
        abs(bpm_a - bpm_b),
        abs(bpm_a - bpm_b * 2.0),
        abs(bpm_a * 2.0 - bpm_b),
        abs(bpm_a - bpm_b / 2.0),
        abs(bpm_a / 2.0 - bpm_b),
    ]
    delta = min(candidates)
    confidence = _pair_confidence(a, b, "bpm_confidence")
    if confidence is None:
        return unavailable(
            DimensionName.TEMPO,
            weight,
            "TEMPO_CONFIDENCE_UNAVAILABLE",
            details={"effective_bpm_delta": round(delta, 3)},
        )

    raw = max(0.0, 100.0 - delta * 10.0)
    effective = _confidence_adjust(raw, confidence)
    risks = ()
    evidence = ("TEMPO_SHIFT_FEASIBLE",)
    if delta > 6.0:
        risks = ("TEMPO_SHIFT_LARGE",)
        evidence = ("TEMPO_SHIFT_DIFFICULT",)
    return DimensionAssessment(
        name=DimensionName.TEMPO,
        score=effective,
        confidence=confidence,
        weight=weight,
        contribution=effective * weight,
        evidence_codes=evidence,
        risk_codes=risks,
        details={"effective_bpm_delta": round(delta, 3)},
    )


def assess_energy(a: Any, b: Any, weight: float) -> DimensionAssessment:
    energy_a = _value(a, "energy")
    energy_b = _value(b, "energy")
    if energy_a is None or energy_b is None:
        return unavailable(DimensionName.ENERGY, weight, "ENERGY_ANALYSIS_UNAVAILABLE")

    delta = float(energy_b) - float(energy_a)
    absolute = abs(delta)
    confidence = _pair_confidence(a, b, "energy_confidence")
    if confidence is None:
        return unavailable(
            DimensionName.ENERGY,
            weight,
            "ENERGY_CONFIDENCE_UNAVAILABLE",
            details={"energy_delta": round(delta, 4)},
        )

    raw = max(0.0, 100.0 - absolute * 100.0)
    if 0.05 <= delta <= 0.25:
        raw = min(100.0, raw + 10.0)
        evidence = ("ENERGY_LIFT_CONTROLLED",)
    elif absolute <= 0.12:
        evidence = ("ENERGY_STEP_SMOOTH",)
    elif delta > 0.35:
        evidence = ("ENERGY_LIFT_STEEP",)
    else:
        evidence = ("ENERGY_DROP_SIGNIFICANT",)

    effective = _confidence_adjust(raw, confidence)
    risks = ("ENERGY_DISCONTINUITY",) if absolute > 0.35 else ()
    return DimensionAssessment(
        name=DimensionName.ENERGY,
        score=effective,
        confidence=confidence,
        weight=weight,
        contribution=effective * weight,
        evidence_codes=evidence,
        risk_codes=risks,
        details={"energy_delta": round(delta, 4)},
    )


def assess_rhythm(a: Any, b: Any, weight: float) -> DimensionAssessment:
    percussive_a = _value(a, "percussive_ratio")
    percussive_b = _value(b, "percussive_ratio")
    if percussive_a is None or percussive_b is None:
        return unavailable(DimensionName.RHYTHM, weight, "RHYTHM_FEATURES_UNAVAILABLE")

    delta = abs(float(percussive_a) - float(percussive_b))
    confidence = _pair_confidence(
        a,
        b,
        "percussive_confidence",
        "rhythm_confidence",
    )
    if confidence is None:
        return unavailable(
            DimensionName.RHYTHM,
            weight,
            "RHYTHM_CONFIDENCE_UNAVAILABLE",
            details={"percussive_ratio_delta": round(delta, 4)},
        )

    raw = max(0.0, 100.0 - delta * 100.0)
    effective = _confidence_adjust(raw, confidence)
    return DimensionAssessment(
        name=DimensionName.RHYTHM,
        score=effective,
        confidence=confidence,
        weight=weight,
        contribution=effective * weight,
        evidence_codes=("RHYTHM_PERCUSSIVE_SIMILARITY",),
        risk_codes=("RHYTHM_CONTRAST_HIGH",) if delta > 0.4 else (),
        details={"percussive_ratio_delta": round(delta, 4)},
    )


def assess_bass(a: Any, b: Any, weight: float) -> DimensionAssessment:
    del a, b
    return unavailable(
        DimensionName.BASS_COLLISION,
        weight,
        "BASS_ACTIVITY_UNAVAILABLE",
        risk_codes=("BASS_PREVIEW_REQUIRED", "PREVIEW_REQUIRED"),
    )


def assess_phrase(a: Any, b: Any, weight: float) -> DimensionAssessment:
    del a, b
    return unavailable(DimensionName.PHRASE, weight, "PHRASE_BOUNDARIES_UNAVAILABLE")


def assess_vocal(a: Any, b: Any, weight: float) -> DimensionAssessment:
    del a, b
    return unavailable(DimensionName.VOCAL_COLLISION, weight, "VOCAL_ACTIVITY_UNAVAILABLE")


__all__ = [
    "_identifier",
    "assess_bass",
    "assess_energy",
    "assess_phrase",
    "assess_rhythm",
    "assess_tempo",
    "assess_tonal",
    "assess_vocal",
]
