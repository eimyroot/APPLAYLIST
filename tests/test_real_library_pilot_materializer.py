from __future__ import annotations

import hashlib

import pytest

from core.analysis.provider_contract import CanonicalAnalysisResult
from core.intelligence.curated_real_library_review_contract import ReviewPlanStrategy
from core.intelligence.music_dna import build_music_dna
from services.intelligence.real_library_pilot import (
    MaterializedTrackEvidence,
    RealLibraryPilotError,
    RealLibraryTrackInput,
    _validate_snapshot,
    required_track_ids,
    reviewer_packet,
)


def _snapshot() -> dict:
    tracks = []
    for index in range(4):
        signature = hashlib.sha256(f"track-{index}".encode("utf-8")).hexdigest()
        track_id = f"trk_{signature[:24]}"
        tracks.append(
            {
                "track_id": track_id,
                "absolute_path": f"/Volumes/EXTRAZALOHA/track-{index}.mp3",
                "file_signature": signature,
                "display_name": f"Artist {index} - Track {index}",
                "artist": f"Artist {index}",
                "genre": "Techno",
                "energy": 5.0 + index,
            }
        )
    return {
        "schema": "applaylist-local-library-snapshot-r1",
        "snapshot_id": "snapshot-r1",
        "snapshot_version": "local-library-subset-r1",
        "library_fingerprint": "fingerprint-r1",
        "created_date": "2026-08-17",
        "scope": {"kind": "REAL_INVENTORY_BACKED_SUBSET"},
        "privacy": {"publishable_to_public_repo": False},
        "tracks": tracks,
    }


def _selection(snapshot: dict) -> dict:
    ids = [item["track_id"] for item in snapshot["tracks"]]
    return {
        "schema": "applaylist-curated-case-selection-r1",
        "snapshot_ref": [snapshot["snapshot_id"], snapshot["snapshot_version"]],
        "case_specs": [
            {
                "case_spec_id": "case-opening",
                "set_role": "OPENING",
                "seed_track_id": ids[0],
                "candidate_scope_track_ids": ids[1:],
            }
        ],
    }


def test_required_track_ids_are_stable_and_unique() -> None:
    snapshot = _snapshot()
    selection = _selection(snapshot)
    expected = tuple(sorted(item["track_id"] for item in snapshot["tracks"]))
    assert required_track_ids(selection) == expected


def test_snapshot_rejects_public_publishable_private_paths() -> None:
    snapshot = _snapshot()
    snapshot["privacy"]["publishable_to_public_repo"] = True
    with pytest.raises(RealLibraryPilotError, match="private evidence"):
        _validate_snapshot(snapshot)


def test_reviewer_packet_contains_no_algorithm_strategy_or_absolute_path() -> None:
    from core.intelligence.curated_real_library_review_contract import (
        BlindedPlanAssignment,
        CuratedReviewCase,
        CuratedSetRole,
        ReviewableSetPlan,
    )
    from core.intelligence.set_optimizer_contract import SetOptimizerResult, SetOptimizerStatus
    from services.intelligence.real_library_pilot import MaterializedCase

    snapshot = _snapshot()
    ids = [item["track_id"] for item in snapshot["tracks"]]
    evidence = {}
    for raw in snapshot["tracks"]:
        track = RealLibraryTrackInput(
            track_id=raw["track_id"],
            absolute_path=raw["absolute_path"],
            file_signature=raw["file_signature"],
            display_name=raw["display_name"],
            artist=raw["artist"],
            genre=raw["genre"],
            snapshot_energy=raw["energy"] / 10.0,
        )
        canonical = CanonicalAnalysisResult(
            path=track.absolute_path,
            provider="librosa",
            bpm=128.0,
            bpm_confidence=0.9,
            key="8A",
            key_confidence=0.8,
            energy=0.6,
            loudness_db=-10.0,
            duration_seconds=300.0,
            genre_hint="techno",
            camelot="8A",
            beat_stability=0.9,
            harmonic_ratio=0.5,
            percussive_ratio=0.7,
            provider_version="0.10.2",
            algorithm_version="baseline-librosa-mir-v1",
        )
        dna = build_music_dna(
            track_id=track.track_id,
            content_identity=f"sha256:{track.file_signature}",
            analysis_revision=f"analysis:{track.track_id}",
            evidence_id=f"evidence:{track.track_id}",
            input_identity=f"sha256:{track.file_signature}",
            canonical=canonical,
        )
        evidence[track.track_id] = MaterializedTrackEvidence(track, canonical, dna)

    greedy = ReviewableSetPlan(
        plan_id="greedy-plan",
        strategy=ReviewPlanStrategy.GREEDY_RECOMMEND_NEXT,
        result_id="greedy-result",
        path_id="greedy-path",
        ordered_track_ids=(ids[0], ids[1], ids[2]),
        transition_ids=("t1", "t2"),
    )
    beam = ReviewableSetPlan(
        plan_id="beam-plan",
        strategy=ReviewPlanStrategy.BOUNDED_BEAM,
        result_id="beam-result",
        path_id="beam-path",
        ordered_track_ids=(ids[0], ids[2], ids[3]),
        transition_ids=("t3", "t4"),
    )
    case = CuratedReviewCase(
        case_id="case-opening",
        snapshot_ref=("snapshot-r1", "local-library-subset-r1"),
        scenario_fingerprint="scenario-fingerprint",
        set_role=CuratedSetRole.OPENING,
        benchmark_ref=("benchmark", "v1"),
        greedy_plan=greedy,
        beam_plan=beam,
        engineering_acceptance_passed=True,
    )
    assignment = BlindedPlanAssignment(
        assignment_id="assignment-1",
        case_id=case.case_id,
        slot_a_plan_id=beam.plan_id,
        slot_b_plan_id=greedy.plan_id,
        assignment_fingerprint="blind-fingerprint",
    )
    result_stub = SetOptimizerResult(
        result_id="result-stub",
        input_fingerprint="input-stub",
        optimizer_ref=("optimizer", "v1"),
        intent_ref=("intent", "v1"),
        root_state_ref=("state", "v1"),
        base_transition_context_ref=("context", "v1"),
        status=SetOptimizerStatus.NO_ELIGIBLE_PATH,
        alternatives=(),
        deepest_depth=0,
        expanded_candidates=0,
        beam_pruned_candidates=0,
        budget_exhausted=False,
        missing_evidence_detected=False,
        deterministic_ordering=True,
    )
    materialized = MaterializedCase(case, assignment, result_stub, result_stub)
    packet = reviewer_packet(
        snapshot_raw=snapshot,
        evidence=evidence,
        cases=(materialized,),
        generated_at="2026-08-17T04:00:00+02:00",
    )
    text = str(packet)
    assert "/Volumes/EXTRAZALOHA" not in text
    assert "greedy_recommend_next" not in text
    assert "bounded_beam" not in text
    assert packet["algorithm_identity_hidden"] is True
    assert packet["cases"][0]["plan_a"] != packet["cases"][0]["plan_b"]


def test_required_tracks_rejects_empty_candidate_scope() -> None:
    snapshot = _snapshot()
    selection = _selection(snapshot)
    selection["case_specs"][0]["candidate_scope_track_ids"] = []
    with pytest.raises(RealLibraryPilotError, match="candidate_scope_track_ids"):
        required_track_ids(selection)
