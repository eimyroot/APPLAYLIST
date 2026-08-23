from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping, Sequence

from core.intelligence.competitive_curation_contract import CompetitiveCurationPolicy
from core.intelligence.curated_real_library_review_contract import CuratedSetRole
from core.intelligence.human_review_preregistration_r2_contract import HoldoutReplacementPolicyR2
from core.intelligence.human_review_protocol_r2_contract import (
    HoldoutCandidate,
    HoldoutCaseSamplingPolicy,
    ReviewDatasetRole,
)
from services.intelligence.competitive_curation import (
    compare_competitive_curation_paths,
    track_curation_evidence_from_music_dna,
)
from services.intelligence.human_review_protocol_r2 import (
    build_effective_holdout_cohort_r2,
    holdout_replacement_policy_fingerprint,
    select_holdout_cases_r2,
)
from services.intelligence.real_library_pilot import (
    MaterializedCase,
    RealLibraryPilotError,
    _intent_for_case,
    _load_json,
    _sha256_json,
    _track_inputs,
    _validate_snapshot,
    analyze_real_tracks,
    materialize_cases,
)

FRESH_PERSONAL_HOLDOUT_RUNNER_VERSION = "fresh-personal-holdout-runner-r1"
FRESH_PERSONAL_HOLDOUT_PRIVATE_SCHEMA = "applaylist-fresh-personal-holdout-private-r1"
FRESH_PERSONAL_HOLDOUT_REVIEWER_SCHEMA = "applaylist-fresh-personal-holdout-reviewer-r1"


class FreshPersonalHoldoutRunnerError(RuntimeError):
    """Fail-closed error for fresh personal holdout execution."""


def _token(value: object, field: str) -> str:
    text = str(value).strip()
    if not text:
        raise FreshPersonalHoldoutRunnerError(f"{field} must not be empty")
    return text


def _fingerprint(label: str, payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return f"{label}:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _case_spec_pool(
    snapshot_raw: Mapping[str, Any],
    *,
    sampling_seed: str,
    cases_per_role: int = 8,
    candidate_scope_size: int = 16,
) -> dict[str, Any]:
    """Build deterministic case specs from snapshot identity only.

    This stage intentionally has no access to optimizer outputs, challenger scores,
    or human evidence. Track ordering is hash-based from frozen snapshot identity.
    """
    snapshot = _validate_snapshot(snapshot_raw)
    seed = _token(sampling_seed, "sampling_seed")
    tracks = _track_inputs(snapshot_raw)
    track_ids = tuple(sorted(tracks))
    minimum_tracks = candidate_scope_size + 1
    if len(track_ids) < minimum_tracks:
        raise FreshPersonalHoldoutRunnerError(
            f"fresh holdout requires at least {minimum_tracks} tracks in the snapshot"
        )
    if cases_per_role < 4:
        raise FreshPersonalHoldoutRunnerError("cases_per_role must be at least 4")

    specs: list[dict[str, Any]] = []
    for role in CuratedSetRole:
        ranked = sorted(
            track_ids,
            key=lambda track_id: hashlib.sha256(
                f"{FRESH_PERSONAL_HOLDOUT_RUNNER_VERSION}|{seed}|{role.value}|seed|{track_id}".encode(
                    "utf-8"
                )
            ).hexdigest(),
        )
        for ordinal, seed_track_id in enumerate(ranked[:cases_per_role]):
            remaining = [track_id for track_id in track_ids if track_id != seed_track_id]
            candidate_scope = sorted(
                remaining,
                key=lambda track_id: hashlib.sha256(
                    (
                        f"{FRESH_PERSONAL_HOLDOUT_RUNNER_VERSION}|{seed}|{role.value}|"
                        f"{ordinal}|scope|{track_id}"
                    ).encode("utf-8")
                ).hexdigest(),
            )[:candidate_scope_size]
            case_spec_id = "fps_" + hashlib.sha256(
                f"{snapshot.library_fingerprint}|{seed}|{role.value}|{ordinal}|{seed_track_id}".encode(
                    "utf-8"
                )
            ).hexdigest()[:24]
            specs.append(
                {
                    "case_spec_id": case_spec_id,
                    "set_role": role.value,
                    "seed_track_id": seed_track_id,
                    "candidate_scope_track_ids": candidate_scope,
                }
            )
    return {
        "schema": "applaylist-curated-case-selection-r1",
        "snapshot_ref": [snapshot.snapshot_id, snapshot.snapshot_version],
        "generator_version": FRESH_PERSONAL_HOLDOUT_RUNNER_VERSION,
        "sampling_seed": seed,
        "case_specs": specs,
    }


def _snapshot_scope_fingerprint(snapshot_raw: Mapping[str, Any]) -> str:
    tracks = _track_inputs(snapshot_raw)
    payload = [
        {"track_id": item.track_id, "file_signature": item.file_signature}
        for item in sorted(tracks.values(), key=lambda item: item.track_id)
    ]
    return _fingerprint("eligible-scope-r1", payload)


def _single_case_selection(selection_raw: Mapping[str, Any], spec: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema": selection_raw["schema"],
        "snapshot_ref": list(selection_raw["snapshot_ref"]),
        "generator_version": selection_raw.get("generator_version"),
        "sampling_seed": selection_raw.get("sampling_seed"),
        "case_specs": [dict(spec)],
    }


def _materialize_candidate_pool(
    *,
    snapshot_raw: Mapping[str, Any],
    selection_raw: Mapping[str, Any],
    evidence: Mapping[str, Any],
    database_path: str | Path,
    generated_at: str,
    blinding_seed: str,
) -> tuple[tuple[MaterializedCase, ...], tuple[dict[str, str], ...]]:
    """Materialize each candidate independently so one invalid case cannot abort the pool."""
    materialized: list[MaterializedCase] = []
    failures: list[dict[str, str]] = []
    for spec in selection_raw["case_specs"]:
        case_id = _token(spec["case_spec_id"], "case_spec_id")
        try:
            result = materialize_cases(
                snapshot_raw=snapshot_raw,
                selection_raw=_single_case_selection(selection_raw, spec),
                evidence=evidence,
                database_path=database_path,
                generated_at=generated_at,
                blinding_seed=blinding_seed,
            )
        except RealLibraryPilotError as exc:
            failures.append(
                {
                    "case_id": case_id,
                    "set_role": str(spec["set_role"]),
                    "technical_invalidity_reason": "engineering_materialization_failed",
                    "detail": str(exc),
                }
            )
            continue
        if len(result) != 1 or result[0].case.case_id != case_id:
            raise FreshPersonalHoldoutRunnerError("single-case materialization identity mismatch")
        materialized.append(result[0])
    return tuple(materialized), tuple(failures)


def _materialized_by_case(cases: Sequence[MaterializedCase]) -> dict[str, MaterializedCase]:
    result: dict[str, MaterializedCase] = {}
    for item in cases:
        if item.case.case_id in result:
            raise FreshPersonalHoldoutRunnerError("duplicate materialized case id")
        result[item.case.case_id] = item
    return result


def _holdout_candidates(
    selection_raw: Mapping[str, Any],
    cases: Sequence[MaterializedCase],
    failures: Sequence[Mapping[str, str]],
) -> tuple[HoldoutCandidate, ...]:
    valid = _materialized_by_case(cases)
    failed = {item["case_id"]: item for item in failures}
    rows: list[HoldoutCandidate] = []
    for spec in selection_raw["case_specs"]:
        case_id = _token(spec["case_spec_id"], "case_spec_id")
        role = CuratedSetRole(str(spec["set_role"]).strip().lower())
        if case_id in valid:
            rows.append(
                HoldoutCandidate(
                    candidate_id=f"holdout:{case_id}",
                    case_id=case_id,
                    set_role=role,
                    engineering_acceptance_passed=True,
                )
            )
        else:
            failure = failed.get(case_id)
            rows.append(
                HoldoutCandidate(
                    candidate_id=f"holdout:{case_id}",
                    case_id=case_id,
                    set_role=role,
                    engineering_acceptance_passed=False,
                    technical_invalidity_reason=(
                        failure["technical_invalidity_reason"]
                        if failure is not None
                        else "engineering_materialization_missing"
                    ),
                )
            )
    return tuple(rows)


def _private_track_evidence(evidence: Mapping[str, Any]) -> tuple[Any, ...]:
    rows = []
    for _, item in sorted(evidence.items()):
        style_tags = (item.source.genre,) if item.source.genre else None
        rows.append(
            track_curation_evidence_from_music_dna(
                music_dna=item.music_dna,
                style_tags=style_tags,
                vocal_presence=None,
            )
        )
    return tuple(rows)


def _optimizer_alternative(item: MaterializedCase, *, strategy: str):
    result = item.greedy_result if strategy == "greedy" else item.beam_result
    path_id = item.case.greedy_plan.path_id if strategy == "greedy" else item.case.beam_plan.path_id
    for alternative in result.alternatives:
        if alternative.path_id == path_id:
            return alternative
    raise FreshPersonalHoldoutRunnerError(
        f"materialized {strategy} path missing for {item.case.case_id}"
    )


def _challenger_record(
    item: MaterializedCase,
    *,
    case_spec: Mapping[str, Any],
    track_evidence: tuple[Any, ...],
) -> dict[str, Any]:
    role = CuratedSetRole(str(case_spec["set_role"]).strip().lower())
    seed_track_id = _token(case_spec["seed_track_id"], "seed_track_id")
    candidate_ids = tuple(
        _token(value, "candidate_scope_track_id")
        for value in case_spec["candidate_scope_track_ids"]
    )
    intent = _intent_for_case(
        case_id=item.case.case_id,
        role=role,
        seed_track_id=seed_track_id,
        candidate_track_ids=candidate_ids,
    )
    greedy = _optimizer_alternative(item, strategy="greedy")
    beam = _optimizer_alternative(item, strategy="beam")
    left, right, comparison = compare_competitive_curation_paths(
        left=greedy,
        right=beam,
        intent=intent,
        track_evidence=track_evidence,
        policy=CompetitiveCurationPolicy(),
    )
    return {
        "case_id": item.case.case_id,
        "left_assessment": asdict(left),
        "right_assessment": asdict(right),
        "comparison": asdict(comparison),
    }


def _reviewer_case(item: MaterializedCase, *, names: Mapping[str, str]) -> dict[str, Any]:
    assignment = item.assignment
    case = item.case
    plan_by_id = {
        case.greedy_plan.plan_id: case.greedy_plan,
        case.beam_plan.plan_id: case.beam_plan,
    }
    plan_a = plan_by_id[assignment.slot_a_plan_id]
    plan_b = plan_by_id[assignment.slot_b_plan_id]
    return {
        "case_id": case.case_id,
        "set_role": case.set_role.value,
        "assignment_id": assignment.assignment_id,
        "plan_a": [names[track_id] for track_id in plan_a.ordered_track_ids],
        "plan_b": [names[track_id] for track_id in plan_b.ordered_track_ids],
        "required_review_dimensions": [
            "energy_flow",
            "dramaturgical_fit",
            "set_coherence",
            "alternative_usefulness",
        ],
        "allowed_preference": ["plan_a", "plan_b", "tie", "abstain"],
        "transition_execution_required": False,
    }


def _write_review_csv(path: Path, rows: Sequence[dict[str, Any]]) -> None:
    columns = [
        "case_index",
        "case_id",
        "set_role",
        "assignment_id",
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
        "reason_codes",
        "notes",
        "observed_at",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for index, row in enumerate(rows, start=1):
            writer.writerow(
                {
                    "case_index": index,
                    "case_id": row["case_id"],
                    "set_role": row["set_role"],
                    "assignment_id": row["assignment_id"],
                }
            )


def materialize_fresh_personal_holdout_r1(
    *,
    snapshot_path: str | Path,
    output_dir: str | Path,
    database_path: str | Path,
    canonical_sha: str,
    generated_at: str,
    sampling_seed: str,
    blinding_seed: str,
    cases_per_role: int = 8,
    candidate_scope_size: int = 16,
    fallback_count: int = 12,
) -> dict[str, str]:
    """Materialize a fresh, frozen, reviewer-safe personal curation holdout."""
    snapshot_raw = _load_json(snapshot_path)
    snapshot = _validate_snapshot(snapshot_raw)
    canonical = _token(canonical_sha, "canonical_sha")
    generated = _token(generated_at, "generated_at")

    selection_raw = _case_spec_pool(
        snapshot_raw,
        sampling_seed=sampling_seed,
        cases_per_role=cases_per_role,
        candidate_scope_size=candidate_scope_size,
    )
    evidence = analyze_real_tracks(snapshot_raw=snapshot_raw, selection_raw=selection_raw)
    cases, candidate_failures = _materialize_candidate_pool(
        snapshot_raw=snapshot_raw,
        selection_raw=selection_raw,
        evidence=evidence,
        database_path=database_path,
        generated_at=generated,
        blinding_seed=blinding_seed,
    )
    if not cases:
        raise FreshPersonalHoldoutRunnerError("candidate materialization produced no valid cases")

    policy = HoldoutCaseSamplingPolicy(
        policy_id="fresh-personal-holdout-r1",
        dataset_role=ReviewDatasetRole.PERSONAL_HOLDOUT,
        canonical_sha=canonical,
        snapshot_fingerprint=snapshot.library_fingerprint,
        eligible_scope_fingerprint=_snapshot_scope_fingerprint(snapshot_raw),
        source_case_generator_version=FRESH_PERSONAL_HOLDOUT_RUNNER_VERSION,
        sampling_seed=_token(sampling_seed, "sampling_seed"),
        role_quotas=tuple((role, 4) for role in CuratedSetRole),
        fallback_count=fallback_count,
        activation_authorized=False,
    )
    selection = select_holdout_cases_r2(
        policy=policy,
        candidates=_holdout_candidates(selection_raw, cases, candidate_failures),
    )
    prereg_payload = {
        "runner_version": FRESH_PERSONAL_HOLDOUT_RUNNER_VERSION,
        "canonical_sha": canonical,
        "snapshot_ref": [snapshot.snapshot_id, snapshot.snapshot_version],
        "snapshot_fingerprint": snapshot.library_fingerprint,
        "sampling_policy": asdict(policy),
        "selection": asdict(selection),
        "candidate_failures": candidate_failures,
        "generated_at": generated,
    }
    prereg_fingerprint = _fingerprint("fresh-personal-holdout-prereg-r1", prereg_payload)
    replacement_policy = HoldoutReplacementPolicyR2(
        policy_id="fresh-personal-holdout-replacement-r1",
        selection_manifest_fingerprint=selection.manifest_fingerprint,
        preregistration_manifest_fingerprint=prereg_fingerprint,
        frozen_at=generated,
        allowed_technical_invalidity_reasons=(
            "audio_path_unreadable",
            "analysis_failed",
            "engineering_acceptance_failed",
            "review_packet_materialization_failed",
        ),
        activation_authorized=False,
    )
    cohort = build_effective_holdout_cohort_r2(
        selection=selection,
        replacement_policy=replacement_policy,
        preregistration_manifest_fingerprint=prereg_fingerprint,
        technical_invalidities=(),
    )

    by_case = _materialized_by_case(cases)
    spec_by_case = {
        _token(spec["case_spec_id"], "case_spec_id"): spec
        for spec in selection_raw["case_specs"]
    }
    frozen_case_ids = tuple(selection.selected_case_ids) + tuple(selection.fallback_case_ids)
    if any(case_id not in by_case for case_id in frozen_case_ids):
        raise FreshPersonalHoldoutRunnerError(
            "selected/fallback holdout references a non-materialized candidate"
        )

    track_evidence = _private_track_evidence(evidence)
    challenger_rows = [
        _challenger_record(
            by_case[case_id],
            case_spec=spec_by_case[case_id],
            track_evidence=track_evidence,
        )
        for case_id in frozen_case_ids
    ]

    names = {track_id: item.source.display_name for track_id, item in evidence.items()}
    reviewer_rows = [
        _reviewer_case(by_case[case_id], names=names)
        for case_id in cohort.effective_case_ids
    ]
    role_counts = {
        role.value: sum(row["set_role"] == role.value for row in reviewer_rows)
        for role in CuratedSetRole
    }
    if len(reviewer_rows) != 24 or any(count != 4 for count in role_counts.values()):
        raise FreshPersonalHoldoutRunnerError(
            "effective reviewer cohort must contain exactly 24 cases, four per set role"
        )

    track_provenance = [
        {
            "track_id": track_id,
            "absolute_path": item.source.absolute_path,
            "inventory_file_signature": item.source.file_signature,
            "content_sha256": item.content_sha256,
            "analysis_revision": item.music_dna.identity.analysis_revision,
            "genre": item.source.genre,
        }
        for track_id, item in sorted(evidence.items())
    ]
    private_payload = {
        "schema": FRESH_PERSONAL_HOLDOUT_PRIVATE_SCHEMA,
        "runner_version": FRESH_PERSONAL_HOLDOUT_RUNNER_VERSION,
        "generated_at": generated,
        "canonical_sha": canonical,
        "snapshot_ref": [snapshot.snapshot_id, snapshot.snapshot_version],
        "snapshot_fingerprint": snapshot.library_fingerprint,
        "privacy": {
            "contains_local_absolute_paths": True,
            "publishable_to_public_repo": False,
            "storage_class": "CASER_PRIVATE_EVIDENCE",
        },
        "track_provenance": track_provenance,
        "candidate_case_specs": selection_raw,
        "candidate_failures": list(candidate_failures),
        "sampling_policy": asdict(policy),
        "selection": asdict(selection),
        "preregistration_fingerprint": prereg_fingerprint,
        "replacement_policy": asdict(replacement_policy),
        "replacement_policy_fingerprint": holdout_replacement_policy_fingerprint(
            replacement_policy
        ),
        "effective_cohort": asdict(cohort),
        "assignments": [
            asdict(by_case[case_id].assignment) for case_id in frozen_case_ids
        ],
        "challenger_evidence": challenger_rows,
        "challenger_frozen_before_reviewer_publication": True,
        "activation_authorized": False,
        "personal_dj_model_training_authorized": False,
    }
    reviewer_payload = {
        "schema": FRESH_PERSONAL_HOLDOUT_REVIEWER_SCHEMA,
        "protocol_version": "human-dj-review-r2",
        "generated_at": generated,
        "snapshot_ref": [snapshot.snapshot_id, snapshot.snapshot_version],
        "algorithm_identity_hidden": True,
        "sequence_only": True,
        "transition_execution_required": False,
        "required_review_dimensions": [
            "energy_flow",
            "dramaturgical_fit",
            "set_coherence",
            "alternative_usefulness",
        ],
        "cases": reviewer_rows,
        "activation_authorized": False,
        "personal_dj_model_training_authorized": False,
    }
    reviewer_payload["packet_fingerprint"] = _sha256_json(reviewer_payload)

    output = Path(output_dir).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    private_path = output / "APPLAYLIST_FRESH_PERSONAL_HOLDOUT_R1.private.json"
    reviewer_path = output / "APPLAYLIST_FRESH_PERSONAL_HOLDOUT_REVIEWER_R1.json"
    csv_path = output / "APPLAYLIST_FRESH_PERSONAL_HOLDOUT_REVIEW_R1.csv"
    private_path.write_text(
        json.dumps(private_payload, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )
    reviewer_path.write_text(
        json.dumps(reviewer_payload, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )
    _write_review_csv(csv_path, reviewer_rows)

    private_text = private_path.read_text(encoding="utf-8")
    reviewer_text = reviewer_path.read_text(encoding="utf-8")
    if any(token in reviewer_text for token in ("absolute_path", "left_score", "right_score")):
        raise FreshPersonalHoldoutRunnerError("reviewer packet leaked private/challenger evidence")
    if any(path in reviewer_text for path in (item.source.absolute_path for item in evidence.values())):
        raise FreshPersonalHoldoutRunnerError("reviewer packet leaked an absolute audio path")
    if "challenger_evidence" not in private_text:
        raise FreshPersonalHoldoutRunnerError("private preregistration is missing challenger evidence")

    return {
        "private_manifest": str(private_path),
        "reviewer_packet": str(reviewer_path),
        "review_csv": str(csv_path),
        "private_manifest_sha256": hashlib.sha256(private_path.read_bytes()).hexdigest(),
        "reviewer_packet_sha256": hashlib.sha256(reviewer_path.read_bytes()).hexdigest(),
        "review_csv_sha256": hashlib.sha256(csv_path.read_bytes()).hexdigest(),
        "effective_case_count": str(len(cohort.effective_case_ids)),
        "fallback_case_count": str(len(selection.fallback_case_ids)),
        "preregistration_fingerprint": prereg_fingerprint,
    }


__all__ = [
    "FRESH_PERSONAL_HOLDOUT_RUNNER_VERSION",
    "FreshPersonalHoldoutRunnerError",
    "materialize_fresh_personal_holdout_r1",
]
