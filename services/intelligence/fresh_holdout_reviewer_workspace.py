from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from services.intelligence.fresh_personal_holdout_runner import (
    FRESH_PERSONAL_HOLDOUT_PRIVATE_SCHEMA,
    FRESH_PERSONAL_HOLDOUT_REVIEWER_SCHEMA,
    FreshPersonalHoldoutRunnerError,
)

REVIEWER_WORKSPACE_VERSION = "fresh-personal-holdout-reviewer-workspace-r1"

_HUMAN_FIELDS = (
    "reviewer_ref",
    "preference",
    "energy_flow_plan_a",
    "energy_flow_plan_b",
    "dramaturgical_fit_plan_a",
    "dramaturgical_fit_plan_b",
    "set_coherence_plan_a",
    "set_coherence_plan_b",
    "alternative_usefulness_plan_a",
    "alternative_usefulness_plan_b",
    "confidence",
    "prior_case_exposure",
    "judgment_mode",
    "transition_execution_used",
    "transition_preview_heard",
    "algorithm_identity_was_hidden",
    "reason_codes",
    "notes",
    "observed_at",
)


def _load(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise FreshPersonalHoldoutRunnerError(f"workspace JSON must be an object: {path}")
    return raw


def _sha256_json(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _token(value: object, field: str) -> str:
    text = str(value).strip()
    if not text:
        raise FreshPersonalHoldoutRunnerError(f"{field} must not be empty")
    return text


def _workspace_session_id(private: Mapping[str, Any], reviewer: Mapping[str, Any]) -> str:
    material = {
        "version": REVIEWER_WORKSPACE_VERSION,
        "canonical_sha": private.get("canonical_sha"),
        "preregistration_fingerprint": private.get("preregistration_fingerprint"),
        "selection_manifest_fingerprint": (private.get("selection") or {}).get(
            "manifest_fingerprint"
        ),
        "effective_cohort_id": (private.get("effective_cohort") or {}).get("cohort_id"),
        "reviewer_packet_prebind_fingerprint": reviewer.get("packet_fingerprint"),
    }
    return "curation-session:" + _sha256_json(material)[:32]


def _write_review_csv(
    *,
    path: Path,
    cases: list[dict[str, Any]],
    session_id: str,
    packet_fingerprint: str,
) -> None:
    columns = [
        "case_index",
        "case_id",
        "set_role",
        "assignment_id",
        "dataset_role",
        "curation_session_id",
        "reviewer_packet_fingerprint",
        "reviewer_ref",
        "preference",
        "energy_flow_plan_a",
        "energy_flow_plan_b",
        "dramaturgical_fit_plan_a",
        "dramaturgical_fit_plan_b",
        "set_coherence_plan_a",
        "set_coherence_plan_b",
        "alternative_usefulness_plan_a",
        "alternative_usefulness_plan_b",
        "confidence",
        "prior_case_exposure",
        "judgment_mode",
        "transition_execution_used",
        "transition_preview_heard",
        "algorithm_identity_was_hidden",
        "reason_codes",
        "notes",
        "observed_at",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for index, case in enumerate(cases, start=1):
            row = {
                "case_index": index,
                "case_id": _token(case.get("case_id"), "case_id"),
                "set_role": _token(case.get("set_role"), "set_role"),
                "assignment_id": _token(case.get("assignment_id"), "assignment_id"),
                "dataset_role": "personal_holdout",
                "curation_session_id": session_id,
                "reviewer_packet_fingerprint": packet_fingerprint,
            }
            for field in _HUMAN_FIELDS:
                row[field] = ""
            writer.writerow(row)


def finalize_fresh_holdout_reviewer_workspace(result: Mapping[str, str]) -> dict[str, str]:
    """Bind reviewer-safe files to frozen private preregistration without adding human labels."""
    private_path = Path(_token(result.get("private_manifest"), "private_manifest"))
    reviewer_path = Path(_token(result.get("reviewer_packet"), "reviewer_packet"))
    csv_path = Path(_token(result.get("review_csv"), "review_csv"))
    private = _load(private_path)
    reviewer = _load(reviewer_path)

    if private.get("schema") != FRESH_PERSONAL_HOLDOUT_PRIVATE_SCHEMA:
        raise FreshPersonalHoldoutRunnerError("unexpected private fresh-holdout schema")
    if reviewer.get("schema") != FRESH_PERSONAL_HOLDOUT_REVIEWER_SCHEMA:
        raise FreshPersonalHoldoutRunnerError("unexpected reviewer fresh-holdout schema")
    if not private.get("challenger_frozen_before_reviewer_publication"):
        raise FreshPersonalHoldoutRunnerError("challenger evidence is not frozen before reviewer publication")

    selection = private.get("selection") or {}
    cohort = private.get("effective_cohort") or {}
    prereg = _token(private.get("preregistration_fingerprint"), "preregistration_fingerprint")
    selection_fp = _token(selection.get("manifest_fingerprint"), "selection manifest fingerprint")
    cohort_id = _token(cohort.get("cohort_id"), "effective cohort id")
    canonical_sha = _token(private.get("canonical_sha"), "canonical_sha")
    session_id = _workspace_session_id(private, reviewer)

    reviewer.pop("packet_fingerprint", None)
    reviewer.update(
        {
            "workspace_version": REVIEWER_WORKSPACE_VERSION,
            "canonical_sha": canonical_sha,
            "preregistration_fingerprint": prereg,
            "selection_manifest_fingerprint": selection_fp,
            "effective_cohort_id": cohort_id,
            "curation_session_id": session_id,
            "dataset_role": "personal_holdout",
            "explicit_human_attestation_required": list(_HUMAN_FIELDS),
        }
    )
    packet_fingerprint = _sha256_json(reviewer)
    reviewer["packet_fingerprint"] = packet_fingerprint

    reviewer_text = json.dumps(reviewer, indent=2, ensure_ascii=False, default=str) + "\n"
    forbidden = (
        "challenger_evidence",
        "left_assessment",
        "right_assessment",
        "left_score",
        "right_score",
        "shadow_right_path_preferred",
        "shadow_left_path_preferred",
        "greedy_recommend_next",
        "bounded_beam",
        "absolute_path",
    )
    if any(token in reviewer_text for token in forbidden):
        raise FreshPersonalHoldoutRunnerError("reviewer workspace contains private/model leakage")

    reviewer_path.write_text(reviewer_text, encoding="utf-8")
    cases = reviewer.get("cases")
    if not isinstance(cases, list) or len(cases) != 24:
        raise FreshPersonalHoldoutRunnerError("reviewer workspace requires exactly 24 cases")
    _write_review_csv(
        path=csv_path,
        cases=cases,
        session_id=session_id,
        packet_fingerprint=packet_fingerprint,
    )

    private["reviewer_workspace_binding"] = {
        "workspace_version": REVIEWER_WORKSPACE_VERSION,
        "curation_session_id": session_id,
        "reviewer_packet_fingerprint": packet_fingerprint,
        "human_labels_present_at_freeze": False,
    }
    private_path.write_text(
        json.dumps(private, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )

    csv_rows = list(csv.DictReader(csv_path.open("r", encoding="utf-8", newline="")))
    if len(csv_rows) != 24:
        raise FreshPersonalHoldoutRunnerError("review CSV requires exactly 24 rows")
    for row in csv_rows:
        if any(str(row.get(field, "")).strip() for field in _HUMAN_FIELDS):
            raise FreshPersonalHoldoutRunnerError("review CSV fabricated a human evidence field")

    finalized = dict(result)
    finalized.update(
        {
            "curation_session_id": session_id,
            "reviewer_packet_fingerprint": packet_fingerprint,
            "private_manifest_sha256": hashlib.sha256(private_path.read_bytes()).hexdigest(),
            "reviewer_packet_sha256": hashlib.sha256(reviewer_path.read_bytes()).hexdigest(),
            "review_csv_sha256": hashlib.sha256(csv_path.read_bytes()).hexdigest(),
        }
    )
    return finalized


__all__ = [
    "REVIEWER_WORKSPACE_VERSION",
    "finalize_fresh_holdout_reviewer_workspace",
]
