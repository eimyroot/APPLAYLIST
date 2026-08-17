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
    SetOptimizerResult,
    SetOptimizerStatus,
    SetPathAlternative,
    SetPathObjective,
)
from core.intelligence.set_optimizer_evaluation_contract import AlternativeDiversityPolicy
from data.repositories.music_intelligence_repository import MusicIntelligenceRepository
from services.intelligence.alternative_diversity import select_diverse_alternatives
from services.intelligence.phase_context import transition_context_for_phase
from services.intelligence.set_engine import balanced_set_ranking_policy_v1
from services.intelligence.set_optimizer_benchmark import benchmark_greedy_vs_beam
from services.intelligence.transition_engine import (
    assess_transition,
    preserve_groove_context_v1,
)


@pytest.fixture
def isolated_database(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    database_path = tmp_path / "optimizer-benchmark.sqlite3"
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


def _phase() -> SetPhase:
    return SetPhase(
        phase_id="phase-1",
        phase_type=SetPhaseType.GROOVE,
        ordinal=0,
        target_fraction_start=0.0,
        target_fraction_end=1.0,
        explanation_label="phase-1",
    )


def _intent(*, target_track_count: int = 3) -> PlaylistIntent:
    phase = _phase()
    return PlaylistIntent(
        intent_id="intent-benchmark",
        intent_version="1",
        goal=SetGoal.CLUB_FLOW,
        eligible_library_scope=EligibleLibraryScope(
            scope_revision="scope-1",
            explicit_track_ids=("track-a", "track-b", "track-c", "track-d"),
        ),
        phase_plan=(phase,),
        energy_trajectory=EnergyTrajectory(
            trajectory_id="trajectory-1",
            trajectory_version="1",
            control_points=(
                EnergyControlPoint(0.0, 0.60, 0.25, phase.phase_id),
                EnergyControlPoint(1.0, 0.60, 0.25, phase.phase_id),
            ),
        ),
        target_track_count=target_track_count,
    )


def _state() -> SequenceState:
    return SequenceState(
        state_id="state-benchmark",
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
        remaining_required_track_ids=(),
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
        remaining_track_count=2,
        context_evidence_refs=("context:evidence:1",),
    )


def _assessment(source_id: str, target_id: str, transition_context):
    return assess_transition(
        source=_dna(source_id),
        source_segment_id=f"{source_id}:whole",
        target=_dna(target_id),
        target_segment_id=f"{target_id}:whole",
        context=transition_context,
        created_at="2026-08-17T01:00:00Z",
    )


def _persist(repo: MusicIntelligenceRepository, transition_context, *pairs: tuple[str, str]) -> None:
    for source_id, target_id in pairs:
        repo.append_transition_assessment(_assessment(source_id, target_id, transition_context))


def _fake_alternative(path_id: str, rank: int, tracks: tuple[str, ...]) -> SetPathAlternative:
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
    resulting = SequenceState(
        state_id=f"state:{path_id}",
        state_version="1",
        selected_steps=(root, *added),
        current_track_id=tracks[-1],
        current_segment_id=f"{tracks[-1]}:whole",
        used_track_ids=("root", *tracks),
        cumulative_duration_seconds=300.0 * (len(tracks) + 1),
        current_energy_state=0.6,
        satisfied_required_track_ids=(),
        remaining_required_track_ids=(),
        evidence_refs=(f"evidence:{path_id}",),
    )
    return SetPathAlternative(
        path_id=path_id,
        rank=rank,
        added_steps=added,
        resulting_state=resulting,
        transition_ids=tuple(f"transition:{path_id}:{index}" for index in range(len(tracks))),
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


def _fake_result() -> SetOptimizerResult:
    alternatives = (
        _fake_alternative("path-1", 1, ("track-b", "track-c", "track-d")),
        _fake_alternative("path-2", 2, ("track-b", "track-c", "track-e")),
        _fake_alternative("path-3", 3, ("track-f", "track-g", "track-h")),
    )
    return SetOptimizerResult(
        result_id="result-diversity",
        input_fingerprint="fingerprint-diversity",
        optimizer_ref=("bounded-beam-lookahead", "bounded-beam-lookahead-v1"),
        intent_ref=("intent", "1"),
        root_state_ref=("state", "1"),
        base_transition_context_ref=("context", "1"),
        status=SetOptimizerStatus.TARGET_REACHED,
        alternatives=alternatives,
        deepest_depth=3,
        expanded_candidates=12,
        beam_pruned_candidates=2,
        budget_exhausted=False,
        missing_evidence_detected=False,
        deterministic_ordering=True,
    )


def test_diversity_preserves_best_path_and_filters_near_duplicate() -> None:
    policy = AlternativeDiversityPolicy(
        alternative_limit=3,
        max_track_jaccard=0.75,
        max_shared_prefix_fraction=0.50,
        minimum_differing_positions=1,
    )
    first = select_diverse_alternatives(result=_fake_result(), policy=policy)
    second = select_diverse_alternatives(result=_fake_result(), policy=policy)

    assert first == second
    assert tuple(item.path_id for item in first.selected_alternatives) == (
        "path-1",
        "path-3",
    )
    assert tuple(item.rank for item in first.selected_alternatives) == (1, 2)
    rejected = next(item for item in first.decisions if item.path_id == "path-2")
    assert rejected.selected is False
    assert "shared_prefix_above_policy" in rejected.reason_codes
    assert first.similarity_fallback_used is False


def test_diversity_fallback_is_explicit_not_silent() -> None:
    policy = AlternativeDiversityPolicy(
        alternative_limit=3,
        max_shared_prefix_fraction=0.50,
        allow_similarity_fallback=True,
    )
    selection = select_diverse_alternatives(result=_fake_result(), policy=policy)

    assert len(selection.selected_alternatives) == 3
    assert selection.similarity_fallback_used is True
    fallback = next(item for item in selection.decisions if item.path_id == "path-2")
    assert fallback.selected is True
    assert fallback.reason_codes == ("similarity_fallback_selected",)


def test_benchmark_exposes_case_where_beam_reaches_target_and_greedy_misses(
    isolated_database: Path,
) -> None:
    repo = MusicIntelligenceRepository()
    intent = _intent(target_track_count=3)
    base_context = preserve_groove_context_v1()
    phase_context = transition_context_for_phase(
        phase=intent.phase("phase-1"),
        base_context=base_context,
    )

    # Equal A->B and A->C evidence makes stable target identity choose B first.
    # B is a dead end. Beam keeps C alive and can discover C->D.
    _persist(
        repo,
        phase_context,
        ("track-a", "track-b"),
        ("track-a", "track-c"),
        ("track-c", "track-d"),
    )

    comparison = benchmark_greedy_vs_beam(
        repository=repo,
        intent=intent,
        root_context=_context(),
        root_state=_state(),
        base_transition_context=base_context,
        ranking_policy=balanced_set_ranking_policy_v1(),
        beam_policy=SetOptimizerPolicy(
            beam_width=2,
            max_depth=2,
            per_state_candidate_limit=2,
            max_expanded_candidates=20,
            alternative_limit=2,
        ),
        diversity_policy=AlternativeDiversityPolicy(alternative_limit=2),
        target_duration_seconds_by_track={
            "track-b": 300.0,
            "track-c": 300.0,
            "track-d": 300.0,
        },
        generated_at="2026-08-17T01:00:00Z",
    )

    assert comparison.greedy.deterministic_replay_match is True
    assert comparison.beam.deterministic_replay_match is True
    assert comparison.greedy.target_reached is False
    assert comparison.beam.target_reached is True
    assert comparison.beam_reaches_target_when_greedy_does_not is True
    assert comparison.beam.status is SetOptimizerStatus.TARGET_REACHED
    assert comparison.activation_authorized is False
    assert "beam_reached_target_greedy_missed" in comparison.explanation_codes


def test_benchmark_rejects_diversity_limit_above_available_beam_alternatives(
    isolated_database: Path,
) -> None:
    with pytest.raises(ValueError, match="diversity alternative_limit"):
        benchmark_greedy_vs_beam(
            repository=MusicIntelligenceRepository(),
            intent=_intent(),
            root_context=_context(),
            root_state=_state(),
            base_transition_context=preserve_groove_context_v1(),
            ranking_policy=balanced_set_ranking_policy_v1(),
            beam_policy=SetOptimizerPolicy(beam_width=2, alternative_limit=1),
            diversity_policy=AlternativeDiversityPolicy(alternative_limit=2),
            target_duration_seconds_by_track={},
            generated_at="2026-08-17T01:00:00Z",
        )
