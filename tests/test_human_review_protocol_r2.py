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
    HumanDimensionPairRating,
    ReviewPlanStrategy,
    ReviewableSetPlan,
)
from core.intelligence.human_review_protocol_r2_contract import (
    Assessability,
    CurationCalibrationCaseR3,
    CurationCalibrationPolicyR3,
    CurationCalibrationVerdict,
    CurationDimensionPairRating,
    CurationPreference,
    CurationReviewR2,
    HoldoutCandidate,
    HoldoutCaseSamplingPolicy,
    HumanExecutionReviewR2,
    HumanTransitionAuditionReviewR2,
    MeaningfulDifferenceStatus,
    PriorCaseExposure,
    ResolvedCurationPreference,
    ReviewDatasetRole,
    TransitionDimensionEvidenceR2,
    TransitionFeasibilityDimension,
    TransitionReviewSpecR2,
    ValidationClaimScope,
)
from services.intelligence.curated_real_library_review import build_blinded_plan_assignment
from services.intelligence.human_review_protocol_r2 import (
    HumanReviewProtocolR2Error,
    build_curation_calibration_report_r3,
    calibrate_curation_case_r3,
    replacement_case_r2,
    select_holdout_cases_r2,
    transition_review_spec_fingerprint,
    vocal_collision_evidence_r2,
    wilson_interval,
)


def _plan(index: int, strategy: ReviewPlanStrategy) -> ReviewableSetPlan:
    label = "greedy" if strategy is ReviewPlanStrategy.GREEDY_RECOMMEND_NEXT else "beam"
    return ReviewableSetPlan(
        plan_id=f"plan:{label}:{index:02d}",
        strategy=strategy,
        result_id=f"result:{label}:{index:02d}",
        path_id=f"path:{label}:{index:02d}",
        ordered_track_ids=tuple(f"track:{index:02d}:{offset}" for offset in range(5)),
        transition_ids=tuple(f"transition:{label}:{index:02d}:{offset}" for offset in range(4)),
        evidence_refs=(f"evidence:{label}:{index:02d}",),
    )


def _case(index: int, role: CuratedSetRole) -> CuratedReviewCase:
    return CuratedReviewCase(
        case_id=f"case-r2-{index:02d}",
        snapshot_ref=("snapshot-holdout", "1"),
        scenario_fingerprint=f"scenario:holdout:{index:02d}",
        set_role=role,
        benchmark_ref=("human-review-protocol-r2", "1"),
        greedy_plan=_plan(index, ReviewPlanStrategy.GREEDY_RECOMMEND_NEXT),
        beam_plan=_plan(index, ReviewPlanStrategy.BOUNDED_BEAM),
        engineering_acceptance_passed=True,
        evidence_refs=(f"evidence:case:{index:02d}",),
    )


def _assignment(case: CuratedReviewCase, *, seed: str = "r2-holdout-blind-seed") -> BlindedPlanAssignment:
    return build_blinded_plan_assignment(case=case, blinding_seed=seed)


def _preference_for(
    case: CuratedReviewCase,
    assignment: BlindedPlanAssignment,
    target: ResolvedCurationPreference,
) -> CurationPreference:
    if target is ResolvedCurationPreference.TIE:
        return CurationPreference.TIE
    if target is ResolvedCurationPreference.ABSTAIN:
        return CurationPreference.ABSTAIN
    plan_id = (
        case.greedy_plan.plan_id
        if target is ResolvedCurationPreference.GREEDY
        else case.beam_plan.plan_id
    )
    return (
        CurationPreference.PLAN_A
        if assignment.slot_a_plan_id == plan_id
        else CurationPreference.PLAN_B
    )


def _review(
    case: CuratedReviewCase,
    assignment: BlindedPlanAssignment,
    target: ResolvedCurationPreference,
    *,
    dataset_role: ReviewDatasetRole = ReviewDatasetRole.PERSONAL_HOLDOUT,
    exposure: PriorCaseExposure = PriorCaseExposure.NO,
    transition_execution_used: bool = False,
    transition_preview_heard: bool = False,
    review_id: str | None = None,
) -> CurationReviewR2:
    ratings = (
        CurationDimensionPairRating(
            dimension=dimension,
            plan_a_score=4.0,
            plan_b_score=3.0,
        )
        for dimension in (
            # explicit tuple keeps test independent from R1 dimensions
            __import__(
                "core.intelligence.human_review_protocol_r2_contract",
                fromlist=["CurationDimension"],
            ).CurationDimension.ENERGY_FLOW,
            __import__(
                "core.intelligence.human_review_protocol_r2_contract",
                fromlist=["CurationDimension"],
            ).CurationDimension.DRAMATURGICAL_FIT,
            __import__(
                "core.intelligence.human_review_protocol_r2_contract",
                fromlist=["CurationDimension"],
            ).CurationDimension.SET_COHERENCE,
            __import__(
                "core.intelligence.human_review_protocol_r2_contract",
                fromlist=["CurationDimension"],
            ).CurationDimension.ALTERNATIVE_USEFULNESS,
        )
    )
    return CurationReviewR2(
        review_id=review_id or f"curation-review:{case.case_id}",
        assignment_id=assignment.assignment_id,
        reviewer_ref="synthetic-personal-reviewer",
        curation_session_id=f"session:{case.case_id}",
        dataset_role=dataset_role,
        preference=_preference_for(case, assignment, target),
        ratings=tuple(ratings),
        confidence=0.9,
        observed_at="2026-08-23T07:00:00Z",
        prior_case_exposure=exposure,
        transition_execution_used=transition_execution_used,
        transition_preview_heard=transition_preview_heard,
        algorithm_identity_was_hidden=True,
        reason_codes=("synthetic_test_fixture_only",),
        activation_authorized=False,
        personal_dj_model_training_authorized=False,
    )


def _comparison(
    case: CuratedReviewCase,
    target: ResolvedCurationPreference,
    *,
    reverse: bool = False,
) -> ShadowPathComparison:
    left = case.beam_plan.path_id if reverse else case.greedy_plan.path_id
    right = case.greedy_plan.path_id if reverse else case.beam_plan.path_id
    if target is ResolvedCurationPreference.TIE:
        preference = ShadowPathPreference.TIE
        delta = 0.0
    elif target is ResolvedCurationPreference.NOT_PROVEN:
        preference = ShadowPathPreference.NOT_PROVEN
        delta = None
    else:
        winner = (
            case.greedy_plan.path_id
            if target is ResolvedCurationPreference.GREEDY
            else case.beam_plan.path_id
        )
        preference = ShadowPathPreference.LEFT if left == winner else ShadowPathPreference.RIGHT
        delta = -0.15 if preference is ShadowPathPreference.LEFT else 0.15
    return ShadowPathComparison(
        left_path_id=left,
        right_path_id=right,
        left_score=None if preference is ShadowPathPreference.NOT_PROVEN else 0.75,
        right_score=None if preference is ShadowPathPreference.NOT_PROVEN else 0.75 + (delta or 0.0),
        right_minus_left=delta,
        preference=preference,
        reason_codes=("synthetic_test_fixture_only",),
        activation_authorized=False,
    )


def _binding(
    case: CuratedReviewCase,
    *,
    dataset_role: ReviewDatasetRole = ReviewDatasetRole.PERSONAL_HOLDOUT,
    difference: MeaningfulDifferenceStatus = MeaningfulDifferenceStatus.MEANINGFULLY_DISTINCT,
) -> CurationCalibrationCaseR3:
    return CurationCalibrationCaseR3(
        case=case,
        dataset_role=dataset_role,
        meaningful_difference_status=difference,
        selection_manifest_fingerprint="holdout-selection-r2:synthetic",
    )


def _calibrated(
    case: CuratedReviewCase,
    target: ResolvedCurationPreference,
    *,
    dataset_role: ReviewDatasetRole = ReviewDatasetRole.PERSONAL_HOLDOUT,
    exposure: PriorCaseExposure = PriorCaseExposure.NO,
    transition_execution_used: bool = False,
    transition_preview_heard: bool = False,
    challenger: ResolvedCurationPreference | None = None,
    review_id: str | None = None,
):
    assignment = _assignment(case)
    return calibrate_curation_case_r3(
        case_binding=_binding(case, dataset_role=dataset_role),
        assignment=assignment,
        review=_review(
            case,
            assignment,
            target,
            dataset_role=dataset_role,
            exposure=exposure,
            transition_execution_used=transition_execution_used,
            transition_preview_heard=transition_preview_heard,
            review_id=review_id,
        ),
        comparison=_comparison(case, challenger or target),
    )


def _personal_cases(count: int = 24) -> tuple[CuratedReviewCase, ...]:
    roles = tuple(CuratedSetRole)
    return tuple(_case(index, roles[index % len(roles)]) for index in range(count))


def test_r1_dimension_set_cannot_satisfy_curation_review_r2() -> None:
    case = _case(0, CuratedSetRole.OPENING)
    assignment = _assignment(case)
    old_ratings = tuple(
        HumanDimensionPairRating(dimension=dimension, plan_a_score=4.0, plan_b_score=3.0)
        for dimension in REQUIRED_HUMAN_REVIEW_DIMENSIONS_R1
    )
    with pytest.raises(ValueError, match="four R2 curation dimensions"):
        CurationReviewR2(
            review_id="r1-masquerade",
            assignment_id=assignment.assignment_id,
            reviewer_ref="reviewer",
            curation_session_id="session",
            dataset_role=ReviewDatasetRole.PERSONAL_HOLDOUT,
            preference=CurationPreference.TIE,
            ratings=old_ratings,  # type: ignore[arg-type]
            confidence=0.5,
            observed_at="2026-08-23T07:00:00Z",
        )


def test_development_case_is_preserved_but_excluded_from_holdout_metrics() -> None:
    case = _case(1, CuratedSetRole.BUILD)
    evidence = _calibrated(
        case,
        ResolvedCurationPreference.GREEDY,
        dataset_role=ReviewDatasetRole.DEVELOPMENT_REGRESSION,
    )
    assert evidence.clean_holdout_eligible is False
    assert evidence.exact_agreement is None
    assert "development_regression_case_excluded_from_holdout_metrics" in evidence.reason_codes


def test_contaminated_manual_mix_review_is_preserved_but_excluded() -> None:
    case = _case(2, CuratedSetRole.MID_SET)
    evidence = _calibrated(
        case,
        ResolvedCurationPreference.BEAM,
        transition_execution_used=True,
    )
    assert evidence.clean_holdout_eligible is False
    assert evidence.exact_agreement is None
    assert "curation_review_not_clean_holdout_eligible" in evidence.reason_codes


def test_prior_case_exposure_excludes_clean_holdout_metrics() -> None:
    case = _case(3, CuratedSetRole.PEAK)
    evidence = _calibrated(
        case,
        ResolvedCurationPreference.GREEDY,
        exposure=PriorCaseExposure.YES,
    )
    assert evidence.clean_holdout_eligible is False


def test_blind_slot_inversion_resolves_source_strategy_not_slot_letter() -> None:
    case = _case(4, CuratedSetRole.RESET)
    assignment = _assignment(case, seed="different-slot-seed")
    review = _review(case, assignment, ResolvedCurationPreference.BEAM)
    evidence = calibrate_curation_case_r3(
        case_binding=_binding(case),
        assignment=assignment,
        review=review,
        comparison=_comparison(case, ResolvedCurationPreference.BEAM, reverse=True),
    )
    assert evidence.human_preference is ResolvedCurationPreference.BEAM
    assert evidence.challenger_preference is ResolvedCurationPreference.BEAM
    assert evidence.exact_agreement is True


def test_dimension_arithmetic_does_not_rewrite_explicit_preference() -> None:
    case = _case(5, CuratedSetRole.CLOSING)
    assignment = _assignment(case)
    review = _review(case, assignment, ResolvedCurationPreference.BEAM)
    # helper ratings always numerically favor Plan A, but explicit preference may resolve to Beam.
    evidence = calibrate_curation_case_r3(
        case_binding=_binding(case),
        assignment=assignment,
        review=review,
        comparison=_comparison(case, ResolvedCurationPreference.BEAM),
    )
    assert evidence.human_preference is ResolvedCurationPreference.BEAM


def test_shadow_path_identity_mismatch_fails_closed() -> None:
    case = _case(6, CuratedSetRole.OPENING)
    assignment = _assignment(case)
    invalid = replace(
        _comparison(case, ResolvedCurationPreference.GREEDY),
        right_path_id="foreign-path",
    )
    with pytest.raises(HumanReviewProtocolR2Error, match="source paths"):
        calibrate_curation_case_r3(
            case_binding=_binding(case),
            assignment=assignment,
            review=_review(case, assignment, ResolvedCurationPreference.GREEDY),
            comparison=invalid,
        )


def test_holdout_selection_is_deterministic_and_input_order_independent() -> None:
    roles = tuple(CuratedSetRole)
    candidates = tuple(
        HoldoutCandidate(
            candidate_id=f"candidate-{index:02d}",
            case_id=f"case-{index:02d}",
            set_role=roles[index % len(roles)],
            engineering_acceptance_passed=True,
        )
        for index in range(36)
    )
    policy = HoldoutCaseSamplingPolicy(
        policy_id="personal-holdout-test",
        dataset_role=ReviewDatasetRole.PERSONAL_HOLDOUT,
        canonical_sha="sha:canonical",
        snapshot_fingerprint="snapshot:1",
        eligible_scope_fingerprint="scope:1",
        source_case_generator_version="case-generator-r1",
        sampling_seed="frozen-seed",
        role_quotas=tuple((role, 4) for role in roles),
        fallback_count=6,
    )
    first = select_holdout_cases_r2(policy=policy, candidates=candidates)
    second = select_holdout_cases_r2(policy=policy, candidates=tuple(reversed(candidates)))
    assert first == second
    assert len(first.selected_case_ids) == 24
    assert len(first.fallback_case_ids) == 6


def test_holdout_sampling_rejects_development_role() -> None:
    with pytest.raises(ValueError, match="development/regression"):
        HoldoutCaseSamplingPolicy(
            policy_id="invalid",
            dataset_role=ReviewDatasetRole.DEVELOPMENT_REGRESSION,
            canonical_sha="sha",
            snapshot_fingerprint="snapshot",
            eligible_scope_fingerprint="scope",
            source_case_generator_version="generator",
            sampling_seed="seed",
            role_quotas=((CuratedSetRole.OPENING, 1),),
        )


def test_fallback_replacement_can_only_follow_frozen_order() -> None:
    candidates = tuple(
        HoldoutCandidate(
            candidate_id=f"c-{index}",
            case_id=f"case-{index}",
            set_role=CuratedSetRole.OPENING,
            engineering_acceptance_passed=True,
        )
        for index in range(5)
    )
    policy = HoldoutCaseSamplingPolicy(
        policy_id="fallback-test",
        dataset_role=ReviewDatasetRole.PERSONAL_HOLDOUT,
        canonical_sha="sha",
        snapshot_fingerprint="snapshot",
        eligible_scope_fingerprint="scope",
        source_case_generator_version="generator",
        sampling_seed="seed",
        role_quotas=((CuratedSetRole.OPENING, 2),),
        fallback_count=3,
    )
    selection = select_holdout_cases_r2(policy=policy, candidates=candidates)
    first = replacement_case_r2(
        selection=selection,
        invalid_case_id=selection.selected_case_ids[0],
    )
    second = replacement_case_r2(
        selection=selection,
        invalid_case_id=selection.selected_case_ids[1],
        already_used_fallback_case_ids=(first,),
    )
    assert first == selection.fallback_case_ids[0]
    assert second == selection.fallback_case_ids[1]
    with pytest.raises(HumanReviewProtocolR2Error, match="outside frozen fallback"):
        replacement_case_r2(
            selection=selection,
            invalid_case_id=selection.selected_case_ids[0],
            already_used_fallback_case_ids=("not-frozen",),
        )


def test_transition_spec_fingerprint_changes_with_bound_window() -> None:
    spec = TransitionReviewSpecR2(
        spec_id="spec-1",
        outgoing_track_id="track-a",
        incoming_track_id="track-b",
        outgoing_segment_id="segment-a",
        incoming_segment_id="segment-b",
        outgoing_analysis_revision="analysis-a",
        incoming_analysis_revision="analysis-b",
        outgoing_evidence_fingerprint="evidence-a",
        incoming_evidence_fingerprint="evidence-b",
        outgoing_window_seconds=(180.0, 210.0),
        incoming_window_seconds=(30.0, 60.0),
        duration_seconds=30.0,
        strategy_id="eq-blend",
        strategy_version="1",
        evidence_refs=("transition:evidence",),
        target_bpm=130.0,
        duration_bars=16.0,
        beat_grid_revision="grid-1",
    )
    changed = replace(spec, outgoing_window_seconds=(181.0, 211.0))
    assert transition_review_spec_fingerprint(spec) != transition_review_spec_fingerprint(changed)


def test_missing_explicit_vocal_evidence_is_not_assessable() -> None:
    evidence = vocal_collision_evidence_r2(value=None, explicit_vocal_evidence_refs=())
    assert evidence.dimension is TransitionFeasibilityDimension.VOCAL_COLLISION_RISK
    assert evidence.assessability is Assessability.NOT_ASSESSABLE
    assert evidence.value is None
    assert evidence.reason_code == "explicit_vocal_evidence_missing"


def test_tempo_and_harmonic_feasibility_are_distinct_dimensions() -> None:
    tempo = TransitionDimensionEvidenceR2(
        dimension=TransitionFeasibilityDimension.TEMPO_FEASIBILITY,
        assessability=Assessability.ASSESSABLE,
        value=0.9,
        reason_code=None,
        evidence_refs=("tempo:evidence",),
    )
    harmonic = TransitionDimensionEvidenceR2(
        dimension=TransitionFeasibilityDimension.HARMONIC_COMPATIBILITY,
        assessability=Assessability.ASSESSABLE,
        value=0.2,
        reason_code=None,
        evidence_refs=("key:evidence",),
    )
    assert tempo.dimension is not harmonic.dimension
    assert tempo.value != harmonic.value


def test_human_transition_audition_requires_preview_or_standardized_recipe() -> None:
    with pytest.raises(ValueError, match="rendered preview or standardized recipe"):
        HumanTransitionAuditionReviewR2(
            review_id="transition-review",
            transition_spec_fingerprint="spec:fingerprint",
            reviewer_ref="reviewer",
            observed_at="2026-08-23T07:00:00Z",
        )


def test_human_execution_review_is_separate_and_cannot_authorize_activation() -> None:
    review = HumanExecutionReviewR2(
        review_id="execution-review",
        reviewer_ref="reviewer",
        execution_session_id="execution-session",
        observed_at="2026-08-23T07:00:00Z",
        free_form_execution=True,
    )
    assert review.free_form_execution is True
    with pytest.raises(ValueError, match="cannot authorize activation"):
        replace(review, activation_authorized=True)


def test_complete_clean_personal_holdout_supports_only_further_evaluation() -> None:
    cases = _personal_cases()
    evidence = tuple(
        _calibrated(
            case,
            ResolvedCurationPreference.GREEDY if index % 2 == 0 else ResolvedCurationPreference.BEAM,
        )
        for index, case in enumerate(cases)
    )
    report = build_curation_calibration_report_r3(case_evidence=evidence)
    replay = build_curation_calibration_report_r3(case_evidence=tuple(reversed(evidence)))
    assert report == replay
    assert report.clean_case_count == 24
    assert report.excluded_case_count == 0
    assert report.exact_agreement_rate == 1.0
    assert report.exact_agreement_interval is not None
    assert report.exact_agreement_interval.lower > 0.5
    assert report.verdict is CurationCalibrationVerdict.SUPPORTS_FURTHER_EVALUATION
    assert report.activation_authorized is False
    assert report.personal_dj_model_training_authorized is False


def test_wilson_lower_bound_not_point_estimate_drives_policy_gate() -> None:
    cases = _personal_cases()
    evidence = []
    for index, case in enumerate(cases):
        human = ResolvedCurationPreference.GREEDY
        challenger = human if index < 16 else ResolvedCurationPreference.BEAM
        evidence.append(_calibrated(case, human, challenger=challenger))
    report = build_curation_calibration_report_r3(
        case_evidence=tuple(evidence),
        policy=CurationCalibrationPolicyR3(
            minimum_exact_agreement_lower_bound=0.60,
            minimum_decisive_agreement_lower_bound=0.60,
        ),
    )
    assert report.exact_agreement_rate == pytest.approx(16 / 24)
    assert report.exact_agreement_interval is not None
    assert report.exact_agreement_interval.lower < 0.60
    assert report.verdict is CurationCalibrationVerdict.DOES_NOT_SUPPORT_FURTHER_EVALUATION


def test_duplicate_review_identity_fails_closed() -> None:
    cases = _personal_cases()
    first = _calibrated(cases[0], ResolvedCurationPreference.GREEDY, review_id="duplicate")
    second = _calibrated(cases[1], ResolvedCurationPreference.GREEDY, review_id="duplicate")
    with pytest.raises(HumanReviewProtocolR2Error, match="duplicate curation review identity"):
        build_curation_calibration_report_r3(case_evidence=(first, second))


def test_general_claim_cannot_use_personal_independent_row_analyzer() -> None:
    case = _case(30, CuratedSetRole.OPENING)
    evidence = (_calibrated(case, ResolvedCurationPreference.GREEDY),)
    with pytest.raises(HumanReviewProtocolR2Error, match="cluster-aware analyzer"):
        build_curation_calibration_report_r3(
            case_evidence=evidence,
            policy=CurationCalibrationPolicyR3(
                claim_scope=ValidationClaimScope.GENERAL_DJ_PRODUCT_VALIDATION,
            ),
        )


def test_near_equivalent_status_is_diagnostic_not_silently_decisive_filter() -> None:
    case = _case(31, CuratedSetRole.RESET)
    assignment = _assignment(case)
    evidence = calibrate_curation_case_r3(
        case_binding=_binding(
            case,
            difference=MeaningfulDifferenceStatus.NEAR_EQUIVALENT,
        ),
        assignment=assignment,
        review=_review(case, assignment, ResolvedCurationPreference.TIE),
        comparison=_comparison(case, ResolvedCurationPreference.GREEDY),
    )
    assert evidence.human_preference is ResolvedCurationPreference.TIE
    assert "near_equivalent_case_report_separately" in evidence.reason_codes
    assert "challenger_false_winner_on_human_tie" in evidence.reason_codes


def test_contracts_reject_activation_authority() -> None:
    with pytest.raises(ValueError, match="cannot authorize activation"):
        CurationCalibrationPolicyR3(activation_authorized=True)
