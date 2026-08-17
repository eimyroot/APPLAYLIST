from __future__ import annotations

from dataclasses import replace

import pytest

from core.analysis.provider_contract import CanonicalAnalysisResult
from core.intelligence.music_dna import build_music_dna
from core.intelligence.set_contract import (
    CandidateDescriptor,
    CandidateEligibility,
    EligibleLibraryScope,
    EnergyControlPoint,
    EnergyTrajectory,
    LockedPosition,
    PlaylistContext,
    PlaylistIntent,
    RangeBand,
    SequenceState,
    SetGoal,
    SetPhase,
    SetPhaseType,
    SetStep,
)
from services.intelligence.set_engine import (
    balanced_set_ranking_policy_v1,
    recommend_next,
)
from services.intelligence.transition_engine import (
    assess_transition,
    preserve_groove_context_v1,
)


def canonical(**overrides: object) -> CanonicalAnalysisResult:
    values: dict[str, object] = {
        "path": "/Users/private/Music/secret-track.wav",
        "provider": "librosa",
        "bpm": 128.0,
        "bpm_confidence": 0.91,
        "key": "8A",
        "key_confidence": 0.84,
        "energy": 0.62,
        "loudness_db": -10.0,
        "duration_seconds": 300.0,
        "genre_hint": "techno",
        "key_tonic": "A",
        "key_scale": "minor",
        "camelot": "8A",
        "beat_stability": 0.94,
        "harmonic_ratio": 0.55,
        "percussive_ratio": 0.72,
        "provider_version": "0.10.2",
        "algorithm_version": "baseline-librosa-mir-v1",
    }
    values.update(overrides)
    return CanonicalAnalysisResult(**values)  # type: ignore[arg-type]


def dna(track_id: str, **overrides: object):
    return build_music_dna(
        track_id=track_id,
        content_identity=f"sha256:{track_id}",
        analysis_revision=f"analysis:{track_id}:1",
        evidence_id=f"evidence:{track_id}:1",
        input_identity=f"input:{track_id}",
        canonical=canonical(**overrides),
        benchmark_status="benchmark-candidate",
    )


def transition(source, target):
    return assess_transition(
        source=source,
        source_segment_id=source.segments[0].segment_id,
        target=target,
        target_segment_id=target.segments[0].segment_id,
        context=preserve_groove_context_v1(),
        created_at="2026-08-17T00:00:00Z",
    )


def phase() -> SetPhase:
    return SetPhase(
        phase_id="groove",
        phase_type=SetPhaseType.GROOVE,
        ordinal=0,
        target_fraction_start=0.0,
        target_fraction_end=1.0,
        explanation_label="Groove body",
        target_energy_band=RangeBand(0.45, 0.8),
    )


def intent(
    *,
    required: tuple[str, ...] = (),
    forbidden: tuple[str, ...] = (),
    locked: tuple[LockedPosition, ...] = (),
    explicit_scope: tuple[str, ...] | None = None,
    include_tags: tuple[str, ...] = (),
    exclude_tags: tuple[str, ...] = (),
    target_duration_seconds: float | None = 3600.0,
) -> PlaylistIntent:
    return PlaylistIntent(
        intent_id="intent-1",
        intent_version="1",
        goal=SetGoal.CLUB_FLOW,
        eligible_library_scope=EligibleLibraryScope(
            scope_revision="scope-1",
            explicit_track_ids=explicit_scope,
            include_tags=include_tags,
            exclude_tags=exclude_tags,
        ),
        phase_plan=(phase(),),
        energy_trajectory=EnergyTrajectory(
            trajectory_id="energy-1",
            trajectory_version="1",
            control_points=(
                EnergyControlPoint(0.0, 0.55, 0.1, "groove"),
                EnergyControlPoint(1.0, 0.75, 0.1, "groove"),
            ),
        ),
        target_duration_seconds=target_duration_seconds,
        target_track_count=10,
        required_track_ids=required,
        forbidden_track_ids=forbidden,
        locked_positions=locked,
    )


def seeded_state(plan: PlaylistIntent, *, duration: float = 300.0) -> SequenceState:
    selected = SetStep(
        order_index=0,
        track_id="track-a",
        segment_id="track-a:whole",
        phase_id="groove",
        explanation_codes=("seed",),
        evidence_refs=("evidence:track-a:1",),
    )
    satisfied = tuple(item for item in plan.required_track_ids if item == "track-a")
    remaining = tuple(item for item in plan.required_track_ids if item != "track-a")
    return SequenceState(
        state_id="state-1",
        state_version="1",
        selected_steps=(selected,),
        current_track_id="track-a",
        current_segment_id="track-a:whole",
        used_track_ids=("track-a",),
        cumulative_duration_seconds=duration,
        current_energy_state=0.62,
        satisfied_required_track_ids=satisfied,
        remaining_required_track_ids=remaining,
        evidence_refs=("evidence:track-a:1",),
    )


def context() -> PlaylistContext:
    return PlaylistContext(
        context_id="context-1",
        context_version="1",
        current_phase_id="groove",
        current_position_index=0,
        elapsed_duration_seconds=300.0,
        phase_progress=0.1,
        current_track_id="track-a",
        current_segment_id="track-a:whole",
        current_energy_state=0.62,
        remaining_duration_seconds=3300.0,
        remaining_track_count=9,
        context_evidence_refs=("evidence:track-a:1",),
    )


def descriptor(source, target, **kwargs: object) -> CandidateDescriptor:
    return CandidateDescriptor(
        transition=transition(source, target),
        target_duration_seconds=target.duration_seconds,
        **kwargs,
    )


def run(
    plan: PlaylistIntent,
    state: SequenceState,
    edges: tuple[CandidateDescriptor, ...],
    **kwargs,
):
    return recommend_next(
        intent=plan,
        context=context(),
        sequence_state=state,
        transition_edges=edges,
        ranking_policy=balanced_set_ranking_policy_v1(),
        candidate_limit=kwargs.pop("candidate_limit", 5),
        generated_at=kwargs.pop("generated_at", "2026-08-17T00:15:00Z"),
        **kwargs,
    )


def test_recommend_next_is_deterministic_and_independent_of_input_edge_order() -> None:
    plan = intent()
    state = seeded_state(plan)
    source = dna("track-a")
    left = descriptor(source, dna("track-b"))
    right = descriptor(source, dna("track-c"))

    first = run(plan, state, (right, left), generated_at="2026-08-17T00:15:00Z")
    second = run(plan, state, (left, right), generated_at="2026-08-17T00:16:00Z")

    assert first.input_fingerprint == second.input_fingerprint
    assert [item.target_track_id for item in first.eligible_candidates] == [
        item.target_track_id for item in second.eligible_candidates
    ]
    assert first.deterministic_ordering is True
    assert first.generated_at != second.generated_at


def test_equal_candidates_use_stable_track_id_tie_break() -> None:
    plan = intent()
    state = seeded_state(plan)
    source = dna("track-a")
    candidates = (
        descriptor(source, dna("track-c")),
        descriptor(source, dna("track-b")),
    )

    result = run(plan, state, candidates)

    assert [item.target_track_id for item in result.eligible_candidates] == [
        "track-b",
        "track-c",
    ]
    assert [item.rank for item in result.eligible_candidates] == [1, 2]


def test_required_track_progress_can_change_ranking_without_rewriting_transition_truth() -> None:
    plan = intent(required=("track-z",))
    state = seeded_state(plan)
    source = dna("track-a")
    ordinary = descriptor(source, dna("track-b"))
    required = descriptor(source, dna("track-z"))

    result = run(plan, state, (ordinary, required))

    assert result.eligible_candidates[0].target_track_id == "track-z"
    assert result.eligible_candidates[0].feature_vector.required_track_progress == 1.0
    assert "required_track_progress" in result.eligible_candidates[0].explanation_codes
    assert ordinary.transition.contextual_projection.score == required.transition.contextual_projection.score


def test_forbidden_repeat_and_locked_next_are_hard_gates() -> None:
    plan = intent(
        forbidden=("track-b",),
        locked=(LockedPosition(track_id="track-c", lock_version="1", position_index=1),),
    )
    state = seeded_state(plan)
    source = dna("track-a")
    forbidden = descriptor(source, dna("track-b"))
    wrong_lock = descriptor(source, dna("track-d"))
    repeated_target = dna("track-a")
    second_step = SetStep(
        order_index=1,
        track_id="track-x",
        segment_id="track-x:whole",
        phase_id="groove",
    )
    repeated_state = SequenceState(
        state_id="state-repeat",
        state_version="1",
        selected_steps=(
            state.selected_steps[0],
            second_step,
        ),
        current_track_id="track-x",
        current_segment_id="track-x:whole",
        used_track_ids=("track-a", "track-x"),
        cumulative_duration_seconds=600.0,
        current_energy_state=0.62,
        remaining_required_track_ids=(),
    )
    repeated_context = replace(
        context(),
        current_position_index=1,
        current_track_id="track-x",
        current_segment_id="track-x:whole",
    )
    repeated_edge = descriptor(dna("track-x"), repeated_target)

    result = run(plan, state, (forbidden, wrong_lock))

    assert not result.eligible_candidates
    by_track = {item.target_track_id: item for item in result.rejected_candidates}
    assert "candidate_forbidden" in by_track["track-b"].blocked_reasons
    assert "locked_next_track_mismatch" in by_track["track-d"].blocked_reasons

    repeated_result = recommend_next(
        intent=intent(),
        context=repeated_context,
        sequence_state=repeated_state,
        transition_edges=(repeated_edge,),
        ranking_policy=balanced_set_ranking_policy_v1(),
        candidate_limit=5,
        generated_at="2026-08-17T00:15:00Z",
    )
    assert repeated_result.rejected_candidates[0].eligibility is CandidateEligibility.BLOCKED
    assert "candidate_repeat_forbidden" in repeated_result.rejected_candidates[0].blocked_reasons


def test_unknown_scope_tag_evidence_is_not_treated_as_a_pass() -> None:
    plan = intent(include_tags=("techno",))
    state = seeded_state(plan)
    source = dna("track-a")
    missing = descriptor(source, dna("track-b"), style_tags=None)
    matching = descriptor(source, dna("track-c"), style_tags=("techno", "hypnotic"))

    result = run(plan, state, (missing, matching))

    assert [item.target_track_id for item in result.eligible_candidates] == ["track-c"]
    assert "scope_tag_evidence_missing" in result.rejected_candidates[0].blocked_reasons


def test_transition_projection_hard_block_flows_into_set_candidate() -> None:
    plan = intent()
    state = seeded_state(plan)
    source = dna("track-a")
    target = dna("track-b", bpm=None, bpm_confidence=None)
    blocked = descriptor(source, target)

    result = run(plan, state, (blocked,))

    assert not result.eligible_candidates
    assert "transition:tempo_evidence_missing" in result.rejected_candidates[0].blocked_reasons
    assert result.rejected_candidates[0].score is None
    assert result.rejected_candidates[0].rank is None


def test_duration_limit_is_a_hard_gate_not_a_soft_penalty() -> None:
    plan = intent(target_duration_seconds=3600.0)
    state = seeded_state(plan, duration=3400.0)
    source = dna("track-a")
    target = dna("track-b", duration_seconds=300.0)

    result = run(plan, state, (descriptor(source, target),))

    assert not result.eligible_candidates
    assert "target_duration_exceeded" in result.rejected_candidates[0].blocked_reasons


def test_candidate_limit_is_bounded_and_reported() -> None:
    plan = intent()
    state = seeded_state(plan)
    source = dna("track-a")
    edges = tuple(descriptor(source, dna(f"track-{letter}")) for letter in ("b", "c", "d"))

    result = run(plan, state, edges, candidate_limit=2)

    assert len(result.eligible_candidates) == 2
    assert "candidate_set_truncated" in result.warnings
    assert "future_feasibility_not_evaluated_v1" in result.warnings


def test_recommend_next_v1_requires_seeded_transition_source() -> None:
    plan = intent()
    empty = SequenceState(
        state_id="empty",
        state_version="1",
        selected_steps=(),
        current_track_id=None,
        current_segment_id=None,
        used_track_ids=(),
        cumulative_duration_seconds=0.0,
        current_energy_state=None,
    )
    empty_context = replace(
        context(),
        current_position_index=0,
        current_track_id=None,
        current_segment_id=None,
    )

    with pytest.raises(ValueError, match="requires a seeded current track"):
        recommend_next(
            intent=plan,
            context=empty_context,
            sequence_state=empty,
            transition_edges=(),
            ranking_policy=balanced_set_ranking_policy_v1(),
            candidate_limit=5,
            generated_at="2026-08-17T00:15:00Z",
        )


def test_required_track_state_must_reconcile_with_intent() -> None:
    plan = intent(required=("track-z",))
    state = replace(
        seeded_state(plan),
        remaining_required_track_ids=(),
    )

    with pytest.raises(ValueError, match="reconcile with PlaylistIntent"):
        run(plan, state, ())
