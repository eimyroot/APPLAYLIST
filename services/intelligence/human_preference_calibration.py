from __future__ import annotations

import hashlib
import json
from collections import Counter

from core.intelligence.competitive_curation_contract import (
    ShadowPathComparison,
    ShadowPathPreference,
)
from core.intelligence.curated_real_library_review_contract import (
    BlindedPlanAssignment,
    CuratedReviewCase,
    HumanDJReview,
    HumanPlanPreference,
)
from core.intelligence.human_preference_calibration_contract import (
    CalibrationVerdict,
    CasePreferenceCalibration,
    HumanPreferenceCalibrationPolicy,
    HumanPreferenceCalibrationReport,
    PreferenceConfusionCell,
    ResolvedPreference,
)


class HumanPreferenceCalibrationError(ValueError):
    """Fail-closed error for invalid human/challenger calibration bindings."""


def _stable_id(prefix: str, payload: object) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return f"{prefix}:{hashlib.sha256(encoded).hexdigest()}"


def _plan_strategy_map(case: CuratedReviewCase) -> dict[str, ResolvedPreference]:
    return {
        case.greedy_plan.plan_id: ResolvedPreference.GREEDY,
        case.beam_plan.plan_id: ResolvedPreference.BEAM,
    }


def _path_strategy_map(case: CuratedReviewCase) -> dict[str, ResolvedPreference]:
    return {
        case.greedy_plan.path_id: ResolvedPreference.GREEDY,
        case.beam_plan.path_id: ResolvedPreference.BEAM,
    }


def _resolve_human_preference(
    *,
    case: CuratedReviewCase,
    assignment: BlindedPlanAssignment,
    review: HumanDJReview,
) -> ResolvedPreference:
    if assignment.case_id != case.case_id:
        raise HumanPreferenceCalibrationError("blind assignment case_id does not match review case")
    if review.assignment_id != assignment.assignment_id:
        raise HumanPreferenceCalibrationError("human review assignment_id does not match blind assignment")
    if not assignment.algorithm_identity_hidden or not review.algorithm_identity_was_hidden:
        raise HumanPreferenceCalibrationError("calibration requires genuinely blinded human review evidence")

    by_plan = _plan_strategy_map(case)
    expected_plan_ids = set(by_plan)
    assigned_plan_ids = {assignment.slot_a_plan_id, assignment.slot_b_plan_id}
    if assigned_plan_ids != expected_plan_ids:
        raise HumanPreferenceCalibrationError("blind assignment does not bind exactly to case source plans")

    if review.preference is HumanPlanPreference.PLAN_A:
        return by_plan[assignment.slot_a_plan_id]
    if review.preference is HumanPlanPreference.PLAN_B:
        return by_plan[assignment.slot_b_plan_id]
    if review.preference is HumanPlanPreference.TIE:
        return ResolvedPreference.TIE
    if review.preference is HumanPlanPreference.ABSTAIN:
        return ResolvedPreference.ABSTAIN
    raise HumanPreferenceCalibrationError("unsupported human preference")


def _resolve_challenger_preference(
    *,
    case: CuratedReviewCase,
    comparison: ShadowPathComparison,
) -> ResolvedPreference:
    by_path = _path_strategy_map(case)
    expected_paths = set(by_path)
    comparison_paths = {comparison.left_path_id, comparison.right_path_id}
    if comparison_paths != expected_paths:
        raise HumanPreferenceCalibrationError("shadow comparison does not bind exactly to case source paths")
    if comparison.activation_authorized:
        raise HumanPreferenceCalibrationError("shadow comparison must not authorize activation")

    if comparison.preference is ShadowPathPreference.LEFT:
        return by_path[comparison.left_path_id]
    if comparison.preference is ShadowPathPreference.RIGHT:
        return by_path[comparison.right_path_id]
    if comparison.preference is ShadowPathPreference.TIE:
        return ResolvedPreference.TIE
    if comparison.preference is ShadowPathPreference.NOT_PROVEN:
        return ResolvedPreference.NOT_PROVEN
    raise HumanPreferenceCalibrationError("unsupported challenger preference")


def calibrate_case_preference(
    *,
    case: CuratedReviewCase,
    assignment: BlindedPlanAssignment,
    review: HumanDJReview,
    comparison: ShadowPathComparison,
) -> CasePreferenceCalibration:
    """Bind one completed blinded human judgment to one shadow challenger decision."""
    human = _resolve_human_preference(case=case, assignment=assignment, review=review)
    challenger = _resolve_challenger_preference(case=case, comparison=comparison)

    exact_agreement: bool | None
    decisive_agreement: bool | None
    reasons: list[str] = []

    if human is ResolvedPreference.ABSTAIN:
        exact_agreement = None
        decisive_agreement = None
        reasons.append("human_abstain_excluded_from_accuracy")
    else:
        exact_agreement = human is challenger
        if exact_agreement:
            reasons.append("challenger_exactly_agrees_with_human")
        else:
            reasons.append("challenger_disagrees_with_human")

        if human in (ResolvedPreference.GREEDY, ResolvedPreference.BEAM):
            decisive_agreement = human is challenger
            if challenger is ResolvedPreference.TIE:
                reasons.append("challenger_tie_on_human_decisive")
            elif challenger is ResolvedPreference.NOT_PROVEN:
                reasons.append("challenger_not_proven_on_human_decisive")
        else:
            decisive_agreement = None

        if human is ResolvedPreference.TIE and challenger in (
            ResolvedPreference.GREEDY,
            ResolvedPreference.BEAM,
        ):
            reasons.append("challenger_false_winner_on_human_tie")

    if challenger is ResolvedPreference.NOT_PROVEN:
        reasons.append("challenger_preference_not_proven")

    return CasePreferenceCalibration(
        case_id=case.case_id,
        set_role=case.set_role,
        review_id=review.review_id,
        reviewer_ref=review.reviewer_ref,
        assignment_id=assignment.assignment_id,
        human_preference=human,
        challenger_preference=challenger,
        human_confidence=review.confidence,
        exact_agreement=exact_agreement,
        decisive_agreement=decisive_agreement,
        human_algorithm_identity_hidden=True,
        source_identity_preserved=True,
        reason_codes=tuple(reasons),
        activation_authorized=False,
        personal_dj_model_training_authorized=False,
    )


def _rate(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return numerator / denominator


def build_human_preference_calibration_report(
    *,
    all_cases: tuple[CuratedReviewCase, ...],
    case_evidence: tuple[CasePreferenceCalibration, ...],
    policy: HumanPreferenceCalibrationPolicy = HumanPreferenceCalibrationPolicy(),
) -> HumanPreferenceCalibrationReport:
    """Aggregate genuine case calibration evidence without granting optimizer authority."""
    cases = tuple(sorted(all_cases, key=lambda item: item.case_id))
    evidence = tuple(sorted(case_evidence, key=lambda item: (item.case_id, item.review_id)))
    if not cases:
        raise HumanPreferenceCalibrationError("calibration requires at least one source case")

    case_ids = [item.case_id for item in cases]
    if len(set(case_ids)) != len(case_ids):
        raise HumanPreferenceCalibrationError("source case identities must be unique")
    known_cases = {item.case_id: item for item in cases}

    review_ids: set[str] = set()
    reviewed_case_ids: set[str] = set()
    for item in evidence:
        if item.case_id not in known_cases:
            raise HumanPreferenceCalibrationError("calibration evidence references unknown case")
        if item.set_role is not known_cases[item.case_id].set_role:
            raise HumanPreferenceCalibrationError("calibration evidence set role mismatches source case")
        if item.review_id in review_ids:
            raise HumanPreferenceCalibrationError("duplicate human review identity in calibration evidence")
        review_ids.add(item.review_id)
        reviewed_case_ids.add(item.case_id)
        if item.activation_authorized or item.personal_dj_model_training_authorized:
            raise HumanPreferenceCalibrationError("case evidence exceeds R2 authority")

    non_abstain = [item for item in evidence if item.human_preference is not ResolvedPreference.ABSTAIN]
    decisive = [
        item
        for item in evidence
        if item.human_preference in (ResolvedPreference.GREEDY, ResolvedPreference.BEAM)
    ]
    human_ties = [item for item in evidence if item.human_preference is ResolvedPreference.TIE]

    exact_agreement_count = sum(item.exact_agreement is True for item in non_abstain)
    decisive_agreement_count = sum(item.decisive_agreement is True for item in decisive)
    challenger_tie_count = sum(item.challenger_preference is ResolvedPreference.TIE for item in non_abstain)
    false_winner_count = sum(
        item.human_preference is ResolvedPreference.TIE
        and item.challenger_preference in (ResolvedPreference.GREEDY, ResolvedPreference.BEAM)
        for item in evidence
    )
    challenger_tie_on_decisive = sum(
        item.human_preference in (ResolvedPreference.GREEDY, ResolvedPreference.BEAM)
        and item.challenger_preference is ResolvedPreference.TIE
        for item in evidence
    )

    confidence_denominator = sum(item.human_confidence for item in decisive)
    confidence_numerator = sum(
        item.human_confidence for item in decisive if item.decisive_agreement is True
    )
    weighted_decisive = (
        None
        if confidence_denominator <= 0.0
        else confidence_numerator / confidence_denominator
    )

    reviewed_fraction = len(reviewed_case_ids) / len(cases)
    exact_rate = _rate(exact_agreement_count, len(non_abstain))
    decisive_rate = _rate(decisive_agreement_count, len(decisive))
    false_winner_rate = _rate(false_winner_count, len(human_ties))

    covered_roles = tuple(sorted({item.set_role for item in evidence}, key=lambda item: item.value))
    missing_roles = tuple(role for role in policy.required_set_roles if role not in covered_roles)

    confusion_counts: Counter[tuple[ResolvedPreference, ResolvedPreference]] = Counter()
    for item in non_abstain:
        confusion_counts[(item.human_preference, item.challenger_preference)] += 1
    confusion = tuple(
        PreferenceConfusionCell(
            human_preference=human,
            challenger_preference=challenger,
            count=count,
        )
        for (human, challenger), count in sorted(
            confusion_counts.items(),
            key=lambda item: (item[0][0].value, item[0][1].value),
        )
    )

    explanations: list[str] = []
    incomplete = False
    if len(cases) < policy.minimum_cases:
        incomplete = True
        explanations.append("calibration_case_count_below_policy")
    if reviewed_fraction < policy.minimum_reviewed_case_fraction:
        incomplete = True
        explanations.append("calibration_reviewed_case_fraction_below_policy")
    if len(decisive) < policy.minimum_decisive_judgments:
        incomplete = True
        explanations.append("calibration_decisive_judgments_below_policy")
    if missing_roles:
        incomplete = True
        explanations.append("calibration_required_set_roles_missing")

    if incomplete:
        verdict = CalibrationVerdict.INCOMPLETE
    else:
        failed = False
        if exact_rate is None or exact_rate < policy.minimum_exact_agreement_rate:
            failed = True
            explanations.append("calibration_exact_agreement_below_policy")
        if decisive_rate is None or decisive_rate < policy.minimum_decisive_agreement_rate:
            failed = True
            explanations.append("calibration_decisive_agreement_below_policy")
        if (
            weighted_decisive is None
            or weighted_decisive < policy.minimum_confidence_weighted_decisive_agreement
        ):
            failed = True
            explanations.append("calibration_confidence_weighted_agreement_below_policy")
        if (
            false_winner_rate is not None
            and false_winner_rate > policy.maximum_false_winner_on_human_tie_rate
        ):
            failed = True
            explanations.append("calibration_false_winner_on_human_tie_above_policy")
        verdict = (
            CalibrationVerdict.DOES_NOT_SUPPORT_ACTIVATION
            if failed
            else CalibrationVerdict.SUPPORTS_FURTHER_EVALUATION
        )
        if not failed:
            explanations.append("calibration_supports_further_evaluation_only")

    payload = {
        "policy": [policy.policy_id, policy.policy_version],
        "cases": case_ids,
        "evidence": [
            {
                "case_id": item.case_id,
                "review_id": item.review_id,
                "human": item.human_preference.value,
                "challenger": item.challenger_preference.value,
                "confidence": item.human_confidence,
            }
            for item in evidence
        ],
    }

    return HumanPreferenceCalibrationReport(
        report_id=_stable_id("human-preference-calibration", payload),
        policy_ref=(policy.policy_id, policy.policy_version),
        case_count=len(cases),
        reviewed_case_count=len(reviewed_case_ids),
        abstain_count=sum(item.human_preference is ResolvedPreference.ABSTAIN for item in evidence),
        decisive_human_count=len(decisive),
        exact_agreement_count=exact_agreement_count,
        decisive_agreement_count=decisive_agreement_count,
        human_tie_count=len(human_ties),
        challenger_tie_count=challenger_tie_count,
        false_winner_on_human_tie_count=false_winner_count,
        challenger_tie_on_human_decisive_count=challenger_tie_on_decisive,
        reviewed_case_fraction=reviewed_fraction,
        exact_agreement_rate=exact_rate,
        decisive_agreement_rate=decisive_rate,
        confidence_weighted_decisive_agreement=weighted_decisive,
        false_winner_on_human_tie_rate=false_winner_rate,
        covered_set_roles=covered_roles,
        missing_set_roles=missing_roles,
        confusion_matrix=confusion,
        case_evidence=evidence,
        verdict=verdict,
        explanation_codes=tuple(explanations),
        activation_authorized=False,
        personal_dj_model_training_authorized=False,
    )


__all__ = [
    "HumanPreferenceCalibrationError",
    "build_human_preference_calibration_report",
    "calibrate_case_preference",
]
