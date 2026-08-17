from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import asdict

from core.intelligence.curated_real_library_review_contract import (
    CURATED_REAL_LIBRARY_BENCHMARK_VERSION,
    HUMAN_DJ_REVIEW_PROTOCOL_VERSION,
    REQUIRED_HUMAN_REVIEW_DIMENSIONS_R1,
    BlindedPlanAssignment,
    CuratedLibrarySnapshot,
    CuratedRealLibraryHumanReviewReport,
    CuratedReviewCase,
    CuratedSetRole,
    DimensionReviewEvidence,
    HumanDJReview,
    HumanPlanPreference,
    HumanReviewDimension,
    HumanReviewProtocolThresholds,
    HumanReviewProtocolVerdict,
    ReviewPlanStrategy,
    ReviewableSetPlan,
)
from core.intelligence.set_optimizer_contract import SetPathAlternative


def reviewable_plan_from_alternative(
    *,
    strategy: ReviewPlanStrategy,
    result_id: str,
    alternative: SetPathAlternative,
) -> ReviewableSetPlan:
    """Project immutable optimizer path evidence into a human-review plan reference."""
    ordered_track_ids = tuple(
        step.track_id for step in alternative.resulting_state.selected_steps
    )
    material = "|".join(
        (
            strategy.value,
            result_id,
            alternative.path_id,
            *ordered_track_ids,
            *alternative.transition_ids,
        )
    )
    plan_id = "hrp_" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:32]
    return ReviewableSetPlan(
        plan_id=plan_id,
        strategy=strategy,
        result_id=result_id,
        path_id=alternative.path_id,
        ordered_track_ids=ordered_track_ids,
        transition_ids=alternative.transition_ids,
        evidence_refs=alternative.evidence_refs,
    )


def build_blinded_plan_assignment(
    *,
    case: CuratedReviewCase,
    blinding_seed: str,
) -> BlindedPlanAssignment:
    """Deterministically map greedy/beam plans to anonymous A/B slots.

    The mapping is governance evidence and should not be exposed in the reviewer UI.
    It does not need to be secret for determinism; algorithm identity must simply be
    hidden from the reviewer while the judgement is made.
    """
    seed = str(blinding_seed).strip()
    if not seed:
        raise ValueError("blinding_seed must not be empty")
    material = "|".join(
        (
            HUMAN_DJ_REVIEW_PROTOCOL_VERSION,
            case.case_id,
            case.scenario_fingerprint,
            seed,
        )
    )
    fingerprint = hashlib.sha256(material.encode("utf-8")).hexdigest()
    if int(fingerprint[:2], 16) % 2 == 0:
        slot_a = case.greedy_plan.plan_id
        slot_b = case.beam_plan.plan_id
    else:
        slot_a = case.beam_plan.plan_id
        slot_b = case.greedy_plan.plan_id
    assignment_id = "hba_" + hashlib.sha256(
        f"{case.case_id}|{slot_a}|{slot_b}|{fingerprint}".encode("utf-8")
    ).hexdigest()[:32]
    return BlindedPlanAssignment(
        assignment_id=assignment_id,
        case_id=case.case_id,
        slot_a_plan_id=slot_a,
        slot_b_plan_id=slot_b,
        assignment_fingerprint=fingerprint,
        algorithm_identity_hidden=True,
    )


def _validate_unique(values: Sequence[str], field_name: str) -> None:
    if len(set(values)) != len(values):
        raise ValueError(f"{field_name} must be unique")


def _strategy_for_slot(
    *,
    assignment: BlindedPlanAssignment,
    case: CuratedReviewCase,
    slot: HumanPlanPreference,
) -> ReviewPlanStrategy | None:
    if slot is HumanPlanPreference.TIE or slot is HumanPlanPreference.ABSTAIN:
        return None
    plan_id = (
        assignment.slot_a_plan_id
        if slot is HumanPlanPreference.PLAN_A
        else assignment.slot_b_plan_id
    )
    if plan_id == case.greedy_plan.plan_id:
        return ReviewPlanStrategy.GREEDY_RECOMMEND_NEXT
    if plan_id == case.beam_plan.plan_id:
        return ReviewPlanStrategy.BOUNDED_BEAM
    raise ValueError("blind assignment references a plan outside the curated case")


def _dimension_evidence(
    *,
    reviews: tuple[HumanDJReview, ...],
    assignment_by_id: dict[str, BlindedPlanAssignment],
    case_by_id: dict[str, CuratedReviewCase],
) -> tuple[DimensionReviewEvidence, ...]:
    greedy_scores: dict[HumanReviewDimension, list[float]] = defaultdict(list)
    beam_scores: dict[HumanReviewDimension, list[float]] = defaultdict(list)

    for review in reviews:
        assignment = assignment_by_id[review.assignment_id]
        case = case_by_id[assignment.case_id]
        a_strategy = (
            ReviewPlanStrategy.GREEDY_RECOMMEND_NEXT
            if assignment.slot_a_plan_id == case.greedy_plan.plan_id
            else ReviewPlanStrategy.BOUNDED_BEAM
        )
        for rating in review.ratings:
            if a_strategy is ReviewPlanStrategy.GREEDY_RECOMMEND_NEXT:
                greedy_scores[rating.dimension].append(rating.plan_a_score)
                beam_scores[rating.dimension].append(rating.plan_b_score)
            else:
                beam_scores[rating.dimension].append(rating.plan_a_score)
                greedy_scores[rating.dimension].append(rating.plan_b_score)

    evidence: list[DimensionReviewEvidence] = []
    for dimension in HumanReviewDimension:
        greedy = greedy_scores.get(dimension, [])
        beam = beam_scores.get(dimension, [])
        if not greedy or not beam or len(greedy) != len(beam):
            continue
        greedy_mean = sum(greedy) / len(greedy)
        beam_mean = sum(beam) / len(beam)
        evidence.append(
            DimensionReviewEvidence(
                dimension=dimension,
                sample_count=len(greedy),
                greedy_mean=greedy_mean,
                beam_mean=beam_mean,
                beam_minus_greedy=beam_mean - greedy_mean,
            )
        )
    return tuple(evidence)


def evaluate_curated_real_library_human_review_r1(
    *,
    snapshot: CuratedLibrarySnapshot,
    cases: Sequence[CuratedReviewCase],
    assignments: Sequence[BlindedPlanAssignment],
    reviews: Sequence[HumanDJReview],
    thresholds: HumanReviewProtocolThresholds = HumanReviewProtocolThresholds(),
) -> CuratedRealLibraryHumanReviewReport:
    """Evaluate completeness and integrity of curated real-library human evidence.

    PASS means the R1 review protocol is complete and internally consistent. It does
    not mean beam is musically superior and cannot activate optimizer/ranking policy.
    Human preference can never override engineering hard gates.
    """
    case_tuple = tuple(cases)
    assignment_tuple = tuple(assignments)
    review_tuple = tuple(reviews)

    _validate_unique(tuple(item.case_id for item in case_tuple), "case ids")
    _validate_unique(
        tuple(item.assignment_id for item in assignment_tuple),
        "assignment ids",
    )
    _validate_unique(tuple(item.review_id for item in review_tuple), "review ids")

    expected_snapshot_ref = (snapshot.snapshot_id, snapshot.snapshot_version)
    snapshot_track_ids = set(snapshot.track_ids)
    case_by_id = {item.case_id: item for item in case_tuple}
    for case in case_tuple:
        if case.snapshot_ref != expected_snapshot_ref:
            raise ValueError("curated case snapshot_ref does not match evaluated snapshot")
        case_tracks = set(case.greedy_plan.ordered_track_ids) | set(
            case.beam_plan.ordered_track_ids
        )
        if not case_tracks.issubset(snapshot_track_ids):
            raise ValueError("curated case references tracks outside the snapshot")

    assignment_by_id = {item.assignment_id: item for item in assignment_tuple}
    assignment_by_case: dict[str, BlindedPlanAssignment] = {}
    for assignment in assignment_tuple:
        if assignment.case_id not in case_by_id:
            raise ValueError("blind assignment references an unknown curated case")
        if assignment.case_id in assignment_by_case:
            raise ValueError("each curated case may have only one blind assignment")
        case = case_by_id[assignment.case_id]
        expected_plan_ids = {case.greedy_plan.plan_id, case.beam_plan.plan_id}
        actual_plan_ids = {assignment.slot_a_plan_id, assignment.slot_b_plan_id}
        if expected_plan_ids != actual_plan_ids:
            raise ValueError("blind assignment plan ids do not match curated case plans")
        assignment_by_case[assignment.case_id] = assignment

    reviews_by_case: dict[str, list[HumanDJReview]] = defaultdict(list)
    reviewer_case_pairs: set[tuple[str, str]] = set()
    for review in review_tuple:
        if review.assignment_id not in assignment_by_id:
            raise ValueError("human review references an unknown blind assignment")
        assignment = assignment_by_id[review.assignment_id]
        reviewer_case_pair = (assignment.case_id, review.reviewer_ref)
        if reviewer_case_pair in reviewer_case_pairs:
            raise ValueError("a reviewer may submit only one review per curated case")
        reviewer_case_pairs.add(reviewer_case_pair)
        reviews_by_case[assignment.case_id].append(review)

    covered_roles = tuple(
        role for role in CuratedSetRole if any(item.set_role is role for item in case_tuple)
    )
    missing_roles = tuple(
        role for role in thresholds.required_set_roles if role not in covered_roles
    )

    reviewed_case_count = sum(
        1
        for case in case_tuple
        if len(reviews_by_case.get(case.case_id, ())) >= thresholds.minimum_reviews_per_case
    )
    reviewed_case_fraction = (
        reviewed_case_count / len(case_tuple) if case_tuple else 0.0
    )

    blind_integrity_successes = sum(
        1
        for review in review_tuple
        if review.algorithm_identity_was_hidden
        and assignment_by_id[review.assignment_id].algorithm_identity_hidden
    )
    blind_integrity_rate = (
        blind_integrity_successes / len(review_tuple) if review_tuple else 0.0
    )

    required_dimensions = set(REQUIRED_HUMAN_REVIEW_DIMENSIONS_R1)
    full_dimension_reviews = sum(
        1
        for review in review_tuple
        if {item.dimension for item in review.ratings} == required_dimensions
    )
    dimension_coverage_rate = (
        full_dimension_reviews / len(review_tuple) if review_tuple else 0.0
    )

    engineering_regression_count = sum(
        1 for case in case_tuple if not case.engineering_acceptance_passed
    )

    greedy_preference_count = 0
    beam_preference_count = 0
    tie_count = 0
    abstain_count = 0
    for review in review_tuple:
        if review.preference is HumanPlanPreference.TIE:
            tie_count += 1
            continue
        if review.preference is HumanPlanPreference.ABSTAIN:
            abstain_count += 1
            continue
        assignment = assignment_by_id[review.assignment_id]
        case = case_by_id[assignment.case_id]
        strategy = _strategy_for_slot(
            assignment=assignment,
            case=case,
            slot=review.preference,
        )
        if strategy is ReviewPlanStrategy.GREEDY_RECOMMEND_NEXT:
            greedy_preference_count += 1
        elif strategy is ReviewPlanStrategy.BOUNDED_BEAM:
            beam_preference_count += 1

    dimension_evidence = _dimension_evidence(
        reviews=review_tuple,
        assignment_by_id=assignment_by_id,
        case_by_id=case_by_id,
    )

    incomplete = (
        len(case_tuple) < thresholds.minimum_cases
        or bool(missing_roles)
        or reviewed_case_fraction < thresholds.minimum_reviewed_case_fraction
        or any(case.case_id not in assignment_by_case for case in case_tuple)
    )

    failures: list[str] = []
    # Absence of review evidence is an INCOMPLETE state, not observed bad evidence.
    # Once reviews exist, integrity/dimension defects are known failures and outrank
    # incomplete coverage, matching the representative-corpus fail-closed precedent.
    if review_tuple and blind_integrity_rate < thresholds.minimum_blind_integrity_rate:
        failures.append("blind_integrity_rate_below_threshold")
    if review_tuple and dimension_coverage_rate < thresholds.minimum_dimension_coverage_rate:
        failures.append("dimension_coverage_rate_below_threshold")
    if engineering_regression_count > thresholds.maximum_engineering_regressions:
        failures.append("engineering_regression_count_above_threshold")

    if failures:
        verdict = HumanReviewProtocolVerdict.FAIL
    elif incomplete:
        verdict = HumanReviewProtocolVerdict.INCOMPLETE
    else:
        verdict = HumanReviewProtocolVerdict.PASS

    material = {
        "benchmark_version": CURATED_REAL_LIBRARY_BENCHMARK_VERSION,
        "protocol_version": HUMAN_DJ_REVIEW_PROTOCOL_VERSION,
        "snapshot_ref": expected_snapshot_ref,
        "snapshot_fingerprint": snapshot.library_fingerprint,
        "thresholds": asdict(thresholds),
        "case_ids": tuple(item.case_id for item in case_tuple),
        "assignment_ids": tuple(item.assignment_id for item in assignment_tuple),
        "review_ids": tuple(item.review_id for item in review_tuple),
        "verdict": verdict.value,
    }
    encoded = json.dumps(material, sort_keys=True, separators=(",", ":"), default=str)
    report_id = "crh_" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:32]

    explanation_codes: list[str] = [
        "curated_real_library_human_review_r1",
        "human_review_is_blinded_pairwise_evidence",
        "engineering_acceptance_is_non_overridable",
        "no_universal_musical_quality_score",
        "optimizer_activation_not_authorized",
        "personal_dj_model_training_not_authorized",
    ]
    if incomplete:
        explanation_codes.append("human_review_protocol_incomplete")
    explanation_codes.extend(failures)
    if verdict is HumanReviewProtocolVerdict.PASS:
        explanation_codes.append("human_review_protocol_integrity_passed")
        explanation_codes.append("musical_superiority_not_implied_by_pass")

    return CuratedRealLibraryHumanReviewReport(
        report_id=report_id,
        snapshot_ref=expected_snapshot_ref,
        protocol_ref=(
            "curated-real-library-human-review",
            HUMAN_DJ_REVIEW_PROTOCOL_VERSION,
        ),
        case_count=len(case_tuple),
        reviewed_case_count=reviewed_case_count,
        review_count=len(review_tuple),
        covered_set_roles=covered_roles,
        missing_set_roles=missing_roles,
        reviewed_case_fraction=reviewed_case_fraction,
        blind_integrity_rate=blind_integrity_rate,
        dimension_coverage_rate=dimension_coverage_rate,
        engineering_regression_count=engineering_regression_count,
        greedy_preference_count=greedy_preference_count,
        beam_preference_count=beam_preference_count,
        tie_count=tie_count,
        abstain_count=abstain_count,
        dimension_evidence=dimension_evidence,
        verdict=verdict,
        activation_authorized=False,
        explanation_codes=tuple(explanation_codes),
    )


__all__ = [
    "build_blinded_plan_assignment",
    "evaluate_curated_real_library_human_review_r1",
    "reviewable_plan_from_alternative",
]
