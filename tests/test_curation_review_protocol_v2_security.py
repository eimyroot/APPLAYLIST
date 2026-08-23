from __future__ import annotations

import inspect

import pytest

import services.intelligence.curation_preference_calibration_v3 as calibration_module
import services.intelligence.curation_review_execution_v2 as review_module
from core.intelligence.curated_real_library_review_contract import CuratedSetRole
from core.intelligence.curation_review_v2_contract import (
    HOLDOUT_VALIDATION_MANIFEST_VERSION,
    CurationCalibrationPolicyV3,
    CurationDJReviewV2,
    CurationDimensionPairRating,
    CurationPreference,
    CurationReviewDimension,
    EvidenceRole,
    HoldoutValidationManifest,
    SelectionScope,
)
from services.intelligence.curation_review_execution_v2 import (
    CurationReviewExecutionV2Error,
    curation_packet_fingerprint,
    validate_curation_review_packet_v2,
)


def _ratings() -> tuple[CurationDimensionPairRating, ...]:
    return tuple(
        CurationDimensionPairRating(dimension=dimension, plan_a_score=4, plan_b_score=3)
        for dimension in CurationReviewDimension
    )


def test_curation_review_structurally_rejects_activation_and_pdm_training() -> None:
    kwargs = dict(
        review_id="review",
        assignment_id="assignment",
        reviewer_ref="dj-01",
        evidence_role=EvidenceRole.DEVELOPMENT_CALIBRATION,
        curation_packet_fingerprint="packet",
        source_blinded_packet_fingerprint="source",
        preference=CurationPreference.PLAN_A,
        ratings=_ratings(),
        confidence=0.9,
        observed_at="2026-08-23T06:00:00Z",
    )
    with pytest.raises(ValueError, match="optimizer activation"):
        CurationDJReviewV2(**kwargs, activation_authorized=True)
    with pytest.raises(ValueError, match="Personal DJ Model training"):
        CurationDJReviewV2(**kwargs, personal_dj_model_training_authorized=True)


def test_holdout_manifest_rejects_labels_available_at_freeze() -> None:
    with pytest.raises(ValueError, match="before human labels"):
        HoldoutValidationManifest(
            holdout_id="holdout",
            holdout_version=HOLDOUT_VALIDATION_MANIFEST_VERSION,
            evidence_role=EvidenceRole.HOLDOUT_VALIDATION,
            selection_scope=SelectionScope.REPRESENTATIVE_HOLDOUT,
            source_snapshot_ref=("snapshot", "1"),
            case_selection_policy_ref=("selection", "1"),
            selection_seed_commitment="seed",
            selected_case_ids=tuple(f"case-{index}" for index in range(12)),
            scenario_fingerprints=tuple(f"scenario-{index}" for index in range(12)),
            required_set_roles=tuple(CuratedSetRole),
            source_optimizer_sha="source",
            challenger_sha="challenger",
            challenger_policy_ref=("challenger", "1"),
            challenger_config_digest="config",
            calibration_policy_digest="policy",
            source_evidence_revisions=("evidence",),
            generated_at="2026-08-23T06:00:00Z",
            human_labels_available_at_freeze=True,
        )


def test_curation_calibration_policy_cannot_authorize_activation_or_training() -> None:
    with pytest.raises(ValueError, match="optimizer activation"):
        CurationCalibrationPolicyV3(activation_authorized=True)
    with pytest.raises(ValueError, match="Personal DJ Model training"):
        CurationCalibrationPolicyV3(personal_dj_model_training_authorized=True)


def test_packet_authority_flags_fail_closed() -> None:
    packet: dict[str, object] = {
        "schema": "applaylist-curation-review-packet-v2",
        "protocol_version": "curation-review-v2",
        "generated_at": "2026-08-23T06:00:00Z",
        "evidence_role": "development_calibration",
        "source_blinded_packet_fingerprint": "source",
        "source_snapshot_ref": ["snapshot", "1"],
        "reviewer_ref": "dj-01",
        "audition_mode": "sequence_curation_only",
        "algorithm_identity_hidden": True,
        "cases": [
            {
                "case_id": "case-01",
                "set_role": "opening",
                "assignment_id": "assignment-01",
                "plan_a": ["A"],
                "plan_b": ["B"],
                "required_review_dimensions": [item.value for item in CurationReviewDimension],
                "allowed_preference": [item.value for item in CurationPreference],
                "execution_quality_exclusion_required": True,
            }
        ],
        "activation_authorized": True,
        "personal_dj_model_training_authorized": False,
    }
    packet["curation_packet_fingerprint"] = curation_packet_fingerprint(packet)
    with pytest.raises(CurationReviewExecutionV2Error, match="cannot authorize activation"):
        validate_curation_review_packet_v2(packet)


def test_curation_protocol_services_are_pure_no_io_network_or_provider_execution() -> None:
    source = inspect.getsource(review_module) + inspect.getsource(calibration_module)
    forbidden = (
        "pathlib",
        "Path(",
        "open(",
        "sqlite3",
        "subprocess",
        "socket",
        "requests",
        "httpx",
        "urllib",
        "analyze_real_tracks",
        "provider.execute",
    )
    for token in forbidden:
        assert token not in source
