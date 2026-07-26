from __future__ import annotations

from core.transition.contracts import TransitionAnalysisResult, TransitionClass, TransitionProfile


def classify_transition(result: TransitionAnalysisResult) -> TransitionClass:
    if result.evidence_coverage < 0.55 or result.overall_confidence < 0.45:
        return TransitionClass.UNKNOWN

    if result.overall_score < 55.0 or result.critical_risks:
        return TransitionClass.RISKY

    if (
        result.profile is TransitionProfile.CREATIVE_TENSION
        and result.overall_score >= 60.0
    ):
        return TransitionClass.CREATIVE

    if result.overall_score >= 82.0 and result.overall_confidence >= 0.70:
        return TransitionClass.SAFE

    return TransitionClass.POSSIBLE
