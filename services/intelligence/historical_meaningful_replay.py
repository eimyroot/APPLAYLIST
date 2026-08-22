from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping

from core.intelligence.curated_real_library_review_contract import CuratedSetRole
from core.intelligence.meaningful_diversity_contract import (
    MeaningfulDiversityPolicy,
    MeaningfulDiversityStatus,
    TrackMusicalEvidence,
)
from core.intelligence.set_contract import SequenceState, SetStep
from core.intelligence.set_optimizer_contract import SetPathAlternative, SetPathObjective
from services.intelligence.meaningful_diversity import compare_meaningful_paths
from services.intelligence.real_library_meaningful_review import _evaluation_intent
from services.intelligence.real_library_pilot import (
    PRIVATE_RUNTIME_EVIDENCE_SCHEMA,
    RealLibraryPilotError,
)

HISTORICAL_MEANINGFUL_REPLAY_SCHEMA = "applaylist-historical-meaningful-replay-r1"
HISTORICAL_MEANINGFUL_REPLAY_VERSION = "historical-meaningful-replay-r1"
_SNAPSHOT_SCHEMA = "applaylist-local-library-snapshot-r1"
_SELECTION_SCHEMA = "applaylist-curated-case-selection-r1"


def _load_json(path: str | Path, *, field_name: str) -> tuple[Path, dict[str, Any]]:
    source = Path(path).expanduser()
    if source.is_symlink():
        raise RealLibraryPilotError(f"{field_name} must not be a symlink: {source}")
    if not source.is_file():
        raise RealLibraryPilotError(f"{field_name} not found: {source}")
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RealLibraryPilotError(f"cannot read {field_name}: {source}") from exc
    if not isinstance(raw, dict):
        raise RealLibraryPilotError(f"{field_name} must contain a JSON object")
    return source, raw


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _non_empty(value: Any, field_name: str) -> str:
    text = str(value).strip()
    if not text:
        raise RealLibraryPilotError(f"{field_name} must not be empty")
    return text


def _unit_or_none(value: Any, field_name: str) -> float | None:
    if value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise RealLibraryPilotError(f"{field_name} must be numeric") from exc
    if not math.isfinite(numeric) or not 0.0 <= numeric <= 1.0:
        raise RealLibraryPilotError(f"{field_name} must be between 0 and 1")
    return numeric


def _positive(value: Any, field_name: str) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise RealLibraryPilotError(f"{field_name} must be numeric") from exc
    if not math.isfinite(numeric) or numeric <= 0.0:
        raise RealLibraryPilotError(f"{field_name} must be positive")
    return numeric


def _snapshot_tracks(snapshot: Mapping[str, Any]) -> tuple[tuple[str, str], dict[str, Mapping[str, Any]]]:
    if snapshot.get("schema") != _SNAPSHOT_SCHEMA:
        raise RealLibraryPilotError("unsupported local-library snapshot schema")
    snapshot_ref = (
        _non_empty(snapshot.get("snapshot_id"), "snapshot_id"),
        _non_empty(snapshot.get("snapshot_version"), "snapshot_version"),
    )
    privacy = snapshot.get("privacy") or {}
    if privacy.get("publishable_to_public_repo") is not False:
        raise RealLibraryPilotError("historical replay requires private real-library snapshot evidence")
    raw_tracks = snapshot.get("tracks")
    if not isinstance(raw_tracks, list) or not raw_tracks:
        raise RealLibraryPilotError("snapshot tracks must be a non-empty array")
    tracks: dict[str, Mapping[str, Any]] = {}
    for raw in raw_tracks:
        if not isinstance(raw, Mapping):
            raise RealLibraryPilotError("snapshot track must be an object")
        track_id = _non_empty(raw.get("track_id"), "snapshot.track_id")
        if track_id in tracks:
            raise RealLibraryPilotError(f"duplicate snapshot track_id: {track_id}")
        tracks[track_id] = raw
    return snapshot_ref, tracks


def _selection_specs(
    selection: Mapping[str, Any],
    *,
    snapshot_ref: tuple[str, str],
) -> dict[str, Mapping[str, Any]]:
    if selection.get("schema") != _SELECTION_SCHEMA:
        raise RealLibraryPilotError("unsupported curated-case selection schema")
    raw_ref = tuple(str(item) for item in (selection.get("snapshot_ref") or ()))
    if raw_ref != snapshot_ref:
        raise RealLibraryPilotError("selection snapshot_ref does not match snapshot")
    raw_specs = selection.get("case_specs")
    if not isinstance(raw_specs, list) or not raw_specs:
        raise RealLibraryPilotError("curated selection requires case_specs")
    specs: dict[str, Mapping[str, Any]] = {}
    for raw in raw_specs:
        if not isinstance(raw, Mapping):
            raise RealLibraryPilotError("curated case spec must be an object")
        case_id = _non_empty(raw.get("case_spec_id"), "case_spec_id")
        if case_id in specs:
            raise RealLibraryPilotError(f"duplicate case_spec_id: {case_id}")
        specs[case_id] = raw
    return specs


def _private_tracks(
    private: Mapping[str, Any],
    *,
    snapshot_ref: tuple[str, str],
) -> dict[str, Mapping[str, Any]]:
    if private.get("schema") != PRIVATE_RUNTIME_EVIDENCE_SCHEMA:
        raise RealLibraryPilotError("unsupported private runtime evidence schema")
    private_ref = tuple(str(item) for item in (private.get("snapshot_ref") or ()))
    if private_ref != snapshot_ref:
        raise RealLibraryPilotError("private manifest snapshot_ref does not match snapshot")
    privacy = private.get("privacy") or {}
    if privacy.get("contains_local_absolute_paths") is not True:
        raise RealLibraryPilotError("private runtime evidence privacy contract is invalid")
    if privacy.get("publishable_to_public_repo") is not False:
        raise RealLibraryPilotError("private runtime evidence must remain non-publishable")
    rows = private.get("tracks")
    if not isinstance(rows, list) or not rows:
        raise RealLibraryPilotError("private runtime evidence tracks must be non-empty")
    tracks: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise RealLibraryPilotError("private track evidence must be an object")
        track_id = _non_empty(row.get("track_id"), "private.track_id")
        if track_id in tracks:
            raise RealLibraryPilotError(f"duplicate private track_id: {track_id}")
        _positive(row.get("duration_seconds"), f"private.duration_seconds:{track_id}")
        _unit_or_none(row.get("energy"), f"private.energy:{track_id}")
        tracks[track_id] = row
    return tracks


def _private_cases(private: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    rows = private.get("cases")
    if not isinstance(rows, list) or not rows:
        raise RealLibraryPilotError("private runtime evidence cases must be non-empty")
    cases: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise RealLibraryPilotError("private case evidence must be an object")
        case = row.get("case")
        if not isinstance(case, Mapping):
            raise RealLibraryPilotError("private case evidence requires case object")
        case_id = _non_empty(case.get("case_id"), "private.case_id")
        if case_id in cases:
            raise RealLibraryPilotError(f"duplicate private case_id: {case_id}")
        cases[case_id] = row
    return cases


def _plan(case: Mapping[str, Any], field_name: str, expected_strategy: str) -> Mapping[str, Any]:
    raw = case.get(field_name)
    if not isinstance(raw, Mapping):
        raise RealLibraryPilotError(f"historical case requires {field_name}")
    if str(raw.get("strategy", "")).strip() != expected_strategy:
        raise RealLibraryPilotError(f"{field_name} strategy mismatch")
    _non_empty(raw.get("plan_id"), f"{field_name}.plan_id")
    _non_empty(raw.get("result_id"), f"{field_name}.result_id")
    _non_empty(raw.get("path_id"), f"{field_name}.path_id")
    tracks = raw.get("ordered_track_ids")
    transitions = raw.get("transition_ids")
    if not isinstance(tracks, list) or len(tracks) < 2:
        raise RealLibraryPilotError(f"{field_name}.ordered_track_ids requires seed + added tracks")
    if not isinstance(transitions, list) or len(transitions) != len(tracks) - 1:
        raise RealLibraryPilotError(f"{field_name} transition count must equal added track count")
    return raw


def _historical_path_view(
    *,
    case_id: str,
    plan: Mapping[str, Any],
    private_tracks: Mapping[str, Mapping[str, Any]],
) -> SetPathAlternative:
    ordered = tuple(_non_empty(item, "ordered_track_id") for item in plan["ordered_track_ids"])
    transitions = tuple(_non_empty(item, "transition_id") for item in plan["transition_ids"])
    phase_id = f"phase:{case_id}"
    root_id = ordered[0]
    if root_id not in private_tracks:
        raise RealLibraryPilotError(f"historical plan references unknown seed track: {root_id}")
    root = SetStep(
        order_index=0,
        track_id=root_id,
        segment_id=f"{root_id}:whole",
        phase_id=phase_id,
        evidence_refs=("historical-replay-root",),
    )
    added = tuple(
        SetStep(
            order_index=index,
            track_id=track_id,
            segment_id=f"{track_id}:whole",
            phase_id=phase_id,
            incoming_transition_id=transitions[index - 1],
            local_projection_score=1.0,
            explanation_codes=("historical-evidence-replay-view",),
            evidence_refs=(f"historical-plan:{plan['plan_id']}",),
        )
        for index, track_id in enumerate(ordered[1:], start=1)
    )
    for track_id in ordered:
        if track_id not in private_tracks:
            raise RealLibraryPilotError(f"historical plan references unknown private track: {track_id}")
    selected = (root, *added)
    duration = sum(_positive(private_tracks[item]["duration_seconds"], f"duration:{item}") for item in ordered)
    current_energy = _unit_or_none(private_tracks[ordered[-1]].get("energy"), "current_energy_state")
    state = SequenceState(
        state_id=f"historical-replay:{case_id}:{plan['path_id']}",
        state_version=HISTORICAL_MEANINGFUL_REPLAY_VERSION,
        selected_steps=selected,
        current_track_id=ordered[-1],
        current_segment_id=f"{ordered[-1]}:whole",
        used_track_ids=ordered,
        cumulative_duration_seconds=duration,
        current_energy_state=current_energy,
        evidence_refs=(f"source-result:{plan['result_id']}", f"source-plan:{plan['plan_id']}"),
    )
    return SetPathAlternative(
        path_id=_non_empty(plan.get("path_id"), "path_id"),
        rank=1,
        added_steps=added,
        resulting_state=state,
        transition_ids=transitions,
        candidate_scores=tuple(1.0 for _ in added),
        objective=SetPathObjective(
            depth=len(added),
            mean_candidate_score=1.0,
            minimum_candidate_score=1.0,
            required_track_completion=1.0,
            remaining_required_count=0,
            target_reached=True,
        ),
        explanation_codes=("historical-evidence-replay-view-only",),
        evidence_refs=(f"source-result:{plan['result_id']}", f"source-plan:{plan['plan_id']}"),
    )


def _track_evidence(
    *,
    track_ids: tuple[str, ...],
    snapshot_tracks: Mapping[str, Mapping[str, Any]],
    private_tracks: Mapping[str, Mapping[str, Any]],
) -> tuple[TrackMusicalEvidence, ...]:
    result: list[TrackMusicalEvidence] = []
    for track_id in sorted(set(track_ids)):
        snapshot = snapshot_tracks.get(track_id)
        private = private_tracks.get(track_id)
        if snapshot is None or private is None:
            raise RealLibraryPilotError(f"replay track binding missing: {track_id}")
        genre = str(snapshot.get("genre") or "").strip().lower()
        energy = _unit_or_none(private.get("energy"), f"private.energy:{track_id}")
        analysis_revision = _non_empty(private.get("analysis_revision"), f"analysis_revision:{track_id}")
        result.append(
            TrackMusicalEvidence(
                track_id=track_id,
                style_tags=((genre,) if genre else None),
                energy=energy,
                evidence_refs=(
                    f"snapshot-genre:{track_id}",
                    f"historical-analysis:{analysis_revision}",
                ),
            )
        )
    return tuple(result)


def _evaluate_case(
    *,
    case_id: str,
    spec: Mapping[str, Any],
    private_row: Mapping[str, Any],
    snapshot_ref: tuple[str, str],
    snapshot_tracks: Mapping[str, Mapping[str, Any]],
    private_tracks: Mapping[str, Mapping[str, Any]],
    policy: MeaningfulDiversityPolicy,
) -> dict[str, Any]:
    case = private_row["case"]
    if tuple(str(item) for item in (case.get("snapshot_ref") or ())) != snapshot_ref:
        raise RealLibraryPilotError(f"case snapshot_ref mismatch: {case_id}")
    if not bool(case.get("engineering_acceptance_passed")):
        raise RealLibraryPilotError(f"case lacks engineering acceptance: {case_id}")
    role_raw = _non_empty(case.get("set_role"), f"set_role:{case_id}")
    if role_raw != _non_empty(spec.get("set_role"), f"selection.set_role:{case_id}"):
        raise RealLibraryPilotError(f"case set_role mismatch: {case_id}")
    try:
        role = CuratedSetRole(role_raw)
    except ValueError as exc:
        raise RealLibraryPilotError(f"unsupported set_role: {role_raw}") from exc
    seed_id = _non_empty(spec.get("seed_track_id"), f"seed_track_id:{case_id}")
    greedy_plan = _plan(case, "greedy_plan", "greedy_recommend_next")
    beam_plan = _plan(case, "beam_plan", "bounded_beam")
    if greedy_plan["ordered_track_ids"][0] != seed_id or beam_plan["ordered_track_ids"][0] != seed_id:
        raise RealLibraryPilotError(f"historical plan seed mismatch: {case_id}")
    if private_row.get("greedy_result_id") != greedy_plan.get("result_id"):
        raise RealLibraryPilotError(f"greedy result binding mismatch: {case_id}")
    if private_row.get("beam_result_id") != beam_plan.get("result_id"):
        raise RealLibraryPilotError(f"beam result binding mismatch: {case_id}")
    assignment = private_row.get("assignment")
    if not isinstance(assignment, Mapping) or assignment.get("algorithm_identity_hidden") is not True:
        raise RealLibraryPilotError(f"historical blind assignment integrity missing: {case_id}")

    greedy = _historical_path_view(case_id=case_id, plan=greedy_plan, private_tracks=private_tracks)
    beam = _historical_path_view(case_id=case_id, plan=beam_plan, private_tracks=private_tracks)
    track_ids = tuple(dict.fromkeys((*greedy.resulting_state.used_track_ids, *beam.resulting_state.used_track_ids)))
    evidence = _track_evidence(
        track_ids=track_ids,
        snapshot_tracks=snapshot_tracks,
        private_tracks=private_tracks,
    )
    seed_snapshot = snapshot_tracks.get(seed_id)
    if seed_snapshot is None:
        raise RealLibraryPilotError(f"seed missing from snapshot: {seed_id}")
    intent = _evaluation_intent(
        case_id=case_id,
        role=role,
        seed_genre=seed_snapshot.get("genre"),
    )
    greedy_coherence, beam_coherence, comparison = compare_meaningful_paths(
        reference=greedy,
        candidate=beam,
        intent=intent,
        track_evidence=evidence,
        policy=policy,
    )
    missing = bool(
        greedy_coherence.missing_style_track_ids
        or greedy_coherence.missing_energy_track_ids
        or beam_coherence.missing_style_track_ids
        or beam_coherence.missing_energy_track_ids
    )
    if missing:
        status = MeaningfulDiversityStatus.NOT_PROVEN_MISSING_EVIDENCE
    elif comparison.meaningful:
        status = MeaningfulDiversityStatus.SUFFICIENT
    else:
        status = MeaningfulDiversityStatus.INSUFFICIENT_MEANINGFUL_DIVERSITY
    return {
        "case_id": case_id,
        "set_role": role.value,
        "seed_track_id": seed_id,
        "source_scenario_fingerprint": case.get("scenario_fingerprint"),
        "source_greedy_plan_id": greedy_plan.get("plan_id"),
        "source_beam_plan_id": beam_plan.get("plan_id"),
        "source_greedy_result_id": greedy_plan.get("result_id"),
        "source_beam_result_id": beam_plan.get("result_id"),
        "source_greedy_path_id": greedy_plan.get("path_id"),
        "source_beam_path_id": beam_plan.get("path_id"),
        "greedy_coherence": asdict(greedy_coherence),
        "beam_coherence": asdict(beam_coherence),
        "comparison": asdict(comparison),
        "status": status.value,
        "historical_evidence_replayed": True,
        "audio_read": False,
        "mir_provider_called": False,
        "optimizer_ranking_mutated": False,
        "activation_authorized": False,
    }


def replay_historical_meaningful_review_r1(
    *,
    snapshot_path: str | Path,
    selection_path: str | Path,
    private_manifest_path: str | Path,
    output_path: str | Path,
    generated_at: str,
    policy: MeaningfulDiversityPolicy = MeaningfulDiversityPolicy(),
) -> dict[str, str]:
    snapshot_source, snapshot = _load_json(snapshot_path, field_name="snapshot")
    selection_source, selection = _load_json(selection_path, field_name="selection")
    private_source, private = _load_json(private_manifest_path, field_name="private manifest")
    snapshot_ref, snapshot_tracks = _snapshot_tracks(snapshot)
    specs = _selection_specs(selection, snapshot_ref=snapshot_ref)
    private_tracks = _private_tracks(private, snapshot_ref=snapshot_ref)
    private_cases = _private_cases(private)
    if set(private_cases) != set(specs):
        raise RealLibraryPilotError("private case ids do not exactly match curated selection")

    output = Path(output_path).expanduser()
    if output.exists() or output.is_symlink():
        raise RealLibraryPilotError(f"refusing to overwrite replay artifact: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)

    cases = tuple(
        _evaluate_case(
            case_id=case_id,
            spec=specs[case_id],
            private_row=private_cases[case_id],
            snapshot_ref=snapshot_ref,
            snapshot_tracks=snapshot_tracks,
            private_tracks=private_tracks,
            policy=policy,
        )
        for case_id in sorted(specs)
    )
    failed = tuple(item for item in cases if item["status"] != MeaningfulDiversityStatus.SUFFICIENT.value)
    report = {
        "schema": HISTORICAL_MEANINGFUL_REPLAY_SCHEMA,
        "replay_version": HISTORICAL_MEANINGFUL_REPLAY_VERSION,
        "generated_at": _non_empty(generated_at, "generated_at"),
        "snapshot_ref": list(snapshot_ref),
        "input_sha256": {
            "snapshot": _sha256(snapshot_source),
            "selection": _sha256(selection_source),
            "private_manifest": _sha256(private_source),
        },
        "policy": asdict(policy),
        "case_count": len(cases),
        "cases": list(cases),
        "all_cases_meaningfully_reviewable": not failed,
        "failed_case_ids": [item["case_id"] for item in failed],
        "source_audio_read": False,
        "mir_provider_called": False,
        "transition_evidence_mutated": False,
        "optimizer_ranking_mutated": False,
        "historical_evidence_mutated": False,
        "reviewer_packet_regenerated": False,
        "cloud_audio_upload_authorized": False,
        "activation_authorized": False,
        "personal_dj_model_training_authorized": False,
    }
    output.write_text(json.dumps(report, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    return {
        "historical_meaningful_replay_report": str(output),
        "historical_meaningful_replay_report_sha256": _sha256(output),
    }


__all__ = [
    "HISTORICAL_MEANINGFUL_REPLAY_SCHEMA",
    "HISTORICAL_MEANINGFUL_REPLAY_VERSION",
    "replay_historical_meaningful_review_r1",
]
