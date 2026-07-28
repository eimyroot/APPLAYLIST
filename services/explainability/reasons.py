from __future__ import annotations

from dataclasses import asdict
from typing import Any

from core.energy_curve import target_energy
from core.harmonic import camelot_compatible
from core.transition.contracts import TransitionProfile
from services.composer.scoring import score_transition
from services.transition.assessment_service import assess_pair


def explain_transition(a: Any, b: Any, position: float) -> dict[str, Any]:
    """Explain the exact legacy composer ranking contributions."""

    reasons = []
    if getattr(a, "bpm", None) is not None and getattr(b, "bpm", None) is not None:
        diff = abs(float(a.bpm) - float(b.bpm))
        contribution = max(0.0, 1.0 - diff / 10.0)
        reasons.append(
            {
                "code": "bpm_delta",
                "value": round(diff, 3),
                "good": diff <= 5.0,
                "contribution": round(contribution, 6),
            }
        )

    harmonic_ok = camelot_compatible(
        getattr(a, "camelot", None),
        getattr(b, "camelot", None),
    )
    reasons.append(
        {
            "code": "harmonic_compatible",
            "value": harmonic_ok,
            "good": harmonic_ok,
            "contribution": 1.0 if harmonic_ok else 0.0,
        }
    )

    if getattr(a, "energy", None) is not None and getattr(b, "energy", None) is not None:
        transition_energy = max(
            0.0,
            1.0 - abs(float(a.energy) - float(b.energy)),
        )
        reasons.append(
            {
                "code": "energy_pair_alignment",
                "value": round(abs(float(a.energy) - float(b.energy)), 3),
                "good": abs(float(a.energy) - float(b.energy)) <= 0.25,
                "contribution": round(transition_energy, 6),
            }
        )

    target = target_energy(position)
    candidate_energy = getattr(b, "energy", None)
    energy_target_bonus = 0.0
    if candidate_energy is not None:
        energy_target_bonus = 1.0 - abs(float(candidate_energy) - target)
        reasons.append(
            {
                "code": "energy_target_alignment",
                "value": round(abs(float(candidate_energy) - target), 3),
                "good": abs(float(candidate_energy) - target) <= 0.25,
                "contribution": round(energy_target_bonus, 6),
            }
        )

    base_score = score_transition(a, b)
    return {
        "schema_version": "composer-explanation-v1",
        "position": round(position, 3),
        "target_energy": round(target, 3),
        "base_transition_score": round(base_score, 6),
        "energy_target_bonus": round(energy_target_bonus, 6),
        "ranking_score": round(base_score + energy_target_bonus, 6),
        "reasons": reasons,
    }


def explain_transition_intelligence(
    a: Any,
    b: Any,
    *,
    profile: TransitionProfile | str = TransitionProfile.BALANCED,
) -> dict[str, Any]:
    """Expose the versioned Transition Intelligence assessment explanation."""

    assessment = assess_pair(a, b, profile=profile)
    reasons = [
        {
            "code": dimension.name.value,
            "value": round(dimension.score, 3),
            "good": dimension.score >= 70.0 and not dimension.unavailable,
            "confidence": round(dimension.confidence, 4),
            "weight": round(dimension.weight, 4),
            "contribution": round(dimension.contribution, 3),
            "evidence_codes": list(dimension.evidence_codes),
            "risk_codes": list(dimension.risk_codes),
            "unavailable": dimension.unavailable,
        }
        for dimension in assessment.analysis.dimensions
    ]
    return {
        "schema_version": "transition-explanation-v1",
        "assessment_id": assessment.assessment_id,
        "analysis_id": assessment.analysis.analysis_id,
        "transition_score": assessment.analysis.overall_score,
        "confidence": assessment.analysis.overall_confidence,
        "evidence_coverage": assessment.analysis.evidence_coverage,
        "classification": assessment.recommendation.classification.value,
        "recommended_strategy": assessment.recommendation.strategy_code,
        "recommended_overlap_beats": assessment.recommendation.overlap_beats,
        "instructions": list(assessment.recommendation.instructions),
        "preview_required": assessment.recommendation.preview_required,
        "explanation": asdict(assessment.explanation),
        "reasons": reasons,
    }
