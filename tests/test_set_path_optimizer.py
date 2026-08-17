from __future__ import annotations

from pathlib import Path

import pytest

from core.analysis.provider_contract import CanonicalAnalysisResult
from core.config.settings import get_settings
from core.intelligence.music_dna import build_music_dna
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
from core.intelligence.set_optimizer_contract import (
    SetOptimizerPolicy,
    SetOptimizerStatus,
)
from data.repositories.music_intelligence_repository import MusicIntelligenceRepository
from services.intelligence.phase_context import transition_context_for_phase
from services.intelligence.set_engine import balanced_set_ranking_policy_v1
from services.intelligence.set_path_optimizer import optimize_set_lookahead
from services.intelligence.transition_engine import (
    assess_transition,
    preserve_groove_context_v1,
)


@pytest.fixture
def isolated_database(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    database_path = tmp_path / "optimizer.sqlite3"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path}")
    get_settings.cache_clear()
    yield database_path
    get_settings.cache_clear()


def _canonical(track_id: str, *, energy: float = 0.6) -> CanonicalAnalysisResult:
    return CanonicalAnalysisResult(
        path=f"/private/music/{track_id}.wav",
        provider="librosa",
        bpm=128.0,
        bpm_confidence=0.90,
        key="8A",
        key_confidence=0.85,
        energy=energy,
        loudness_db=-10.0,
        duration_seconds=300.0,
        genre_hint="techno",
        key_tonic="A",
        key_scale="minor",
        camelot="8A",
        beat_stability=0.92,
        harmonic_ratio=0.55,
        percussive_ratio=0.72,
        provider_version="0.10.2",
        algorithm_version="baseline-librosa-mir-v1",
    )


def _dna(track_id: str, *, energy: float = 0.6):
    return build_music_dna(
        track_id=track_id,
        content_identity=f"sha256:{track_id}",
        analysis_revision=f"analysis:{track_id}:1",
        evidence_id=f"evidence:{track_id}:1",
        input_identity=f"input:{track_id}",
        canonical=_canonical(track_id, energy=energy),
        benchmark_status="benchmark-candidate",
    )


def _phase(phase_id: str = "phase-1", *, ordinal: int = 0, start: float = 0.0, end: float = 1.0) -> SetPhase:
    return SetPhase(
        phase_id=phase_id,
        phase_type=SetPhaseType.GROOVE,
        ordinal=ordinal,
        target_fraction_start=start,
        target_fraction_end=end,
        explanation_label=phase_id,
    )


def _intent(
    *,
    required: tuple[str, ...] = (),
    forbidden: tuple[str, ...] = (),
    target_track_count: int = 5,
    phases: tuple[SetPhase, ...] | None = None,
) -> PlaylistIntent:
    phase_plan = phases or (_phase(),)
    return PlaylistIntent(
        intent_id="intent-optimizer",
        intent_version="1",
        goal=SetGoal.CLUB_FLOW,
        eligible_library_scope=EligibleLibraryScope(
            scope_revision="scope-1",
            explicit_track_ids=("track-a", "track-b", "track-c", "track-d", "track-e"),
        ),
        phase_plan=phase_plan,
        energy_trajectory=EnergyTrajectory(
            trajectory_id="trajectory-1",
            trajectory_version="1",
            control_points=(
                EnergyControlPoint(0.0, 0.55, 0.25, phase_plan[0].phase_id),
                EnergyControlPoint(1.0, 0.75, 0.25, phase_plan[-1].phase_id),
            ),
        ),
        target_track_count=target_track_count,
        required_track_ids=required,
        forbidden_track_ids=forbidden,
    )


def _state(required: tuple[str, ...] = ()) -> SequenceState:
    return SequenceState(
        state_id="state-optimizer",
        state_version="1",
        selected_steps=(
            SetStep(
                order_index=0,
                track_id="track-a",
                segment_id="track-a:whole",
                phase_id="phase-1",
            ),
        ),
        current_track_id="track-a",
        current_segment_id="track-a:whole",
        used_track_ids=("track-a",),
        cumulative_duration_seconds=300.0,
        current_energy_state=0.6,
        satisfied_required_track_ids=(),
        remaining_required_track_ids=required,
        evidence_refs=("evidence:track-a:1",),
    )


def _context() -> PlaylistContext:
    return PlaylistContext(
        context_id="playlist-context",
        context_version="1",
        current_phase_id="phase-1",
        current_position_index=0,
        elapsed_duration_seconds=300.0,
        phase_progress=0.0,
        current_track_id="track-a",
        current_segment_id="track-a:whole",
        current_energy_state=0.6,
        remaining_track_count=4,
        context_evidence_refs=("context:evidence:1",),
    )


def _assessment(source_id: str, target_id: str, transition_context, *, energy: float = 0.6):
    return assess_transition(
        source=_dna(source_id, energy=energy),
        source_segment_id=f"{source_id}:whole",
        target=_dna(target_id, energy=energy),
        target_segment_id=f"{target_id}:whole",
        context=transition_context,
        created_at="2026-08-17T01:00:00Z",
    )


def _persist(repo: MusicIntelligenceRepository, transition_context, *pairs: tuple[str, str]) -> None:
    for source_id, target_id in pairs:
        repo.append_transition_assessment(_assessment(source_id, target_id, transition_context))


def _run(
    *,
    repo: MusicIntelligenceRepository,
    intent: PlaylistIntent,
    state: SequenceState,
    policy: SetOptimizerPolicy,
    durations: dict[str, float],
):
    return optimize_set_lookahead(
        repository=repo,
        intent=intent,
        root_context=_context(),
        root_state=state,
        base_transition_context=preserve_groove_context_v1(),
        ranking_policy=balanced_set_ranking_policy_v1(),
        optimizer_policy=policy,
        target_duration_seconds_by_track=durations,
        generated_at="2026-08-17T01:00:00Z",
    )


def test_optimizer_is_deterministic_and_prioritizes_required_progress(isolated_database: Path) -> None:
    repo = MusicIntelligenceRepository()
    intent = _intent(required=("track-c",), target_track_count=5)
    context = transition_context_for_phase(
        phase=intent.phase("phase-1"),
        base_context=preserve_groove_context_v1(),
    )
    _persist(
        repo,
        context,
        ("track-a", "track-b"),
        ("track-a", "track-c"),
        ("track-b", "track-d"),
        ("track-c", "track-d"),
    )
    kwargs = dict(
        repo=repo,
        intent=intent,
        state=_state(("track-c",)),
        policy=SetOptimizerPolicy(beam_width=2, max_depth=2, alternative_limit=2),
        durations={"track-b": 300.0, "track-c": 300.0, "track-d": 300.0},
    )
    first = _run(**kwargs)
    second = _run(**kwargs)
    assert first == second
    assert first.status is SetOptimizerStatus.PATHS_FOUND
    assert first.alternatives[0].added_steps[0].track_id == "track-c"
    assert first.alternatives[0].objective.required_track_completion == 1.0


def test_optimizer_reuses_set_hard_gates_for_forbidden_tracks(isolated_database: Path) -> None:
    repo = MusicIntelligenceRepository()
    intent = _intent(forbidden=("track-b",))
    context = transition_context_for_phase(
        phase=intent.phase("phase-1"),
        base_context=preserve_groove_context_v1(),
    )
    _persist(repo, context, ("track-a", "track-b"), ("track-a", "track-c"))
    result = _run(
        repo=repo,
        intent=intent,
        state=_state(),
        policy=SetOptimizerPolicy(beam_width=2, max_depth=1, alternative_limit=2),
        durations={"track-b": 300.0, "track-c": 300.0},
    )
    assert result.status is SetOptimizerStatus.PATHS_FOUND
    assert tuple(item.added_steps[0].track_id for item in result.alternatives) == ("track-c",)


def test_optimizer_switches_to_persisted_phase_context_between_depths(isolated_database: Path) -> None:
    repo = MusicIntelligenceRepository()
    phases = (
        _phase("phase-1", ordinal=0, start=0.0, end=0.5),
        _phase("phase-2", ordinal=1, start=0.5, end=1.0),
    )
    intent = _intent(target_track_count=4, phases=phases)
    base_context = preserve_groove_context_v1()
    phase_1_context = transition_context_for_phase(phase=phases[0], base_context=base_context)
    phase_2_context = transition_context_for_phase(phase=phases[1], base_context=base_context)
    _persist(repo, phase_1_context, ("track-a", "track-b"))
    _persist(repo, phase_2_context, ("track-b", "track-c"))

    result = _run(
        repo=repo,
        intent=intent,
        state=_state(),
        policy=SetOptimizerPolicy(beam_width=2, max_depth=2, alternative_limit=2),
        durations={"track-b": 300.0, "track-c": 300.0},
    )
    assert result.status is SetOptimizerStatus.PATHS_FOUND
    assert tuple(step.track_id for step in result.alternatives[0].added_steps) == (
        "track-b",
        "track-c",
    )
    assert tuple(step.phase_id for step in result.alternatives[0].added_steps) == (
        "phase-1",
        "phase-2",
    )


def test_optimizer_reports_missing_duration_evidence_instead_of_false_dead_end(isolated_database: Path) -> None:
    repo = MusicIntelligenceRepository()
    intent = _intent()
    context = transition_context_for_phase(
        phase=intent.phase("phase-1"),
        base_context=preserve_groove_context_v1(),
    )
    _persist(repo, context, ("track-a", "track-b"))
    result = _run(
        repo=repo,
        intent=intent,
        state=_state(),
        policy=SetOptimizerPolicy(beam_width=2, max_depth=1, alternative_limit=2),
        durations={},
    )
    assert result.status is SetOptimizerStatus.NOT_PROVEN_MISSING_EVIDENCE
    assert result.missing_evidence_detected is True
    assert result.alternatives == ()


def test_optimizer_records_beam_pruning_and_returns_top_n(isolated_database: Path) -> None:
    repo = MusicIntelligenceRepository()
    intent = _intent()
    context = transition_context_for_phase(
        phase=intent.phase("phase-1"),
        base_context=preserve_groove_context_v1(),
    )
    _persist(
        repo,
        context,
        ("track-a", "track-b"),
        ("track-a", "track-c"),
        ("track-a", "track-d"),
    )
    result = _run(
        repo=repo,
        intent=intent,
        state=_state(),
        policy=SetOptimizerPolicy(beam_width=2, max_depth=1, alternative_limit=2),
        durations={"track-b": 300.0, "track-c": 300.0, "track-d": 300.0},
    )
    assert len(result.alternatives) == 2
    assert result.beam_pruned_candidates == 1
    assert tuple(item.rank for item in result.alternatives) == (1, 2)


def test_optimizer_marks_target_reached_when_horizon_completes_set(isolated_database: Path) -> None:
    repo = MusicIntelligenceRepository()
    intent = _intent(target_track_count=2)
    context = transition_context_for_phase(
        phase=intent.phase("phase-1"),
        base_context=preserve_groove_context_v1(),
    )
    _persist(repo, context, ("track-a", "track-b"))
    result = _run(
        repo=repo,
        intent=intent,
        state=_state(),
        policy=SetOptimizerPolicy(beam_width=2, max_depth=2, alternative_limit=2),
        durations={"track-b": 300.0},
    )
    assert result.status is SetOptimizerStatus.TARGET_REACHED
    assert result.alternatives[0].objective.target_reached is True
    assert result.alternatives[0].added_steps[0].track_id == "track-b"


def test_optimizer_budget_exhaustion_preserves_explored_partial_path(isolated_database: Path) -> None:
    repo = MusicIntelligenceRepository()
    intent = _intent()
    context = transition_context_for_phase(
        phase=intent.phase("phase-1"),
        base_context=preserve_groove_context_v1(),
    )
    _persist(repo, context, ("track-a", "track-b"), ("track-a", "track-c"))

    result = _run(
        repo=repo,
        intent=intent,
        state=_state(),
        policy=SetOptimizerPolicy(
            beam_width=2,
            max_depth=2,
            max_expanded_candidates=1,
            alternative_limit=2,
        ),
        durations={"track-b": 300.0, "track-c": 300.0},
    )

    assert result.status is SetOptimizerStatus.BUDGET_EXHAUSTED
    assert result.budget_exhausted is True
    assert result.expanded_candidates == 1
    assert result.deepest_depth == 1
    assert len(result.alternatives) == 1
    assert result.alternatives[0].added_steps[0].track_id == "track-b"
