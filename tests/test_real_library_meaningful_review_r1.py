from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from core.analysis.provider_contract import CanonicalAnalysisResult
from core.intelligence.curated_real_library_review_contract import (
    BlindedPlanAssignment,
    CuratedReviewCase,
    CuratedSetRole,
    ReviewableSetPlan,
    ReviewPlanStrategy,
)
from core.intelligence.meaningful_diversity_contract import (
    MeaningfulDiversityPolicy,
    MeaningfulDiversityStatus,
)
from core.intelligence.music_dna import build_music_dna
from core.intelligence.set_contract import SequenceState, SetStep
from core.intelligence.set_optimizer_contract import (
    SetOptimizerResult,
    SetOptimizerStatus,
    SetPathAlternative,
    SetPathObjective,
)
from services.intelligence.real_library_meaningful_review import (
    MEANINGFUL_REVIEW_REPORT_SCHEMA,
    evaluate_materialized_case_r1,
    materialize_real_library_pilot_meaningful_r1,
)
from services.intelligence.real_library_pilot import (
    MaterializedCase,
    MaterializedTrackEvidence,
    RealLibraryPilotError,
    RealLibraryTrackInput,
)

CASE_ID = "case-opening"
PHASE_ID = f"phase:{CASE_ID}"


def _path(path_id: str, rank: int, tracks: tuple[str, ...]) -> SetPathAlternative:
    root = SetStep(
        order_index=0,
        track_id="seed",
        segment_id="seed:whole",
        phase_id=PHASE_ID,
    )
    added = tuple(
        SetStep(
            order_index=index + 1,
            track_id=track_id,
            segment_id=f"{track_id}:whole",
            phase_id=PHASE_ID,
            incoming_transition_id=f"transition:{path_id}:{index}",
            local_projection_score=0.8,
        )
        for index, track_id in enumerate(tracks)
    )
    selected = (root, *added)
    state = SequenceState(
        state_id=f"state:{path_id}",
        state_version="1",
        selected_steps=selected,
        current_track_id=tracks[-1],
        current_segment_id=f"{tracks[-1]}:whole",
        used_track_ids=tuple(step.track_id for step in selected),
        cumulative_duration_seconds=float(len(selected) * 300),
        current_energy_state=0.52,
        evidence_refs=(f"evidence:{path_id}",),
    )
    return SetPathAlternative(
        path_id=path_id,
        rank=rank,
        added_steps=added,
        resulting_state=state,
        transition_ids=tuple(
            f"transition:{path_id}:{index}" for index in range(len(tracks))
        ),
        candidate_scores=tuple(0.8 for _ in tracks),
        objective=SetPathObjective(
            depth=len(tracks),
            mean_candidate_score=0.8,
            minimum_candidate_score=0.8,
            required_track_completion=1.0,
            remaining_required_count=0,
            target_reached=True,
        ),
        explanation_codes=("test-path",),
        evidence_refs=(f"evidence:{path_id}",),
    )


def _result(result_id: str, path: SetPathAlternative) -> SetOptimizerResult:
    return SetOptimizerResult(
        result_id=result_id,
        input_fingerprint=f"input:{result_id}",
        optimizer_ref=("optimizer", "v1"),
        intent_ref=("intent", "v1"),
        root_state_ref=("state", "v1"),
        base_transition_context_ref=("context", "v1"),
        status=SetOptimizerStatus.TARGET_REACHED,
        alternatives=(path,),
        deepest_depth=len(path.added_steps),
        expanded_candidates=10,
        beam_pruned_candidates=0,
        budget_exhausted=False,
        missing_evidence_detected=False,
        deterministic_ordering=True,
    )


def _review_plan(
    *,
    plan_id: str,
    strategy: ReviewPlanStrategy,
    result: SetOptimizerResult,
) -> ReviewableSetPlan:
    path = result.alternatives[0]
    return ReviewableSetPlan(
        plan_id=plan_id,
        strategy=strategy,
        result_id=result.result_id,
        path_id=path.path_id,
        ordered_track_ids=tuple(step.track_id for step in path.added_steps),
        transition_ids=path.transition_ids,
    )


def _materialized_case(
    greedy_path: SetPathAlternative,
    beam_path: SetPathAlternative,
) -> MaterializedCase:
    greedy_result = _result("greedy-result", greedy_path)
    beam_result = _result("beam-result", beam_path)
    greedy_plan = _review_plan(
        plan_id="greedy-plan",
        strategy=ReviewPlanStrategy.GREEDY_RECOMMEND_NEXT,
        result=greedy_result,
    )
    beam_plan = _review_plan(
        plan_id="beam-plan",
        strategy=ReviewPlanStrategy.BOUNDED_BEAM,
        result=beam_result,
    )
    case = CuratedReviewCase(
        case_id=CASE_ID,
        snapshot_ref=("snapshot", "1"),
        scenario_fingerprint="scenario-fingerprint",
        set_role=CuratedSetRole.OPENING,
        benchmark_ref=("benchmark", "v1"),
        greedy_plan=greedy_plan,
        beam_plan=beam_plan,
        engineering_acceptance_passed=True,
    )
    assignment = BlindedPlanAssignment(
        assignment_id="assignment",
        case_id=CASE_ID,
        slot_a_plan_id=greedy_plan.plan_id,
        slot_b_plan_id=beam_plan.plan_id,
        assignment_fingerprint="assignment-fingerprint",
    )
    return MaterializedCase(case, assignment, greedy_result, beam_result)


def _track(track_id: str, genre: str | None, energy: float | None) -> MaterializedTrackEvidence:
    source = RealLibraryTrackInput(
        track_id=track_id,
        absolute_path=f"/private/{track_id}.mp3",
        file_signature=hashlib.sha256(track_id.encode()).hexdigest(),
        display_name=track_id,
        artist="artist",
        genre=genre,
        snapshot_energy=energy,
    )
    canonical = CanonicalAnalysisResult(
        path=source.absolute_path,
        provider="librosa",
        bpm=128.0,
        bpm_confidence=0.9,
        key="8A",
        key_confidence=0.8,
        energy=energy,
        loudness_db=-10.0,
        duration_seconds=300.0,
        genre_hint=genre,
        camelot="8A",
        beat_stability=0.9,
        harmonic_ratio=0.5,
        percussive_ratio=0.7,
        provider_version="0.10.2",
        algorithm_version="baseline-librosa-mir-v1",
    )
    content_sha = hashlib.sha256(f"content:{track_id}".encode()).hexdigest()
    dna = build_music_dna(
        track_id=track_id,
        content_identity=f"sha256:{content_sha}",
        analysis_revision=f"analysis:{track_id}",
        evidence_id=f"evidence:{track_id}",
        input_identity=f"sha256:{content_sha}",
        canonical=canonical,
    )
    return MaterializedTrackEvidence(source, content_sha, canonical, dna)


def _evidence(styles: dict[str, str | None]) -> dict[str, MaterializedTrackEvidence]:
    return {
        track_id: _track(track_id, genre, 0.52)
        for track_id, genre in styles.items()
    }


def test_cross_strategy_near_equivalent_paths_are_not_reviewable() -> None:
    materialized = _materialized_case(
        _path("greedy", 1, ("a", "b", "c", "d")),
        _path("beam", 1, ("d", "a", "b", "c")),
    )
    evidence = _evidence(
        {
            "seed": "House",
            "a": "House",
            "b": "House",
            "c": "House",
            "d": "House",
        }
    )

    result = evaluate_materialized_case_r1(
        materialized=materialized,
        seed_track_id="seed",
        evidence=evidence,
    )

    assert result["status"] == MeaningfulDiversityStatus.INSUFFICIENT_MEANINGFUL_DIVERSITY.value
    assert result["comparison"]["technically_different"] is True
    assert result["comparison"]["meaningful"] is False
    assert "insufficient_meaningful_musical_distance" in result["comparison"]["reason_codes"]
    assert result["activation_authorized"] is False


def test_cross_strategy_pair_can_be_meaningful_while_both_paths_remain_coherent() -> None:
    materialized = _materialized_case(
        _path("greedy", 1, ("a", "b", "c", "d")),
        _path("beam", 1, ("e", "f", "g", "h")),
    )
    evidence = _evidence(
        {
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
    )

    result = evaluate_materialized_case_r1(
        materialized=materialized,
        seed_track_id="seed",
        evidence=evidence,
    )

    assert result["status"] == MeaningfulDiversityStatus.SUFFICIENT.value
    assert result["greedy_coherence"]["coherence_pass"] is True
    assert result["beam_coherence"]["coherence_pass"] is True
    assert result["comparison"]["meaningful"] is True
    assert result["comparison"]["meaningful_distance"] >= 0.20


def test_style_saturation_fails_case_coherence() -> None:
    materialized = _materialized_case(
        _path("greedy", 1, ("a", "b", "c", "d")),
        _path("beam", 1, ("e", "f", "g", "h")),
    )
    evidence = _evidence(
        {
            "seed": "House",
            "a": "House",
            "b": "House",
            "c": "House",
            "d": "House",
            "e": "House",
            "f": "UKG",
            "g": "UKG",
            "h": "UKG",
        }
    )

    result = evaluate_materialized_case_r1(
        materialized=materialized,
        seed_track_id="seed",
        evidence=evidence,
    )

    assert result["status"] == MeaningfulDiversityStatus.INSUFFICIENT_MEANINGFUL_DIVERSITY.value
    assert "non_target_style_concentration_above_policy" in result["beam_coherence"]["reason_codes"]


def test_missing_style_evidence_is_not_proven() -> None:
    materialized = _materialized_case(
        _path("greedy", 1, ("a", "b", "c", "d")),
        _path("beam", 1, ("e", "f", "g", "h")),
    )
    evidence = _evidence(
        {
            "seed": "House",
            "a": "House",
            "b": "House",
            "c": "House",
            "d": "House",
            "e": "House",
            "f": None,
            "g": "House",
            "h": "House",
        }
    )

    result = evaluate_materialized_case_r1(
        materialized=materialized,
        seed_track_id="seed",
        evidence=evidence,
    )

    assert result["status"] == MeaningfulDiversityStatus.NOT_PROVEN_MISSING_EVIDENCE.value
    assert "f" in result["beam_coherence"]["missing_style_track_ids"]


def test_failed_gate_writes_report_but_withholds_reviewer_packet(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import services.intelligence.real_library_meaningful_review as module

    materialized = _materialized_case(
        _path("greedy", 1, ("a", "b", "c", "d")),
        _path("beam", 1, ("d", "a", "b", "c")),
    )
    evidence = _evidence(
        {
            "seed": "House",
            "a": "House",
            "b": "House",
            "c": "House",
            "d": "House",
        }
    )
    snapshot_path = tmp_path / "snapshot.json"
    selection_path = tmp_path / "selection.json"
    snapshot_path.write_text(json.dumps({"placeholder": True}), encoding="utf-8")
    selection_path.write_text(
        json.dumps(
            {
                "case_specs": [
                    {
                        "case_spec_id": CASE_ID,
                        "seed_track_id": "seed",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "analyze_real_tracks", lambda **_: evidence)
    monkeypatch.setattr(module, "materialize_cases", lambda **_: (materialized,))

    output = tmp_path / "out"
    with pytest.raises(RealLibraryPilotError, match="reviewer packet withheld"):
        materialize_real_library_pilot_meaningful_r1(
            snapshot_path=snapshot_path,
            selection_path=selection_path,
            output_dir=output,
            database_path=tmp_path / "pilot.sqlite",
            generated_at="2026-08-22T01:00:00Z",
            blinding_seed="local-test-seed",
        )

    report_path = output / "APPLAYLIST_MEANINGFUL_DIVERSITY_STYLE_ENERGY_R1_REPORT.json"
    assert report_path.is_file()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["schema"] == MEANINGFUL_REVIEW_REPORT_SCHEMA
    assert report["all_cases_meaningfully_reviewable"] is False
    assert report["failed_case_ids"] == [CASE_ID]
    assert report["optimizer_ranking_mutated"] is False
    assert report["activation_authorized"] is False
    assert not (output / "APPLAYLIST_BLINDED_HUMAN_DJ_REVIEW_PACKET_R1.json").exists()
    assert not (output / "APPLAYLIST_REAL_LIBRARY_RUNTIME_EVIDENCE_R1.private.json").exists()


def test_evaluation_does_not_mutate_source_rank_or_path_identity() -> None:
    greedy_path = _path("greedy", 1, ("a", "b", "c", "d"))
    beam_path = _path("beam", 1, ("e", "f", "g", "h"))
    materialized = _materialized_case(greedy_path, beam_path)
    evidence = _evidence(
        {
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
    )

    evaluate_materialized_case_r1(
        materialized=materialized,
        seed_track_id="seed",
        evidence=evidence,
        policy=MeaningfulDiversityPolicy(),
    )

    assert greedy_path.rank == 1
    assert beam_path.rank == 1
    assert greedy_path.path_id == "greedy"
    assert beam_path.path_id == "beam"
