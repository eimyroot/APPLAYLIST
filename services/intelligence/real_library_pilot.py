from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from core.analysis.provider_contract import CanonicalAnalysisResult, normalize_provider_result
from core.config.settings import get_settings
from core.intelligence.curated_real_library_review_contract import (
    CURATED_REAL_LIBRARY_BENCHMARK_VERSION,
    BlindedPlanAssignment,
    CuratedLibrarySnapshot,
    CuratedReviewCase,
    CuratedSetRole,
    ReviewPlanStrategy,
)
from core.intelligence.music_dna import MusicDNARevision, build_music_dna
from core.intelligence.set_contract import (
    EligibleLibraryScope,
    EnergyControlPoint,
    EnergyTrajectory,
    PlaylistContext,
    PlaylistIntent,
    SequenceState,
    SetGoal,
    SetPhase,
    SetPhaseType,
    SetStep,
)
from core.intelligence.set_optimizer_contract import SetOptimizerPolicy, SetOptimizerResult
from data.repositories.music_intelligence_repository import MusicIntelligenceRepository
from services.analysis.librosa_baseline import BaselineLibrosaMIR
from services.intelligence.curated_real_library_review import (
    build_blinded_plan_assignment,
    reviewable_plan_from_alternative,
)
from services.intelligence.phase_context import transition_context_for_phase
from services.intelligence.set_engine import balanced_set_ranking_policy_v1
from services.intelligence.set_optimizer_benchmark import greedy_recommend_next_policy_v1
from services.intelligence.set_path_optimizer import optimize_set_lookahead
from services.intelligence.transition_engine import assess_transition, preserve_groove_context_v1

REAL_LIBRARY_MATERIALIZER_VERSION = "real-library-evidence-materializer-r1"
PRIVATE_RUNTIME_EVIDENCE_SCHEMA = "applaylist-private-runtime-music-evidence-r1"
BLIND_REVIEW_PACKET_SCHEMA = "applaylist-blind-human-dj-review-packet-r1"


class RealLibraryPilotError(RuntimeError):
    """Fail-closed error while materializing real-library pilot evidence."""


@dataclass(frozen=True, slots=True)
class RealLibraryTrackInput:
    track_id: str
    absolute_path: str
    file_signature: str
    display_name: str
    artist: str
    genre: str | None
    snapshot_energy: float | None


@dataclass(frozen=True, slots=True)
class MaterializedTrackEvidence:
    source: RealLibraryTrackInput
    content_sha256: str
    canonical: CanonicalAnalysisResult
    music_dna: MusicDNARevision


@dataclass(frozen=True, slots=True)
class MaterializedCase:
    case: CuratedReviewCase
    assignment: BlindedPlanAssignment
    greedy_result: SetOptimizerResult
    beam_result: SetOptimizerResult


_ROLE_POLICY: dict[CuratedSetRole, tuple[SetGoal, SetPhaseType, float]] = {
    CuratedSetRole.OPENING: (SetGoal.WARM_UP, SetPhaseType.WARMUP, 0.52),
    CuratedSetRole.BUILD: (SetGoal.CLUB_FLOW, SetPhaseType.LIFT, 0.64),
    CuratedSetRole.MID_SET: (SetGoal.CLUB_FLOW, SetPhaseType.GROOVE, 0.72),
    CuratedSetRole.PEAK: (SetGoal.PEAK_TIME, SetPhaseType.PEAK, 0.86),
    CuratedSetRole.RESET: (SetGoal.STYLE_BRIDGE, SetPhaseType.AFTERGLOW, 0.62),
    CuratedSetRole.CLOSING: (SetGoal.CLOSING, SetPhaseType.CLOSING, 0.78),
}


def _non_empty(value: Any, field_name: str) -> str:
    text = str(value).strip()
    if not text:
        raise RealLibraryPilotError(f"{field_name} must not be empty")
    return text


def _sha256_json(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _sha256_file(path: str | Path, *, chunk_size: int = 1024 * 1024) -> str:
    """Return SHA-256 calculated from the actual local file bytes."""
    source = Path(path)
    if not source.is_file():
        raise RealLibraryPilotError(f"audio file not found: {source}")
    digest = hashlib.sha256()
    try:
        with source.open("rb") as handle:
            for chunk in iter(lambda: handle.read(chunk_size), b""):
                digest.update(chunk)
    except OSError as exc:
        raise RealLibraryPilotError(f"cannot read audio file for hashing: {source}") from exc
    return digest.hexdigest()


def _load_json(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    if not source.is_file():
        raise RealLibraryPilotError(f"input JSON not found: {source}")
    raw = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise RealLibraryPilotError(f"input JSON must contain an object: {source}")
    return raw


def _track_inputs(snapshot_raw: Mapping[str, Any]) -> dict[str, RealLibraryTrackInput]:
    tracks_raw = snapshot_raw.get("tracks")
    if not isinstance(tracks_raw, list) or not tracks_raw:
        raise RealLibraryPilotError("snapshot tracks must be a non-empty array")
    tracks: dict[str, RealLibraryTrackInput] = {}
    for raw in tracks_raw:
        if not isinstance(raw, Mapping):
            raise RealLibraryPilotError("snapshot track must be an object")
        track_id = _non_empty(raw.get("track_id"), "track_id")
        if track_id in tracks:
            raise RealLibraryPilotError(f"duplicate snapshot track_id: {track_id}")
        tracks[track_id] = RealLibraryTrackInput(
            track_id=track_id,
            absolute_path=_non_empty(raw.get("absolute_path"), "absolute_path"),
            file_signature=_non_empty(raw.get("file_signature"), "file_signature"),
            display_name=_non_empty(raw.get("display_name"), "display_name"),
            artist=_non_empty(raw.get("artist"), "artist"),
            genre=(str(raw.get("genre")).strip() if raw.get("genre") else None),
            snapshot_energy=(
                float(raw["energy"]) / 10.0 if raw.get("energy") is not None else None
            ),
        )
    return tracks


def _validate_snapshot(snapshot_raw: Mapping[str, Any]) -> CuratedLibrarySnapshot:
    if snapshot_raw.get("schema") != "applaylist-local-library-snapshot-r1":
        raise RealLibraryPilotError("unsupported local-library snapshot schema")
    scope = snapshot_raw.get("scope") or {}
    privacy = snapshot_raw.get("privacy") or {}
    if scope.get("kind") != "REAL_INVENTORY_BACKED_SUBSET":
        raise RealLibraryPilotError("R1 pilot requires a real inventory-backed snapshot")
    if privacy.get("publishable_to_public_repo") is not False:
        raise RealLibraryPilotError("real-library snapshot must remain private evidence")
    tracks = _track_inputs(snapshot_raw)
    return CuratedLibrarySnapshot(
        snapshot_id=_non_empty(snapshot_raw.get("snapshot_id"), "snapshot_id"),
        snapshot_version=_non_empty(snapshot_raw.get("snapshot_version"), "snapshot_version"),
        library_fingerprint=_non_empty(
            snapshot_raw.get("library_fingerprint"), "library_fingerprint"
        ),
        track_ids=tuple(sorted(tracks)),
        generated_at=_non_empty(snapshot_raw.get("created_date"), "created_date"),
        evidence_refs=("real_inventory_backed_subset",),
    )


def _case_specs(selection_raw: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    if selection_raw.get("schema") != "applaylist-curated-case-selection-r1":
        raise RealLibraryPilotError("unsupported curated-case selection schema")
    raw_specs = selection_raw.get("case_specs")
    if not isinstance(raw_specs, list) or not raw_specs:
        raise RealLibraryPilotError("curated selection requires case_specs")
    ids: set[str] = set()
    specs: list[Mapping[str, Any]] = []
    for raw in raw_specs:
        if not isinstance(raw, Mapping):
            raise RealLibraryPilotError("curated case spec must be an object")
        case_id = _non_empty(raw.get("case_spec_id"), "case_spec_id")
        if case_id in ids:
            raise RealLibraryPilotError(f"duplicate case_spec_id: {case_id}")
        ids.add(case_id)
        specs.append(raw)
    return tuple(specs)


def required_track_ids(selection_raw: Mapping[str, Any]) -> tuple[str, ...]:
    values: set[str] = set()
    for case in _case_specs(selection_raw):
        values.add(_non_empty(case.get("seed_track_id"), "seed_track_id"))
        scope = case.get("candidate_scope_track_ids")
        if not isinstance(scope, list) or not scope:
            raise RealLibraryPilotError("candidate_scope_track_ids must be a non-empty array")
        values.update(_non_empty(item, "candidate_scope_track_id") for item in scope)
    return tuple(sorted(values))


def _analysis_revision(
    track: RealLibraryTrackInput,
    canonical: CanonicalAnalysisResult,
    content_sha256: str,
) -> str:
    material = {
        "materializer": REAL_LIBRARY_MATERIALIZER_VERSION,
        "inventory_file_signature": track.file_signature,
        "content_sha256": content_sha256,
        "provider": canonical.provider,
        "provider_version": canonical.provider_version,
        "algorithm_version": canonical.algorithm_version,
        "duration_seconds": canonical.duration_seconds,
        "bpm": canonical.bpm,
        "camelot": canonical.camelot,
        "energy": canonical.energy,
    }
    return "analysis:" + _sha256_json(material)[:32]


def analyze_real_tracks(
    *,
    snapshot_raw: Mapping[str, Any],
    selection_raw: Mapping[str, Any],
    analyzer: BaselineLibrosaMIR | None = None,
) -> dict[str, MaterializedTrackEvidence]:
    """Decode actual selected audio and build path-free Music DNA evidence.

    Snapshot BPM/key/energy and the audit's opaque File Signature remain provenance
    metadata only. Runtime content identity is SHA-256 computed from the actual bytes.
    Provider failure never falls back to spreadsheet metadata.
    """
    _validate_snapshot(snapshot_raw)
    tracks = _track_inputs(snapshot_raw)
    selected_ids = required_track_ids(selection_raw)
    missing = tuple(track_id for track_id in selected_ids if track_id not in tracks)
    if missing:
        raise RealLibraryPilotError(f"curated selection references unknown tracks: {missing}")

    provider = analyzer or BaselineLibrosaMIR()
    evidence: dict[str, MaterializedTrackEvidence] = {}
    for track_id in selected_ids:
        track = tracks[track_id]
        content_sha256 = _sha256_file(track.absolute_path)
        raw = provider.analyze(track.absolute_path)
        canonical = normalize_provider_result(
            raw,
            path=track.absolute_path,
            expected_provider=provider.provider_name,
        )
        if canonical.duration_seconds is None or canonical.duration_seconds <= 0.0:
            raise RealLibraryPilotError(f"positive duration evidence missing for {track_id}")
        revision = _analysis_revision(track, canonical, content_sha256)
        evidence_id = f"evidence:{track_id}:{revision.split(':', 1)[1]}"
        content_identity = f"sha256:{content_sha256}"
        dna = build_music_dna(
            track_id=track_id,
            content_identity=content_identity,
            analysis_revision=revision,
            evidence_id=evidence_id,
            input_identity=content_identity,
            canonical=canonical,
            rhythmic_structure=None,
            benchmark_status="real-library-pilot-r1-candidate",
        )
        evidence[track_id] = MaterializedTrackEvidence(
            source=track,
            content_sha256=content_sha256,
            canonical=canonical,
            music_dna=dna,
        )
    return evidence


def _role(raw: Mapping[str, Any]) -> CuratedSetRole:
    try:
        return CuratedSetRole(str(raw.get("set_role", "")).strip().lower())
    except ValueError as exc:
        raise RealLibraryPilotError(f"unknown curated set role: {raw.get('set_role')}") from exc


def _phase_for_case(case_id: str, role: CuratedSetRole) -> SetPhase:
    _, phase_type, _ = _ROLE_POLICY[role]
    return SetPhase(
        phase_id=f"phase:{case_id}",
        phase_type=phase_type,
        ordinal=0,
        target_fraction_start=0.0,
        target_fraction_end=1.0,
        explanation_label=f"real-library-{role.value}",
    )


def _intent_for_case(
    *,
    case_id: str,
    role: CuratedSetRole,
    seed_track_id: str,
    candidate_track_ids: Sequence[str],
) -> PlaylistIntent:
    goal, _, target_energy = _ROLE_POLICY[role]
    phase = _phase_for_case(case_id, role)
    scope = tuple(dict.fromkeys((seed_track_id, *candidate_track_ids)))
    return PlaylistIntent(
        intent_id=f"intent:{case_id}",
        intent_version=REAL_LIBRARY_MATERIALIZER_VERSION,
        goal=goal,
        eligible_library_scope=EligibleLibraryScope(
            scope_revision=f"scope:{case_id}:r1",
            explicit_track_ids=scope,
        ),
        phase_plan=(phase,),
        energy_trajectory=EnergyTrajectory(
            trajectory_id=f"energy:{case_id}",
            trajectory_version=REAL_LIBRARY_MATERIALIZER_VERSION,
            control_points=(
                EnergyControlPoint(0.0, target_energy, 0.35, phase.phase_id),
                EnergyControlPoint(1.0, target_energy, 0.35, phase.phase_id),
            ),
        ),
        target_track_count=5,
    )


def _state_for_case(
    *,
    case_id: str,
    seed: MaterializedTrackEvidence,
    phase: SetPhase,
) -> SequenceState:
    evidence_ref = seed.music_dna.identity.evidence_refs[0]
    duration = seed.canonical.duration_seconds
    if duration is None or duration <= 0.0:
        raise RealLibraryPilotError("seed duration evidence must be positive")
    return SequenceState(
        state_id=f"state:{case_id}",
        state_version=REAL_LIBRARY_MATERIALIZER_VERSION,
        selected_steps=(
            SetStep(
                order_index=0,
                track_id=seed.source.track_id,
                segment_id=f"{seed.source.track_id}:whole",
                phase_id=phase.phase_id,
                evidence_refs=(evidence_ref,),
            ),
        ),
        current_track_id=seed.source.track_id,
        current_segment_id=f"{seed.source.track_id}:whole",
        used_track_ids=(seed.source.track_id,),
        cumulative_duration_seconds=float(duration),
        current_energy_state=seed.canonical.energy,
        evidence_refs=(evidence_ref,),
    )


def _playlist_context(
    case_id: str,
    state: SequenceState,
    phase: SetPhase,
) -> PlaylistContext:
    return PlaylistContext(
        context_id=f"playlist-context:{case_id}",
        context_version=REAL_LIBRARY_MATERIALIZER_VERSION,
        current_phase_id=phase.phase_id,
        current_position_index=0,
        elapsed_duration_seconds=state.cumulative_duration_seconds,
        phase_progress=0.0,
        current_track_id=state.current_track_id,
        current_segment_id=state.current_segment_id,
        current_energy_state=state.current_energy_state,
        remaining_track_count=4,
        context_evidence_refs=state.evidence_refs,
    )


def _prepare_database(database_path: str | Path) -> None:
    db = Path(database_path).expanduser().resolve()
    db.parent.mkdir(parents=True, exist_ok=True)
    os.environ["DATABASE_URL"] = f"sqlite:///{db}"
    get_settings.cache_clear()


def _persist_case_adjacency(
    *,
    repository: MusicIntelligenceRepository,
    evidence: Mapping[str, MaterializedTrackEvidence],
    phase: SetPhase,
    track_ids: Sequence[str],
    generated_at: str,
) -> int:
    context = transition_context_for_phase(
        phase=phase,
        base_context=preserve_groove_context_v1(),
    )
    persisted = 0
    unique_ids = tuple(dict.fromkeys(track_ids))
    for source_id in unique_ids:
        for target_id in unique_ids:
            if source_id == target_id:
                continue
            assessment = assess_transition(
                source=evidence[source_id].music_dna,
                source_segment_id=f"{source_id}:whole",
                target=evidence[target_id].music_dna,
                target_segment_id=f"{target_id}:whole",
                context=context,
                created_at=generated_at,
            )
            repository.append_transition_assessment(assessment)
            persisted += 1
    return persisted


def _run_optimizer_pair(
    *,
    repository: MusicIntelligenceRepository,
    intent: PlaylistIntent,
    root_context: PlaylistContext,
    root_state: SequenceState,
    durations: Mapping[str, float],
    generated_at: str,
) -> tuple[SetOptimizerResult, SetOptimizerResult]:
    beam_policy = SetOptimizerPolicy(
        optimizer_id="bounded-beam-real-library-r1",
        optimizer_version=REAL_LIBRARY_MATERIALIZER_VERSION,
        beam_width=8,
        max_depth=4,
        per_state_candidate_limit=16,
        max_expanded_candidates=5000,
        alternative_limit=3,
    )
    greedy_policy = greedy_recommend_next_policy_v1(beam_policy)
    common = dict(
        repository=repository,
        intent=intent,
        root_context=root_context,
        root_state=root_state,
        base_transition_context=preserve_groove_context_v1(),
        ranking_policy=balanced_set_ranking_policy_v1(),
        target_duration_seconds_by_track=durations,
        generated_at=generated_at,
    )
    greedy = optimize_set_lookahead(optimizer_policy=greedy_policy, **common)
    beam = optimize_set_lookahead(optimizer_policy=beam_policy, **common)
    return greedy, beam


def _best_plan(result: SetOptimizerResult, strategy: ReviewPlanStrategy):
    if not result.alternatives:
        raise RealLibraryPilotError(
            f"{strategy.value} produced no reviewable alternative: {result.status.value}"
        )
    return reviewable_plan_from_alternative(
        strategy=strategy,
        result_id=result.result_id,
        alternative=result.alternatives[0],
    )


def materialize_cases(
    *,
    snapshot_raw: Mapping[str, Any],
    selection_raw: Mapping[str, Any],
    evidence: Mapping[str, MaterializedTrackEvidence],
    database_path: str | Path,
    generated_at: str,
    blinding_seed: str,
) -> tuple[MaterializedCase, ...]:
    snapshot = _validate_snapshot(snapshot_raw)
    selection_snapshot_ref = tuple(selection_raw.get("snapshot_ref") or ())
    if selection_snapshot_ref != (snapshot.snapshot_id, snapshot.snapshot_version):
        raise RealLibraryPilotError("curated selection snapshot_ref does not match snapshot")
    _prepare_database(database_path)
    repository = MusicIntelligenceRepository()
    repository.ensure_schema()

    materialized: list[MaterializedCase] = []
    for spec in _case_specs(selection_raw):
        case_id = _non_empty(spec.get("case_spec_id"), "case_spec_id")
        role = _role(spec)
        seed_id = _non_empty(spec.get("seed_track_id"), "seed_track_id")
        candidates = tuple(
            _non_empty(item, "candidate_scope_track_id")
            for item in (spec.get("candidate_scope_track_ids") or ())
        )
        scope = tuple(dict.fromkeys((seed_id, *candidates)))
        missing = tuple(track_id for track_id in scope if track_id not in evidence)
        if missing:
            raise RealLibraryPilotError(f"case {case_id} missing MIR evidence: {missing}")

        intent = _intent_for_case(
            case_id=case_id,
            role=role,
            seed_track_id=seed_id,
            candidate_track_ids=candidates,
        )
        phase = intent.phase_plan[0]
        _persist_case_adjacency(
            repository=repository,
            evidence=evidence,
            phase=phase,
            track_ids=scope,
            generated_at=generated_at,
        )
        root_state = _state_for_case(
            case_id=case_id,
            seed=evidence[seed_id],
            phase=phase,
        )
        root_context = _playlist_context(case_id, root_state, phase)
        durations: dict[str, float] = {}
        for track_id in scope:
            duration = evidence[track_id].canonical.duration_seconds
            if duration is None or duration <= 0.0:
                raise RealLibraryPilotError(
                    f"case {case_id} missing positive duration for {track_id}"
                )
            durations[track_id] = float(duration)

        greedy_result, beam_result = _run_optimizer_pair(
            repository=repository,
            intent=intent,
            root_context=root_context,
            root_state=root_state,
            durations=durations,
            generated_at=generated_at,
        )
        greedy_plan = _best_plan(
            greedy_result,
            ReviewPlanStrategy.GREEDY_RECOMMEND_NEXT,
        )
        beam_plan = _best_plan(
            beam_result,
            ReviewPlanStrategy.BOUNDED_BEAM,
        )
        if (
            greedy_plan.ordered_track_ids == beam_plan.ordered_track_ids
            and greedy_plan.transition_ids == beam_plan.transition_ids
        ):
            raise RealLibraryPilotError(
                f"case {case_id} is not blind-reviewable because greedy and beam "
                "produced the same path"
            )
        engineering_passed = (
            not greedy_result.missing_evidence_detected
            and not beam_result.missing_evidence_detected
            and not greedy_result.budget_exhausted
            and not beam_result.budget_exhausted
        )
        if not engineering_passed:
            raise RealLibraryPilotError(
                f"case {case_id} failed engineering acceptance before human review"
            )
        scenario_fingerprint = _sha256_json(
            {
                "case_spec": spec,
                "snapshot_ref": (snapshot.snapshot_id, snapshot.snapshot_version),
                "greedy_result": greedy_result.input_fingerprint,
                "beam_result": beam_result.input_fingerprint,
            }
        )
        case = CuratedReviewCase(
            case_id=case_id,
            snapshot_ref=(snapshot.snapshot_id, snapshot.snapshot_version),
            scenario_fingerprint=scenario_fingerprint,
            set_role=role,
            benchmark_ref=(
                "real-library-greedy-vs-beam",
                CURATED_REAL_LIBRARY_BENCHMARK_VERSION,
            ),
            greedy_plan=greedy_plan,
            beam_plan=beam_plan,
            engineering_acceptance_passed=True,
            evidence_refs=(
                f"greedy:{greedy_result.result_id}",
                f"beam:{beam_result.result_id}",
            ),
        )
        assignment = build_blinded_plan_assignment(
            case=case,
            blinding_seed=blinding_seed,
        )
        materialized.append(
            MaterializedCase(case, assignment, greedy_result, beam_result)
        )
    return tuple(materialized)


def private_runtime_manifest(
    *,
    snapshot_raw: Mapping[str, Any],
    evidence: Mapping[str, MaterializedTrackEvidence],
    cases: Sequence[MaterializedCase],
    generated_at: str,
) -> dict[str, Any]:
    snapshot = _validate_snapshot(snapshot_raw)
    tracks = []
    for track_id in sorted(evidence):
        item = evidence[track_id]
        tracks.append(
            {
                "track_id": track_id,
                "absolute_path": item.source.absolute_path,
                "inventory_file_signature": item.source.file_signature,
                "content_sha256": item.content_sha256,
                "duration_seconds": item.canonical.duration_seconds,
                "provider": item.canonical.provider,
                "provider_version": item.canonical.provider_version,
                "algorithm_version": item.canonical.algorithm_version,
                "analysis_revision": item.music_dna.identity.analysis_revision,
                "bpm": item.canonical.bpm,
                "camelot": item.canonical.camelot,
                "energy": item.canonical.energy,
                "warnings": item.canonical.warnings,
            }
        )
    return {
        "schema": PRIVATE_RUNTIME_EVIDENCE_SCHEMA,
        "materializer_version": REAL_LIBRARY_MATERIALIZER_VERSION,
        "generated_at": generated_at,
        "snapshot_ref": [snapshot.snapshot_id, snapshot.snapshot_version],
        "library_fingerprint": snapshot.library_fingerprint,
        "privacy": {
            "contains_local_absolute_paths": True,
            "publishable_to_public_repo": False,
            "storage_class": "CASER_PRIVATE_EVIDENCE",
        },
        "tracks": tracks,
        "cases": [
            {
                "case": asdict(item.case),
                "assignment": asdict(item.assignment),
                "greedy_status": item.greedy_result.status.value,
                "beam_status": item.beam_result.status.value,
                "greedy_result_id": item.greedy_result.result_id,
                "beam_result_id": item.beam_result.result_id,
            }
            for item in cases
        ],
        "activation_authorized": False,
        "personal_dj_model_training_authorized": False,
    }


def reviewer_packet(
    *,
    snapshot_raw: Mapping[str, Any],
    evidence: Mapping[str, MaterializedTrackEvidence],
    cases: Sequence[MaterializedCase],
    generated_at: str,
) -> dict[str, Any]:
    snapshot = _validate_snapshot(snapshot_raw)
    names = {
        track_id: item.source.display_name
        for track_id, item in evidence.items()
    }
    rows: list[dict[str, Any]] = []
    for item in cases:
        case = item.case
        assignment = item.assignment
        plan_by_id = {
            case.greedy_plan.plan_id: case.greedy_plan,
            case.beam_plan.plan_id: case.beam_plan,
        }
        plan_a = plan_by_id[assignment.slot_a_plan_id]
        plan_b = plan_by_id[assignment.slot_b_plan_id]
        rows.append(
            {
                "case_id": case.case_id,
                "set_role": case.set_role.value,
                "assignment_id": assignment.assignment_id,
                "plan_a": [names[track_id] for track_id in plan_a.ordered_track_ids],
                "plan_b": [names[track_id] for track_id in plan_b.ordered_track_ids],
                "required_review_dimensions": [
                    "transition_smoothness",
                    "phrase_alignment",
                    "energy_flow",
                    "dramaturgical_fit",
                    "set_coherence",
                    "alternative_usefulness",
                ],
                "allowed_preference": ["plan_a", "plan_b", "tie", "abstain"],
            }
        )
    packet = {
        "schema": BLIND_REVIEW_PACKET_SCHEMA,
        "protocol_version": "human-dj-review-r1",
        "generated_at": generated_at,
        "snapshot_ref": [snapshot.snapshot_id, snapshot.snapshot_version],
        "algorithm_identity_hidden": True,
        "cases": rows,
        "activation_authorized": False,
        "personal_dj_model_training_authorized": False,
    }
    packet["packet_fingerprint"] = _sha256_json(packet)
    return packet


def materialize_real_library_pilot_r1(
    *,
    snapshot_path: str | Path,
    selection_path: str | Path,
    output_dir: str | Path,
    database_path: str | Path,
    generated_at: str,
    blinding_seed: str,
    analyzer: BaselineLibrosaMIR | None = None,
) -> dict[str, str]:
    snapshot_raw = _load_json(snapshot_path)
    selection_raw = _load_json(selection_path)
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
    if len(cases) != len(_case_specs(selection_raw)):
        raise RealLibraryPilotError("not every curated case produced a blind plan pair")

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    private_path = output / "APPLAYLIST_REAL_LIBRARY_RUNTIME_EVIDENCE_R1.private.json"
    reviewer_path = output / "APPLAYLIST_BLINDED_HUMAN_DJ_REVIEW_PACKET_R1.json"
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
        "private_runtime_manifest": str(private_path),
        "blind_reviewer_packet": str(reviewer_path),
        "private_runtime_manifest_sha256": hashlib.sha256(
            private_path.read_bytes()
        ).hexdigest(),
        "blind_reviewer_packet_sha256": hashlib.sha256(
            reviewer_path.read_bytes()
        ).hexdigest(),
    }


__all__ = [
    "BLIND_REVIEW_PACKET_SCHEMA",
    "PRIVATE_RUNTIME_EVIDENCE_SCHEMA",
    "REAL_LIBRARY_MATERIALIZER_VERSION",
    "MaterializedCase",
    "MaterializedTrackEvidence",
    "RealLibraryPilotError",
    "RealLibraryTrackInput",
    "_sha256_file",
    "analyze_real_tracks",
    "materialize_cases",
    "materialize_real_library_pilot_r1",
    "private_runtime_manifest",
    "required_track_ids",
    "reviewer_packet",
]
