from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict

from core.intelligence.competitive_curation_contract import (
    ShadowPathComparison,
    ShadowPathPreference,
)
from core.intelligence.curated_real_library_review_contract import (
    BlindedPlanAssignment,
    CuratedSetRole,
)
from core.intelligence.human_review_protocol_r2_contract import (
    Assessability,
    CurationCalibrationCaseR3,
    CurationCalibrationEvidenceR3,
    CurationCalibrationPolicyR3,
    CurationCalibrationReportR3,
    CurationCalibrationVerdict,
    CurationPreference,
    CurationReviewR2,
    HoldoutCandidate,
    HoldoutCaseSamplingPolicy,
    HoldoutSelectionEntry,
    HoldoutSelectionResult,
    MeaningfulDifferenceStatus,
    ResolvedCurationPreference,
    ReviewDatasetRole,
    TransitionDimensionEvidenceR2,
    TransitionFeasibilityDimension,
    TransitionReviewSpecR2,
    ValidationClaimScope,
    WilsonInterval,
)


class HumanReviewProtocolR2Error(ValueError):
    """Fail-closed error for Human Review Protocol R2 evidence."""


def _canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        + "\n"
    ).encode("utf-8")


def _fingerprint(prefix: str, value: object) -> str:
    return f"{prefix}:{hashlib.sha256(_canonical_json_bytes(value)).hexdigest()}"


def transition_review_spec_fingerprint(spec: TransitionReviewSpecR2) -> str:
    """Bind every transition-review parameter to a deterministic identity."""
    return _fingerprint("transition-review-spec-r2", asdict(spec))


def not_assessable_transition_dimension(
    dimension: TransitionFeasibilityDimension,
    *,
    reason_code: str,
) -> TransitionDimensionEvidenceR2:
    return TransitionDimensionEvidenceR2(
        dimension=dimension,
        assessability=Assessability.NOT_ASSESSABLE,
        value=None,
        reason_code=reason_code,
        evidence_refs=(),
    )


def vocal_collision_evidence_r2(
    *,
    value: float | None,
    explicit_vocal_evidence_refs: tuple[str, ...],
) -> TransitionDimensionEvidenceR2:
    """Never infer vocal collision evidence from unrelated acoustic features."""
    if value is None or not explicit_vocal_evidence_refs:
        return not_assessable_transition_dimension(
            TransitionFeasibilityDimension.VOCAL_COLLISION_RISK,
            reason_code="explicit_vocal_evidence_missing",
        )
    return TransitionDimensionEvidenceR2(
        dimension=TransitionFeasibilityDimension.VOCAL_COLLISION_RISK,
        assessability=Assessability.ASSESSABLE,
        value=value,
        reason_code=None,
        evidence_refs=explicit_vocal_evidence_refs,
    )


def _sampling_key(policy: HoldoutCaseSamplingPolicy, candidate: HoldoutCandidate) -> str:
    material = (
        f"{policy.policy_id}|{policy.policy_version}|{policy.sampling_seed}|"
        f"{policy.snapshot_fingerprint}|{candidate.candidate_id}|{candidate.case_id}"
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def select_holdout_cases_r2(
    *,
    policy: HoldoutCaseSamplingPolicy,
    candidates: tuple[HoldoutCandidate, ...],
) -> HoldoutSelectionResult:
    """Select a holdout without accepting challenger scores or human labels as inputs."""
    if policy.dataset_role is ReviewDatasetRole.DEVELOPMENT_REGRESSION:
        raise HumanReviewProtocolR2Error("development/regression data cannot be selected as holdout")
    if not candidates:
        raise HumanReviewProtocolR2Error("holdout selection requires candidates")

    candidate_ids = [item.candidate_id for item in candidates]
    case_ids = [item.case_id for item in candidates]
    if len(set(candidate_ids)) != len(candidate_ids) or len(set(case_ids)) != len(case_ids):
        raise HumanReviewProtocolR2Error("holdout candidate and case identities must be unique")

    quotas = dict(policy.role_quotas)
    ordered = sorted(candidates, key=lambda item: (_sampling_key(policy, item), item.candidate_id))
    selected: list[str] = []
    fallback: list[str] = []
    selected_by_role: dict[CuratedSetRole, int] = {role: 0 for role in quotas}
    ledger: list[HoldoutSelectionEntry] = []

    pending_eligible: list[tuple[int, HoldoutCandidate]] = []
    for ordinal, candidate in enumerate(ordered):
        if not candidate.technically_eligible:
            reason = candidate.technical_invalidity_reason or "engineering_acceptance_failed"
            ledger.append(
                HoldoutSelectionEntry(
                    candidate_id=candidate.candidate_id,
                    case_id=candidate.case_id,
                    set_role=candidate.set_role,
                    sampling_ordinal=ordinal,
                    selected=False,
                    reason_code=f"technical_ineligible:{reason}",
                )
            )
            continue
        if candidate.set_role not in quotas:
            ledger.append(
                HoldoutSelectionEntry(
                    candidate_id=candidate.candidate_id,
                    case_id=candidate.case_id,
                    set_role=candidate.set_role,
                    sampling_ordinal=ordinal,
                    selected=False,
                    reason_code="role_not_requested",
                )
            )
            continue
        if selected_by_role[candidate.set_role] < quotas[candidate.set_role]:
            selected_by_role[candidate.set_role] += 1
            selected.append(candidate.case_id)
            ledger.append(
                HoldoutSelectionEntry(
                    candidate_id=candidate.candidate_id,
                    case_id=candidate.case_id,
                    set_role=candidate.set_role,
                    sampling_ordinal=ordinal,
                    selected=True,
                    reason_code="selected_for_frozen_role_quota",
                )
            )
        else:
            pending_eligible.append((ordinal, candidate))

    missing = {
        role.value: quotas[role] - selected_by_role.get(role, 0)
        for role in quotas
        if selected_by_role.get(role, 0) < quotas[role]
    }
    if missing:
        raise HumanReviewProtocolR2Error(f"holdout role quotas not satisfiable: {missing}")

    fallback_ids = {item.case_id for _, item in pending_eligible[: policy.fallback_count]}
    fallback.extend(item.case_id for _, item in pending_eligible[: policy.fallback_count])
    for ordinal, candidate in pending_eligible:
        ledger.append(
            HoldoutSelectionEntry(
                candidate_id=candidate.candidate_id,
                case_id=candidate.case_id,
                set_role=candidate.set_role,
                sampling_ordinal=ordinal,
                selected=False,
                reason_code=(
                    "frozen_fallback_reserve"
                    if candidate.case_id in fallback_ids
                    else "quota_full_not_in_fallback"
                ),
            )
        )

    ledger.sort(key=lambda item: item.sampling_ordinal)
    payload = {
        "policy": asdict(policy),
        "selected_case_ids": selected,
        "fallback_case_ids": fallback,
        "ledger": [asdict(item) for item in ledger],
    }
    return HoldoutSelectionResult(
        policy_ref=(policy.policy_id, policy.policy_version),
        selected_case_ids=tuple(selected),
        fallback_case_ids=tuple(fallback),
        ledger=tuple(ledger),
        manifest_fingerprint=_fingerprint("holdout-selection-r2", payload),
        activation_authorized=False,
    )


def replacement_case_r2(
    *,
    selection: HoldoutSelectionResult,
    invalid_case_id: str,
    already_used_fallback_case_ids: tuple[str, ...] = (),
) -> str:
    """Return only the next case from the already-frozen fallback order."""
    if invalid_case_id not in selection.selected_case_ids:
        raise HumanReviewProtocolR2Error("replacement target must be a selected holdout case")
    used = set(already_used_fallback_case_ids)
    if not used.issubset(set(selection.fallback_case_ids)):
        raise HumanReviewProtocolR2Error("used fallback case id is outside frozen fallback reservoir")
    for case_id in selection.fallback_case_ids:
        if case_id not in used:
            return case_id
    raise HumanReviewProtocolR2Error("frozen fallback reservoir exhausted")


def _human_preference(
    *,
    case_binding: CurationCalibrationCaseR3,
    assignment: BlindedPlanAssignment,
    review: CurationReviewR2,
) -> ResolvedCurationPreference:
    case = case_binding.case
    if assignment.case_id != case.case_id:
        raise HumanReviewProtocolR2Error("assignment case does not match calibration case")
    if review.assignment_id != assignment.assignment_id:
        raise HumanReviewProtocolR2Error("curation review assignment does not match blind assignment")
    if not assignment.algorithm_identity_hidden or not review.algorithm_identity_was_hidden:
        raise HumanReviewProtocolR2Error("curation calibration requires genuine blind assignment/review")
    if review.dataset_role is not case_binding.dataset_role:
        raise HumanReviewProtocolR2Error("curation review dataset role mismatches case binding")

    by_plan = {
        case.greedy_plan.plan_id: ResolvedCurationPreference.GREEDY,
        case.beam_plan.plan_id: ResolvedCurationPreference.BEAM,
    }
    if {assignment.slot_a_plan_id, assignment.slot_b_plan_id} != set(by_plan):
        raise HumanReviewProtocolR2Error("blind assignment does not bind exactly to source plans")
    if review.preference is CurationPreference.PLAN_A:
        return by_plan[assignment.slot_a_plan_id]
    if review.preference is CurationPreference.PLAN_B:
        return by_plan[assignment.slot_b_plan_id]
    if review.preference is CurationPreference.TIE:
        return ResolvedCurationPreference.TIE
    if review.preference is CurationPreference.ABSTAIN:
        return ResolvedCurationPreference.ABSTAIN
    raise HumanReviewProtocolR2Error("unsupported curation preference")


def _challenger_preference(
    *,
    case_binding: CurationCalibrationCaseR3,
    comparison: ShadowPathComparison,
) -> ResolvedCurationPreference:
    case = case_binding.case
    by_path = {
        case.greedy_plan.path_id: ResolvedCurationPreference.GREEDY,
        case.beam_plan.path_id: ResolvedCurationPreference.BEAM,
    }
    if {comparison.left_path_id, comparison.right_path_id} != set(by_path):
        raise HumanReviewProtocolR2Error("shadow comparison does not bind exactly to source paths")
    if comparison.activation_authorized:
        raise HumanReviewProtocolR2Error("shadow comparison exceeds calibration authority")
    if comparison.preference is ShadowPathPreference.LEFT:
        return by_path[comparison.left_path_id]
    if comparison.preference is ShadowPathPreference.RIGHT:
        return by_path[comparison.right_path_id]
    if comparison.preference is ShadowPathPreference.TIE:
        return ResolvedCurationPreference.TIE
    if comparison.preference is ShadowPathPreference.NOT_PROVEN:
        return ResolvedCurationPreference.NOT_PROVEN
    raise HumanReviewProtocolR2Error("unsupported shadow preference")


def calibrate_curation_case_r3(
    *,
    case_binding: CurationCalibrationCaseR3,
    assignment: BlindedPlanAssignment,
    review: CurationReviewR2,
    comparison: ShadowPathComparison,
) -> CurationCalibrationEvidenceR3:
    """Calibrate only explicit curation preference; transition/execution are not inputs."""
    human = _human_preference(case_binding=case_binding, assignment=assignment, review=review)
    challenger = _challenger_preference(case_binding=case_binding, comparison=comparison)

    clean = bool(
        case_binding.dataset_role in (ReviewDatasetRole.PERSONAL_HOLDOUT, ReviewDatasetRole.GENERAL_HOLDOUT)
        and review.clean_holdout_eligible
    )
    reasons: list[str] = []
    if case_binding.dataset_role is ReviewDatasetRole.DEVELOPMENT_REGRESSION:
        reasons.append("development_regression_case_excluded_from_holdout_metrics")
    if not review.clean_holdout_eligible:
        reasons.append("curation_review_not_clean_holdout_eligible")

    exact: bool | None = None
    decisive: bool | None = None
    if clean and human is not ResolvedCurationPreference.ABSTAIN:
        exact = human is challenger
        if exact:
            reasons.append("curation_challenger_exact_agreement")
        else:
            reasons.append("curation_challenger_disagreement")
        if human in (ResolvedCurationPreference.GREEDY, ResolvedCurationPreference.BEAM):
            decisive = human is challenger
    elif human is ResolvedCurationPreference.ABSTAIN:
        reasons.append("human_abstain_excluded_from_accuracy")

    if human is ResolvedCurationPreference.TIE and challenger in (
        ResolvedCurationPreference.GREEDY,
        ResolvedCurationPreference.BEAM,
    ):
        reasons.append("challenger_false_winner_on_human_tie")
    if challenger is ResolvedCurationPreference.NOT_PROVEN:
        reasons.append("challenger_preference_not_proven")
    if case_binding.meaningful_difference_status is MeaningfulDifferenceStatus.NEAR_EQUIVALENT:
        reasons.append("near_equivalent_case_report_separately")

    return CurationCalibrationEvidenceR3(
        case_id=case_binding.case.case_id,
        set_role=case_binding.case.set_role,
        review_id=review.review_id,
        reviewer_ref=review.reviewer_ref,
        assignment_id=assignment.assignment_id,
        dataset_role=case_binding.dataset_role,
        meaningful_difference_status=case_binding.meaningful_difference_status,
        human_preference=human,
        challenger_preference=challenger,
        human_confidence=review.confidence,
        exact_agreement=exact,
        decisive_agreement=decisive,
        clean_holdout_eligible=clean,
        reason_codes=tuple(reasons),
        activation_authorized=False,
        personal_dj_model_training_authorized=False,
    )


def _rate(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return numerator / denominator


def wilson_interval(successes: int, total: int, *, z: float = 1.959963984540054) -> WilsonInterval | None:
    if total <= 0:
        return None
    if successes < 0 or successes > total:
        raise HumanReviewProtocolR2Error("Wilson successes must be between zero and total")
    p = successes / total
    z2 = z * z
    denominator = 1.0 + z2 / total
    center = (p + z2 / (2.0 * total)) / denominator
    margin = (
        z
        * math.sqrt((p * (1.0 - p) / total) + z2 / (4.0 * total * total))
        / denominator
    )
    return WilsonInterval(lower=max(0.0, center - margin), upper=min(1.0, center + margin))


def build_curation_calibration_report_r3(
    *,
    case_evidence: tuple[CurationCalibrationEvidenceR3, ...],
    policy: CurationCalibrationPolicyR3 = CurationCalibrationPolicyR3(),
) -> CurationCalibrationReportR3:
    """Build a personal-DJ curation report without reading transition/execution evidence."""
    if policy.claim_scope is ValidationClaimScope.GENERAL_DJ_PRODUCT_VALIDATION:
        raise HumanReviewProtocolR2Error(
            "general DJ validation requires the separate pre-registered cluster-aware analyzer"
        )

    evidence = tuple(sorted(case_evidence, key=lambda item: (item.case_id, item.review_id)))
    if not evidence:
        raise HumanReviewProtocolR2Error("curation calibration requires evidence")
    review_ids = [item.review_id for item in evidence]
    if len(set(review_ids)) != len(review_ids):
        raise HumanReviewProtocolR2Error("duplicate curation review identity")

    clean = tuple(
        item
        for item in evidence
        if item.clean_holdout_eligible and item.dataset_role is ReviewDatasetRole.PERSONAL_HOLDOUT
    )
    reviewer_refs = {item.reviewer_ref for item in clean}
    if len(reviewer_refs) > 1:
        raise HumanReviewProtocolR2Error(
            "personal DJ calibration report cannot combine multiple reviewers"
        )

    non_abstain = tuple(
        item for item in clean if item.human_preference is not ResolvedCurationPreference.ABSTAIN
    )
    decisive = tuple(
        item
        for item in clean
        if item.human_preference in (
            ResolvedCurationPreference.GREEDY,
            ResolvedCurationPreference.BEAM,
        )
    )
    human_ties = tuple(item for item in clean if item.human_preference is ResolvedCurationPreference.TIE)

    exact_agreement_count = sum(item.exact_agreement is True for item in non_abstain)
    decisive_agreement_count = sum(item.decisive_agreement is True for item in decisive)
    false_winner_count = sum(
        item.human_preference is ResolvedCurationPreference.TIE
        and item.challenger_preference in (
            ResolvedCurationPreference.GREEDY,
            ResolvedCurationPreference.BEAM,
        )
        for item in human_ties
    )

    exact_rate = _rate(exact_agreement_count, len(non_abstain))
    decisive_rate = _rate(decisive_agreement_count, len(decisive))
    false_winner_rate = _rate(false_winner_count, len(human_ties))
    exact_interval = wilson_interval(exact_agreement_count, len(non_abstain))
    decisive_interval = wilson_interval(decisive_agreement_count, len(decisive))

    covered_roles = tuple(sorted({item.set_role for item in clean}, key=lambda item: item.value))
    missing_roles = tuple(role for role in CuratedSetRole if role not in covered_roles)

    explanations: list[str] = []
    incomplete = False
    if len(clean) < policy.minimum_clean_cases:
        incomplete = True
        explanations.append("clean_personal_holdout_case_count_below_policy")
    if len(decisive) < policy.minimum_decisive_cases:
        incomplete = True
        explanations.append("decisive_personal_holdout_case_count_below_policy")
    if missing_roles:
        incomplete = True
        explanations.append("required_set_roles_missing")

    if incomplete:
        verdict = CurationCalibrationVerdict.INCOMPLETE
    else:
        failed = False
        if (
            exact_interval is None
            or exact_interval.lower < policy.minimum_exact_agreement_lower_bound
        ):
            failed = True
            explanations.append("exact_agreement_wilson_lower_bound_below_policy")
        if (
            decisive_interval is None
            or decisive_interval.lower < policy.minimum_decisive_agreement_lower_bound
        ):
            failed = True
            explanations.append("decisive_agreement_wilson_lower_bound_below_policy")
        if (
            false_winner_rate is not None
            and false_winner_rate > policy.maximum_false_winner_on_human_tie_rate
        ):
            failed = True
            explanations.append("false_winner_on_human_tie_above_policy")
        verdict = (
            CurationCalibrationVerdict.DOES_NOT_SUPPORT_FURTHER_EVALUATION
            if failed
            else CurationCalibrationVerdict.SUPPORTS_FURTHER_EVALUATION
        )
        if not failed:
            explanations.append("personal_curation_calibration_supports_further_evaluation_only")

    payload = {
        "policy": asdict(policy),
        "clean_case_evidence": [
            {
                "case_id": item.case_id,
                "review_id": item.review_id,
                "reviewer_ref": item.reviewer_ref,
                "dataset_role": item.dataset_role.value,
                "meaningful_difference_status": item.meaningful_difference_status.value,
                "human_preference": item.human_preference.value,
                "challenger_preference": item.challenger_preference.value,
                "human_confidence": item.human_confidence,
                "exact_agreement": item.exact_agreement,
                "decisive_agreement": item.decisive_agreement,
            }
            for item in clean
        ],
    }

    return CurationCalibrationReportR3(
        report_id=_fingerprint("curation-calibration-r3", payload),
        policy_ref=(policy.policy_id, policy.policy_version),
        claim_scope=policy.claim_scope,
        clean_case_count=len(clean),
        excluded_case_count=len(evidence) - len(clean),
        decisive_case_count=len(decisive),
        exact_agreement_count=exact_agreement_count,
        decisive_agreement_count=decisive_agreement_count,
        human_tie_count=len(human_ties),
        false_winner_on_human_tie_count=false_winner_count,
        exact_agreement_rate=exact_rate,
        decisive_agreement_rate=decisive_rate,
        false_winner_on_human_tie_rate=false_winner_rate,
        exact_agreement_interval=exact_interval,
        decisive_agreement_interval=decisive_interval,
        covered_set_roles=covered_roles,
        missing_set_roles=missing_roles,
        case_evidence=evidence,
        verdict=verdict,
        explanation_codes=tuple(explanations),
        activation_authorized=False,
        personal_dj_model_training_authorized=False,
    )


__all__ = [
    "HumanReviewProtocolR2Error",
    "build_curation_calibration_report_r3",
    "calibrate_curation_case_r3",
    "not_assessable_transition_dimension",
    "replacement_case_r2",
    "select_holdout_cases_r2",
    "transition_review_spec_fingerprint",
    "vocal_collision_evidence_r2",
    "wilson_interval",
]
