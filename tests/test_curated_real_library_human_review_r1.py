from __future__ import annotations

from dataclasses import replace

import pytest

from core.intelligence.curated_real_library_review_contract import (
    REQUIRED_HUMAN_REVIEW_DIMENSIONS_R1,
    BlindedPlanAssignment,
    CuratedLibrarySnapshot,
    CuratedReviewCase,
    CuratedSetRole,
    HumanDJReview,
    HumanDimensionPairRating,
    HumanPlanPreference,
    HumanReviewProtocolThresholds,
    HumanReviewProtocolVerdict,
    ReviewPlanStrategy,
    ReviewableSetPlan,
)
from services.intelligence.curated_real_library_review import (
    build_blinded_plan_assignment,
    evaluate_curated_real_library_human_review_r1,
)


def _snapshot() -> CuratedLibrarySnapshot:
    return CuratedLibrarySnapshot(
        snapshot_id="library-snapshot-r1",
        snapshot_version="1",
        library_fingerprint="sha256:fixture-library",
        track_ids=tuple(f"track-{index:02d}" for index in range(40)),
        generated_at="2026-08-17T04:00:00+02:00",
        evidence_refs=("evidence:library-manifest",),
    )


def _plan(
    *,
    case_index: int,
    strategy: ReviewPlanStrategy,
    tracks: tuple[str, ...],
) -> ReviewableSetPlan:
    prefix = "greedy" if strategy is ReviewPlanStrategy.GREEDY_RECOMMEND_NEXT else "beam"
    return ReviewableSetPlan(
        plan_id=f"plan:{prefix}:{case_index}",
        strategy=strategy,
        result_id=f"result:{prefix}:{case_index}",
        path_id=f"path:{prefix}:{case_index}",
        ordered_track_ids=tracks,
        transition_ids=(f"transition:{prefix}:{case_index}:1",),
        evidence_refs=(f"evidence:{prefix}:{case_index}",),
    )


def _case(index: int, role: CuratedSetRole, *, engineering_ok: bool = True) -> CuratedReviewCase:
    tracks = (
        f"track-{(index * 3) % 40:02d}",
        f"track-{(index * 3 + 1) % 40:02d}",
        f"track-{(index * 3 + 2) % 40:02d}",
    )
    return CuratedReviewCase(
        case_id=f"case-{index:02d}",
        snapshot_ref=("library-snapshot-r1", "1"),
        scenario_fingerprint=f"scenario:{index:02d}",
        set_role=role,
        benchmark_ref=(f"benchmark:{index:02d}", "optimizer-benchmark-v1"),
        greedy_plan=_plan(
            case_index=index,
            strategy=ReviewPlanStrategy.GREEDY_RECOMMEND_NEXT,
            tracks=tracks,
        ),
        beam_plan=_plan(
            case_index=index,
            strategy=ReviewPlanStrategy.BOUNDED_BEAM,
            tracks=tracks,
        ),
        engineering_acceptance_passed=engineering_ok,
        evidence_refs=(f"evidence:case:{index:02d}",),
    )


def _cases(*, engineering_failure_index: int | None = None) -> tuple[CuratedReviewCase, ...]:
    roles = tuple(CuratedSetRole)
    return tuple(
        _case(
            index,
            roles[index % len(roles)],
            engineering_ok=index != engineering_failure_index,
        )
        for index in range(12)
    )


def _review(
    *,
    case: CuratedReviewCase,
    assignment: BlindedPlanAssignment,
    reviewer_ref: str = "dj-reviewer-1",
) -> HumanDJReview:
    beam_is_a = assignment.slot_a_plan_id == case.beam_plan.plan_id
    ratings = tuple(
        HumanDimensionPairRating(
            dimension=dimension,
            plan_a_score=5.0 if beam_is_a else 3.0,
            plan_b_score=3.0 if beam_is_a else 5.0,
        )
        for dimension in REQUIRED_HUMAN_REVIEW_DIMENSIONS_R1
    )
    return HumanDJReview(
        review_id=f"review:{case.case_id}:{reviewer_ref}",
        assignment_id=assignment.assignment_id,
        reviewer_ref=reviewer_ref,
        preference=(
            HumanPlanPreference.PLAN_A if beam_is_a else HumanPlanPreference.PLAN_B
        ),
        ratings=ratings,
        confidence=0.9,
        observed_at="2026-08-17T04:05:00+02:00",
        algorithm_identity_was_hidden=True,
        reason_codes=("fixture_blind_review",),
    )


def _evidence(
    cases: tuple[CuratedReviewCase, ...],
) -> tuple[tuple[BlindedPlanAssignment, ...], tuple[HumanDJReview, ...]]:
    assignments = tuple(
        build_blinded_plan_assignment(case=case, blinding_seed="review-seed-r1")
        for case in cases
    )
    reviews = tuple(
        _review(case=case, assignment=assignment)
        for case, assignment in zip(cases, assignments, strict=True)
    )
    return assignments, reviews


def test_blinded_assignment_is_deterministic_and_contains_both_plans() -> None:
    case = _case(0, CuratedSetRole.OPENING)

    first = build_blinded_plan_assignment(case=case, blinding_seed="seed-1")
    second = build_blinded_plan_assignment(case=case, blinding_seed="seed-1")

    assert first == second
    assert first.algorithm_identity_hidden is True
    assert {first.slot_a_plan_id, first.slot_b_plan_id} == {
        case.greedy_plan.plan_id,
        case.beam_plan.plan_id,
    }


def test_complete_blind_real_library_protocol_passes_integrity_not_activation() -> None:
    snapshot = _snapshot()
    cases = _cases()
    assignments, reviews = _evidence(cases)

    result = evaluate_curated_real_library_human_review_r1(
        snapshot=snapshot,
        cases=cases,
        assignments=assignments,
        reviews=reviews,
    )

    assert result.verdict is HumanReviewProtocolVerdict.PASS
    assert result.case_count == 12
    assert result.reviewed_case_count == 12
    assert result.review_count == 12
    assert result.missing_set_roles == ()
    assert result.reviewed_case_fraction == 1.0
    assert result.blind_integrity_rate == 1.0
    assert result.dimension_coverage_rate == 1.0
    assert result.engineering_regression_count == 0
    assert result.beam_preference_count == 12
    assert result.greedy_preference_count == 0
    assert len(result.dimension_evidence) == len(REQUIRED_HUMAN_REVIEW_DIMENSIONS_R1)
    assert all(item.beam_mean > item.greedy_mean for item in result.dimension_evidence)
    assert result.activation_authorized is False
    assert "musical_superiority_not_implied_by_pass" in result.explanation_codes
    assert "personal_dj_model_training_not_authorized" in result.explanation_codes


def test_human_preference_cannot_override_engineering_regression() -> None:
    snapshot = _snapshot()
    cases = _cases(engineering_failure_index=4)
    assignments, reviews = _evidence(cases)

    result = evaluate_curated_real_library_human_review_r1(
        snapshot=snapshot,
        cases=cases,
        assignments=assignments,
        reviews=reviews,
    )

    assert result.beam_preference_count == 12
    assert result.engineering_regression_count == 1
    assert result.verdict is HumanReviewProtocolVerdict.FAIL
    assert "engineering_regression_count_above_threshold" in result.explanation_codes
    assert result.activation_authorized is False


def test_missing_real_library_coverage_is_incomplete_not_pass() -> None:
    snapshot = _snapshot()
    cases = _cases()[:5]
    assignments, reviews = _evidence(cases)

    result = evaluate_curated_real_library_human_review_r1(
        snapshot=snapshot,
        cases=cases,
        assignments=assignments,
        reviews=reviews,
    )

    assert result.verdict is HumanReviewProtocolVerdict.INCOMPLETE
    assert result.case_count == 5
    assert result.missing_set_roles
    assert result.activation_authorized is False


def test_unreviewed_case_keeps_protocol_incomplete() -> None:
    snapshot = _snapshot()
    cases = _cases()
    assignments, reviews = _evidence(cases)

    result = evaluate_curated_real_library_human_review_r1(
        snapshot=snapshot,
        cases=cases,
        assignments=assignments,
        reviews=reviews[:-1],
    )

    assert result.verdict is HumanReviewProtocolVerdict.INCOMPLETE
    assert result.reviewed_case_count == 11
    assert result.reviewed_case_fraction < 1.0


def test_dimension_gap_is_fail_closed() -> None:
    snapshot = _snapshot()
    cases = _cases()
    assignments, reviews = _evidence(cases)
    incomplete_review = replace(reviews[0], ratings=reviews[0].ratings[:-1])

    result = evaluate_curated_real_library_human_review_r1(
        snapshot=snapshot,
        cases=cases,
        assignments=assignments,
        reviews=(incomplete_review, *reviews[1:]),
    )

    assert result.verdict is HumanReviewProtocolVerdict.FAIL
    assert result.dimension_coverage_rate < 1.0
    assert "dimension_coverage_rate_below_threshold" in result.explanation_codes


def test_review_contract_rejects_visible_algorithm_identity() -> None:
    case = _case(0, CuratedSetRole.OPENING)
    assignment = build_blinded_plan_assignment(case=case, blinding_seed="seed-1")

    with pytest.raises(ValueError, match="algorithm identity was visible"):
        replace(
            _review(case=case, assignment=assignment),
            algorithm_identity_was_hidden=False,
        )


def test_thresholds_cannot_authorize_activation() -> None:
    with pytest.raises(ValueError, match="cannot authorize activation"):
        HumanReviewProtocolThresholds(activation_authorized=True)
