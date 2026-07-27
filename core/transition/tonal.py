from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


# Preserve legacy Enum.__str__ behavior for downstream compatibility.
class TonalRelation(str, Enum):  # noqa: UP042
    SAME_KEY = "same_key"
    RELATIVE_MODE = "relative_mode"
    ADJACENT = "adjacent"
    TWO_STEPS = "two_steps"
    DISTANT = "distant"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class TonalAssessment:
    relation: TonalRelation
    score: float
    confidence: float
    evidence_codes: tuple[str, ...]
    risk_codes: tuple[str, ...] = ()
    distance: int | None = None


def _parse_camelot(value: str | None) -> tuple[int, str] | None:
    if not value:
        return None
    normalized = value.strip().upper()
    if len(normalized) < 2:
        return None
    try:
        number = int(normalized[:-1])
    except ValueError:
        return None
    mode = normalized[-1]
    if not 1 <= number <= 12 or mode not in {"A", "B"}:
        return None
    return number, mode


def _ring_distance(a: int, b: int) -> int:
    direct = abs(a - b)
    return min(direct, 12 - direct)


def _measured_confidence(
    confidence_a: float | None,
    confidence_b: float | None,
) -> float:
    if confidence_a is None or confidence_b is None:
        return 0.0
    return min(
        max(0.0, min(1.0, float(confidence_a))),
        max(0.0, min(1.0, float(confidence_b))),
    )


def assess_tonal_relation(
    key_a: str | None,
    key_b: str | None,
    *,
    confidence_a: float | None = None,
    confidence_b: float | None = None,
) -> TonalAssessment:
    parsed_a = _parse_camelot(key_a)
    parsed_b = _parse_camelot(key_b)
    if parsed_a is None or parsed_b is None:
        return TonalAssessment(
            relation=TonalRelation.UNKNOWN,
            score=50.0,
            confidence=0.0,
            evidence_codes=("KEY_ANALYSIS_UNAVAILABLE",),
            risk_codes=("PREVIEW_REQUIRED",),
        )

    confidence = _measured_confidence(confidence_a, confidence_b)
    number_a, mode_a = parsed_a
    number_b, mode_b = parsed_b
    distance = _ring_distance(number_a, number_b)

    if parsed_a == parsed_b:
        relation, score, evidence, risks = (
            TonalRelation.SAME_KEY,
            100.0,
            ("TONAL_SAME_KEY",),
            (),
        )
    elif number_a == number_b and mode_a != mode_b:
        relation, score, evidence, risks = (
            TonalRelation.RELATIVE_MODE,
            94.0,
            ("TONAL_RELATIVE_MODE",),
            (),
        )
    elif mode_a == mode_b and distance == 1:
        relation, score, evidence, risks = (
            TonalRelation.ADJACENT,
            90.0,
            ("TONAL_ADJACENT_CAMELOT",),
            (),
        )
    elif distance <= 2:
        relation, score, evidence, risks = (
            TonalRelation.TWO_STEPS,
            70.0,
            ("TONAL_MODERATE_DISTANCE",),
            ("SHORTER_OVERLAP_RECOMMENDED",),
        )
    else:
        relation, score, evidence, risks = (
            TonalRelation.DISTANT,
            38.0,
            ("TONAL_DISTANCE_HIGH",),
            ("MELODIC_OVERLAP_RISK",),
        )

    if confidence == 0.0:
        evidence = evidence + ("KEY_CONFIDENCE_UNAVAILABLE",)
        risks = risks + ("PREVIEW_REQUIRED",)
    elif confidence < 0.45:
        evidence = evidence + ("KEY_CONFIDENCE_LOW",)
        risks = risks + ("PREVIEW_REQUIRED",)

    return TonalAssessment(
        relation=relation,
        score=score,
        confidence=confidence,
        evidence_codes=evidence,
        risk_codes=risks,
        distance=distance,
    )
