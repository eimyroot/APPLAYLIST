from __future__ import annotations

from dataclasses import replace

import pytest

from core.intelligence.competitive_curation_contract import (
    ShadowPathComparison,
    ShadowPathPreference,
)
from core.intelligence.curated_real_library_review_contract import (
    CuratedReviewCase,
    CuratedSetRole,
    HumanDJReview,
    HumanDimensionPairRating,
    HumanPlanPreference,
    HumanReviewDimension,
    ReviewPlanStrategy,
    ReviewableSetPlan,
)
from core.intelligence.curation_review_v2_contract import (
    CURATION_AUDITION_MODE,
    HOLDOUT_VALIDATION_MANIFEST_VERSION,
    CurationBlindAssignmentV2,
    CurationCalibrationPolicyV3,
    CurationDJReviewV2,
    CurationDimensionPairRating,
    CurationPreference,
    CurationReviewDimension,
    EvaluationScope,
    EvidenceRole,
    HoldoutCaseExecutionEvidence,
    HoldoutSystemOutcome,
    HoldoutValidationManifest,
    SelectionScope,
)
from core.intelligence.human_preference_calibration_contract import CalibrationVerdict
from services.intelligence.curation_preference_calibration_v3 import (
    CurationPreferenceCalibrationV3Error,
    build_curation_calibration_report_v3,
)
from services.intelligence.curation_review_execution_v2 import (
    CURATION_REVIEW_PACKET_SCHEMA_V2,
    CURATION_REVIEW_SUBMISSION_SCHEMA_V2,
    CurationReviewExecutionV2Error,
    curation_packet_fingerprint,
    parse_curation_review_submission_v2,
    validate_curation_review_packet_v2,
)

ROLES = tuple(CuratedSetRole)


def _plan(case_index: int, strategy: ReviewPlanStrategy) -> ReviewableSetPlan:
    suffix = "g" if strategy is ReviewPlanStrategy.GREEDY_RECOMMEND_NEXT else "b"
    return ReviewableSetPlan(
        plan_id=f"plan-{case_index}-{suffix}",
        strategy=strategy,
        result_id=f"result-{case_index}-{suffix}",
        path_id=f"path-{case_index}-{suffix}",
        ordered_track_ids=(f"track-{case_index}-0", f"track-{case_index}-{suffix}"),
        transition_ids=(f"transition-{case_index}-{suffix}",),
        evidence_refs=(f"evidence-{case_index}-{suffix}",),
    )


def _case(index: int) -> CuratedReviewCase:
    role = ROLES[(index - 1) % len(ROLES)]
    return CuratedReviewCase(
        case_id=f"case-{index:02d}",
        snapshot_ref=("snapshot", "1"),
        scenario_fingerprint=f"scenario-{index:02d}",
        set_role=role,
        benchmark_ref=("benchmark", "1"),
        greedy_plan=_plan(index, ReviewPlanStrategy.GREEDY_RECOMMEND_NEXT),
        beam_plan=_plan(index, ReviewPlanStrategy.BOUNDED_BEAM),
        engineering_acceptance_passed=True,
        evidence_refs=(f"case-evidence-{index}",),
    )


def _cases() -> tuple[CuratedReviewCase, ...]:
    return tuple(_case(index) for index in range(1, 13))


def _assignment(case: CuratedReviewCase, reviewer: str, index: int) -> CurationBlindAssignmentV2:
    greedy_in_a = index % 2 == 0
    return CurationBlindAssignmentV2(
        assignment_id=f"assignment-{reviewer}-{index}",
        case_id=case.case_id,
        reviewer_ref=reviewer,
        slot_a_plan_id=case.greedy_plan.plan_id if greedy_in_a else case.beam_plan.plan_id,
        slot_b_plan_id=case.beam_plan.plan_id if greedy_in_a else case.greedy_plan.plan_id,
        assignment_fingerprint=f"assignment-fingerprint-{reviewer}-{index}",
        algorithm_identity_hidden=True,
    )


def _ratings(a: float = 4.0, b: float = 3.0) -> tuple[CurationDimensionPairRating, ...]:
    return tuple(
        CurationDimensionPairRating(dimension=dimension, plan_a_score=a, plan_b_score=b)
        for dimension in CurationReviewDimension
    )


def _review(
    assignment: CurationBlindAssignmentV2,
    *,
    role: EvidenceRole = EvidenceRole.DEVELOPMENT_CALIBRATION,
    preference: CurationPreference = CurationPreference.PLAN_A,
    confidence: float = 0.9,
) -> CurationDJReviewV2:
    return CurationDJReviewV2(
        review_id=f"review-{assignment.assignment_id}",
        assignment_id=assignment.assignment_id,
        reviewer_ref=assignment.reviewer_ref,
        evidence_role=role,
        curation_packet_fingerprint="curation-packet-fingerprint",
        source_blinded_packet_fingerprint="legacy-source-fingerprint",
        preference=preference,
        ratings=_ratings(),
        confidence=confidence,
        observed_at="2026-08-23T06:00:00Z",
        audition_mode=CURATION_AUDITION_MODE,
        algorithm_identity_was_hidden=True,
        execution_quality_excluded_from_curation_judgment=True,
    )


def _comparison(case: CuratedReviewCase, preference: ShadowPathPreference = ShadowPathPreference.LEFT) -> ShadowPathComparison:
    return ShadowPathComparison(
        left_path_id=case.greedy_plan.path_id,
        right_path_id=case.beam_plan.path_id,
        left_score=0.8,
        right_score=0.7,
        right_minus_left=-0.1,
        preference=preference,
        reason_codes=("shadow-test",),
        activation_authorized=False,
    )


def _outcome(
    case: CuratedReviewCase,
    outcome: HoldoutSystemOutcome = HoldoutSystemOutcome.REVIEWABLE_PAIR,
) -> HoldoutCaseExecutionEvidence:
    return HoldoutCaseExecutionEvidence(
        case_id=case.case_id,
        set_role=case.set_role,
        outcome=outcome,
        scenario_fingerprint=case.scenario_fingerprint,
        evidence_refs=(f"outcome-evidence-{case.case_id}",),
    )


def _packet() -> dict[str, object]:
    packet: dict[str, object] = {
        "schema": CURATION_REVIEW_PACKET_SCHEMA_V2,
        "protocol_version": "curation-review-v2",
        "generated_at": "2026-08-23T06:00:00Z",
        "evidence_role": "development_calibration",
        "source_blinded_packet_fingerprint": "legacy-source-fingerprint",
        "source_snapshot_ref": ["snapshot", "1"],
        "reviewer_ref": "dj-01",
        "audition_mode": "sequence_curation_only",
        "algorithm_identity_hidden": True,
        "cases": [
            {
                "case_id": "case-01",
                "set_role": "opening",
                "assignment_id": "assignment-dj-01-1",
                "plan_a": ["Track 1", "Track 2"],
                "plan_b": ["Track 1", "Track 3"],
                "required_review_dimensions": [item.value for item in CurationReviewDimension],
                "allowed_preference": [item.value for item in CurationPreference],
                "execution_quality_exclusion_required": True,
            }
        ],
        "activation_authorized": False,
        "personal_dj_model_training_authorized": False,
    }
    packet["curation_packet_fingerprint"] = curation_packet_fingerprint(packet)
    return packet


def _submission(packet: dict[str, object]) -> dict[str, object]:
    return {
        "schema": CURATION_REVIEW_SUBMISSION_SCHEMA_V2,
        "protocol_version": "curation-review-v2",
        "curation_packet_fingerprint": packet["curation_packet_fingerprint"],
        "reviewer_ref": "dj-01",
        "reviews": [
            {
                "review_id": "review-01",
                "case_id": "case-01",
                "assignment_id": "assignment-dj-01-1",
                "preference": "plan_a",
                "ratings": [
                    {"dimension": item.value, "plan_a_score": 4, "plan_b_score": 3}
                    for item in CurationReviewDimension
                ],
                "confidence": 0.9,
                "observed_at": "2026-08-23T06:10:00Z",
                "audition_mode": "sequence_curation_only",
                "algorithm_identity_was_hidden": True,
                "execution_quality_excluded_from_curation_judgment": True,
                "reason_codes": [],
                "notes": "sequence only",
                "activation_authorized": False,
                "personal_dj_model_training_authorized": False,
            }
        ],
        "activation_authorized": False,
        "personal_dj_model_training_authorized": False,
    }


def _holdout_manifest(cases: tuple[CuratedReviewCase, ...], *, scope: SelectionScope = SelectionScope.REPRESENTATIVE_HOLDOUT) -> HoldoutValidationManifest:
    return HoldoutValidationManifest(
        holdout_id="holdout-01",
        holdout_version=HOLDOUT_VALIDATION_MANIFEST_VERSION,
        evidence_role=EvidenceRole.HOLDOUT_VALIDATION,
        selection_scope=scope,
        source_snapshot_ref=("snapshot", "1"),
        case_selection_policy_ref=("selection", "1"),
        selection_seed_commitment="seed-commitment",
        selected_case_ids=tuple(case.case_id for case in cases),
        scenario_fingerprints=tuple(case.scenario_fingerprint for case in cases),
        required_set_roles=tuple(CuratedSetRole),
        source_optimizer_sha="source-sha",
        challenger_sha="challenger-sha",
        challenger_policy_ref=("competitive-curation-shadow", "competitive-curation-r1"),
        challenger_config_digest="challenger-config",
        calibration_policy_digest="calibration-policy",
        source_evidence_revisions=("evidence-r1",),
        generated_at="2026-08-23T06:00:00Z",
        human_labels_available_at_freeze=False,
        algorithm_identity_hidden=True,
    )


def test_v2_packet_rejects_legacy_bundle63_submission_schema() -> None:
    packet = _packet()
    submission = _submission(packet)
    submission["schema"] = "applaylist-human-dj-review-submission-r1"

    with pytest.raises(CurationReviewExecutionV2Error, match="unsupported curation review submission schema"):
        parse_curation_review_submission_v2(packet=packet, submission=submission)


def test_v2_packet_requires_execution_quality_exclusion() -> None:
    packet = _packet()
    submission = _submission(packet)
    submission["reviews"][0]["execution_quality_excluded_from_curation_judgment"] = False  # type: ignore[index]

    with pytest.raises(CurationReviewExecutionV2Error, match="execution-quality exclusion"):
        parse_curation_review_submission_v2(packet=packet, submission=submission)


def test_v2_packet_rejects_transition_fields_in_curation_case() -> None:
    packet = _packet()
    packet["cases"][0]["transition_smoothness"] = 5  # type: ignore[index]
    packet["curation_packet_fingerprint"] = curation_packet_fingerprint(packet)

    with pytest.raises(CurationReviewExecutionV2Error, match="unexpected fields"):
        validate_curation_review_packet_v2(packet)


def test_curation_review_requires_all_five_dimensions() -> None:
    assignment = _assignment(_case(1), "dj-01", 1)
    with pytest.raises(ValueError, match="all V2 dimensions"):
        CurationDJReviewV2(
            review_id="review",
            assignment_id=assignment.assignment_id,
            reviewer_ref="dj-01",
            evidence_role=EvidenceRole.DEVELOPMENT_CALIBRATION,
            curation_packet_fingerprint="packet",
            source_blinded_packet_fingerprint="source",
            preference=CurationPreference.PLAN_A,
            ratings=_ratings()[:-1],
            confidence=0.8,
            observed_at="2026-08-23T06:00:00Z",
        )


def test_legacy_human_review_is_a_distinct_contract_not_curation_v2() -> None:
    legacy = HumanDJReview(
        review_id="legacy-review",
        assignment_id="legacy-assignment",
        reviewer_ref="dj-01",
        preference=HumanPlanPreference.PLAN_A,
        ratings=tuple(
            HumanDimensionPairRating(dimension=dimension, plan_a_score=4, plan_b_score=3)
            for dimension in HumanReviewDimension
        ),
        confidence=0.8,
        observed_at="2026-08-23T06:00:00Z",
    )
    assert not isinstance(legacy, CurationDJReviewV2)


def test_development_calibration_cannot_claim_independent_validation() -> None:
    cases = _cases()
    assignments = tuple(_assignment(case, "dj-01", index) for index, case in enumerate(cases, 1))
    reviews = tuple(_review(assignment) for assignment in assignments)
    comparisons = {case.case_id: _comparison(case) for case in cases}
    outcomes = tuple(_outcome(case) for case in cases)

    report = build_curation_calibration_report_v3(
        all_cases=cases,
        assignments=assignments,
        reviews=reviews,
        comparisons_by_case=comparisons,
        system_outcomes=outcomes,
        evidence_role=EvidenceRole.DEVELOPMENT_CALIBRATION,
        evaluation_scope=EvaluationScope.PERSONAL_DJ_CALIBRATION,
    )

    assert report.independent_validation is False
    assert report.representative_performance_claim_allowed is False
    assert "development_result_requires_fresh_holdout_validation" in report.explanation_codes


def test_non_reviewable_system_failures_stay_in_denominator_and_are_negative_evidence() -> None:
    cases = _cases()
    outcomes = tuple(
        _outcome(
            case,
            HoldoutSystemOutcome.NO_MEANINGFUL_ALTERNATIVE
            if index <= 8
            else HoldoutSystemOutcome.REVIEWABLE_PAIR,
        )
        for index, case in enumerate(cases, 1)
    )
    reviewable = [case for index, case in enumerate(cases, 1) if index > 8]
    assignments = tuple(_assignment(case, "dj-01", index) for index, case in enumerate(reviewable, 9))
    reviews = tuple(_review(assignment) for assignment in assignments)
    comparisons = {case.case_id: _comparison(case) for case in reviewable}

    report = build_curation_calibration_report_v3(
        all_cases=cases,
        assignments=assignments,
        reviews=reviews,
        comparisons_by_case=comparisons,
        system_outcomes=outcomes,
        evidence_role=EvidenceRole.DEVELOPMENT_CALIBRATION,
        evaluation_scope=EvaluationScope.PERSONAL_DJ_CALIBRATION,
        policy=CurationCalibrationPolicyV3(maximum_assignment_imbalance=4),
    )

    assert report.selected_case_count == 12
    assert report.reviewable_pair_count == 4
    assert report.non_reviewable_system_outcome_count == 8
    assert report.reviewable_pair_fraction == pytest.approx(4 / 12)
    assert report.verdict is CalibrationVerdict.DOES_NOT_SUPPORT_ACTIVATION
    assert "curation_meaningful_alternative_availability_below_policy" in report.explanation_codes


def test_human_review_cannot_be_attached_to_non_reviewable_machine_outcome() -> None:
    cases = _cases()
    assignments = tuple(_assignment(case, "dj-01", index) for index, case in enumerate(cases, 1))
    reviews = tuple(_review(assignment) for assignment in assignments)
    comparisons = {case.case_id: _comparison(case) for case in cases}
    outcomes = tuple(
        _outcome(case, HoldoutSystemOutcome.TECHNICALLY_IDENTICAL_PAIR if index == 1 else HoldoutSystemOutcome.REVIEWABLE_PAIR)
        for index, case in enumerate(cases, 1)
    )

    with pytest.raises(CurationPreferenceCalibrationV3Error, match="cannot replace a non-reviewable"):
        build_curation_calibration_report_v3(
            all_cases=cases,
            assignments=assignments,
            reviews=reviews,
            comparisons_by_case=comparisons,
            system_outcomes=outcomes,
            evidence_role=EvidenceRole.DEVELOPMENT_CALIBRATION,
            evaluation_scope=EvaluationScope.PERSONAL_DJ_CALIBRATION,
        )


def test_holdout_freeze_rejects_post_label_challenger_mutation() -> None:
    cases = _cases()
    manifest = _holdout_manifest(cases)
    assignments = tuple(_assignment(case, "dj-01", index) for index, case in enumerate(cases, 1))
    reviews = tuple(
        replace(_review(assignment), evidence_role=EvidenceRole.HOLDOUT_VALIDATION)
        for assignment in assignments
    )
    comparisons = {case.case_id: _comparison(case) for case in cases}
    outcomes = tuple(_outcome(case) for case in cases)

    with pytest.raises(CurationPreferenceCalibrationV3Error, match="challenger revision"):
        build_curation_calibration_report_v3(
            all_cases=cases,
            assignments=assignments,
            reviews=reviews,
            comparisons_by_case=comparisons,
            system_outcomes=outcomes,
            evidence_role=EvidenceRole.HOLDOUT_VALIDATION,
            evaluation_scope=EvaluationScope.PERSONAL_DJ_CALIBRATION,
            holdout_manifest=manifest,
            expected_source_optimizer_sha="source-sha",
            expected_challenger_sha="changed-after-labels",
            expected_challenger_config_digest="challenger-config",
            expected_calibration_policy_digest="calibration-policy",
        )


def test_representative_holdout_can_claim_only_protocol_bounded_independent_validation() -> None:
    cases = _cases()
    manifest = _holdout_manifest(cases)
    assignments = tuple(_assignment(case, "dj-01", index) for index, case in enumerate(cases, 1))
    reviews = tuple(
        replace(_review(assignment), evidence_role=EvidenceRole.HOLDOUT_VALIDATION)
        for assignment in assignments
    )
    comparisons = {case.case_id: _comparison(case) for case in cases}
    outcomes = tuple(_outcome(case) for case in cases)

    report = build_curation_calibration_report_v3(
        all_cases=cases,
        assignments=assignments,
        reviews=reviews,
        comparisons_by_case=comparisons,
        system_outcomes=outcomes,
        evidence_role=EvidenceRole.HOLDOUT_VALIDATION,
        evaluation_scope=EvaluationScope.PERSONAL_DJ_CALIBRATION,
        holdout_manifest=manifest,
        expected_source_optimizer_sha="source-sha",
        expected_challenger_sha="challenger-sha",
        expected_challenger_config_digest="challenger-config",
        expected_calibration_policy_digest="calibration-policy",
    )

    assert report.independent_validation is True
    assert report.representative_performance_claim_allowed is True


def test_diagnostic_holdout_never_allows_representative_performance_claim() -> None:
    cases = _cases()
    manifest = _holdout_manifest(cases, scope=SelectionScope.DIAGNOSTIC_CHALLENGE_SET)
    assignments = tuple(_assignment(case, "dj-01", index) for index, case in enumerate(cases, 1))
    reviews = tuple(
        replace(_review(assignment), evidence_role=EvidenceRole.HOLDOUT_VALIDATION)
        for assignment in assignments
    )
    comparisons = {case.case_id: _comparison(case) for case in cases}
    outcomes = tuple(_outcome(case) for case in cases)

    report = build_curation_calibration_report_v3(
        all_cases=cases,
        assignments=assignments,
        reviews=reviews,
        comparisons_by_case=comparisons,
        system_outcomes=outcomes,
        evidence_role=EvidenceRole.HOLDOUT_VALIDATION,
        evaluation_scope=EvaluationScope.PERSONAL_DJ_CALIBRATION,
        holdout_manifest=manifest,
        expected_source_optimizer_sha="source-sha",
        expected_challenger_sha="challenger-sha",
        expected_challenger_config_digest="challenger-config",
        expected_calibration_policy_digest="calibration-policy",
    )

    assert report.independent_validation is True
    assert report.representative_performance_claim_allowed is False


def test_personal_dj_assignment_position_imbalance_fails_completeness() -> None:
    cases = _cases()
    assignments = tuple(
        CurationBlindAssignmentV2(
            assignment_id=f"assignment-dj-01-{index}",
            case_id=case.case_id,
            reviewer_ref="dj-01",
            slot_a_plan_id=case.greedy_plan.plan_id,
            slot_b_plan_id=case.beam_plan.plan_id,
            assignment_fingerprint=f"fingerprint-{index}",
        )
        for index, case in enumerate(cases, 1)
    )
    reviews = tuple(_review(assignment) for assignment in assignments)
    comparisons = {case.case_id: _comparison(case) for case in cases}
    outcomes = tuple(_outcome(case) for case in cases)

    report = build_curation_calibration_report_v3(
        all_cases=cases,
        assignments=assignments,
        reviews=reviews,
        comparisons_by_case=comparisons,
        system_outcomes=outcomes,
        evidence_role=EvidenceRole.DEVELOPMENT_CALIBRATION,
        evaluation_scope=EvaluationScope.PERSONAL_DJ_CALIBRATION,
    )

    assert report.verdict is CalibrationVerdict.INCOMPLETE
    assert "curation_calibration_assignment_position_imbalance" in report.explanation_codes


def test_multi_dj_scope_requires_minimum_independent_reviewers() -> None:
    cases = _cases()
    assignments = tuple(_assignment(case, "dj-01", index) for index, case in enumerate(cases, 1))
    reviews = tuple(_review(assignment) for assignment in assignments)
    comparisons = {case.case_id: _comparison(case) for case in cases}
    outcomes = tuple(_outcome(case) for case in cases)

    report = build_curation_calibration_report_v3(
        all_cases=cases,
        assignments=assignments,
        reviews=reviews,
        comparisons_by_case=comparisons,
        system_outcomes=outcomes,
        evidence_role=EvidenceRole.DEVELOPMENT_CALIBRATION,
        evaluation_scope=EvaluationScope.MULTI_DJ_PRODUCT_EVALUATION,
    )

    assert report.verdict is CalibrationVerdict.INCOMPLETE
    assert "curation_calibration_independent_reviewer_count_below_policy" in report.explanation_codes
