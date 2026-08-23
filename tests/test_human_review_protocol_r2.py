from __future__ import annotations

from dataclasses import replace

import pytest

from core.intelligence.competitive_curation_contract import ShadowPathComparison, ShadowPathPreference
from core.intelligence.curated_real_library_review_contract import (
    REQUIRED_HUMAN_REVIEW_DIMENSIONS_R1,
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
    CurationDimension,
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
)


def _plan(index: int, strategy: ReviewPlanStrategy) -> ReviewableSetPlan:
    name = "greedy" if strategy is ReviewPlanStrategy.GREEDY_RECOMMEND_NEXT else "beam"
    return ReviewableSetPlan(
        plan_id=f"plan:{name}:{index}",
        strategy=strategy,
        result_id=f"result:{name}:{index}",
        path_id=f"path:{name}:{index}",
        ordered_track_ids=tuple(f"track:{index}:{offset}" for offset in range(5)),
        transition_ids=tuple(f"transition:{name}:{index}:{offset}" for offset in range(4)),
        evidence_refs=(f"evidence:{name}:{index}",),
    )


def _case(index: int, role: CuratedSetRole) -> CuratedReviewCase:
    return CuratedReviewCase(
        case_id=f"case-{index:02d}",
        snapshot_ref=("snapshot-holdout", "1"),
        scenario_fingerprint=f"scenario:{index:02d}",
        set_role=role,
        benchmark_ref=("human-review-r2", "1"),
        greedy_plan=_plan(index, ReviewPlanStrategy.GREEDY_RECOMMEND_NEXT),
        beam_plan=_plan(index, ReviewPlanStrategy.BOUNDED_BEAM),
        engineering_acceptance_passed=True,
        evidence_refs=(f"evidence:case:{index:02d}",),
    )


def _cases(count: int = 24) -> tuple[CuratedReviewCase, ...]:
    roles = tuple(CuratedSetRole)
    return tuple(_case(index, roles[index % len(roles)]) for index in range(count))


def _assignment(case: CuratedReviewCase, seed: str = "r2-blind-seed"):
    return build_blinded_plan_assignment(case=case, blinding_seed=seed)


def _curation_preference(case, assignment, target: ResolvedCurationPreference) -> CurationPreference:
    if target is ResolvedCurationPreference.TIE:
        return CurationPreference.TIE
    if target is ResolvedCurationPreference.ABSTAIN:
        return CurationPreference.ABSTAIN
    plan_id = case.greedy_plan.plan_id if target is ResolvedCurationPreference.GREEDY else case.beam_plan.plan_id
    return CurationPreference.PLAN_A if assignment.slot_a_plan_id == plan_id else CurationPreference.PLAN_B


def _ratings() -> tuple[CurationDimensionPairRating, ...]:
    return tuple(
        CurationDimensionPairRating(dimension=dimension, plan_a_score=4.0, plan_b_score=3.0)
        for dimension in CurationDimension
    )


def _review(
    case,
    assignment,
    target: ResolvedCurationPreference,
    *,
    dataset_role: ReviewDatasetRole = ReviewDatasetRole.PERSONAL_HOLDOUT,
    exposure: PriorCaseExposure = PriorCaseExposure.NO,
    transition_execution_used: bool = False,
    transition_preview_heard: bool = False,
    review_id: str | None = None,
):
    return CurationReviewR2(
        review_id=review_id or f"review:{case.case_id}",
        assignment_id=assignment.assignment_id,
        reviewer_ref="synthetic-reviewer",
        curation_session_id=f"session:{case.case_id}",
        dataset_role=dataset_role,
        preference=_curation_preference(case, assignment, target),
        ratings=_ratings(),
        confidence=0.9,
        observed_at="2026-08-23T07:00:00Z",
        prior_case_exposure=exposure,
        transition_execution_used=transition_execution_used,
        transition_preview_heard=transition_preview_heard,
        algorithm_identity_was_hidden=True,
        reason_codes=("synthetic_test_fixture_only",),
    )


def _comparison(case, target: ResolvedCurationPreference, *, reverse: bool = False):
    left = case.beam_plan.path_id if reverse else case.greedy_plan.path_id
    right = case.greedy_plan.path_id if reverse else case.beam_plan.path_id
    if target is ResolvedCurationPreference.TIE:
        pref = ShadowPathPreference.TIE
        delta = 0.0
    elif target is ResolvedCurationPreference.NOT_PROVEN:
        pref = ShadowPathPreference.NOT_PROVEN
        delta = None
    else:
        winner = case.greedy_plan.path_id if target is ResolvedCurationPreference.GREEDY else case.beam_plan.path_id
        pref = ShadowPathPreference.LEFT if winner == left else ShadowPathPreference.RIGHT
        delta = -0.15 if pref is ShadowPathPreference.LEFT else 0.15
    return ShadowPathComparison(
        left_path_id=left,
        right_path_id=right,
        left_score=None if pref is ShadowPathPreference.NOT_PROVEN else 0.75,
        right_score=None if pref is ShadowPathPreference.NOT_PROVEN else 0.75 + (delta or 0.0),
        right_minus_left=delta,
        preference=pref,
        reason_codes=("synthetic_test_fixture_only",),
    )


def _binding(case, dataset_role=ReviewDatasetRole.PERSONAL_HOLDOUT, difference=MeaningfulDifferenceStatus.MEANINGFULLY_DISTINCT):
    return CurationCalibrationCaseR3(
        case=case,
        dataset_role=dataset_role,
        meaningful_difference_status=difference,
        selection_manifest_fingerprint="holdout-selection-r2:synthetic",
    )


def _evidence(
    case,
    human: ResolvedCurationPreference,
    *,
    challenger: ResolvedCurationPreference | None = None,
    dataset_role=ReviewDatasetRole.PERSONAL_HOLDOUT,
    exposure=PriorCaseExposure.NO,
    transition_execution_used=False,
    transition_preview_heard=False,
    attested=True,
    review_id=None,
):
    assignment = _assignment(case)
    return calibrate_curation_case_r3(
        case_binding=_binding(case, dataset_role=dataset_role),
        assignment=assignment,
        review=_review(
            case,
            assignment,
            human,
            dataset_role=dataset_role,
            exposure=exposure,
            transition_execution_used=transition_execution_used,
            transition_preview_heard=transition_preview_heard,
            review_id=review_id,
        ),
        comparison=_comparison(case, challenger or human),
        clean_sequence_attestation=attested,
    )


def _selection(cases: tuple[CuratedReviewCase, ...], *, fallback_extra: int = 0):
    roles = tuple(CuratedSetRole)
    per_role = len(cases) // len(roles)
    candidates = [
        HoldoutCandidate(
            candidate_id=f"candidate:{case.case_id}",
            case_id=case.case_id,
            set_role=case.set_role,
            engineering_acceptance_passed=True,
        )
        for case in cases
    ]
    for index in range(fallback_extra):
        role = roles[index % len(roles)]
        candidates.append(
            HoldoutCandidate(
                candidate_id=f"fallback-candidate:{index}",
                case_id=f"fallback-case:{index}",
                set_role=role,
                engineering_acceptance_passed=True,
            )
        )
    policy = HoldoutCaseSamplingPolicy(
        policy_id="synthetic-holdout",
        dataset_role=ReviewDatasetRole.PERSONAL_HOLDOUT,
        canonical_sha="sha:canonical",
        snapshot_fingerprint="snapshot:synthetic",
        eligible_scope_fingerprint="scope:synthetic",
        source_case_generator_version="generator-r1",
        sampling_seed="selection-seed",
        role_quotas=tuple((role, per_role) for role in roles),
        fallback_count=fallback_extra,
    )
    return select_holdout_cases_r2(policy=policy, candidates=tuple(candidates))


def _report(evidence, selection, policy=None):
    return build_curation_calibration_report_r3(
        case_evidence=tuple(evidence),
        selection=selection,
        preregistration_manifest_fingerprint="preregistration:synthetic",
        policy=policy or CurationCalibrationPolicyR3(),
    )


def test_r1_six_dimension_ratings_cannot_masquerade_as_r2() -> None:
    case = _case(0, CuratedSetRole.OPENING)
    assignment = _assignment(case)
    old = tuple(
        HumanDimensionPairRating(dimension=d, plan_a_score=4.0, plan_b_score=3.0)
        for d in REQUIRED_HUMAN_REVIEW_DIMENSIONS_R1
    )
    with pytest.raises(ValueError, match="four R2 curation dimensions"):
        CurationReviewR2(
            review_id="legacy",
            assignment_id=assignment.assignment_id,
            reviewer_ref="reviewer",
            curation_session_id="session",
            dataset_role=ReviewDatasetRole.PERSONAL_HOLDOUT,
            preference=CurationPreference.TIE,
            ratings=old,  # type: ignore[arg-type]
            confidence=0.5,
            observed_at="2026-08-23T07:00:00Z",
        )


def test_explicit_attestation_is_required_for_clean_metrics() -> None:
    case = _case(1, CuratedSetRole.BUILD)
    evidence = _evidence(case, ResolvedCurationPreference.GREEDY, attested=False)
    assert evidence.clean_holdout_eligible is False
    assert evidence.exact_agreement is None
    assert "explicit_clean_sequence_attestation_missing" in evidence.reason_codes


def test_manual_mix_or_prior_case_exposure_is_preserved_but_excluded() -> None:
    case = _case(2, CuratedSetRole.MID_SET)
    mixed = _evidence(case, ResolvedCurationPreference.BEAM, transition_execution_used=True)
    exposed = _evidence(case, ResolvedCurationPreference.BEAM, exposure=PriorCaseExposure.YES)
    assert mixed.clean_holdout_eligible is False
    assert exposed.clean_holdout_eligible is False


def test_development_regression_case_cannot_count_as_holdout() -> None:
    case = _case(3, CuratedSetRole.PEAK)
    evidence = _evidence(
        case,
        ResolvedCurationPreference.GREEDY,
        dataset_role=ReviewDatasetRole.DEVELOPMENT_REGRESSION,
    )
    assert evidence.clean_holdout_eligible is False
    assert "development_regression_case_excluded_from_holdout_metrics" in evidence.reason_codes


def test_blind_slot_inversion_resolves_to_source_strategy() -> None:
    case = _case(4, CuratedSetRole.RESET)
    assignment = _assignment(case, seed="reverse-seed")
    evidence = calibrate_curation_case_r3(
        case_binding=_binding(case),
        assignment=assignment,
        review=_review(case, assignment, ResolvedCurationPreference.BEAM),
        comparison=_comparison(case, ResolvedCurationPreference.BEAM, reverse=True),
        clean_sequence_attestation=True,
    )
    assert evidence.human_preference is ResolvedCurationPreference.BEAM
    assert evidence.challenger_preference is ResolvedCurationPreference.BEAM
    assert evidence.exact_agreement is True


def test_dimension_arithmetic_does_not_rewrite_explicit_preference() -> None:
    case = _case(5, CuratedSetRole.CLOSING)
    evidence = _evidence(case, ResolvedCurationPreference.BEAM)
    assert evidence.human_preference is ResolvedCurationPreference.BEAM


def test_shadow_path_identity_mismatch_fails_closed() -> None:
    case = _case(6, CuratedSetRole.OPENING)
    assignment = _assignment(case)
    invalid = replace(_comparison(case, ResolvedCurationPreference.GREEDY), right_path_id="foreign")
    with pytest.raises(HumanReviewProtocolR2Error, match="source paths"):
        calibrate_curation_case_r3(
            case_binding=_binding(case),
            assignment=assignment,
            review=_review(case, assignment, ResolvedCurationPreference.GREEDY),
            comparison=invalid,
            clean_sequence_attestation=True,
        )


def test_holdout_selection_is_deterministic_and_input_order_independent() -> None:
    cases = _cases()
    first = _selection(cases, fallback_extra=6)
    roles = tuple(CuratedSetRole)
    candidates = tuple(
        HoldoutCandidate(
            candidate_id=f"candidate:{case.case_id}",
            case_id=case.case_id,
            set_role=case.set_role,
            engineering_acceptance_passed=True,
        )
        for case in cases
    ) + tuple(
        HoldoutCandidate(
            candidate_id=f"fallback-candidate:{index}",
            case_id=f"fallback-case:{index}",
            set_role=roles[index % len(roles)],
            engineering_acceptance_passed=True,
        )
        for index in range(6)
    )
    policy = HoldoutCaseSamplingPolicy(
        policy_id="synthetic-holdout",
        dataset_role=ReviewDatasetRole.PERSONAL_HOLDOUT,
        canonical_sha="sha:canonical",
        snapshot_fingerprint="snapshot:synthetic",
        eligible_scope_fingerprint="scope:synthetic",
        source_case_generator_version="generator-r1",
        sampling_seed="selection-seed",
        role_quotas=tuple((role, 4) for role in roles),
        fallback_count=6,
    )
    second = select_holdout_cases_r2(policy=policy, candidates=tuple(reversed(candidates)))
    assert first == second
    assert len(first.selected_case_ids) == 24


def test_replacement_requires_pre_registered_technical_reason_and_frozen_order() -> None:
    cases = _cases()
    selection = _selection(cases, fallback_extra=6)
    selected = selection.selected_case_ids[0]
    first = replacement_case_r2(
        selection=selection,
        invalid_case_id=selected,
        technical_invalidity_reason="audio_path_unreadable",
        allowed_technical_invalidity_reasons=("audio_path_unreadable", "packet_binding_failed"),
    )
    assert first == selection.fallback_case_ids[0]
    with pytest.raises(HumanReviewProtocolR2Error, match="outside pre-registered"):
        replacement_case_r2(
            selection=selection,
            invalid_case_id=selected,
            technical_invalidity_reason="human_preference_disliked_case",
            allowed_technical_invalidity_reasons=("audio_path_unreadable",),
        )


def test_transition_spec_fingerprint_binds_mix_window() -> None:
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
        beat_grid_revision="grid-r1",
    )
    assert transition_review_spec_fingerprint(spec) != transition_review_spec_fingerprint(
        replace(spec, outgoing_window_seconds=(181.0, 211.0))
    )


def test_missing_vocal_evidence_is_not_assessable_and_tempo_harmony_are_separate() -> None:
    vocal = vocal_collision_evidence_r2(value=None, explicit_vocal_evidence_refs=())
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
    assert vocal.assessability is Assessability.NOT_ASSESSABLE
    assert vocal.reason_code == "explicit_vocal_evidence_missing"
    assert tempo.dimension is not harmonic.dimension


def test_human_audition_requires_render_or_standardized_recipe() -> None:
    with pytest.raises(ValueError, match="rendered preview or standardized recipe"):
        HumanTransitionAuditionReviewR2(
            review_id="transition-review",
            transition_spec_fingerprint="spec:fingerprint",
            reviewer_ref="reviewer",
            observed_at="2026-08-23T07:00:00Z",
        )
    execution = HumanExecutionReviewR2(
        review_id="execution-review",
        reviewer_ref="reviewer",
        execution_session_id="execution-session",
        observed_at="2026-08-23T07:00:00Z",
        free_form_execution=True,
    )
    assert execution.free_form_execution is True


def test_report_is_bound_to_frozen_holdout_selection() -> None:
    cases = _cases()
    selection = _selection(cases)
    evidence = tuple(_evidence(case, ResolvedCurationPreference.GREEDY) for case in cases)
    foreign = _evidence(_case(99, CuratedSetRole.OPENING), ResolvedCurationPreference.GREEDY)
    with pytest.raises(HumanReviewProtocolR2Error, match="outside frozen holdout"):
        _report(evidence + (foreign,), selection)


def test_same_case_cannot_inflate_personal_holdout_n_with_multiple_review_ids() -> None:
    cases = _cases()
    selection = _selection(cases)
    duplicate_case_a = _evidence(cases[0], ResolvedCurationPreference.GREEDY, review_id="review-a")
    duplicate_case_b = _evidence(cases[0], ResolvedCurationPreference.GREEDY, review_id="review-b")
    with pytest.raises(HumanReviewProtocolR2Error, match="at most one clean review"):
        _report((duplicate_case_a, duplicate_case_b), selection)


def test_missing_selected_clean_review_keeps_holdout_incomplete() -> None:
    cases = _cases()
    selection = _selection(cases)
    evidence = tuple(_evidence(case, ResolvedCurationPreference.GREEDY) for case in cases[:-1])
    report = _report(evidence, selection)
    assert report.verdict is CurationCalibrationVerdict.INCOMPLETE
    assert "frozen_holdout_cases_missing_clean_review" in report.explanation_codes


def test_complete_clean_personal_holdout_supports_only_further_evaluation() -> None:
    cases = _cases()
    selection = _selection(cases)
    evidence = tuple(
        _evidence(case, ResolvedCurationPreference.GREEDY if index % 2 == 0 else ResolvedCurationPreference.BEAM)
        for index, case in enumerate(cases)
    )
    report = _report(evidence, selection)
    replay = _report(tuple(reversed(evidence)), selection)
    assert report == replay
    assert report.clean_case_count == 24
    assert report.exact_agreement_rate == 1.0
    assert report.exact_agreement_interval is not None
    assert report.exact_agreement_interval.lower > 0.5
    assert report.verdict is CurationCalibrationVerdict.SUPPORTS_FURTHER_EVALUATION
    assert report.activation_authorized is False


def test_wilson_lower_bound_not_point_estimate_drives_gate() -> None:
    cases = _cases()
    selection = _selection(cases)
    evidence = tuple(
        _evidence(
            case,
            ResolvedCurationPreference.GREEDY,
            challenger=(
                ResolvedCurationPreference.GREEDY
                if index < 16
                else ResolvedCurationPreference.BEAM
            ),
        )
        for index, case in enumerate(cases)
    )
    report = _report(
        evidence,
        selection,
        CurationCalibrationPolicyR3(
            minimum_exact_agreement_lower_bound=0.60,
            minimum_decisive_agreement_lower_bound=0.60,
        ),
    )
    assert report.exact_agreement_rate == pytest.approx(16 / 24)
    assert report.exact_agreement_interval is not None
    assert report.exact_agreement_interval.lower < 0.60
    assert report.verdict is CurationCalibrationVerdict.DOES_NOT_SUPPORT_FURTHER_EVALUATION


def test_general_claim_refuses_personal_independent_row_analyzer() -> None:
    cases = _cases()
    selection = _selection(cases)
    evidence = tuple(_evidence(case, ResolvedCurationPreference.GREEDY) for case in cases)
    with pytest.raises(HumanReviewProtocolR2Error, match="cluster-aware analyzer"):
        _report(
            evidence,
            selection,
            CurationCalibrationPolicyR3(claim_scope=ValidationClaimScope.GENERAL_DJ_PRODUCT_VALIDATION),
        )


def test_near_equivalent_tie_is_preserved_as_diagnostic_product_evidence() -> None:
    case = _case(40, CuratedSetRole.RESET)
    assignment = _assignment(case)
    evidence = calibrate_curation_case_r3(
        case_binding=_binding(case, difference=MeaningfulDifferenceStatus.NEAR_EQUIVALENT),
        assignment=assignment,
        review=_review(case, assignment, ResolvedCurationPreference.TIE),
        comparison=_comparison(case, ResolvedCurationPreference.GREEDY),
        clean_sequence_attestation=True,
    )
    assert evidence.human_preference is ResolvedCurationPreference.TIE
    assert "near_equivalent_case_report_separately" in evidence.reason_codes
    assert "challenger_false_winner_on_human_tie" in evidence.reason_codes


def test_activation_authority_remains_rejected() -> None:
    with pytest.raises(ValueError, match="cannot authorize activation"):
        CurationCalibrationPolicyR3(activation_authorized=True)
