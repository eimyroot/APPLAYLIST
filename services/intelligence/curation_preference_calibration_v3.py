from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from collections.abc import Mapping

from core.intelligence.competitive_curation_contract import ShadowPathComparison, ShadowPathPreference
from core.intelligence.curated_real_library_review_contract import (
    CuratedReviewCase,
    ReviewPlanStrategy,
)
from core.intelligence.curation_review_v2_contract import (
    CurationBlindAssignmentV2,
    CurationCalibrationPolicyV3,
    CurationCalibrationReportV3,
    CurationCasePreferenceCalibration,
    CurationDJReviewV2,
    CurationPreference,
    EvaluationScope,
    EvidenceRole,
    HoldoutCaseExecutionEvidence,
    HoldoutSystemOutcome,
    HoldoutValidationManifest,
    SelectionScope,
)
from core.intelligence.human_preference_calibration_contract import CalibrationVerdict, ResolvedPreference


class CurationPreferenceCalibrationV3Error(ValueError):
    """Fail-closed error for curation-only calibration evidence."""


def _stable_id(prefix: str, payload: object) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return f"{prefix}:{hashlib.sha256(encoded).hexdigest()}"


def _rate(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return numerator / denominator


def _path_strategy_map(case: CuratedReviewCase) -> dict[str, ResolvedPreference]:
    return {
        case.greedy_plan.path_id: ResolvedPreference.GREEDY,
        case.beam_plan.path_id: ResolvedPreference.BEAM,
    }


def _plan_strategy_map(case: CuratedReviewCase) -> dict[str, ResolvedPreference]:
    return {
        case.greedy_plan.plan_id: ResolvedPreference.GREEDY,
        case.beam_plan.plan_id: ResolvedPreference.BEAM,
    }


def _resolve_human_preference(
    *,
    case: CuratedReviewCase,
    assignment: CurationBlindAssignmentV2,
    review: CurationDJReviewV2,
) -> ResolvedPreference:
    if assignment.case_id != case.case_id:
        raise CurationPreferenceCalibrationV3Error("assignment case_id mismatch")
    if assignment.reviewer_ref != review.reviewer_ref:
        raise CurationPreferenceCalibrationV3Error("assignment reviewer mismatch")
    if assignment.assignment_id != review.assignment_id:
        raise CurationPreferenceCalibrationV3Error("review assignment mismatch")
    if not assignment.algorithm_identity_hidden or not review.algorithm_identity_was_hidden:
        raise CurationPreferenceCalibrationV3Error("curation calibration requires blinded evidence")
    if not review.execution_quality_excluded_from_curation_judgment:
        raise CurationPreferenceCalibrationV3Error("execution-contaminated review is invalid")

    by_plan = _plan_strategy_map(case)
    if {assignment.slot_a_plan_id, assignment.slot_b_plan_id} != set(by_plan):
        raise CurationPreferenceCalibrationV3Error("assignment does not bind exactly to source plans")

    if review.preference is CurationPreference.PLAN_A:
        return by_plan[assignment.slot_a_plan_id]
    if review.preference is CurationPreference.PLAN_B:
        return by_plan[assignment.slot_b_plan_id]
    if review.preference is CurationPreference.TIE:
        return ResolvedPreference.TIE
    if review.preference is CurationPreference.ABSTAIN:
        return ResolvedPreference.ABSTAIN
    raise CurationPreferenceCalibrationV3Error("unsupported curation preference")


def _resolve_challenger_preference(
    *,
    case: CuratedReviewCase,
    comparison: ShadowPathComparison,
) -> ResolvedPreference:
    by_path = _path_strategy_map(case)
    if {comparison.left_path_id, comparison.right_path_id} != set(by_path):
        raise CurationPreferenceCalibrationV3Error("challenger comparison path binding mismatch")
    if comparison.activation_authorized:
        raise CurationPreferenceCalibrationV3Error("challenger comparison exceeds shadow authority")
    if comparison.preference is ShadowPathPreference.LEFT:
        return by_path[comparison.left_path_id]
    if comparison.preference is ShadowPathPreference.RIGHT:
        return by_path[comparison.right_path_id]
    if comparison.preference is ShadowPathPreference.TIE:
        return ResolvedPreference.TIE
    if comparison.preference is ShadowPathPreference.NOT_PROVEN:
        return ResolvedPreference.NOT_PROVEN
    raise CurationPreferenceCalibrationV3Error("unsupported challenger preference")


def calibrate_curation_case_v3(
    *,
    case: CuratedReviewCase,
    assignment: CurationBlindAssignmentV2,
    review: CurationDJReviewV2,
    comparison: ShadowPathComparison,
) -> CurationCasePreferenceCalibration:
    human = _resolve_human_preference(case=case, assignment=assignment, review=review)
    challenger = _resolve_challenger_preference(case=case, comparison=comparison)

    reasons: list[str] = []
    exact: bool | None
    decisive: bool | None
    if human is ResolvedPreference.ABSTAIN:
        exact = None
        decisive = None
        reasons.append("curation_human_abstain_excluded_from_accuracy")
    else:
        exact = human is challenger
        reasons.append(
            "curation_challenger_exactly_agrees_with_human"
            if exact
            else "curation_challenger_disagrees_with_human"
        )
        if human in (ResolvedPreference.GREEDY, ResolvedPreference.BEAM):
            decisive = human is challenger
            if challenger is ResolvedPreference.TIE:
                reasons.append("curation_challenger_tie_on_human_decisive")
            elif challenger is ResolvedPreference.NOT_PROVEN:
                reasons.append("curation_challenger_not_proven_on_human_decisive")
        else:
            decisive = None
        if human is ResolvedPreference.TIE and challenger in (
            ResolvedPreference.GREEDY,
            ResolvedPreference.BEAM,
        ):
            reasons.append("curation_challenger_false_winner_on_human_tie")
    if challenger is ResolvedPreference.NOT_PROVEN:
        reasons.append("curation_challenger_preference_not_proven")

    return CurationCasePreferenceCalibration(
        case_id=case.case_id,
        set_role=case.set_role,
        review_id=review.review_id,
        reviewer_ref=review.reviewer_ref,
        assignment_id=assignment.assignment_id,
        human_preference=human,
        challenger_preference=challenger,
        confidence=review.confidence,
        exact_agreement=exact,
        decisive_agreement=decisive,
        reason_codes=tuple(reasons),
        activation_authorized=False,
        personal_dj_model_training_authorized=False,
    )


def _validate_holdout_binding(
    *,
    cases: tuple[CuratedReviewCase, ...],
    manifest: HoldoutValidationManifest,
    expected_source_optimizer_sha: str,
    expected_challenger_sha: str,
    expected_challenger_config_digest: str,
    expected_calibration_policy_digest: str,
) -> None:
    case_ids = tuple(item.case_id for item in cases)
    scenario_fingerprints = tuple(item.scenario_fingerprint for item in cases)
    if case_ids != manifest.selected_case_ids:
        raise CurationPreferenceCalibrationV3Error("holdout selected case identities changed after freeze")
    if scenario_fingerprints != manifest.scenario_fingerprints:
        raise CurationPreferenceCalibrationV3Error("holdout scenario fingerprints changed after freeze")
    if expected_source_optimizer_sha != manifest.source_optimizer_sha:
        raise CurationPreferenceCalibrationV3Error("source optimizer revision does not match holdout freeze")
    if expected_challenger_sha != manifest.challenger_sha:
        raise CurationPreferenceCalibrationV3Error("challenger revision does not match holdout freeze")
    if expected_challenger_config_digest != manifest.challenger_config_digest:
        raise CurationPreferenceCalibrationV3Error("challenger configuration changed after holdout freeze")
    if expected_calibration_policy_digest != manifest.calibration_policy_digest:
        raise CurationPreferenceCalibrationV3Error("calibration policy changed after holdout freeze")


def _assignment_position_counts(
    *,
    cases_by_id: Mapping[str, CuratedReviewCase],
    assignments: tuple[CurationBlindAssignmentV2, ...],
) -> tuple[int, int, int, int]:
    a_greedy = 0
    b_greedy = 0
    a_beam = 0
    b_beam = 0
    for assignment in assignments:
        case = cases_by_id.get(assignment.case_id)
        if case is None:
            raise CurationPreferenceCalibrationV3Error("assignment references unknown case")
        by_plan = {
            case.greedy_plan.plan_id: ReviewPlanStrategy.GREEDY_RECOMMEND_NEXT,
            case.beam_plan.plan_id: ReviewPlanStrategy.BOUNDED_BEAM,
        }
        if {assignment.slot_a_plan_id, assignment.slot_b_plan_id} != set(by_plan):
            raise CurationPreferenceCalibrationV3Error("assignment plan identity mismatch")
        if by_plan[assignment.slot_a_plan_id] is ReviewPlanStrategy.GREEDY_RECOMMEND_NEXT:
            a_greedy += 1
            b_beam += 1
        else:
            a_beam += 1
            b_greedy += 1
    return a_greedy, b_greedy, a_beam, b_beam


def build_curation_calibration_report_v3(
    *,
    all_cases: tuple[CuratedReviewCase, ...],
    assignments: tuple[CurationBlindAssignmentV2, ...],
    reviews: tuple[CurationDJReviewV2, ...],
    comparisons_by_case: Mapping[str, ShadowPathComparison],
    system_outcomes: tuple[HoldoutCaseExecutionEvidence, ...],
    evidence_role: EvidenceRole,
    evaluation_scope: EvaluationScope,
    policy: CurationCalibrationPolicyV3 = CurationCalibrationPolicyV3(),
    holdout_manifest: HoldoutValidationManifest | None = None,
    expected_source_optimizer_sha: str = "development",
    expected_challenger_sha: str = "development",
    expected_challenger_config_digest: str = "development",
    expected_calibration_policy_digest: str = "development",
) -> CurationCalibrationReportV3:
    cases = tuple(all_cases)
    if not cases:
        raise CurationPreferenceCalibrationV3Error("curation calibration requires source cases")
    case_ids = tuple(item.case_id for item in cases)
    if len(set(case_ids)) != len(case_ids):
        raise CurationPreferenceCalibrationV3Error("source case identities must be unique")
    cases_by_id = {item.case_id: item for item in cases}

    if evidence_role is EvidenceRole.HOLDOUT_VALIDATION:
        if holdout_manifest is None:
            raise CurationPreferenceCalibrationV3Error("holdout validation requires frozen manifest")
        _validate_holdout_binding(
            cases=cases,
            manifest=holdout_manifest,
            expected_source_optimizer_sha=expected_source_optimizer_sha,
            expected_challenger_sha=expected_challenger_sha,
            expected_challenger_config_digest=expected_challenger_config_digest,
            expected_calibration_policy_digest=expected_calibration_policy_digest,
        )
        selection_scope: SelectionScope | None = holdout_manifest.selection_scope
        independent_validation = True
        representative_allowed = selection_scope is SelectionScope.REPRESENTATIVE_HOLDOUT
    else:
        if holdout_manifest is not None:
            raise CurationPreferenceCalibrationV3Error("development evidence cannot bind a holdout manifest")
        selection_scope = None
        independent_validation = False
        representative_allowed = False

    outcomes_by_case = {item.case_id: item for item in system_outcomes}
    if len(outcomes_by_case) != len(system_outcomes) or set(outcomes_by_case) != set(case_ids):
        raise CurationPreferenceCalibrationV3Error("system outcomes must cover selected cases exactly once")
    for case in cases:
        outcome = outcomes_by_case[case.case_id]
        if outcome.set_role is not case.set_role or outcome.scenario_fingerprint != case.scenario_fingerprint:
            raise CurationPreferenceCalibrationV3Error("system outcome source binding mismatch")

    assignments_by_id: dict[str, CurationBlindAssignmentV2] = {}
    for assignment in assignments:
        if assignment.assignment_id in assignments_by_id:
            raise CurationPreferenceCalibrationV3Error("duplicate curation assignment identity")
        assignments_by_id[assignment.assignment_id] = assignment

    review_ids: set[str] = set()
    calibration_evidence: list[CurationCasePreferenceCalibration] = []
    reviewed_case_ids: set[str] = set()
    reviewers: set[str] = set()
    reviews_by_case: dict[str, list[CurationDJReviewV2]] = defaultdict(list)
    for review in reviews:
        if review.review_id in review_ids:
            raise CurationPreferenceCalibrationV3Error("duplicate curation review identity")
        review_ids.add(review.review_id)
        if review.evidence_role is not evidence_role:
            raise CurationPreferenceCalibrationV3Error("review evidence role mismatch")
        assignment = assignments_by_id.get(review.assignment_id)
        if assignment is None:
            raise CurationPreferenceCalibrationV3Error("review references unknown assignment")
        case = cases_by_id.get(assignment.case_id)
        if case is None:
            raise CurationPreferenceCalibrationV3Error("assignment references unknown case")
        outcome = outcomes_by_case[case.case_id]
        if not outcome.human_review_eligible:
            raise CurationPreferenceCalibrationV3Error(
                "human review cannot replace a non-reviewable machine/system outcome"
            )
        comparison = comparisons_by_case.get(case.case_id)
        if comparison is None:
            raise CurationPreferenceCalibrationV3Error("reviewable case requires challenger comparison")
        calibration_evidence.append(
            calibrate_curation_case_v3(
                case=case,
                assignment=assignment,
                review=review,
                comparison=comparison,
            )
        )
        reviewed_case_ids.add(case.case_id)
        reviewers.add(review.reviewer_ref)
        reviews_by_case[case.case_id].append(review)

    reviewable_case_ids = {
        case_id
        for case_id, outcome in outcomes_by_case.items()
        if outcome.outcome is HoldoutSystemOutcome.REVIEWABLE_PAIR
    }
    if not reviewed_case_ids <= reviewable_case_ids:
        raise CurationPreferenceCalibrationV3Error("reviewed case set exceeds reviewable case set")

    reviewable_pair_count = len(reviewable_case_ids)
    selected_count = len(cases)
    non_reviewable_count = selected_count - reviewable_pair_count
    reviewable_fraction = reviewable_pair_count / selected_count
    meaningful_availability = reviewable_fraction
    reviewed_reviewable_fraction = (
        1.0 if reviewable_pair_count == 0 else len(reviewed_case_ids) / reviewable_pair_count
    )

    non_abstain = [
        item for item in calibration_evidence if item.human_preference is not ResolvedPreference.ABSTAIN
    ]
    decisive = [
        item
        for item in calibration_evidence
        if item.human_preference in (ResolvedPreference.GREEDY, ResolvedPreference.BEAM)
    ]
    human_ties = [item for item in calibration_evidence if item.human_preference is ResolvedPreference.TIE]
    exact_count = sum(item.exact_agreement is True for item in non_abstain)
    decisive_count = sum(item.decisive_agreement is True for item in decisive)
    false_winner_count = sum(
        item.human_preference is ResolvedPreference.TIE
        and item.challenger_preference in (ResolvedPreference.GREEDY, ResolvedPreference.BEAM)
        for item in calibration_evidence
    )
    exact_rate = _rate(exact_count, len(non_abstain))
    decisive_rate = _rate(decisive_count, len(decisive))
    false_winner_rate = _rate(false_winner_count, len(human_ties))
    confidence_denominator = sum(item.confidence for item in decisive)
    confidence_weighted = (
        None
        if confidence_denominator <= 0.0
        else sum(item.confidence for item in decisive if item.decisive_agreement is True)
        / confidence_denominator
    )

    reviewer_rates: list[float] = []
    for reviewer in sorted(reviewers):
        items = [
            item
            for item in calibration_evidence
            if item.reviewer_ref == reviewer and item.human_preference is not ResolvedPreference.ABSTAIN
        ]
        if items:
            reviewer_rates.append(sum(item.exact_agreement is True for item in items) / len(items))
    macro_agreement = None if not reviewer_rates else sum(reviewer_rates) / len(reviewer_rates)

    disagreement_cases = 0
    multi_review_cases = 0
    for case_id, case_reviews in reviews_by_case.items():
        preferences = [review.preference for review in case_reviews if review.preference is not CurationPreference.ABSTAIN]
        if len(preferences) >= 2:
            multi_review_cases += 1
            if len(set(preferences)) > 1:
                disagreement_cases += 1
    disagreement_rate = _rate(disagreement_cases, multi_review_cases)

    a_greedy, b_greedy, a_beam, b_beam = _assignment_position_counts(
        cases_by_id=cases_by_id,
        assignments=assignments,
    )
    assignment_imbalance = abs(a_greedy - b_greedy)

    covered_roles = tuple(sorted({item.set_role for item in cases}, key=lambda item: item.value))
    missing_roles = tuple(role for role in policy.required_set_roles if role not in covered_roles)
    outcome_counter = Counter(item.outcome for item in system_outcomes)
    outcome_counts = tuple((outcome, outcome_counter.get(outcome, 0)) for outcome in HoldoutSystemOutcome)

    explanations: list[str] = []
    incomplete = False
    if selected_count < policy.minimum_cases:
        incomplete = True
        explanations.append("curation_calibration_case_count_below_policy")
    if missing_roles:
        incomplete = True
        explanations.append("curation_calibration_required_set_roles_missing")
    if reviewed_reviewable_fraction < policy.minimum_reviewed_reviewable_case_fraction:
        incomplete = True
        explanations.append("curation_calibration_reviewable_case_coverage_below_policy")
    if assignment_imbalance > policy.maximum_assignment_imbalance:
        incomplete = True
        explanations.append("curation_calibration_assignment_position_imbalance")
    if evaluation_scope is EvaluationScope.MULTI_DJ_PRODUCT_EVALUATION:
        if len(reviewers) < policy.minimum_independent_reviewers_for_multi_dj:
            incomplete = True
            explanations.append("curation_calibration_independent_reviewer_count_below_policy")

    if incomplete:
        verdict = CalibrationVerdict.INCOMPLETE
    else:
        failed = False
        if meaningful_availability < policy.minimum_meaningful_alternative_availability_rate:
            failed = True
            explanations.append("curation_meaningful_alternative_availability_below_policy")
        if reviewable_pair_count > 0:
            if exact_rate is None or exact_rate < policy.minimum_exact_agreement_rate:
                failed = True
                explanations.append("curation_exact_agreement_below_policy")
            if decisive_rate is None or decisive_rate < policy.minimum_decisive_agreement_rate:
                failed = True
                explanations.append("curation_decisive_agreement_below_policy")
            if (
                confidence_weighted is None
                or confidence_weighted < policy.minimum_confidence_weighted_decisive_agreement
            ):
                failed = True
                explanations.append("curation_confidence_weighted_agreement_below_policy")
            if (
                false_winner_rate is not None
                and false_winner_rate > policy.maximum_false_winner_on_human_tie_rate
            ):
                failed = True
                explanations.append("curation_false_winner_on_human_tie_above_policy")
        verdict = (
            CalibrationVerdict.DOES_NOT_SUPPORT_ACTIVATION
            if failed
            else CalibrationVerdict.SUPPORTS_FURTHER_EVALUATION
        )
        if not failed:
            explanations.append("curation_calibration_supports_further_evaluation_only")
            if evidence_role is EvidenceRole.DEVELOPMENT_CALIBRATION:
                explanations.append("development_result_requires_fresh_holdout_validation")
            elif selection_scope is SelectionScope.DIAGNOSTIC_CHALLENGE_SET:
                explanations.append("diagnostic_result_not_representative_performance")

    payload = {
        "policy": [policy.policy_id, policy.policy_version],
        "evidence_role": evidence_role.value,
        "evaluation_scope": evaluation_scope.value,
        "selection_scope": None if selection_scope is None else selection_scope.value,
        "cases": case_ids,
        "outcomes": [(item.case_id, item.outcome.value) for item in system_outcomes],
        "reviews": [
            (
                item.case_id,
                item.review_id,
                item.reviewer_ref,
                item.human_preference.value,
                item.challenger_preference.value,
                item.confidence,
            )
            for item in sorted(calibration_evidence, key=lambda value: (value.case_id, value.review_id))
        ],
    }

    return CurationCalibrationReportV3(
        report_id=_stable_id("curation-preference-calibration-v3", payload),
        policy_ref=(policy.policy_id, policy.policy_version),
        evidence_role=evidence_role,
        evaluation_scope=evaluation_scope,
        selection_scope=selection_scope,
        independent_validation=independent_validation,
        representative_performance_claim_allowed=representative_allowed,
        selected_case_count=selected_count,
        reviewable_pair_count=reviewable_pair_count,
        non_reviewable_system_outcome_count=non_reviewable_count,
        human_reviewed_case_count=len(reviewed_case_ids),
        reviewer_count=len(reviewers),
        reviewable_pair_fraction=reviewable_fraction,
        meaningful_alternative_availability_rate=meaningful_availability,
        exact_agreement_rate=exact_rate,
        decisive_agreement_rate=decisive_rate,
        confidence_weighted_decisive_agreement=confidence_weighted,
        false_winner_on_human_tie_rate=false_winner_rate,
        reviewer_disagreement_rate=disagreement_rate,
        macro_reviewer_agreement_rate=macro_agreement,
        pooled_agreement_rate=exact_rate,
        plan_a_greedy_count=a_greedy,
        plan_b_greedy_count=b_greedy,
        plan_a_beam_count=a_beam,
        plan_b_beam_count=b_beam,
        covered_set_roles=covered_roles,
        missing_set_roles=missing_roles,
        outcome_counts=outcome_counts,
        case_evidence=tuple(sorted(calibration_evidence, key=lambda value: (value.case_id, value.review_id))),
        verdict=verdict,
        explanation_codes=tuple(explanations),
        activation_authorized=False,
        personal_dj_model_training_authorized=False,
    )


__all__ = [
    "CurationPreferenceCalibrationV3Error",
    "build_curation_calibration_report_v3",
    "calibrate_curation_case_v3",
]
