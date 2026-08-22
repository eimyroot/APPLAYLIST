from __future__ import annotations

from dataclasses import replace

import pytest

from core.intelligence.meaningful_diversity_contract import (
    MeaningfulDiversityPolicy,
    MeaningfulDiversityStatus,
    TrackMusicalEvidence,
)
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
from core.intelligence.set_optimizer_contract import (
    SetOptimizerResult,
    SetOptimizerStatus,
    SetPathAlternative,
    SetPathObjective,
)
from services.intelligence.meaningful_diversity import (
    select_meaningfully_diverse_alternatives,
)


def _intent(
    *,
    style_targets: tuple[str, ...] = ("house",),
    style_avoid: tuple[str, ...] = ("rave techno",),
    target_energy: float = 0.65,
) -> PlaylistIntent:
    phase = SetPhase(
        phase_id="main",
        phase_type=SetPhaseType.GROOVE,
        ordinal=0,
        target_fraction_start=0.0,
        target_fraction_end=1.0,
        explanation_label="Main body",
        target_energy_band=RangeBand(max(0.0, target_energy - 0.20), min(1.0, target_energy + 0.20)),
        style_targets=style_targets,
        style_avoid=style_avoid,
    )
    return PlaylistIntent(
        intent_id="intent-meaningful-diversity-r1",
        intent_version="1",
        goal=SetGoal.CLUB_FLOW,
        eligible_library_scope=EligibleLibraryScope(scope_revision="scope-1"),
        phase_plan=(phase,),
        energy_trajectory=EnergyTrajectory(
            trajectory_id="energy-main",
            trajectory_version="1",
            control_points=(
                EnergyControlPoint(0.0, target_energy, 0.15, "main"),
                EnergyControlPoint(1.0, target_energy, 0.15, "main"),
            ),
        ),
        target_track_count=8,
    )


def _path(path_id: str, rank: int, tracks: tuple[str, ...]) -> SetPathAlternative:
    root = SetStep(
        order_index=0,
        track_id="root",
        segment_id="root:whole",
        phase_id="main",
    )
    added = tuple(
        SetStep(
            order_index=index + 1,
            track_id=track_id,
            segment_id=f"{track_id}:whole",
            phase_id="main",
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
        current_energy_state=0.65,
        evidence_refs=(f"evidence:{path_id}",),
    )
    return SetPathAlternative(
        path_id=path_id,
        rank=rank,
        added_steps=added,
        resulting_state=state,
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


def _result(*paths: SetPathAlternative) -> SetOptimizerResult:
    return SetOptimizerResult(
        result_id="optimizer-result-r1",
        input_fingerprint="optimizer-input-r1",
        optimizer_ref=("bounded-beam-lookahead", "bounded-beam-lookahead-v1"),
        intent_ref=("intent-meaningful-diversity-r1", "1"),
        root_state_ref=("state-root", "1"),
        base_transition_context_ref=("context", "1"),
        status=SetOptimizerStatus.TARGET_REACHED,
        alternatives=tuple(paths),
        deepest_depth=max(len(item.added_steps) for item in paths),
        expanded_candidates=20,
        beam_pruned_candidates=3,
        budget_exhausted=False,
        missing_evidence_detected=False,
        deterministic_ordering=True,
    )


def _evidence(
    track_id: str,
    tags: tuple[str, ...] | None,
    energy: float | None,
) -> TrackMusicalEvidence:
    return TrackMusicalEvidence(
        track_id=track_id,
        style_tags=tags,
        energy=energy,
        evidence_refs=(f"music-dna:{track_id}",),
    )


def test_technically_different_but_musically_near_equivalent_is_rejected() -> None:
    path_a = _path("path-a", 1, ("a", "b", "c"))
    path_b = _path("path-b", 2, ("c", "a", "b"))
    evidence = (
        _evidence("a", ("house", "uk house"), 0.62),
        _evidence("b", ("house", "uk house"), 0.64),
        _evidence("c", ("house", "uk house"), 0.66),
    )
    selection = select_meaningfully_diverse_alternatives(
        result=_result(path_a, path_b),
        intent=_intent(),
        track_evidence=evidence,
        policy=MeaningfulDiversityPolicy(
            minimum_meaningful_distance=0.20,
            maximum_non_target_style_concentration=1.0,
        ),
    )

    assert selection.status is MeaningfulDiversityStatus.INSUFFICIENT_MEANINGFUL_DIVERSITY
    assert tuple(item.path_id for item in selection.selected_alternatives) == ("path-a",)
    pair = selection.pairwise_comparisons[0]
    assert pair.technically_different is True
    assert pair.meaningful is False
    assert pair.meaningful_distance is not None
    assert pair.meaningful_distance < 0.20
    assert "insufficient_meaningful_musical_distance" in pair.reason_codes


def test_meaningfully_different_coherent_alternative_is_selected_without_reranking() -> None:
    path_a = _path("path-a", 1, ("a", "b", "c"))
    path_b = _path("path-b", 2, ("d", "e", "f"))
    evidence = (
        _evidence("a", ("house", "uk house"), 0.58),
        _evidence("b", ("house", "uk house"), 0.62),
        _evidence("c", ("house", "uk house"), 0.66),
        _evidence("d", ("house", "tech house"), 0.66),
        _evidence("e", ("house", "tech house"), 0.68),
        _evidence("f", ("house", "tech house"), 0.70),
    )
    selection = select_meaningfully_diverse_alternatives(
        result=_result(path_a, path_b),
        intent=_intent(),
        track_evidence=evidence,
        policy=MeaningfulDiversityPolicy(
            minimum_meaningful_distance=0.20,
            maximum_non_target_style_concentration=1.0,
        ),
    )

    assert selection.status is MeaningfulDiversityStatus.SUFFICIENT
    assert tuple((item.path_id, item.rank) for item in selection.selected_alternatives) == (
        ("path-a", 1),
        ("path-b", 2),
    )
    assert selection.activation_authorized is False
    assert selection.pairwise_comparisons[0].meaningful is True


def test_style_drift_and_avoided_style_fail_coherence() -> None:
    path = _path("path-a", 1, ("a", "b", "c", "d"))
    evidence = (
        _evidence("a", ("house", "uk house"), 0.60),
        _evidence("b", ("house", "uk house"), 0.62),
        _evidence("c", ("rave techno",), 0.76),
        _evidence("d", ("rave techno",), 0.78),
    )
    selection = select_meaningfully_diverse_alternatives(
        result=_result(path),
        intent=_intent(),
        track_evidence=evidence,
    )

    assessment = selection.coherence_assessments[0]
    assert assessment.coherence_pass is False
    assert assessment.style_drift_fraction is not None
    assert assessment.style_drift_fraction > 0.0
    assert "style_drift_above_policy" in assessment.reason_codes
    assert "style_avoid_fraction_above_policy" in assessment.reason_codes


def test_non_target_style_saturation_is_reported() -> None:
    path = _path("path-a", 1, ("a", "b", "c", "d"))
    evidence = tuple(
        _evidence(track_id, ("house", "ukg"), 0.64)
        for track_id in ("a", "b", "c", "d")
    )
    selection = select_meaningfully_diverse_alternatives(
        result=_result(path),
        intent=_intent(),
        track_evidence=evidence,
    )

    assessment = selection.coherence_assessments[0]
    assert assessment.non_target_style_concentration == 1.0
    assert "non_target_style_concentration_above_policy" in assessment.reason_codes


def test_peak_energy_mismatch_fails_coherence() -> None:
    path = _path("path-a", 1, ("a", "b", "c"))
    evidence = tuple(
        _evidence(track_id, ("house",), 0.35)
        for track_id in ("a", "b", "c")
    )
    selection = select_meaningfully_diverse_alternatives(
        result=_result(path),
        intent=_intent(target_energy=0.85),
        track_evidence=evidence,
    )

    assessment = selection.coherence_assessments[0]
    assert assessment.energy_coherence is not None
    assert assessment.energy_coherence < 0.55
    assert "energy_coherence_below_policy" in assessment.reason_codes


def test_missing_musical_evidence_is_fail_closed_not_positive_signal() -> None:
    path_a = _path("path-a", 1, ("a", "b"))
    path_b = _path("path-b", 2, ("b", "a"))
    evidence = (
        _evidence("a", ("house",), 0.62),
        _evidence("b", None, None),
    )
    selection = select_meaningfully_diverse_alternatives(
        result=_result(path_a, path_b),
        intent=_intent(),
        track_evidence=evidence,
    )

    assert selection.status is MeaningfulDiversityStatus.NOT_PROVEN_MISSING_EVIDENCE
    assert tuple(item.path_id for item in selection.selected_alternatives) == ("path-a",)
    assert any(
        "missing_style_evidence" in item.reason_codes
        or "missing_energy_evidence" in item.reason_codes
        for item in selection.coherence_assessments
    )


def test_selection_is_deterministic_for_identical_inputs() -> None:
    path_a = _path("path-a", 1, ("a", "b", "c"))
    path_b = _path("path-b", 2, ("d", "e", "f"))
    evidence = (
        _evidence("a", ("house", "uk house"), 0.58),
        _evidence("b", ("house", "uk house"), 0.62),
        _evidence("c", ("house", "uk house"), 0.66),
        _evidence("d", ("house", "tech house"), 0.66),
        _evidence("e", ("house", "tech house"), 0.68),
        _evidence("f", ("house", "tech house"), 0.70),
    )
    policy = MeaningfulDiversityPolicy(maximum_non_target_style_concentration=1.0)
    first = select_meaningfully_diverse_alternatives(
        result=_result(path_a, path_b),
        intent=_intent(),
        track_evidence=evidence,
        policy=policy,
    )
    second = select_meaningfully_diverse_alternatives(
        result=_result(path_a, path_b),
        intent=_intent(),
        track_evidence=tuple(reversed(evidence)),
        policy=policy,
    )

    assert first == second
    assert first.selection_id == second.selection_id
    assert first.deterministic_ordering is True


def test_duplicate_track_evidence_is_rejected() -> None:
    path = _path("path-a", 1, ("a",))
    duplicate = _evidence("a", ("house",), 0.65)
    with pytest.raises(ValueError, match="duplicate musical evidence"):
        select_meaningfully_diverse_alternatives(
            result=_result(path),
            intent=_intent(),
            track_evidence=(duplicate, replace(duplicate, energy=0.66)),
        )


def test_contract_bounds_untrusted_style_tag_cardinality() -> None:
    with pytest.raises(ValueError, match="at most 32"):
        TrackMusicalEvidence(
            track_id="track-a",
            style_tags=tuple(f"tag-{index}" for index in range(33)),
            energy=0.65,
        )
