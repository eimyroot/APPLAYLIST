from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping

from core.intelligence.curated_real_library_review_contract import CuratedSetRole
from core.intelligence.meaningful_diversity_contract import (
    MeaningfulDiversityPolicy,
    MeaningfulDiversityStatus,
    TrackMusicalEvidence,
)
from core.intelligence.set_contract import (
    EligibleLibraryScope,
    EnergyControlPoint,
    EnergyTrajectory,
    PlaylistIntent,
    RangeBand,
    SetGoal,
    SetPhase,
    SetPhaseType,
)
from services.intelligence.meaningful_diversity import compare_meaningful_paths
from services.intelligence.real_library_pilot import (
    MaterializedCase,
    MaterializedTrackEvidence,
    RealLibraryPilotError,
    analyze_real_tracks,
    materialize_cases,
    private_runtime_manifest,
    reviewer_packet,
)

MEANINGFUL_REVIEW_GATE_VERSION = "real-library-meaningful-review-gate-r1"
MEANINGFUL_REVIEW_REPORT_SCHEMA = "applaylist-meaningful-diversity-style-energy-report-r1"
_REVIEW_ENERGY_TOLERANCE = 0.15

_ROLE_POLICY: dict[CuratedSetRole, tuple[SetGoal, SetPhaseType, float]] = {
    CuratedSetRole.OPENING: (SetGoal.WARM_UP, SetPhaseType.WARMUP, 0.52),
    CuratedSetRole.BUILD: (SetGoal.CLUB_FLOW, SetPhaseType.LIFT, 0.64),
    CuratedSetRole.MID_SET: (SetGoal.CLUB_FLOW, SetPhaseType.GROOVE, 0.72),
    CuratedSetRole.PEAK: (SetGoal.PEAK_TIME, SetPhaseType.PEAK, 0.86),
    CuratedSetRole.RESET: (SetGoal.STYLE_BRIDGE, SetPhaseType.AFTERGLOW, 0.62),
    CuratedSetRole.CLOSING: (SetGoal.CLOSING, SetPhaseType.CLOSING, 0.78),
}


def _load_json(path: str | Path) -> dict[str, Any]:
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise RealLibraryPilotError(f"input JSON not found: {source}")
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RealLibraryPilotError(f"cannot read input JSON: {source}") from exc
    if not isinstance(raw, dict):
        raise RealLibraryPilotError(f"input JSON must contain an object: {source}")
    return raw


def _case_specs(selection_raw: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    raw_specs = selection_raw.get("case_specs")
    if not isinstance(raw_specs, list) or not raw_specs:
        raise RealLibraryPilotError("curated selection requires case_specs")
    result: dict[str, Mapping[str, Any]] = {}
    for raw in raw_specs:
        if not isinstance(raw, Mapping):
            raise RealLibraryPilotError("curated case spec must be an object")
        case_id = str(raw.get("case_spec_id", "")).strip()
        if not case_id:
            raise RealLibraryPilotError("case_spec_id must not be empty")
        if case_id in result:
            raise RealLibraryPilotError(f"duplicate case_spec_id: {case_id}")
        result[case_id] = raw
    return result


def _evaluation_intent(
    *,
    case_id: str,
    role: CuratedSetRole,
    seed_genre: str | None,
) -> PlaylistIntent:
    goal, phase_type, target_energy = _ROLE_POLICY[role]
    normalized_seed_genre = str(seed_genre or "").strip().lower()
    style_targets = (
        ()
        if role is CuratedSetRole.RESET or not normalized_seed_genre
        else (normalized_seed_genre,)
    )
    phase = SetPhase(
        phase_id=f"phase:{case_id}",
        phase_type=phase_type,
        ordinal=0,
        target_fraction_start=0.0,
        target_fraction_end=1.0,
        explanation_label=f"meaningful-review-{role.value}",
        target_energy_band=RangeBand(
            max(0.0, target_energy - _REVIEW_ENERGY_TOLERANCE),
            min(1.0, target_energy + _REVIEW_ENERGY_TOLERANCE),
        ),
        style_targets=style_targets,
    )
    return PlaylistIntent(
        intent_id=f"meaningful-review-intent:{case_id}",
        intent_version=MEANINGFUL_REVIEW_GATE_VERSION,
        goal=goal,
        eligible_library_scope=EligibleLibraryScope(
            scope_revision=f"meaningful-review-scope:{case_id}",
        ),
        phase_plan=(phase,),
        energy_trajectory=EnergyTrajectory(
            trajectory_id=f"meaningful-review-energy:{case_id}",
            trajectory_version=MEANINGFUL_REVIEW_GATE_VERSION,
            control_points=(
                EnergyControlPoint(
                    0.0,
                    target_energy,
                    _REVIEW_ENERGY_TOLERANCE,
                    phase.phase_id,
                ),
                EnergyControlPoint(
                    1.0,
                    target_energy,
                    _REVIEW_ENERGY_TOLERANCE,
                    phase.phase_id,
                ),
            ),
        ),
        target_track_count=5,
    )


def _track_evidence(
    *,
    track_ids: tuple[str, ...],
    evidence: Mapping[str, MaterializedTrackEvidence],
) -> tuple[TrackMusicalEvidence, ...]:
    rows: list[TrackMusicalEvidence] = []
    for track_id in sorted(set(track_ids)):
        item = evidence.get(track_id)
        if item is None:
            raise RealLibraryPilotError(
                f"meaningful review missing materialized evidence for {track_id}"
            )
        genre = str(item.source.genre or "").strip().lower()
        refs = tuple(item.music_dna.identity.evidence_refs)
        if genre:
            refs = (*refs, f"library-genre:{track_id}")
        rows.append(
            TrackMusicalEvidence(
                track_id=track_id,
                style_tags=((genre,) if genre else None),
                energy=item.canonical.energy,
                evidence_refs=refs,
            )
        )
    return tuple(rows)


def evaluate_materialized_case_r1(
    *,
    materialized: MaterializedCase,
    seed_track_id: str,
    evidence: Mapping[str, MaterializedTrackEvidence],
    policy: MeaningfulDiversityPolicy = MeaningfulDiversityPolicy(),
) -> dict[str, Any]:
    if not materialized.greedy_result.alternatives:
        raise RealLibraryPilotError("greedy result has no alternative for meaningful review")
    if not materialized.beam_result.alternatives:
        raise RealLibraryPilotError("beam result has no alternative for meaningful review")
    seed = evidence.get(seed_track_id)
    if seed is None:
        raise RealLibraryPilotError(
            f"meaningful review seed evidence missing: {seed_track_id}"
        )

    greedy = materialized.greedy_result.alternatives[0]
    beam = materialized.beam_result.alternatives[0]
    track_ids = tuple(
        dict.fromkeys(
            (
                seed_track_id,
                *(step.track_id for step in greedy.added_steps),
                *(step.track_id for step in beam.added_steps),
            )
        )
    )
    musical_evidence = _track_evidence(track_ids=track_ids, evidence=evidence)
    evaluation_intent = _evaluation_intent(
        case_id=materialized.case.case_id,
        role=materialized.case.set_role,
        seed_genre=seed.source.genre,
    )
    greedy_coherence, beam_coherence, comparison = compare_meaningful_paths(
        reference=greedy,
        candidate=beam,
        intent=evaluation_intent,
        track_evidence=musical_evidence,
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
        "case_id": materialized.case.case_id,
        "set_role": materialized.case.set_role.value,
        "seed_track_id": seed_track_id,
        "seed_style_anchor": (
            None
            if materialized.case.set_role is CuratedSetRole.RESET
            else str(seed.source.genre or "").strip().lower() or None
        ),
        "greedy_result_id": materialized.greedy_result.result_id,
        "beam_result_id": materialized.beam_result.result_id,
        "greedy_path_id": greedy.path_id,
        "beam_path_id": beam.path_id,
        "policy": asdict(policy),
        "evaluation_energy_tolerance": _REVIEW_ENERGY_TOLERANCE,
        "greedy_coherence": asdict(greedy_coherence),
        "beam_coherence": asdict(beam_coherence),
        "comparison": asdict(comparison),
        "status": status.value,
        "activation_authorized": False,
    }


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def materialize_real_library_pilot_meaningful_r1(
    *,
    snapshot_path: str | Path,
    selection_path: str | Path,
    output_dir: str | Path,
    database_path: str | Path,
    generated_at: str,
    blinding_seed: str,
    analyzer=None,
    policy: MeaningfulDiversityPolicy = MeaningfulDiversityPolicy(),
) -> dict[str, str]:
    """Materialize a blind packet only if every case passes the R1 meaningful gate.

    This wrapper intentionally leaves the existing real-library materializer untouched.
    Historical R1/R2 evidence remains immutable. The gate evaluates already-produced
    greedy/beam source paths and never changes optimizer scores or ranks.
    """
    snapshot_raw = _load_json(snapshot_path)
    selection_raw = _load_json(selection_path)
    specs = _case_specs(selection_raw)
    evidence = analyze_real_tracks(
        snapshot_raw=snapshot_raw,
        selection_raw=selection_raw,
        analyzer=analyzer,
    )
    cases = materialize_cases(
        snapshot_raw=snapshot_raw,
        selection_raw=selection_raw,
        evidence=evidence,
        database_path=database_path,
        generated_at=generated_at,
        blinding_seed=blinding_seed,
    )

    evaluations: list[dict[str, Any]] = []
    for materialized in cases:
        spec = specs.get(materialized.case.case_id)
        if spec is None:
            raise RealLibraryPilotError(
                f"materialized case missing source spec: {materialized.case.case_id}"
            )
        seed_track_id = str(spec.get("seed_track_id", "")).strip()
        if not seed_track_id:
            raise RealLibraryPilotError("seed_track_id must not be empty")
        evaluations.append(
            evaluate_materialized_case_r1(
                materialized=materialized,
                seed_track_id=seed_track_id,
                evidence=evidence,
                policy=policy,
            )
        )

    output = Path(output_dir).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    report_path = output / "APPLAYLIST_MEANINGFUL_DIVERSITY_STYLE_ENERGY_R1_REPORT.json"
    private_path = output / "APPLAYLIST_REAL_LIBRARY_RUNTIME_EVIDENCE_R1.private.json"
    reviewer_path = output / "APPLAYLIST_BLINDED_HUMAN_DJ_REVIEW_PACKET_R1.json"
    for target in (report_path, private_path, reviewer_path):
        if target.exists() or target.is_symlink():
            raise RealLibraryPilotError(f"refusing to overwrite evidence artifact: {target}")

    failed = tuple(
        row for row in evaluations if row["status"] != MeaningfulDiversityStatus.SUFFICIENT.value
    )
    report = {
        "schema": MEANINGFUL_REVIEW_REPORT_SCHEMA,
        "gate_version": MEANINGFUL_REVIEW_GATE_VERSION,
        "generated_at": generated_at,
        "case_count": len(evaluations),
        "cases": evaluations,
        "all_cases_meaningfully_reviewable": not failed,
        "failed_case_ids": [row["case_id"] for row in failed],
        "optimizer_ranking_mutated": False,
        "transition_evidence_mutated": False,
        "cloud_audio_upload_authorized": False,
        "activation_authorized": False,
        "personal_dj_model_training_authorized": False,
    }
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )

    if failed:
        raise RealLibraryPilotError(
            "meaningful diversity/style-energy gate failed; reviewer packet withheld; "
            f"report={report_path}"
        )

    private_payload = private_runtime_manifest(
        snapshot_raw=snapshot_raw,
        evidence=evidence,
        cases=cases,
        generated_at=generated_at,
    )
    reviewer_payload = reviewer_packet(
        snapshot_raw=snapshot_raw,
        evidence=evidence,
        cases=cases,
        generated_at=generated_at,
    )
    private_path.write_text(
        json.dumps(private_payload, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )
    reviewer_path.write_text(
        json.dumps(reviewer_payload, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )
    return {
        "meaningful_review_report": str(report_path),
        "meaningful_review_report_sha256": _sha256(report_path),
        "private_runtime_manifest": str(private_path),
        "private_runtime_manifest_sha256": _sha256(private_path),
        "blind_reviewer_packet": str(reviewer_path),
        "blind_reviewer_packet_sha256": _sha256(reviewer_path),
    }


__all__ = [
    "MEANINGFUL_REVIEW_GATE_VERSION",
    "MEANINGFUL_REVIEW_REPORT_SCHEMA",
    "evaluate_materialized_case_r1",
    "materialize_real_library_pilot_meaningful_r1",
]
