from __future__ import annotations

import hashlib
import json
from typing import Any

from core.transition.classification import classify_transition
from core.transition.contracts import (
    DimensionAssessment,
    DimensionName,
    TransitionAnalysisResult,
    TransitionAssessment,
    TransitionExplanation,
    TransitionProfile,
    TransitionRecommendation,
)
from core.transition.dimensions import (
    _identifier,
    assess_bass,
    assess_energy,
    assess_phrase,
    assess_rhythm,
    assess_tempo,
    assess_tonal,
    assess_vocal,
)
from core.transition.profiles import weights_for

ANALYSIS_VERSION = "transition-analysis-v1"
ASSESSMENT_VERSION = "transition-assessment-v1"

CRITICAL_RISK_CODES = {
    "TEMPO_SHIFT_LARGE",
    "ENERGY_DISCONTINUITY",
    "VOCAL_OVERLAP_HIGH",
    "BASS_OVERLAP_HIGH",
}


def _stable_id(prefix: str, payload: object) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    return f"{prefix}_{digest[:24]}"


def _analysis(a: Any, b: Any, profile: TransitionProfile) -> TransitionAnalysisResult:
    weights = weights_for(profile)
    dimensions: list[DimensionAssessment] = [
        assess_phrase(a, b, weights[DimensionName.PHRASE]),
        assess_energy(a, b, weights[DimensionName.ENERGY]),
        assess_rhythm(a, b, weights[DimensionName.RHYTHM]),
        assess_tonal(a, b, weights[DimensionName.TONAL]),
        assess_tempo(a, b, weights[DimensionName.TEMPO]),
        assess_bass(a, b, weights[DimensionName.BASS_COLLISION]),
        assess_vocal(a, b, weights[DimensionName.VOCAL_COLLISION]),
    ]

    overall_score = round(sum(d.contribution for d in dimensions), 3)
    available = [dimension for dimension in dimensions if not dimension.unavailable]
    evidence_coverage = round(sum(d.weight for d in available), 4)
    if evidence_coverage > 0:
        confidence = min(
            1.0,
            sum(d.confidence * d.weight for d in available) / evidence_coverage,
        )
    else:
        confidence = 0.0

    critical = tuple(
        sorted(
            {
                risk
                for dimension in dimensions
                if not dimension.unavailable and dimension.confidence >= 0.6
                for risk in dimension.risk_codes
                if risk in CRITICAL_RISK_CODES
            }
        )
    )
    track_a_id = _identifier(a)
    track_b_id = _identifier(b)
    analysis_payload = {
        "track_a_id": track_a_id,
        "track_b_id": track_b_id,
        "profile": profile.value,
        "analysis_version": ANALYSIS_VERSION,
        "dimensions": [
            {
                "name": d.name.value,
                "score": round(d.score, 6),
                "confidence": round(d.confidence, 6),
                "weight": round(d.weight, 6),
                "contribution": round(d.contribution, 6),
                "evidence_codes": list(d.evidence_codes),
                "risk_codes": list(d.risk_codes),
                "unavailable": d.unavailable,
                "details": dict(d.details),
            }
            for d in dimensions
        ],
    }

    return TransitionAnalysisResult(
        analysis_id=_stable_id("analysis", analysis_payload),
        track_a_id=track_a_id,
        track_b_id=track_b_id,
        profile=profile,
        dimensions=tuple(dimensions),
        overall_score=overall_score,
        overall_confidence=round(confidence, 4),
        evidence_coverage=evidence_coverage,
        critical_risks=critical,
        analysis_version=ANALYSIS_VERSION,
    )


def _recommendation(
    result: TransitionAnalysisResult,
    assessment_id: str,
) -> TransitionRecommendation:
    classification = classify_transition(result)
    risk_codes = {
        risk
        for dimension in result.dimensions
        for risk in dimension.risk_codes
    }
    evidence_codes = {
        evidence
        for dimension in result.dimensions
        for evidence in dimension.evidence_codes
    }
    phrase_available = "PHRASE_BOUNDARIES_UNAVAILABLE" not in evidence_codes

    instructions: list[str] = []
    if phrase_available:
        strategy = "phrase_aligned_blend"
        overlap: int | None = 16
    else:
        strategy = "preview_required_manual_transition"
        overlap = None
        instructions.append("set_transition_points_by_ear")

    if "MELODIC_OVERLAP_RISK" in risk_codes:
        strategy = (
            "percussion_only_short_transition"
            if phrase_available
            else "percussion_only_preview_required"
        )
        overlap = 16 if phrase_available else None
        instructions.append("avoid_long_melodic_overlap")

    if "BASS_ACTIVITY_UNAVAILABLE" in evidence_codes:
        instructions.append("verify_bass_handoff_by_ear")

    if "VOCAL_ACTIVITY_UNAVAILABLE" in evidence_codes:
        instructions.append("do_not_overlap_lead_vocals_without_preview")

    if "TEMPO_SHIFT_LARGE" in risk_codes:
        strategy = "cut_or_effect_transition"
        overlap = None
        instructions.append("avoid_long_tempo_blend")

    if classification.value == "creative":
        strategy = (
            "controlled_tension_transition"
            if phrase_available
            else "controlled_tension_preview_required"
        )
        overlap = overlap if phrase_available else None
        instructions.append("use_harmonic_tension_intentionally")

    uncertainty = (
        result.overall_confidence < 0.7
        or result.evidence_coverage < 0.8
        or any(d.unavailable for d in result.dimensions)
    )
    if uncertainty:
        instructions.append("preview_required")

    return TransitionRecommendation(
        assessment_id=assessment_id,
        classification=classification,
        strategy_code=strategy,
        overlap_beats=overlap,
        instructions=tuple(dict.fromkeys(instructions)),
        preview_required=uncertainty or classification.value in {"unknown", "risky"},
    )


def _explanation(
    result: TransitionAnalysisResult,
    recommendation: TransitionRecommendation,
    assessment_id: str,
) -> TransitionExplanation:
    positives: list[str] = []
    risks: list[str] = []
    uncertainty: list[str] = []

    for dimension in result.dimensions:
        if dimension.unavailable:
            uncertainty.extend(dimension.evidence_codes)
        elif dimension.score >= 70.0:
            positives.extend(dimension.evidence_codes)
        risks.extend(dimension.risk_codes)

    summary = f"TRANSITION_{recommendation.classification.value.upper()}"
    return TransitionExplanation(
        assessment_id=assessment_id,
        summary_code=summary,
        positive_reasons=tuple(dict.fromkeys(positives)),
        risk_reasons=tuple(dict.fromkeys(risks)),
        uncertainty_reasons=tuple(dict.fromkeys(uncertainty)),
    )


def assess_transition(
    a: Any,
    b: Any,
    *,
    profile: TransitionProfile = TransitionProfile.BALANCED,
) -> TransitionAssessment:
    analysis = _analysis(a, b, profile)
    assessment_id = _stable_id(
        "assessment",
        {
            "analysis_id": analysis.analysis_id,
            "assessment_version": ASSESSMENT_VERSION,
        },
    )
    recommendation = _recommendation(analysis, assessment_id)
    explanation = _explanation(analysis, recommendation, assessment_id)
    return TransitionAssessment(
        assessment_id=assessment_id,
        analysis=analysis,
        recommendation=recommendation,
        explanation=explanation,
        assessment_version=ASSESSMENT_VERSION,
    )
