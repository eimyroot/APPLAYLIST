from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from core.analysis.provider_contract import CanonicalAnalysisResult
from core.config.settings import get_settings
from core.intelligence.feasibility_contract import (
    FeasibilityPolicy,
    FeasibilityStatus,
)
from core.intelligence.music_dna import build_music_dna
from core.intelligence.set_contract import (
    EligibleLibraryScope,
    EnergyControlPoint,
    EnergyTrajectory,
    PlaylistIntent,
    SequenceState,
    SetGoal,
    SetPhase,
    SetPhaseType,
    SetStep,
)
from core.intelligence.transition_contract import TransitionStrategy
from data.repositories.music_intelligence_repository import MusicIntelligenceRepository
from services.intelligence.feasibility import evaluate_future_feasibility
from services.intelligence.phase_context import transition_context_for_phase
from services.intelligence.transition_engine import (
    assess_transition,
    preserve_groove_context_v1,
)


@pytest.fixture
def isolated_database(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    database_path = tmp_path / "music-intelligence.sqlite3"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path}")
    get_settings.cache_clear()
    yield database_path
    get_settings.cache_clear()


def _canonical(track_id: str, *, bpm: float = 128.0, energy: float = 0.6) -> CanonicalAnalysisResult:
    return CanonicalAnalysisResult(
        path=f"/private/music/{track_id}.wav",
        provider="librosa",
        bpm=bpm,
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


def _dna(track_id: str, *, bpm: float = 128.0, energy: float = 0.6):
    return build_music_dna(
        track_id=track_id,
        content_identity=f"sha256:{track_id}",
        analysis_revision=f"analysis:{track_id}:1",
        evidence_id=f"evidence:{track_id}:1",
        input_identity=f"input:{track_id}",
        canonical=_canonical(track_id, bpm=bpm, energy=energy),
        benchmark_status="benchmark-candidate",
    )


def _phase(*, forbidden: tuple[TransitionStrategy, ...] = (), preferred: tuple[TransitionStrategy, ...] = ()) -> SetPhase:
    return SetPhase(
        phase_id="phase-1",
        phase_type=SetPhaseType.GROOVE,
        ordinal=0,
        target_fraction_start=0.0,
        target_fraction_end=1.0,
        explanation_label="Groove",
        forbidden_transition_strategies=forbidden,
        preferred_transition_strategies=preferred,
    )


def _intent(
    required: tuple[str, ...],
    *,
    explicit_scope: tuple[str, ...] = ("track-a", "track-b", "track-c", "track-d"),
    target_duration_seconds: float | None = None,
) -> PlaylistIntent:
    phase = _phase()
    return PlaylistIntent(
        intent_id="intent-1",
        intent_version="1",
        goal=SetGoal.CLUB_FLOW,
        eligible_library_scope=EligibleLibraryScope(
            scope_revision="scope-1",
            explicit_track_ids=explicit_scope,
        ),
        phase_plan=(phase,),
        energy_trajectory=EnergyTrajectory(
            trajectory_id="energy-1",
            trajectory_version="1",
            control_points=(
                EnergyControlPoint(0.0, 0.5, 0.2, phase.phase_id),
                EnergyControlPoint(1.0, 0.8, 0.2, phase.phase_id),
            ),
        ),
        target_track_count=6,
        target_duration_seconds=target_duration_seconds,
        required_track_ids=required,
    )


def _state(required: tuple[str, ...]) -> SequenceState:
    return SequenceState(
        state_id="state-1",
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


def _assessment(source_id: str, target_id: str, context):
    source = _dna(source_id, bpm=128.0)
    target = _dna(target_id, bpm=129.0)
    return assess_transition(
        source=source,
        source_segment_id=f"{source_id}:whole",
        target=target,
        target_segment_id=f"{target_id}:whole",
        context=context,
        created_at="2026-08-17T00:00:00Z",
    )


def test_transition_snapshot_round_trip_is_context_aware_and_idempotent(
    isolated_database: Path,
) -> None:
    repo = MusicIntelligenceRepository()
    phase = _phase()
    context = transition_context_for_phase(
        phase=phase,
        base_context=preserve_groove_context_v1(),
    )
    assessment = _assessment("track-a", "track-b", context)

    snapshot_id = repo.append_transition_assessment(assessment)
    assert repo.append_transition_assessment(assessment) == snapshot_id
    assert repo.get_transition_snapshot(snapshot_id) == assessment
    assert repo.list_outgoing(
        source_track_id="track-a",
        source_segment_id="track-a:whole",
        context_id=context.context_id,
        context_version=context.context_version,
    ) == (assessment,)
    assert isolated_database.exists()


def test_transition_snapshot_rejects_same_context_identity_with_changed_payload(
    isolated_database: Path,
) -> None:
    repo = MusicIntelligenceRepository()
    context = transition_context_for_phase(
        phase=_phase(),
        base_context=preserve_groove_context_v1(),
    )
    assessment = _assessment("track-a", "track-b", context)
    repo.append_transition_assessment(assessment)

    with pytest.raises(ValueError, match="immutable transition assessment snapshot collision"):
        repo.append_transition_assessment(replace(assessment, warnings=("changed",)))


def test_same_transition_relation_can_persist_under_two_explicit_contexts(
    isolated_database: Path,
) -> None:
    repo = MusicIntelligenceRepository()
    base = preserve_groove_context_v1()
    phase_a = _phase()
    phase_b = replace(phase_a, phase_id="phase-2", explanation_label="Peak")
    context_a = transition_context_for_phase(phase=phase_a, base_context=base)
    context_b = transition_context_for_phase(phase=phase_b, base_context=base)
    first = _assessment("track-a", "track-b", context_a)
    second = _assessment("track-a", "track-b", context_b)

    assert first.identity.transition_id == second.identity.transition_id
    assert repo.append_transition_assessment(first) != repo.append_transition_assessment(second)
    assert repo.list_outgoing(
        source_track_id="track-a",
        source_segment_id="track-a:whole",
        context_id=context_a.context_id,
        context_version=context_a.context_version,
    ) == (first,)
    assert repo.list_outgoing(
        source_track_id="track-a",
        source_segment_id="track-a:whole",
        context_id=context_b.context_id,
        context_version=context_b.context_version,
    ) == (second,)


def test_sequence_state_persistence_is_immutable_and_round_trips(
    isolated_database: Path,
) -> None:
    repo = MusicIntelligenceRepository()
    state = _state(("track-c",))
    repo.append_sequence_state(state)
    repo.append_sequence_state(state)
    assert repo.get_sequence_state(state.state_id, state.state_version) == state

    with pytest.raises(ValueError, match="immutable sequence state identity collision"):
        repo.append_sequence_state(replace(state, warnings=("changed",)))


def test_phase_context_mapping_only_narrows_explicit_strategy_hard_gate() -> None:
    base = preserve_groove_context_v1()
    phase = _phase(
        forbidden=(TransitionStrategy.CUT,),
        preferred=(TransitionStrategy.LONG_BLEND,),
    )
    mapped = transition_context_for_phase(phase=phase, base_context=base)

    assert mapped.context_id == "preserve-groove:phase:phase-1"
    assert mapped.context_version.startswith("phase-transition-context-v1:")
    assert TransitionStrategy.CUT not in mapped.allowed_strategies
    assert TransitionStrategy.LONG_BLEND in mapped.allowed_strategies
    assert mapped.max_tempo_change_percent == base.max_tempo_change_percent
    assert mapped.minimum_harmonic_fit == base.minimum_harmonic_fit
    assert mapped.require_phrase_evidence == base.require_phrase_evidence
    assert mapped.weights == base.weights
    assert mapped.goal == base.goal


def test_phase_context_mapping_fails_closed_if_every_strategy_is_forbidden() -> None:
    base = preserve_groove_context_v1()
    phase = _phase(forbidden=base.allowed_strategies)
    with pytest.raises(ValueError, match="removed every allowed"):
        transition_context_for_phase(phase=phase, base_context=base)


def test_bounded_feasibility_proves_required_track_reachable(
    isolated_database: Path,
) -> None:
    repo = MusicIntelligenceRepository()
    context = transition_context_for_phase(
        phase=_phase(),
        base_context=preserve_groove_context_v1(),
    )
    repo.append_transition_assessment(_assessment("track-a", "track-b", context))
    repo.append_transition_assessment(_assessment("track-b", "track-c", context))
    required = ("track-c",)

    result = evaluate_future_feasibility(
        repository=repo,
        sequence_state=_state(required),
        intent=_intent(required),
        transition_context=context,
        policy=FeasibilityPolicy(max_depth=3, max_expanded_states=20),
    )

    assert result.status is FeasibilityStatus.REACHABLE
    assert result.score == 1.0
    assert result.reached_required_track_ids == required
    assert result.unresolved_required_track_ids == ()


def test_depth_limit_is_not_misreported_as_infeasible(
    isolated_database: Path,
) -> None:
    repo = MusicIntelligenceRepository()
    context = transition_context_for_phase(
        phase=_phase(),
        base_context=preserve_groove_context_v1(),
    )
    repo.append_transition_assessment(_assessment("track-a", "track-b", context))
    repo.append_transition_assessment(_assessment("track-b", "track-c", context))
    required = ("track-c",)

    result = evaluate_future_feasibility(
        repository=repo,
        sequence_state=_state(required),
        intent=_intent(required),
        transition_context=context,
        policy=FeasibilityPolicy(max_depth=1, max_expanded_states=20),
    )

    assert result.status is FeasibilityStatus.NOT_PROVEN_WITHIN_BUDGET
    assert result.score is None
    assert result.budget_exhausted is True
    assert "lookahead_depth_exhausted" in result.explanation_codes


def test_exhausted_complete_frontier_is_infeasible(
    isolated_database: Path,
) -> None:
    repo = MusicIntelligenceRepository()
    context = transition_context_for_phase(
        phase=_phase(),
        base_context=preserve_groove_context_v1(),
    )
    repo.append_transition_assessment(_assessment("track-a", "track-b", context))
    required = ("track-c",)

    result = evaluate_future_feasibility(
        repository=repo,
        sequence_state=_state(required),
        intent=_intent(required),
        transition_context=context,
        policy=FeasibilityPolicy(max_depth=3, max_expanded_states=20),
    )

    assert result.status is FeasibilityStatus.INFEASIBLE
    assert result.score == 0.0
    assert result.budget_exhausted is False


def test_missing_duration_evidence_is_not_misreported_as_infeasible(
    isolated_database: Path,
) -> None:
    context = transition_context_for_phase(
        phase=_phase(),
        base_context=preserve_groove_context_v1(),
    )
    required = ("track-c",)
    result = evaluate_future_feasibility(
        repository=MusicIntelligenceRepository(),
        sequence_state=_state(required),
        intent=_intent(required, target_duration_seconds=1800.0),
        transition_context=context,
        policy=FeasibilityPolicy(),
    )

    assert result.status is FeasibilityStatus.NOT_PROVEN_MISSING_EVIDENCE
    assert result.score is None
    assert "duration_evidence_required_for_bounded_feasibility" in result.explanation_codes
