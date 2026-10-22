from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from core.intelligence.curated_real_library_review_contract import CuratedSetRole
from core.intelligence.curation_review_v2_contract import (
    CURATION_AUDITION_MODE,
    CURATION_REVIEW_PROTOCOL_VERSION,
    REQUIRED_CURATION_REVIEW_DIMENSIONS_V2,
    CurationDJReviewV2,
    CurationDimensionPairRating,
    CurationPreference,
    CurationReviewDimension,
    EvidenceRole,
)

CURATION_REVIEW_PACKET_SCHEMA_V2 = "applaylist-curation-review-packet-v2"
CURATION_REVIEW_SUBMISSION_SCHEMA_V2 = "applaylist-curation-review-submission-v2"

_ALLOWED_PREFERENCES = tuple(item.value for item in CurationPreference)
_REQUIRED_DIMENSIONS = tuple(item.value for item in REQUIRED_CURATION_REVIEW_DIMENSIONS_V2)


class CurationReviewExecutionV2Error(ValueError):
    """Fail-closed error for curation-only human review evidence."""


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _token(value: object, field: str, *, maximum: int = 512) -> str:
    if not isinstance(value, str):
        raise CurationReviewExecutionV2Error(f"{field} must be text")
    normalized = value.strip()
    if (
        not normalized
        or normalized != value
        or len(normalized) > maximum
        or any(ord(character) < 32 for character in normalized)
    ):
        raise CurationReviewExecutionV2Error(f"{field} is invalid")
    return normalized


def curation_packet_fingerprint(packet: Mapping[str, Any]) -> str:
    material = dict(packet)
    supplied = material.pop("curation_packet_fingerprint", None)
    if supplied is not None and not isinstance(supplied, str):
        raise CurationReviewExecutionV2Error("curation_packet_fingerprint must be text")
    encoded = json.dumps(
        material,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return _sha256_bytes(encoded)


def validate_curation_review_packet_v2(packet: Mapping[str, Any]) -> dict[str, Any]:
    if packet.get("schema") != CURATION_REVIEW_PACKET_SCHEMA_V2:
        raise CurationReviewExecutionV2Error("unsupported curation review packet schema")
    if packet.get("protocol_version") != CURATION_REVIEW_PROTOCOL_VERSION:
        raise CurationReviewExecutionV2Error("unsupported curation review protocol version")
    if packet.get("audition_mode") != CURATION_AUDITION_MODE:
        raise CurationReviewExecutionV2Error("curation packet must use sequence_curation_only audition mode")
    if packet.get("algorithm_identity_hidden") is not True:
        raise CurationReviewExecutionV2Error("algorithm identity must remain hidden")
    if packet.get("activation_authorized") is not False:
        raise CurationReviewExecutionV2Error("curation packet cannot authorize activation")
    if packet.get("personal_dj_model_training_authorized") is not False:
        raise CurationReviewExecutionV2Error("curation packet cannot authorize Personal DJ Model training")

    try:
        evidence_role = EvidenceRole(str(packet.get("evidence_role")))
    except ValueError as exc:
        raise CurationReviewExecutionV2Error("unknown curation evidence role") from exc

    source_blinded_packet_fingerprint = _token(
        packet.get("source_blinded_packet_fingerprint"),
        "source_blinded_packet_fingerprint",
    )
    reviewer_ref = _token(packet.get("reviewer_ref"), "reviewer_ref")
    generated_at = _token(packet.get("generated_at"), "generated_at")

    snapshot_ref = packet.get("source_snapshot_ref")
    if not isinstance(snapshot_ref, list) or len(snapshot_ref) != 2:
        raise CurationReviewExecutionV2Error("source_snapshot_ref must contain exactly two values")
    normalized_snapshot_ref = [
        _token(snapshot_ref[0], "source_snapshot_ref[0]"),
        _token(snapshot_ref[1], "source_snapshot_ref[1]"),
    ]

    cases = packet.get("cases")
    if not isinstance(cases, list) or not cases:
        raise CurationReviewExecutionV2Error("curation packet cases must be a non-empty array")

    case_ids: set[str] = set()
    assignment_ids: set[str] = set()
    normalized_cases: list[dict[str, Any]] = []
    for raw in cases:
        if not isinstance(raw, dict):
            raise CurationReviewExecutionV2Error("curation case must be an object")
        allowed_keys = {
            "case_id",
            "set_role",
            "assignment_id",
            "plan_a",
            "plan_b",
            "required_review_dimensions",
            "allowed_preference",
            "execution_quality_exclusion_required",
        }
        if set(raw) != allowed_keys:
            raise CurationReviewExecutionV2Error("curation case has unexpected fields")
        case_id = _token(raw.get("case_id"), "case_id")
        assignment_id = _token(raw.get("assignment_id"), "assignment_id")
        if case_id in case_ids or assignment_id in assignment_ids:
            raise CurationReviewExecutionV2Error("case/assignment identities must be unique")
        case_ids.add(case_id)
        assignment_ids.add(assignment_id)
        try:
            role = CuratedSetRole(str(raw.get("set_role"))).value
        except ValueError as exc:
            raise CurationReviewExecutionV2Error("unknown curated set role") from exc

        plans: dict[str, list[str]] = {}
        for key in ("plan_a", "plan_b"):
            value = raw.get(key)
            if not isinstance(value, list) or not value:
                raise CurationReviewExecutionV2Error(f"{key} must be a non-empty array")
            plans[key] = [_token(item, f"{key} display name") for item in value]

        dimensions = raw.get("required_review_dimensions")
        if not isinstance(dimensions, list) or tuple(dimensions) != _REQUIRED_DIMENSIONS:
            raise CurationReviewExecutionV2Error("curation dimensions do not match V2 protocol")
        preferences = raw.get("allowed_preference")
        if not isinstance(preferences, list) or tuple(preferences) != _ALLOWED_PREFERENCES:
            raise CurationReviewExecutionV2Error("curation preference choices do not match V2 protocol")
        if raw.get("execution_quality_exclusion_required") is not True:
            raise CurationReviewExecutionV2Error("curation case must require execution-quality exclusion")

        normalized_cases.append(
            {
                "case_id": case_id,
                "set_role": role,
                "assignment_id": assignment_id,
                "plan_a": plans["plan_a"],
                "plan_b": plans["plan_b"],
                "required_review_dimensions": list(_REQUIRED_DIMENSIONS),
                "allowed_preference": list(_ALLOWED_PREFERENCES),
                "execution_quality_exclusion_required": True,
            }
        )

    expected_fingerprint = curation_packet_fingerprint(packet)
    if packet.get("curation_packet_fingerprint") != expected_fingerprint:
        raise CurationReviewExecutionV2Error("curation packet fingerprint mismatch")

    return {
        "schema": CURATION_REVIEW_PACKET_SCHEMA_V2,
        "protocol_version": CURATION_REVIEW_PROTOCOL_VERSION,
        "generated_at": generated_at,
        "evidence_role": evidence_role.value,
        "source_blinded_packet_fingerprint": source_blinded_packet_fingerprint,
        "source_snapshot_ref": normalized_snapshot_ref,
        "reviewer_ref": reviewer_ref,
        "audition_mode": CURATION_AUDITION_MODE,
        "algorithm_identity_hidden": True,
        "cases": normalized_cases,
        "activation_authorized": False,
        "personal_dj_model_training_authorized": False,
        "curation_packet_fingerprint": expected_fingerprint,
    }


def _number(value: object, field: str, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CurationReviewExecutionV2Error(f"{field} must be numeric")
    result = float(value)
    if not minimum <= result <= maximum:
        raise CurationReviewExecutionV2Error(f"{field} must be between {minimum} and {maximum}")
    return result


def parse_curation_review_submission_v2(
    *,
    packet: Mapping[str, Any],
    submission: Mapping[str, Any],
) -> tuple[CurationDJReviewV2, ...]:
    validated_packet = validate_curation_review_packet_v2(packet)
    if submission.get("schema") != CURATION_REVIEW_SUBMISSION_SCHEMA_V2:
        raise CurationReviewExecutionV2Error("unsupported curation review submission schema")
    if submission.get("protocol_version") != CURATION_REVIEW_PROTOCOL_VERSION:
        raise CurationReviewExecutionV2Error("submission protocol version mismatch")
    if submission.get("curation_packet_fingerprint") != validated_packet["curation_packet_fingerprint"]:
        raise CurationReviewExecutionV2Error("submission does not bind to curation packet")
    if submission.get("reviewer_ref") != validated_packet["reviewer_ref"]:
        raise CurationReviewExecutionV2Error("submission reviewer does not bind to curation packet")
    if submission.get("activation_authorized") is not False:
        raise CurationReviewExecutionV2Error("submission cannot authorize activation")
    if submission.get("personal_dj_model_training_authorized") is not False:
        raise CurationReviewExecutionV2Error("submission cannot authorize Personal DJ Model training")

    reviews = submission.get("reviews")
    if not isinstance(reviews, list):
        raise CurationReviewExecutionV2Error("submission reviews must be an array")

    by_assignment = {item["assignment_id"]: item for item in validated_packet["cases"]}
    seen_assignments: set[str] = set()
    parsed: list[CurationDJReviewV2] = []
    for raw in reviews:
        if not isinstance(raw, dict):
            raise CurationReviewExecutionV2Error("review must be an object")
        assignment_id = _token(raw.get("assignment_id"), "assignment_id")
        case_id = _token(raw.get("case_id"), "case_id")
        case = by_assignment.get(assignment_id)
        if case is None or case["case_id"] != case_id:
            raise CurationReviewExecutionV2Error("review assignment/case binding mismatch")
        if assignment_id in seen_assignments:
            raise CurationReviewExecutionV2Error("duplicate review assignment in submission")
        seen_assignments.add(assignment_id)

        if raw.get("algorithm_identity_was_hidden") is not True:
            raise CurationReviewExecutionV2Error("algorithm identity exposure invalidates curation review")
        if raw.get("execution_quality_excluded_from_curation_judgment") is not True:
            raise CurationReviewExecutionV2Error("execution-quality exclusion acknowledgement is required")
        if raw.get("audition_mode") != CURATION_AUDITION_MODE:
            raise CurationReviewExecutionV2Error("review audition mode mismatch")
        if raw.get("activation_authorized") is not False:
            raise CurationReviewExecutionV2Error("review cannot authorize activation")
        if raw.get("personal_dj_model_training_authorized") is not False:
            raise CurationReviewExecutionV2Error("review cannot authorize Personal DJ Model training")

        try:
            preference = CurationPreference(str(raw.get("preference")))
        except ValueError as exc:
            raise CurationReviewExecutionV2Error("unknown curation preference") from exc

        ratings_raw = raw.get("ratings")
        if not isinstance(ratings_raw, list):
            raise CurationReviewExecutionV2Error("ratings must be an array")
        ratings: list[CurationDimensionPairRating] = []
        for rating in ratings_raw:
            if not isinstance(rating, dict) or set(rating) != {
                "dimension",
                "plan_a_score",
                "plan_b_score",
            }:
                raise CurationReviewExecutionV2Error("invalid curation rating shape")
            try:
                dimension = CurationReviewDimension(str(rating["dimension"]))
            except ValueError as exc:
                raise CurationReviewExecutionV2Error("unknown curation review dimension") from exc
            ratings.append(
                CurationDimensionPairRating(
                    dimension=dimension,
                    plan_a_score=_number(rating["plan_a_score"], "plan_a_score", 1.0, 5.0),
                    plan_b_score=_number(rating["plan_b_score"], "plan_b_score", 1.0, 5.0),
                )
            )

        reason_codes_raw = raw.get("reason_codes", [])
        if not isinstance(reason_codes_raw, list):
            raise CurationReviewExecutionV2Error("reason_codes must be an array")
        reason_codes = tuple(_token(item, "reason_code") for item in reason_codes_raw)
        notes = raw.get("notes", "")
        if not isinstance(notes, str) or len(notes) > 4000:
            raise CurationReviewExecutionV2Error("notes must be bounded text")

        parsed.append(
            CurationDJReviewV2(
                review_id=_token(raw.get("review_id"), "review_id"),
                assignment_id=assignment_id,
                reviewer_ref=validated_packet["reviewer_ref"],
                evidence_role=EvidenceRole(validated_packet["evidence_role"]),
                curation_packet_fingerprint=validated_packet["curation_packet_fingerprint"],
                source_blinded_packet_fingerprint=validated_packet["source_blinded_packet_fingerprint"],
                preference=preference,
                ratings=tuple(ratings),
                confidence=_number(raw.get("confidence"), "confidence", 0.0, 1.0),
                observed_at=_token(raw.get("observed_at"), "observed_at"),
                audition_mode=CURATION_AUDITION_MODE,
                algorithm_identity_was_hidden=True,
                execution_quality_excluded_from_curation_judgment=True,
                reason_codes=reason_codes,
                notes=notes,
                activation_authorized=False,
                personal_dj_model_training_authorized=False,
            )
        )

    return tuple(parsed)


__all__ = [
    "CURATION_REVIEW_PACKET_SCHEMA_V2",
    "CURATION_REVIEW_SUBMISSION_SCHEMA_V2",
    "CurationReviewExecutionV2Error",
    "curation_packet_fingerprint",
    "parse_curation_review_submission_v2",
    "validate_curation_review_packet_v2",
]
