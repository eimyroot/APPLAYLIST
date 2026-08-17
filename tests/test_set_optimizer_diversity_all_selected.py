from __future__ import annotations

from core.intelligence.set_contract import SequenceState, SetStep
from core.intelligence.set_optimizer_contract import (
    SetOptimizerResult,
    SetOptimizerStatus,
    SetPathAlternative,
    SetPathObjective,
)
from core.intelligence.set_optimizer_evaluation_contract import AlternativeDiversityPolicy
from services.intelligence.alternative_diversity import select_diverse_alternatives


def _path(path_id: str, rank: int, tracks: tuple[str, ...]) -> SetPathAlternative:
    root = SetStep(
        order_index=0,
        track_id="root",
        segment_id="root:whole",
        phase_id="phase-1",
    )
    added = tuple(
        SetStep(
            order_index=index + 1,
            track_id=track_id,
            segment_id=f"{track_id}:whole",
            phase_id="phase-1",
            incoming_transition_id=f"transition:{path_id}:{index}",
            local_projection_score=0.8,
        )
        for index, track_id in enumerate(tracks)
    )
    state = SequenceState(
        state_id=f"state:{path_id}",
        state_version="1",
        selected_steps=(root, *added),
        current_track_id=tracks[-1],
        current_segment_id=f"{tracks[-1]}:whole",
        used_track_ids=("root", *tracks),
        cumulative_duration_seconds=float((len(tracks) + 1) * 300),
        current_energy_state=0.6,
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


def test_candidate_must_pass_policy_against_every_selected_path() -> None:
    # Candidate path-3 has a high Jaccard similarity to path-1 but stays within the
    # configured Jaccard limit. It has only low Jaccard similarity to path-2, yet
    # shares the first decision with path-2 and therefore violates the stricter
    # shared-prefix limit. A selector checking only one nearest path could miss this.
    alternatives = (
        _path("path-1", 1, ("a", "b", "c", "d", "e")),
        _path("path-2", 2, ("x", "p", "q", "r", "s")),
        _path("path-3", 3, ("x", "a", "b", "c", "d")),
    )
    result = SetOptimizerResult(
        result_id="result-all-selected",
        input_fingerprint="fingerprint-all-selected",
        optimizer_ref=("bounded-beam-lookahead", "bounded-beam-lookahead-v1"),
        intent_ref=("intent", "1"),
        root_state_ref=("state", "1"),
        base_transition_context_ref=("context", "1"),
        status=SetOptimizerStatus.TARGET_REACHED,
        alternatives=alternatives,
        deepest_depth=5,
        expanded_candidates=20,
        beam_pruned_candidates=0,
        budget_exhausted=False,
        missing_evidence_detected=False,
        deterministic_ordering=True,
    )
    selection = select_diverse_alternatives(
        result=result,
        policy=AlternativeDiversityPolicy(
            alternative_limit=3,
            max_track_jaccard=0.70,
            max_shared_prefix_fraction=0.10,
            minimum_differing_positions=1,
        ),
    )

    assert tuple(item.path_id for item in selection.selected_alternatives) == (
        "path-1",
        "path-2",
    )
    rejected = next(item for item in selection.decisions if item.path_id == "path-3")
    assert rejected.selected is False
    assert rejected.nearest_selected_path_id == "path-2"
    assert rejected.track_jaccard is not None and rejected.track_jaccard < 0.70
    assert rejected.shared_prefix_fraction == 0.20
    assert "shared_prefix_above_policy" in rejected.reason_codes
