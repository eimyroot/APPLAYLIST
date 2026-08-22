from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.intelligence.meaningful_diversity_contract import MeaningfulDiversityStatus
from services.intelligence.historical_meaningful_replay import (
    HISTORICAL_MEANINGFUL_REPLAY_SCHEMA,
    replay_historical_meaningful_review_r1,
)
from services.intelligence.real_library_pilot import RealLibraryPilotError

SNAPSHOT_REF = ("snapshot-r2", "2")
CASE_ID = "case-opening"
TRACKS = ("seed", "a", "b", "c", "d", "e", "f", "g", "h")


def _snapshot(*, missing_genre: str | None = None) -> dict:
    genres = {
        "seed": "House",
        "a": "House",
        "b": "House",
        "c": "House",
        "d": "House",
        "e": "House",
        "f": "House",
        "g": "Tech House",
        "h": "Tech House",
    }
    if missing_genre is not None:
        genres[missing_genre] = None
    return {
        "schema": "applaylist-local-library-snapshot-r1",
        "snapshot_id": SNAPSHOT_REF[0],
        "snapshot_version": SNAPSHOT_REF[1],
        "library_fingerprint": "library-fingerprint-r2",
        "scope": {"kind": "REAL_INVENTORY_BACKED_SUBSET"},
        "privacy": {"publishable_to_public_repo": False},
        "tracks": [
            {
                "track_id": track_id,
                "absolute_path": f"/Volumes/DOES-NOT-EXIST/{track_id}.mp3",
                "file_signature": f"signature-{track_id}",
                "display_name": track_id,
                "artist": "artist",
                "genre": genres[track_id],
                "energy": 5.2,
            }
            for track_id in TRACKS
        ],
    }


def _selection() -> dict:
    return {
        "schema": "applaylist-curated-case-selection-r1",
        "snapshot_ref": list(SNAPSHOT_REF),
        "case_specs": [
            {
                "case_spec_id": CASE_ID,
                "set_role": "opening",
                "seed_track_id": "seed",
                "candidate_scope_track_ids": list(TRACKS[1:]),
            }
        ],
    }


def _plan(plan_id: str, strategy: str, result_id: str, path_id: str, tracks: tuple[str, ...]) -> dict:
    return {
        "plan_id": plan_id,
        "strategy": strategy,
        "result_id": result_id,
        "path_id": path_id,
        "ordered_track_ids": list(tracks),
        "transition_ids": [f"transition:{path_id}:{index}" for index in range(len(tracks) - 1)],
        "evidence_refs": [f"source:{path_id}"],
    }


def _private(*, meaningful: bool = False, missing_energy: str | None = None) -> dict:
    greedy_tracks = ("seed", "a", "b", "c", "d")
    beam_tracks = ("seed", "e", "f", "g", "h") if meaningful else ("seed", "d", "a", "b", "c")
    tracks = []
    for track_id in TRACKS:
        tracks.append(
            {
                "track_id": track_id,
                "absolute_path": f"/Volumes/DOES-NOT-EXIST/{track_id}.mp3",
                "inventory_file_signature": f"signature-{track_id}",
                "content_sha256": f"content-{track_id}",
                "duration_seconds": 300.0,
                "provider": "librosa",
                "provider_version": "0.10.2",
                "algorithm_version": "baseline-librosa-mir-v1",
                "analysis_revision": f"analysis:{track_id}",
                "bpm": 128.0,
                "camelot": "8A",
                "energy": None if track_id == missing_energy else 0.52,
                "warnings": [],
            }
        )
    greedy = _plan(
        "greedy-plan",
        "greedy_recommend_next",
        "greedy-result",
        "greedy-path",
        greedy_tracks,
    )
    beam = _plan(
        "beam-plan",
        "bounded_beam",
        "beam-result",
        "beam-path",
        beam_tracks,
    )
    return {
        "schema": "applaylist-private-runtime-music-evidence-r1",
        "materializer_version": "real-library-evidence-materializer-r1",
        "generated_at": "2026-08-18T14:52:25Z",
        "snapshot_ref": list(SNAPSHOT_REF),
        "library_fingerprint": "library-fingerprint-r2",
        "privacy": {
            "contains_local_absolute_paths": True,
            "publishable_to_public_repo": False,
            "storage_class": "CASER_PRIVATE_EVIDENCE",
        },
        "tracks": tracks,
        "cases": [
            {
                "case": {
                    "case_id": CASE_ID,
                    "snapshot_ref": list(SNAPSHOT_REF),
                    "scenario_fingerprint": "scenario-r2",
                    "set_role": "opening",
                    "benchmark_ref": ["real-library-greedy-vs-beam", "curated-real-library-benchmark-r1"],
                    "greedy_plan": greedy,
                    "beam_plan": beam,
                    "engineering_acceptance_passed": True,
                    "evidence_refs": ["greedy:greedy-result", "beam:beam-result"],
                },
                "assignment": {
                    "assignment_id": "assignment-r2",
                    "case_id": CASE_ID,
                    "slot_a_plan_id": "greedy-plan",
                    "slot_b_plan_id": "beam-plan",
                    "assignment_fingerprint": "assignment-fingerprint-r2",
                    "algorithm_identity_hidden": True,
                },
                "greedy_status": "target_reached",
                "beam_status": "target_reached",
                "greedy_result_id": "greedy-result",
                "beam_result_id": "beam-result",
            }
        ],
        "activation_authorized": False,
        "personal_dj_model_training_authorized": False,
    }


def _write_inputs(tmp_path: Path, *, snapshot: dict | None = None, private: dict | None = None):
    snapshot_path = tmp_path / "snapshot.json"
    selection_path = tmp_path / "selection.json"
    private_path = tmp_path / "private.json"
    snapshot_path.write_text(json.dumps(snapshot or _snapshot()), encoding="utf-8")
    selection_path.write_text(json.dumps(_selection()), encoding="utf-8")
    private_path.write_text(json.dumps(private or _private()), encoding="utf-8")
    return snapshot_path, selection_path, private_path


def test_replay_uses_existing_json_evidence_without_audio_access(tmp_path: Path) -> None:
    snapshot, selection, private = _write_inputs(tmp_path)
    output = tmp_path / "report.json"

    result = replay_historical_meaningful_review_r1(
        snapshot_path=snapshot,
        selection_path=selection,
        private_manifest_path=private,
        output_path=output,
        generated_at="2026-08-22T02:50:00Z",
    )

    assert output.is_file()
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["schema"] == HISTORICAL_MEANINGFUL_REPLAY_SCHEMA
    assert report["source_audio_read"] is False
    assert report["mir_provider_called"] is False
    assert report["historical_evidence_mutated"] is False
    assert report["reviewer_packet_regenerated"] is False
    assert report["cases"][0]["status"] == MeaningfulDiversityStatus.INSUFFICIENT_MEANINGFUL_DIVERSITY.value
    assert "insufficient_meaningful_musical_distance" in report["cases"][0]["comparison"]["reason_codes"]
    assert result["historical_meaningful_replay_report_sha256"]


def test_replay_can_prove_meaningful_coherent_pair_from_historical_plans(tmp_path: Path) -> None:
    snapshot, selection, private = _write_inputs(tmp_path, private=_private(meaningful=True))
    output = tmp_path / "report.json"

    replay_historical_meaningful_review_r1(
        snapshot_path=snapshot,
        selection_path=selection,
        private_manifest_path=private,
        output_path=output,
        generated_at="2026-08-22T02:50:00Z",
    )

    report = json.loads(output.read_text(encoding="utf-8"))
    case = report["cases"][0]
    assert case["status"] == MeaningfulDiversityStatus.SUFFICIENT.value
    assert case["comparison"]["meaningful"] is True
    assert case["source_greedy_result_id"] == "greedy-result"
    assert case["source_beam_result_id"] == "beam-result"
    assert case["source_greedy_path_id"] == "greedy-path"
    assert case["source_beam_path_id"] == "beam-path"


def test_missing_historical_style_or_energy_is_fail_closed(tmp_path: Path) -> None:
    snapshot, selection, private = _write_inputs(
        tmp_path,
        snapshot=_snapshot(missing_genre="g"),
        private=_private(meaningful=True, missing_energy="h"),
    )
    output = tmp_path / "report.json"

    replay_historical_meaningful_review_r1(
        snapshot_path=snapshot,
        selection_path=selection,
        private_manifest_path=private,
        output_path=output,
        generated_at="2026-08-22T02:50:00Z",
    )

    case = json.loads(output.read_text(encoding="utf-8"))["cases"][0]
    assert case["status"] == MeaningfulDiversityStatus.NOT_PROVEN_MISSING_EVIDENCE.value
    assert "g" in case["beam_coherence"]["missing_style_track_ids"]
    assert "h" in case["beam_coherence"]["missing_energy_track_ids"]


def test_replay_rejects_cross_artifact_binding_mismatch(tmp_path: Path) -> None:
    private = _private()
    private["cases"][0]["greedy_result_id"] = "tampered-result"
    snapshot, selection, private_path = _write_inputs(tmp_path, private=private)

    with pytest.raises(RealLibraryPilotError, match="greedy result binding mismatch"):
        replay_historical_meaningful_review_r1(
            snapshot_path=snapshot,
            selection_path=selection,
            private_manifest_path=private_path,
            output_path=tmp_path / "report.json",
            generated_at="2026-08-22T02:50:00Z",
        )


def test_replay_is_deterministic_for_identical_input_bytes(tmp_path: Path) -> None:
    snapshot, selection, private = _write_inputs(tmp_path, private=_private(meaningful=True))
    first = replay_historical_meaningful_review_r1(
        snapshot_path=snapshot,
        selection_path=selection,
        private_manifest_path=private,
        output_path=tmp_path / "first.json",
        generated_at="2026-08-22T02:50:00Z",
    )
    second = replay_historical_meaningful_review_r1(
        snapshot_path=snapshot,
        selection_path=selection,
        private_manifest_path=private,
        output_path=tmp_path / "second.json",
        generated_at="2026-08-22T02:50:00Z",
    )

    assert first["historical_meaningful_replay_report_sha256"] == second["historical_meaningful_replay_report_sha256"]


def test_replay_refuses_existing_output_and_dangling_symlink(tmp_path: Path) -> None:
    snapshot, selection, private = _write_inputs(tmp_path)
    existing = tmp_path / "existing.json"
    existing.write_text("{}", encoding="utf-8")
    with pytest.raises(RealLibraryPilotError, match="refusing to overwrite"):
        replay_historical_meaningful_review_r1(
            snapshot_path=snapshot,
            selection_path=selection,
            private_manifest_path=private,
            output_path=existing,
            generated_at="2026-08-22T02:50:00Z",
        )

    dangling = tmp_path / "dangling.json"
    dangling.symlink_to(tmp_path / "outside-does-not-exist.json")
    with pytest.raises(RealLibraryPilotError, match="refusing to overwrite"):
        replay_historical_meaningful_review_r1(
            snapshot_path=snapshot,
            selection_path=selection,
            private_manifest_path=private,
            output_path=dangling,
            generated_at="2026-08-22T02:50:00Z",
        )
