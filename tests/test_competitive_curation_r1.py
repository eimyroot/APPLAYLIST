from __future__ import annotations

from core.analysis.provider_contract import CanonicalAnalysisResult
from core.intelligence.competitive_curation_contract import (
    CompetitiveCurationStatus,
    ShadowPathPreference,
    TrackCurationEvidence,
)
from core.intelligence.music_dna import build_music_dna
from core.intelligence.set_contract import (
    EligibleLibraryScope,
    EnergyControlPoint,
    EnergyTrajectory,
    PlaylistIntent,
    RangeBand,
    SequenceState,
    SetGoal,
    SetPhase,
    SetPhaseType,
    SetStep,
)
from core.intelligence.set_optimizer_contract import SetPathAlternative, SetPathObjective
from core.intelligence.transition_contract import TransitionStrategy
from services.intelligence.competitive_curation import (
    assess_competitive_curation_path,
    compare_competitive_curation_paths,
    expand_style_tags,
    track_curation_evidence_from_music_dna,
)

PHASE_ID = "phase:peak"


def _intent(*, goal: SetGoal = SetGoal.PEAK_TIME) -> PlaylistIntent:
    return PlaylistIntent(
        intent_id="intent:competitive-test",
        intent_version="1",
        goal=goal,
        eligible_library_scope=EligibleLibraryScope(
            scope_revision="scope:competitive-test",
            explicit_track_ids=None,
        ),
        phase_plan=(
            SetPhase(
                phase_id=PHASE_ID,
                phase_type=SetPhaseType.PEAK,
                ordinal=0,
                target_fraction_start=0.0,
                target_fraction_end=1.0,
                explanation_label="peak",
                target_energy_band=RangeBand(0.76, 1.0),
                style_targets=("House",),
                style_avoid=(),
            ),
        ),
        energy_trajectory=EnergyTrajectory(
            trajectory_id="energy:peak",
            trajectory_version="1",
            control_points=(
                EnergyControlPoint(0.0, 0.86, 0.12, PHASE_ID),
                EnergyControlPoint(1.0, 0.90, 0.12, PHASE_ID),
            ),
        ),
        target_track_count=5,
    )


def _path(
    path_id: str,
    tracks: tuple[str, ...],
    *,
    strategies: tuple[TransitionStrategy | None, ...] | None = None,
) -> SetPathAlternative:
    if strategies is None:
        strategies = tuple(None for _ in tracks)
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
            chosen_strategy=strategies[index],
            local_projection_score=0.80,
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
        current_energy_state=0.86,
        evidence_refs=(f"evidence:{path_id}",),
    )
    return SetPathAlternative(
        path_id=path_id,
        rank=1,
        added_steps=added,
        resulting_state=state,
        transition_ids=tuple(f"transition:{path_id}:{index}" for index in range(len(tracks))),
        candidate_scores=tuple(0.80 for _ in tracks),
        objective=SetPathObjective(
            depth=len(tracks),
            mean_candidate_score=0.80,
            minimum_candidate_score=0.80,
            required_track_completion=1.0,
            remaining_required_count=0,
            target_reached=True,
        ),
        explanation_codes=("source-optimizer-path",),
        evidence_refs=(f"evidence:{path_id}",),
    )


def _track(
    track_id: str,
    style: str | None,
    energy: float | None,
    *,
    percussive: float | None = 0.78,
    harmonic: float | None = 0.42,
    stability: float | None = 0.90,
    phrase_density: float | None = 1.5,
    structure: float | None = 0.75,
) -> TrackCurationEvidence:
    return TrackCurationEvidence(
        track_id=track_id,
        style_tags=None if style is None else (style,),
        baseline_energy=energy,
        percussive_ratio=percussive,
        harmonic_ratio=harmonic,
        beat_stability=stability,
        phrase_boundary_density_per_minute=phrase_density,
        structural_label_diversity=structure,
        vocal_presence=None,
        analysis_revision=f"analysis:{track_id}",
        evidence_refs=(f"evidence:{track_id}",),
    )


def _evidence(values: dict[str, tuple[str | None, float | None]]) -> tuple[TrackCurationEvidence, ...]:
    return tuple(_track(track_id, style, energy) for track_id, (style, energy) in values.items())


def test_style_taxonomy_keeps_house_family_coherent_without_collapsing_rave_techno() -> None:
    tech_house = expand_style_tags(("Tech House",))
    uk_house = expand_style_tags(("UK House",))
    rave_techno = expand_style_tags(("Rave Techno",))

    assert tech_house is not None and {"tech house", "house"} <= tech_house
    assert uk_house is not None and {"uk house", "house"} <= uk_house
    assert rave_techno is not None and {"rave techno", "techno", "rave"} <= rave_techno
    assert "house" not in rave_techno


def test_coherent_house_path_beats_ukg_rave_drift_path() -> None:
    coherent = _path("coherent", ("h1", "h2", "h3", "h4"))
    drift = _path("drift", ("u1", "u2", "r1", "r2"))
    evidence = _evidence(
        {
            "h1": ("House", 0.82),
            "h2": ("Tech House", 0.86),
            "h3": ("UK House", 0.88),
            "h4": ("Tech House", 0.90),
            "u1": ("UKG", 0.82),
            "u2": ("UKG", 0.84),
            "r1": ("Rave Techno", 0.90),
            "r2": ("Rave Techno", 0.92),
        }
    )

    left, right, comparison = compare_competitive_curation_paths(
        left=coherent,
        right=drift,
        intent=_intent(),
        track_evidence=evidence,
    )

    assert left.status is CompetitiveCurationStatus.COMPETITIVE
    assert right.status is CompetitiveCurationStatus.INSUFFICIENT
    assert left.score is not None and right.score is not None
    assert left.score > right.score
    assert comparison.preference is ShadowPathPreference.LEFT
    assert "competitive_non_target_style_run_above_policy" in right.reason_codes
    assert "competitive_unexplained_contrast_above_policy" in right.reason_codes


def test_under_energy_peak_path_is_explicitly_rejected() -> None:
    path = _path("low-energy-peak", ("a", "b", "c", "d"))
    evidence = _evidence(
        {
            "a": ("House", 0.40),
            "b": ("Tech House", 0.44),
            "c": ("House", 0.48),
            "d": ("Tech House", 0.50),
        }
    )

    assessment = assess_competitive_curation_path(
        path=path,
        intent=_intent(),
        track_evidence=evidence,
    )

    assert assessment.status is CompetitiveCurationStatus.INSUFFICIENT
    assert "competitive_energy_trajectory_below_floor" in assessment.reason_codes


def test_repeated_non_target_style_saturation_is_reported() -> None:
    path = _path("saturated", ("h1", "u1", "u2", "u3"))
    evidence = _evidence(
        {
            "h1": ("House", 0.82),
            "u1": ("UKG", 0.84),
            "u2": ("UKG", 0.86),
            "u3": ("UKG", 0.88),
        }
    )

    assessment = assess_competitive_curation_path(
        path=path,
        intent=_intent(),
        track_evidence=evidence,
    )

    assert assessment.status is CompetitiveCurationStatus.INSUFFICIENT
    assert assessment.non_target_run_fraction == 0.75
    assert "competitive_non_target_style_run_above_policy" in assessment.reason_codes


def test_deliberate_contrast_does_not_count_as_unexplained_contrast() -> None:
    path = _path(
        "deliberate",
        ("h1", "h2", "r1", "h3"),
        strategies=(None, None, TransitionStrategy.DELIBERATE_CONTRAST, TransitionStrategy.DELIBERATE_CONTRAST),
    )
    evidence = _evidence(
        {
            "h1": ("House", 0.82),
            "h2": ("Tech House", 0.86),
            "r1": ("Rave Techno", 0.90),
            "h3": ("House", 0.88),
        }
    )

    assessment = assess_competitive_curation_path(
        path=path,
        intent=_intent(goal=SetGoal.STYLE_BRIDGE),
        track_evidence=evidence,
    )

    assert assessment.unexplained_contrast_fraction == 0.0
    assert "competitive_unexplained_contrast_above_policy" not in assessment.reason_codes


def test_missing_style_or_energy_is_fail_closed_not_proven() -> None:
    path = _path("missing", ("a", "b", "c", "d"))
    evidence = _evidence(
        {
            "a": ("House", 0.82),
            "b": (None, 0.84),
            "c": ("House", None),
            "d": ("Tech House", 0.88),
        }
    )

    assessment = assess_competitive_curation_path(
        path=path,
        intent=_intent(),
        track_evidence=evidence,
    )

    assert assessment.status is CompetitiveCurationStatus.NOT_PROVEN_MISSING_EVIDENCE
    assert assessment.score is None
    assert assessment.missing_style_track_ids == ("b",)
    assert assessment.missing_energy_track_ids == ("c",)


def test_near_equivalent_paths_are_shadow_tie() -> None:
    left = _path("left", ("h1", "h2", "h3", "h4"))
    right = _path("right", ("h2", "h1", "h4", "h3"))
    evidence = _evidence(
        {
            "h1": ("House", 0.84),
            "h2": ("Tech House", 0.85),
            "h3": ("House", 0.86),
            "h4": ("Tech House", 0.87),
        }
    )

    _, _, comparison = compare_competitive_curation_paths(
        left=left,
        right=right,
        intent=_intent(),
        track_evidence=evidence,
    )

    assert comparison.preference is ShadowPathPreference.TIE
    assert comparison.activation_authorized is False


def test_shadow_assessment_never_mutates_source_optimizer_truth() -> None:
    path = _path("immutable", ("a", "b", "c", "d"))
    original_rank = path.rank
    original_scores = path.candidate_scores
    original_path_id = path.path_id
    evidence = _evidence(
        {
            "a": ("House", 0.82),
            "b": ("Tech House", 0.84),
            "c": ("House", 0.86),
            "d": ("Tech House", 0.88),
        }
    )

    first = assess_competitive_curation_path(
        path=path,
        intent=_intent(),
        track_evidence=evidence,
    )
    second = assess_competitive_curation_path(
        path=path,
        intent=_intent(),
        track_evidence=evidence,
    )

    assert first == second
    assert path.rank == original_rank
    assert path.candidate_scores == original_scores
    assert path.path_id == original_path_id
    assert first.source_identity_preserved is True
    assert first.activation_authorized is False


def test_music_dna_projection_does_not_fabricate_vocal_evidence() -> None:
    canonical = CanonicalAnalysisResult(
        path="/private/nonexistent.mp3",
        provider="test-provider",
        bpm=128.0,
        bpm_confidence=0.9,
        key="A minor",
        key_confidence=0.8,
        energy=0.84,
        loudness_db=-9.0,
        duration_seconds=300.0,
        genre_hint="Tech House",
        camelot="8A",
        beat_stability=0.91,
        harmonic_ratio=0.40,
        percussive_ratio=0.79,
        provider_version="1",
        algorithm_version="test-v1",
    )
    dna = build_music_dna(
        track_id="track-1",
        content_identity="sha256:content",
        analysis_revision="analysis:1",
        evidence_id="evidence:1",
        input_identity="sha256:input",
        canonical=canonical,
    )

    evidence = track_curation_evidence_from_music_dna(
        music_dna=dna,
        style_tags=("Tech House",),
    )

    assert evidence.baseline_energy == 0.84
    assert evidence.percussive_ratio == 0.79
    assert evidence.harmonic_ratio == 0.40
    assert evidence.beat_stability == 0.91
    assert evidence.vocal_presence is None
    assert evidence.phrase_boundary_density_per_minute is None
    assert evidence.analysis_revision == "analysis:1"
