from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

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


def _plan_tuple(value: object, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise FreshPersonalHoldoutRunnerError(f"{field} must be a non-empty plan array")
    return tuple(_token(item, field) for item in value)


def _plan_fingerprint(plan: tuple[str, ...], *, namespace: str = "plan") -> str:
    return f"{namespace}:" + _sha256_json(plan)


def _case_exposure_fingerprint(case: Mapping[str, Any]) -> str:
    role = _token(case.get("set_role"), "set_role")
    plan_a = _plan_tuple(case.get("plan_a"), "plan_a")
    plan_b = _plan_tuple(case.get("plan_b"), "plan_b")
    pair = tuple(sorted((_plan_fingerprint(plan_a), _plan_fingerprint(plan_b))))
    return "case-exposure:" + _sha256_json((role, pair))


def _verify_prefinalization_hash(
    *,
    result: Mapping[str, str],
    path: Path,
    result_key: str,
) -> None:
    expected = _token(result.get(result_key), result_key)
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        raise FreshPersonalHoldoutRunnerError(
            f"pre-finalization file hash mismatch for {path.name}"
        )


def _prior_exposure_registry(paths: Sequence[str | Path]) -> dict[str, Any]:
    if not paths:
        raise FreshPersonalHoldoutRunnerError(
            "fresh formal holdout requires at least one prior reviewer packet exclusion source"
        )
    case_fingerprints: set[str] = set()
    plan_fingerprints: set[str] = set()
    sources: list[dict[str, str]] = []
    for raw_path in paths:
        path = Path(raw_path).expanduser().resolve()
        packet = _load(path)
        cases = packet.get("cases")
        if not isinstance(cases, list) or not cases:
            raise FreshPersonalHoldoutRunnerError(
                f"prior reviewer packet contains no cases: {path}"
            )
        for case in cases:
            if not isinstance(case, Mapping):
                raise FreshPersonalHoldoutRunnerError("prior reviewer case must be an object")
            case_fingerprints.add(_case_exposure_fingerprint(case))
            plan_fingerprints.add(_plan_fingerprint(_plan_tuple(case.get("plan_a"), "plan_a")))
            plan_fingerprints.add(_plan_fingerprint(_plan_tuple(case.get("plan_b"), "plan_b")))
        sources.append(
            {
                "path_sha256": hashlib.sha256(str(path).encode("utf-8")).hexdigest(),
                "content_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    registry_payload = {
        "case_fingerprints": sorted(case_fingerprints),
        "plan_fingerprints": sorted(plan_fingerprints),
        "source_content_sha256": sorted(item["content_sha256"] for item in sources),
    }
    return {
        "case_fingerprints": case_fingerprints,
        "plan_fingerprints": plan_fingerprints,
        "sources": sources,
        "registry_fingerprint": "prior-exposure-registry:" + _sha256_json(registry_payload),
    }


def _historical_private_sequences(raw: Mapping[str, Any]) -> tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...]:
    cases = raw.get("cases")
    if not isinstance(cases, list) or not cases:
        raise FreshPersonalHoldoutRunnerError(
            "historical private manifest contains no stable case sequence evidence"
        )
    rows: list[tuple[str, tuple[str, ...], tuple[str, ...]]] = []
    for item in cases:
        if not isinstance(item, Mapping):
            raise FreshPersonalHoldoutRunnerError("historical private case must be an object")
        case = item.get("case")
        assignment = item.get("assignment")
        if not isinstance(case, Mapping) or not isinstance(assignment, Mapping):
            raise FreshPersonalHoldoutRunnerError(
                "historical private case lacks case/assignment binding"
            )
        greedy = case.get("greedy_plan")
        beam = case.get("beam_plan")
        if not isinstance(greedy, Mapping) or not isinstance(beam, Mapping):
            raise FreshPersonalHoldoutRunnerError("historical private case lacks plan evidence")
        plan_by_id = {
            _token(greedy.get("plan_id"), "greedy plan_id"): _plan_tuple(
                greedy.get("ordered_track_ids"), "greedy ordered_track_ids"
            ),
            _token(beam.get("plan_id"), "beam plan_id"): _plan_tuple(
                beam.get("ordered_track_ids"), "beam ordered_track_ids"
            ),
        }
        slot_a_id = _token(assignment.get("slot_a_plan_id"), "slot_a_plan_id")
        slot_b_id = _token(assignment.get("slot_b_plan_id"), "slot_b_plan_id")
        if slot_a_id not in plan_by_id or slot_b_id not in plan_by_id:
            raise FreshPersonalHoldoutRunnerError(
                "historical private assignment references unknown plans"
            )
        rows.append(
            (
                _token(case.get("set_role"), "set_role"),
                plan_by_id[slot_a_id],
                plan_by_id[slot_b_id],
            )
        )
    return tuple(rows)


def _fresh_private_stable_registry(raw: Mapping[str, Any]) -> tuple[set[str], set[str]]:
    stable = raw.get("stable_exposure_registry")
    if not isinstance(stable, Mapping):
        raise FreshPersonalHoldoutRunnerError(
            "prior fresh private manifest lacks stable exposure registry"
        )
    plans = stable.get("stable_plan_fingerprints")
    cases = stable.get("stable_case_fingerprints")
    if not isinstance(plans, list) or not isinstance(cases, list):
        raise FreshPersonalHoldoutRunnerError(
            "prior fresh stable exposure registry is malformed"
        )
    return (
        {_token(item, "stable plan fingerprint") for item in plans},
        {_token(item, "stable case fingerprint") for item in cases},
    )


def _prior_private_exposure_registry(paths: Sequence[str | Path]) -> dict[str, Any]:
    if not paths:
        raise FreshPersonalHoldoutRunnerError(
            "fresh formal holdout requires at least one prior private stable-identity source"
        )
    stable_plans: set[str] = set()
    stable_cases: set[str] = set()
    sources: list[dict[str, str]] = []
    for raw_path in paths:
        path = Path(raw_path).expanduser().resolve()
        raw = _load(path)
        schema = _token(raw.get("schema"), "prior private schema")
        if schema == "applaylist-private-runtime-music-evidence-r1":
            for role, plan_a, plan_b in _historical_private_sequences(raw):
                a_fp = _plan_fingerprint(plan_a, namespace="stable-plan")
                b_fp = _plan_fingerprint(plan_b, namespace="stable-plan")
                stable_plans.update((a_fp, b_fp))
                stable_cases.add(
                    "stable-case:" + _sha256_json((role, tuple(sorted((a_fp, b_fp)))))
                )
        elif schema == FRESH_PERSONAL_HOLDOUT_PRIVATE_SCHEMA:
            plans, cases = _fresh_private_stable_registry(raw)
            stable_plans.update(plans)
            stable_cases.update(cases)
        else:
            raise FreshPersonalHoldoutRunnerError(
                f"unsupported prior private exposure schema: {schema}"
            )
        sources.append(
            {
                "path_sha256": hashlib.sha256(str(path).encode("utf-8")).hexdigest(),
                "content_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    payload = {
        "stable_plan_fingerprints": sorted(stable_plans),
        "stable_case_fingerprints": sorted(stable_cases),
        "source_content_sha256": sorted(item["content_sha256"] for item in sources),
    }
    return {
        "stable_plan_fingerprints": stable_plans,
        "stable_case_fingerprints": stable_cases,
        "sources": sources,
        "registry_fingerprint": "prior-private-exposure-registry:" + _sha256_json(payload),
    }


def _snapshot_display_to_track_id(snapshot_path: str | Path) -> dict[str, str]:
    path = Path(snapshot_path).expanduser().resolve()
    raw = _load(path)
    if raw.get("schema") != "applaylist-local-library-snapshot-r1":
        raise FreshPersonalHoldoutRunnerError("unexpected snapshot schema for stable exposure")
    tracks = raw.get("tracks")
    if not isinstance(tracks, list) or not tracks:
        raise FreshPersonalHoldoutRunnerError("snapshot contains no tracks")
    mapping: dict[str, str] = {}
    for item in tracks:
        if not isinstance(item, Mapping):
            raise FreshPersonalHoldoutRunnerError("snapshot track must be an object")
        name = _token(item.get("display_name"), "display_name")
        track_id = _token(item.get("track_id"), "track_id")
        if name in mapping and mapping[name] != track_id:
            raise FreshPersonalHoldoutRunnerError(
                "snapshot display names are not unique enough for stable exposure binding"
            )
        mapping[name] = track_id
    return mapping


def _current_stable_exposure(
    cases: Sequence[Mapping[str, Any]],
    *,
    snapshot_path: str | Path,
) -> dict[str, Any]:
    names = _snapshot_display_to_track_id(snapshot_path)
    stable_plans: set[str] = set()
    stable_cases: set[str] = set()
    case_rows: list[dict[str, Any]] = []
    for case in cases:
        role = _token(case.get("set_role"), "set_role")
        resolved: dict[str, tuple[str, ...]] = {}
        for field in ("plan_a", "plan_b"):
            display_plan = _plan_tuple(case.get(field), field)
            try:
                track_plan = tuple(names[name] for name in display_plan)
            except KeyError as exc:
                raise FreshPersonalHoldoutRunnerError(
                    "reviewer plan contains a display name absent from frozen snapshot"
                ) from exc
            resolved[field] = track_plan
        a_fp = _plan_fingerprint(resolved["plan_a"], namespace="stable-plan")
        b_fp = _plan_fingerprint(resolved["plan_b"], namespace="stable-plan")
        case_fp = "stable-case:" + _sha256_json((role, tuple(sorted((a_fp, b_fp)))))
        stable_plans.update((a_fp, b_fp))
        stable_cases.add(case_fp)
        case_rows.append(
            {
                "case_id": _token(case.get("case_id"), "case_id"),
                "stable_plan_a_fingerprint": a_fp,
                "stable_plan_b_fingerprint": b_fp,
                "stable_case_fingerprint": case_fp,
            }
        )
    return {
        "stable_plan_fingerprints": stable_plans,
        "stable_case_fingerprints": stable_cases,
        "case_rows": case_rows,
    }


def _assert_fresh_cases(
    cases: list[dict[str, Any]],
    reviewer_registry: Mapping[str, Any],
    private_registry: Mapping[str, Any],
    *,
    snapshot_path: str | Path,
) -> dict[str, Any]:
    prior_cases = set(reviewer_registry["case_fingerprints"])
    prior_plans = set(reviewer_registry["plan_fingerprints"])
    for case in cases:
        if not isinstance(case, Mapping):
            raise FreshPersonalHoldoutRunnerError("reviewer case must be an object")
        if _case_exposure_fingerprint(case) in prior_cases:
            raise FreshPersonalHoldoutRunnerError(
                "fresh holdout selected an A/B case pair already exposed in prior review"
            )
        for field in ("plan_a", "plan_b"):
            plan = _plan_tuple(case.get(field), field)
            if _plan_fingerprint(plan) in prior_plans:
                raise FreshPersonalHoldoutRunnerError(
                    "fresh holdout selected a plan sequence already exposed in prior review"
                )

    stable = _current_stable_exposure(cases, snapshot_path=snapshot_path)
    if stable["stable_plan_fingerprints"] & set(private_registry["stable_plan_fingerprints"]):
        raise FreshPersonalHoldoutRunnerError(
            "fresh holdout selected a stable track-id plan already exposed in prior review"
        )
    if stable["stable_case_fingerprints"] & set(private_registry["stable_case_fingerprints"]):
        raise FreshPersonalHoldoutRunnerError(
            "fresh holdout selected a stable track-id A/B pair already exposed in prior review"
        )
    return stable


def _workspace_session_id(
    private: Mapping[str, Any],
    reviewer: Mapping[str, Any],
    *,
    reviewer_exposure_registry_fingerprint: str,
    private_exposure_registry_fingerprint: str,
) -> str:
    material = {
        "version": REVIEWER_WORKSPACE_VERSION,
        "canonical_sha": private.get("canonical_sha"),
        "preregistration_fingerprint": private.get("preregistration_fingerprint"),
        "selection_manifest_fingerprint": (private.get("selection") or {}).get(
            "manifest_fingerprint"
        ),
        "effective_cohort_id": (private.get("effective_cohort") or {}).get("cohort_id"),
        "reviewer_packet_prebind_fingerprint": reviewer.get("packet_fingerprint"),
        "reviewer_exposure_registry_fingerprint": reviewer_exposure_registry_fingerprint,
        "private_exposure_registry_fingerprint": private_exposure_registry_fingerprint,
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


def finalize_fresh_holdout_reviewer_workspace(
    result: Mapping[str, str],
    *,
    snapshot_path: str | Path,
    prior_reviewer_packet_paths: Sequence[str | Path],
    prior_private_manifest_paths: Sequence[str | Path],
) -> dict[str, str]:
    """Bind reviewer-safe files to frozen preregistration and reject prior exposure."""
    private_path = Path(_token(result.get("private_manifest"), "private_manifest"))
    reviewer_path = Path(_token(result.get("reviewer_packet"), "reviewer_packet"))
    csv_path = Path(_token(result.get("review_csv"), "review_csv"))

    _verify_prefinalization_hash(
        result=result,
        path=private_path,
        result_key="private_manifest_sha256",
    )
    _verify_prefinalization_hash(
        result=result,
        path=reviewer_path,
        result_key="reviewer_packet_sha256",
    )
    _verify_prefinalization_hash(
        result=result,
        path=csv_path,
        result_key="review_csv_sha256",
    )

    private = _load(private_path)
    reviewer = _load(reviewer_path)

    if private.get("schema") != FRESH_PERSONAL_HOLDOUT_PRIVATE_SCHEMA:
        raise FreshPersonalHoldoutRunnerError("unexpected private fresh-holdout schema")
    if reviewer.get("schema") != FRESH_PERSONAL_HOLDOUT_REVIEWER_SCHEMA:
        raise FreshPersonalHoldoutRunnerError("unexpected reviewer fresh-holdout schema")
    if not private.get("challenger_frozen_before_reviewer_publication"):
        raise FreshPersonalHoldoutRunnerError(
            "challenger evidence is not frozen before reviewer publication"
        )

    selection = private.get("selection") or {}
    policy = private.get("sampling_policy") or {}
    cohort = private.get("effective_cohort") or {}
    selected = selection.get("selected_case_ids") or []
    fallback = selection.get("fallback_case_ids") or []
    effective = cohort.get("effective_case_ids") or []
    expected_fallback = int(policy.get("fallback_count", -1))
    if len(selected) != 24:
        raise FreshPersonalHoldoutRunnerError("frozen holdout selection must contain 24 cases")
    if expected_fallback < 0 or len(fallback) != expected_fallback:
        raise FreshPersonalHoldoutRunnerError(
            "frozen fallback reservoir does not satisfy preregistered fallback_count"
        )
    if len(effective) != 24:
        raise FreshPersonalHoldoutRunnerError("effective cohort must contain exactly 24 cases")

    cases = reviewer.get("cases")
    if not isinstance(cases, list) or len(cases) != 24:
        raise FreshPersonalHoldoutRunnerError("reviewer workspace requires exactly 24 cases")
    reviewer_case_ids = tuple(_token(case.get("case_id"), "case_id") for case in cases)
    if reviewer_case_ids != tuple(_token(item, "effective_case_id") for item in effective):
        raise FreshPersonalHoldoutRunnerError(
            "reviewer case order/identity does not match frozen effective cohort"
        )

    assignments = private.get("assignments")
    if not isinstance(assignments, list):
        raise FreshPersonalHoldoutRunnerError("private manifest lacks assignment bindings")
    assignment_by_case = {
        _token(item.get("case_id"), "assignment case_id"): _token(
            item.get("assignment_id"), "assignment_id"
        )
        for item in assignments
        if isinstance(item, Mapping)
    }
    specs = ((private.get("candidate_case_specs") or {}).get("case_specs") or [])
    role_by_case = {
        _token(item.get("case_spec_id"), "case_spec_id"): _token(item.get("set_role"), "set_role")
        for item in specs
        if isinstance(item, Mapping)
    }
    for case in cases:
        case_id = _token(case.get("case_id"), "case_id")
        if assignment_by_case.get(case_id) != _token(case.get("assignment_id"), "assignment_id"):
            raise FreshPersonalHoldoutRunnerError(
                "reviewer assignment does not match frozen private assignment"
            )
        if role_by_case.get(case_id) != _token(case.get("set_role"), "set_role"):
            raise FreshPersonalHoldoutRunnerError(
                "reviewer set role does not match frozen candidate spec"
            )

    reviewer_registry = _prior_exposure_registry(prior_reviewer_packet_paths)
    private_registry = _prior_private_exposure_registry(prior_private_manifest_paths)
    stable_current = _assert_fresh_cases(
        cases,
        reviewer_registry,
        private_registry,
        snapshot_path=snapshot_path,
    )

    prereg = _token(private.get("preregistration_fingerprint"), "preregistration_fingerprint")
    selection_fp = _token(selection.get("manifest_fingerprint"), "selection manifest fingerprint")
    cohort_id = _token(cohort.get("cohort_id"), "effective cohort id")
    canonical_sha = _token(private.get("canonical_sha"), "canonical_sha")
    session_id = _workspace_session_id(
        private,
        reviewer,
        reviewer_exposure_registry_fingerprint=reviewer_registry["registry_fingerprint"],
        private_exposure_registry_fingerprint=private_registry["registry_fingerprint"],
    )

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
            "prior_exposure_registry_fingerprint": reviewer_registry["registry_fingerprint"],
            "prior_private_exposure_registry_fingerprint": private_registry["registry_fingerprint"],
            "explicit_human_fields_required": list(_HUMAN_FIELDS),
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
        raise FreshPersonalHoldoutRunnerError(
            "reviewer workspace contains private/model leakage"
        )

    reviewer_path.write_text(reviewer_text, encoding="utf-8")
    _write_review_csv(
        path=csv_path,
        cases=cases,
        session_id=session_id,
        packet_fingerprint=packet_fingerprint,
    )

    stable_registry_payload = {
        "registry_version": "stable-exposure-registry-r1",
        "snapshot_ref": private.get("snapshot_ref"),
        "stable_plan_fingerprints": sorted(stable_current["stable_plan_fingerprints"]),
        "stable_case_fingerprints": sorted(stable_current["stable_case_fingerprints"]),
        "case_rows": stable_current["case_rows"],
    }
    stable_registry_payload["registry_fingerprint"] = (
        "stable-exposure-registry:" + _sha256_json(stable_registry_payload)
    )
    private["stable_exposure_registry"] = stable_registry_payload
    private["reviewer_workspace_binding"] = {
        "workspace_version": REVIEWER_WORKSPACE_VERSION,
        "curation_session_id": session_id,
        "reviewer_packet_fingerprint": packet_fingerprint,
        "prior_exposure_registry_fingerprint": reviewer_registry["registry_fingerprint"],
        "prior_exposure_sources": reviewer_registry["sources"],
        "prior_private_exposure_registry_fingerprint": private_registry["registry_fingerprint"],
        "prior_private_exposure_sources": private_registry["sources"],
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
            raise FreshPersonalHoldoutRunnerError(
                "review CSV fabricated a human evidence field"
            )

    finalized = dict(result)
    finalized.update(
        {
            "curation_session_id": session_id,
            "reviewer_packet_fingerprint": packet_fingerprint,
            "prior_exposure_registry_fingerprint": reviewer_registry["registry_fingerprint"],
            "prior_private_exposure_registry_fingerprint": private_registry["registry_fingerprint"],
            "stable_exposure_registry_fingerprint": stable_registry_payload["registry_fingerprint"],
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
