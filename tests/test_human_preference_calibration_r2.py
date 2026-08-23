from __future__ import annotations

from dataclasses import replace

import pytest

from core.intelligence.competitive_curation_contract import (
    ShadowPathComparison,
    ShadowPathPreference,
)
from core.intelligence.curated_real_library_review_contract import (
    REQUIRED_HUMAN_REVIEW_DIMENSIONS_R1,
    BlindedPlanAssignment,
    CuratedReviewCase,
    CuratedSetRole,
    HumanDJReview,
    HumanDimensionPairRating,
    HumanPlanPreference,
    ReviewPlanStrategy,
    ReviewableSetPlan,
)
from core.intelligence.human_preference_calibration_contract import (
    CalibrationVerdict,
    HumanPreferenceCalibrationPolicy,
    ResolvedPreference,
)
from services.intelligence.curated_real_library_review import build_blinded_plan_assignment
from services.intelligence.human_preference_calibration import (
    HumanPreferenceCalibrationError,
    build_human_preference_calibration_report,
    calibrate_case_preference,
)


def _plan(index: int, strategy: ReviewPlanStrategy) -> ReviewableSetPlan:
    label = "greedy" if strategy is ReviewPlanStrategy.GREEDY_RECOMMEND_NEXT else "beam"
    return ReviewableSetPlan(
        plan_id=f"plan:{label}:{index:02d}",
        strategy=strategy,
        result_id=f"result:{label}:{index:02d}",
        path_id=f"path:{label}:{index:02d}",
        ordered_track_ids=tuple(f"track:{index:02d}:{offset}" for offset in range(4)),
        transition_ids=tuple(f"transition:{label}:{index:02d}:{offset}" for offset in range(3)),
        evidence_refs=(f"evidence:{label}:{index:02d}",),
    )


def _case(index: int, role: CuratedSetRole) -> CuratedReviewCase:
    return CuratedReviewCase(
        case_id=f"case-{index:02d}",
        snapshot_ref=("snapshot-r2", "1"),
        scenario_fingerprint=f"scenario:{index:02d}",
        set_role=role,
        benchmark_ref=("human-preference-calibration", "r2"),
        greedy_plan=_plan(index, ReviewPlanStrategy.GREEDY_RECOMMEND_NEXT),
        beam_plan=_plan(index, ReviewPlanStrategy.BOUNDED_BEAM),
        engineering_acceptance_passed=True,
        evidence_refs=(f"evidence:case:{index:02d}",),
    )


def _cases() -> tuple[CuratedReviewCase, ...]:
    roles = tuple(CuratedSetRole)
    return tuple(_case(index, roles[index % len(roles)]) for index in range(12))


def _assignment(case: CuratedReviewCase) -> BlindedPlanAssignment:
    return build_blinded_plan_assignment(case=case, blinding_seed="bundle-68-synthetic-test-seed")


def _preference_for_strategy(
    case: CuratedReviewCase,
    assignment: BlindedPlanAssignment,
    strategy: ResolvedPreference,
) -> HumanPlanPreference:
    if strategy is ResolvedPreference.TIE:
        return HumanPlanPreference.TIE
    if strategy is ResolvedPreference.ABSTAIN:
        return HumanPlanPreference.ABSTAIN
    target_plan_id = (
        case.greedy_plan.plan_id
        if strategy is ResolvedPreference.GREEDY
        else case.beam_plan.plan_id
    )
    return (
        HumanPlanPreference.PLAN_A
        if assignment.slot_a_plan_id == target_plan_id
        else HumanPlanPreference.PLAN_B
    )


def _review(
    case: CuratedReviewCase,
    assignment: BlindedPlanAssignment,
    human: ResolvedPreference,
    *,
    confidence: float = 0.9,
) -> HumanDJReview:
    preference = _preference_for_strategy(case, assignment, human)
    ratings = tuple(
        HumanDimensionPairRating(
            dimension=dimension,
            plan_a_score=4.0,
            plan_b_score=3.0,
        )
        for dimension in REQUIRED_HUMAN_REVIEW_DIMENSIONS_R1
    )
    return HumanDJReview(
        review_id=f"review:{case.case_id}",
        assignment_id=assignment.assignment_id,
        reviewer_ref="synthetic-test-reviewer",
        preference=preference,
        ratings=ratings,
        confidence=confidence,
        observed_at="2026-08-23T03:00:00Z",
        algorithm_identity_was_hidden=True,
        reason_codes=("synthetic_test_fixture_only",),
        evidence_refs=(f"evidence:review:{case.case_id}",),
        activation_authorized=False,
    )


def _comparison(
    case: CuratedReviewCase,
    challenger: ResolvedPreference,
    *,
    reverse: bool = False,
) -> ShadowPathComparison:
    left_path = case.beam_plan.path_id if reverse else case.greedy_plan.path_id
    right_path = case.greedy_plan.path_id if reverse else case.beam_plan.path_id
    path_for_strategy = {
        ResolvedPreference.GREEDY: case.greedy_plan.path_id,
        ResolvedPreference.BEAM: case.beam_plan.path_id,
    }
    if challenger is ResolvedPreference.TIE:
        shadow = ShadowPathPreference.TIE
        delta = 0.0
    elif challenger is ResolvedPreference.NOT_PROVEN:
        shadow = ShadowPathPreference.NOT_PROVEN
        delta = None
    else:
        winner_path = path_for_strategy[challenger]
        shadow = (
            ShadowPathPreference.LEFT
            if winner_path == left_path
            else ShadowPathPreference.RIGHT
        )
        delta = -0.2 if shadow is ShadowPathPreference.LEFT else 0.2
    return ShadowPathComparison(
        left_path_id=left_path,
        right_path_id=right_path,
        left_score=None if shadow is ShadowPathPreference.NOT_PROVEN else 0.8,
        right_score=None if shadow is ShadowPathPreference.NOT_PROVEN else 0.8 + (delta or 0.0),
        right_minus_left=delta,
        preference=shadow,
        reason_codes=("synthetic_test_fixture_only",),
        activation_authorized=False,
    )


def test_blind_slot_resolution_maps_back_to_source_strategy_not_slot_letter() -> None:
    case = _case(0, CuratedSetRole.PEAK)
    assignment = _assignment(case)
    human_strategy = ResolvedPreference.BEAM
    review = _review(case, assignment, human_strategy)
    comparison = _comparison(case, human_strategy, reverse=True)

    evidence = calibrate_case_preference(
        case=case,
        assignment=assignment,
        review=review,
        comparison=comparison,
    )

    assert evidence.human_preference is ResolvedPreference.BEAM
    assert evidence.challenger_preference is ResolvedPreference.BEAM
    assert evidence.exact_agreement is True
    assert evidence.decisive_agreement is True
    assert evidence.activation_authorized is False


def test_human_tie_is_preserved_and_false_winner_is_surfaced() -> None:
    case = _case(1, CuratedSetRole.BUILD)
    assignment = _assignment(case)
    evidence = calibrate_case_preference(
        case=case,
        assignment=assignment,
        review=_review(case, assignment, ResolvedPreference.TIE),
        comparison=_comparison(case, ResolvedPreference.GREEDY),
    )

    assert evidence.human_preference is ResolvedPreference.TIE
    assert evidence.challenger_preference is ResolvedPreference.GREEDY
    assert evidence.exact_agreement is False
    assert evidence.decisive_agreement is None
    assert "challenger_false_winner_on_human_tie" in evidence.reason_codes


def test_abstain_is_excluded_from_accuracy_denominators() -> None:
    cases = (_case(0, CuratedSetRole.OPENING),)
    case = cases[0]
    assignment = _assignment(case)
    evidence = calibrate_case_preference(
        case=case,
        assignment=assignment,
        review=_review(case, assignment, ResolvedPreference.ABSTAIN),
        comparison=_comparison(case, ResolvedPreference.BEAM),
    )
    report = build_human_preference_calibration_report(
        all_cases=cases,
        case_evidence=(evidence,),
        policy=HumanPreferenceCalibrationPolicy(
            minimum_cases=1,
            minimum_decisive_judgments=1,
            required_set_roles=(CuratedSetRole.OPENING,),
        ),
    )

    assert report.abstain_count == 1
    assert report.exact_agreement_rate is None
    assert report.decisive_agreement_rate is None
    assert report.verdict is CalibrationVerdict.INCOMPLETE


def test_shadow_path_identity_mismatch_is_fail_closed() -> None:
    case = _case(2, CuratedSetRole.MID_SET)
    assignment = _assignment(case)
    valid = _comparison(case, ResolvedPreference.GREEDY)
    invalid = replace(valid, right_path_id="path:foreign")

    with pytest.raises(HumanPreferenceCalibrationError, match="bind exactly"):
        calibrate_case_preference(
            case=case,
            assignment=assignment,
            review=_review(case, assignment, ResolvedPreference.GREEDY),
            comparison=invalid,
        )


def test_assignment_plan_identity_mismatch_is_fail_closed() -> None:
    case = _case(3, CuratedSetRole.RESET)
    assignment = _assignment(case)
    invalid = BlindedPlanAssignment(
        assignment_id=assignment.assignment_id,
        case_id=case.case_id,
        slot_a_plan_id=case.greedy_plan.plan_id,
        slot_b_plan_id="plan:foreign",
        assignment_fingerprint=assignment.assignment_fingerprint,
        algorithm_identity_hidden=True,
    )

    with pytest.raises(HumanPreferenceCalibrationError, match="source plans"):
        calibrate_case_preference(
            case=case,
            assignment=invalid,
            review=_review(case, invalid, ResolvedPreference.GREEDY),
            comparison=_comparison(case, ResolvedPreference.GREEDY),
        )


def test_low_case_or_role_coverage_is_incomplete() -> None:
    cases = (_case(0, CuratedSetRole.OPENING), _case(1, CuratedSetRole.BUILD))
    evidence = []
    for case in cases:
        assignment = _assignment(case)
        evidence.append(
            calibrate_case_preference(
                case=case,
                assignment=assignment,
                review=_review(case, assignment, ResolvedPreference.GREEDY),
                comparison=_comparison(case, ResolvedPreference.GREEDY),
            )
        )

    report = build_human_preference_calibration_report(
        all_cases=cases,
        case_evidence=tuple(evidence),
    )

    assert report.verdict is CalibrationVerdict.INCOMPLETE
    assert "calibration_case_count_below_policy" in report.explanation_codes
    assert "calibration_required_set_roles_missing" in report.explanation_codes


def test_high_agreement_complete_synthetic_matrix_supports_further_evaluation_only() -> None:
    cases = _cases()
    evidence = []
    for index, case in enumerate(cases):
        assignment = _assignment(case)
        human = ResolvedPreference.GREEDY if index % 2 == 0 else ResolvedPreference.BEAM
        evidence.append(
            calibrate_case_preference(
                case=case,
                assignment=assignment,
                review=_review(case, assignment, human, confidence=0.9),
                comparison=_comparison(case, human, reverse=index % 3 == 0),
            )
        )

    report = build_human_preference_calibration_report(
        all_cases=cases,
        case_evidence=tuple(evidence),
    )
    replay = build_human_preference_calibration_report(
        all_cases=tuple(reversed(cases)),
        case_evidence=tuple(reversed(evidence)),
    )

    assert report == replay
    assert report.reviewed_case_count == 12
    assert report.decisive_human_count == 12
    assert report.exact_agreement_rate == 1.0
    assert report.decisive_agreement_rate == 1.0
    assert report.confidence_weighted_decisive_agreement == 1.0
    assert report.verdict is CalibrationVerdict.SUPPORTS_FURTHER_EVALUATION
    assert report.activation_authorized is False
    assert report.personal_dj_model_training_authorized is False
    assert "calibration_supports_further_evaluation_only" in report.explanation_codes


def test_complete_but_poor_agreement_does_not_support_activation() -> None:
    cases = _cases()
    evidence = []
    for case in cases:
        assignment = _assignment(case)
        evidence.append(
            calibrate_case_preference(
                case=case,
                assignment=assignment,
                review=_review(case, assignment, ResolvedPreference.GREEDY, confidence=1.0),
                comparison=_comparison(case, ResolvedPreference.BEAM),
            )
        )

    report = build_human_preference_calibration_report(
        all_cases=cases,
        case_evidence=tuple(evidence),
    )

    assert report.verdict is CalibrationVerdict.DOES_NOT_SUPPORT_ACTIVATION
    assert report.exact_agreement_rate == 0.0
    assert report.decisive_agreement_rate == 0.0
    assert "calibration_decisive_agreement_below_policy" in report.explanation_codes
    assert report.activation_authorized is False


def test_confidence_weighting_is_transparent_and_abstains_do_not_change_it() -> None:
    cases = _cases()
    evidence = []
    for index, case in enumerate(cases):
        assignment = _assignment(case)
        if index == 11:
            human = ResolvedPreference.ABSTAIN
            challenger = ResolvedPreference.GREEDY
            confidence = 1.0
        else:
            human = ResolvedPreference.GREEDY
            challenger = ResolvedPreference.GREEDY if index < 6 else ResolvedPreference.BEAM
            confidence = 1.0 if index < 6 else 0.25
        evidence.append(
            calibrate_case_preference(
                case=case,
                assignment=assignment,
                review=_review(case, assignment, human, confidence=confidence),
                comparison=_comparison(case, challenger),
            )
        )

    report = build_human_preference_calibration_report(
        all_cases=cases,
        case_evidence=tuple(evidence),
        policy=HumanPreferenceCalibrationPolicy(minimum_decisive_judgments=6),
    )

    assert report.abstain_count == 1
    assert report.decisive_human_count == 11
    assert report.confidence_weighted_decisive_agreement is not None
    assert report.confidence_weighted_decisive_agreement > report.decisive_agreement_rate


def test_contract_rejects_activation_or_training_authority() -> None:
    with pytest.raises(ValueError, match="optimizer activation"):
        HumanPreferenceCalibrationPolicy(activation_authorized=True)
    with pytest.raises(ValueError, match="Personal DJ Model"):
        HumanPreferenceCalibrationPolicy(personal_dj_model_training_authorized=True)
