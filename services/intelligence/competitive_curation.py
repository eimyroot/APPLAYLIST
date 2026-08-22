from __future__ import annotations

from collections.abc import Mapping

from core.intelligence.competitive_curation_contract import (
    CompetitiveCurationPolicy,
    CompetitiveCurationStatus,
    PathCurationAssessment,
    ShadowPathComparison,
    ShadowPathPreference,
    TrackCurationEvidence,
)
from core.intelligence.music_dna import FactStatus, MusicDNARevision
from core.intelligence.set_contract import PlaylistIntent, SetGoal, SetStep
from core.intelligence.set_optimizer_contract import SetPathAlternative
from core.intelligence.transition_contract import TransitionStrategy


_STYLE_PARENTS: dict[str, tuple[str, ...]] = {
    "tech house": ("house",),
    "uk house": ("house",),
    "bass house": ("house",),
    "deep house": ("house",),
    "progressive house": ("house",),
    "acid house": ("house",),
    "ukg": ("uk garage", "garage"),
    "uk garage": ("garage",),
    "speed garage": ("garage",),
    "bassline": ("uk bass",),
    "uk bassline": ("bassline", "uk bass"),
    "uk bass": ("bass",),
    "rave techno": ("techno", "rave"),
    "hard techno": ("techno",),
    "peak time techno": ("techno",),
    "melodic techno": ("techno",),
    "industrial techno": ("techno",),
    "minimal techno": ("techno",),
    "breakbeat": ("breaks",),
    "drum and bass": ("dnb", "bass"),
    "drum & bass": ("dnb", "bass"),
}


def expand_style_tags(tags: tuple[str, ...] | None) -> frozenset[str] | None:
    """Expand bounded DJ-style aliases into explicit parent families.

    This is intentionally a small deterministic taxonomy, not an ML genre classifier.
    Unknown tags are preserved exactly after normalization.
    """
    if tags is None:
        return None
    expanded: set[str] = set()
    queue = [str(item).strip().lower() for item in tags if str(item).strip()]
    while queue:
        tag = queue.pop()
        if tag in expanded:
            continue
        expanded.add(tag)
        queue.extend(_STYLE_PARENTS.get(tag, ()))
    return frozenset(expanded) or None


def track_curation_evidence_from_music_dna(
    *,
    music_dna: MusicDNARevision,
    style_tags: tuple[str, ...] | None,
    vocal_presence: float | None = None,
) -> TrackCurationEvidence:
    """Project immutable MusicDNA into bounded curation evidence without audio access."""
    duration_minutes = music_dna.duration_seconds / 60.0
    phrase_density = None
    if music_dna.rhythm.timing_status is not FactStatus.UNAVAILABLE:
        phrase_density = len(music_dna.rhythm.phrase_boundaries_seconds) / duration_minutes

    labels = tuple(
        segment.structural_label
        for segment in music_dna.segments
        if segment.structural_label
    )
    structural_diversity = None
    if labels:
        structural_diversity = len(set(labels)) / len(labels)

    percussive = music_dna.energy.percussive_ratio
    if percussive is None:
        percussive = music_dna.rhythm.percussive_ratio

    return TrackCurationEvidence(
        track_id=music_dna.identity.track_id,
        style_tags=style_tags,
        baseline_energy=music_dna.energy.baseline_energy,
        percussive_ratio=percussive,
        harmonic_ratio=music_dna.energy.harmonic_ratio,
        beat_stability=music_dna.rhythm.beat_stability,
        phrase_boundary_density_per_minute=phrase_density,
        structural_label_diversity=structural_diversity,
        vocal_presence=vocal_presence,
        analysis_revision=music_dna.identity.analysis_revision,
        evidence_refs=music_dna.identity.evidence_refs,
    )


def _index(
    evidence: tuple[TrackCurationEvidence, ...],
) -> dict[str, TrackCurationEvidence]:
    result: dict[str, TrackCurationEvidence] = {}
    for item in evidence:
        if item.track_id in result:
            raise ValueError(f"duplicate curation evidence for track: {item.track_id}")
        result[item.track_id] = item
    return result


def _jaccard(left: frozenset[str], right: frozenset[str]) -> float:
    union = left | right
    if not union:
        return 1.0
    return len(left & right) / len(union)


def _position(intent: PlaylistIntent, step: SetStep) -> float:
    if intent.target_track_count is not None:
        return min(1.0, max(0.0, step.order_index / intent.target_track_count))
    phase = intent.phase(step.phase_id)
    return (phase.target_fraction_start + phase.target_fraction_end) / 2.0


def _style_target_fit(
    *,
    tags: frozenset[str],
    intent: PlaylistIntent,
    step: SetStep,
) -> tuple[float, bool]:
    phase = intent.phase(step.phase_id)
    wanted = expand_style_tags(phase.style_targets) or frozenset()
    avoided = expand_style_tags(phase.style_avoid) or frozenset()
    if tags & avoided:
        return 0.0, False
    if not wanted:
        return 1.0, True
    return len(tags & wanted) / len(wanted), bool(tags & wanted)


def _energy_fit(
    *,
    energy: float,
    intent: PlaylistIntent,
    step: SetStep,
    policy: CompetitiveCurationPolicy,
) -> float:
    target, declared_tolerance = intent.energy_trajectory.target_at(_position(intent, step))
    effective_tolerance = min(declared_tolerance, policy.max_effective_energy_tolerance)
    distance = abs(energy - target)
    if distance <= effective_tolerance:
        trajectory_fit = 1.0
    else:
        denominator = max(0.05, 1.0 - effective_tolerance)
        trajectory_fit = max(
            0.0,
            1.0 - (distance - effective_tolerance) / denominator,
        )

    phase = intent.phase(step.phase_id)
    if phase.target_energy_band is None:
        return trajectory_fit
    band_fit = phase.target_energy_band.fit(energy)
    if band_fit is None:
        return trajectory_fit
    return (trajectory_fit + band_fit) / 2.0


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _longest_true_run(values: list[bool]) -> int:
    longest = 0
    current = 0
    for value in values:
        if value:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def _texture_similarity(
    left: TrackCurationEvidence,
    right: TrackCurationEvidence,
) -> float | None:
    similarities: list[float] = []
    for field_name in ("percussive_ratio", "harmonic_ratio", "beat_stability"):
        left_value = getattr(left, field_name)
        right_value = getattr(right, field_name)
        if left_value is not None and right_value is not None:
            similarities.append(1.0 - abs(left_value - right_value))
    return _mean(similarities)


def _structure_readiness(item: TrackCurationEvidence) -> float | None:
    components: list[float] = []
    if item.phrase_boundary_density_per_minute is not None:
        components.append(1.0 if item.phrase_boundary_density_per_minute > 0.0 else 0.0)
    if item.structural_label_diversity is not None:
        components.append(item.structural_label_diversity)
    return _mean(components)


def _evidence_completeness(items: tuple[TrackCurationEvidence | None, ...]) -> float:
    if not items:
        return 0.0
    available = 0
    expected = len(items) * 7
    for item in items:
        if item is None:
            continue
        available += int(bool(item.style_tags))
        available += int(item.baseline_energy is not None)
        available += int(item.percussive_ratio is not None)
        available += int(item.harmonic_ratio is not None)
        available += int(item.beat_stability is not None)
        available += int(item.phrase_boundary_density_per_minute is not None)
        available += int(item.structural_label_diversity is not None)
    return available / expected


def _weighted_score(
    *,
    components: Mapping[str, float | None],
    policy: CompetitiveCurationPolicy,
    intent: PlaylistIntent,
) -> float | None:
    weights = {
        "style_target_fit": policy.style_target_weight,
        "style_continuity": policy.style_continuity_weight,
        "energy_trajectory_fit": policy.energy_trajectory_weight,
        "texture_groove_continuity": policy.texture_groove_weight,
        "structure_phrase_readiness": policy.structure_readiness_weight,
        "contrast_control": policy.contrast_control_weight,
        "saturation_control": policy.saturation_control_weight,
        "evidence_completeness": policy.evidence_completeness_weight,
    }
    if intent.goal is SetGoal.STYLE_BRIDGE:
        weights["style_continuity"] *= 0.5
        weights["contrast_control"] *= 0.75

    available = [
        (components[name], weight)
        for name, weight in weights.items()
        if weight > 0.0 and components.get(name) is not None
    ]
    if not available:
        return None
    denominator = sum(weight for _, weight in available)
    assert denominator > 0.0
    return sum(float(value) * weight for value, weight in available) / denominator


def assess_competitive_curation_path(
    *,
    path: SetPathAlternative,
    intent: PlaylistIntent,
    track_evidence: tuple[TrackCurationEvidence, ...],
    policy: CompetitiveCurationPolicy = CompetitiveCurationPolicy(),
) -> PathCurationAssessment:
    """Score a source optimizer path in shadow mode without mutating optimizer truth."""
    evidence_by_track = _index(track_evidence)
    path_items = tuple(evidence_by_track.get(step.track_id) for step in path.added_steps)

    missing_style = tuple(
        step.track_id
        for step, item in zip(path.added_steps, path_items)
        if item is None or not item.style_tags
    )
    missing_energy = tuple(
        step.track_id
        for step, item in zip(path.added_steps, path_items)
        if item is None or item.baseline_energy is None
    )
    completeness = _evidence_completeness(path_items)

    style_fit_scores: list[float] = []
    target_misses: list[bool] = []
    expanded_styles: list[frozenset[str] | None] = []
    energy_scores: list[float] = []
    structure_scores: list[float] = []

    for step, item in zip(path.added_steps, path_items):
        if item is None:
            expanded_styles.append(None)
            target_misses.append(False)
            continue
        expanded = expand_style_tags(item.style_tags)
        expanded_styles.append(expanded)
        if expanded is not None:
            style_fit, target_match = _style_target_fit(
                tags=expanded,
                intent=intent,
                step=step,
            )
            style_fit_scores.append(style_fit)
            target_misses.append(not target_match)
        else:
            target_misses.append(False)
        if item.baseline_energy is not None:
            energy_scores.append(
                _energy_fit(
                    energy=item.baseline_energy,
                    intent=intent,
                    step=step,
                    policy=policy,
                )
            )
        readiness = _structure_readiness(item)
        if readiness is not None:
            structure_scores.append(readiness)

    style_continuity_scores: list[float] = []
    texture_scores: list[float] = []
    unexplained_contrasts = 0
    comparable_style_pairs = 0
    for index, (left_style, right_style) in enumerate(
        zip(expanded_styles, expanded_styles[1:])
    ):
        left_item = path_items[index]
        right_item = path_items[index + 1]
        next_step = path.added_steps[index + 1]
        if left_style is not None and right_style is not None:
            overlap = _jaccard(left_style, right_style)
            style_continuity_scores.append(overlap)
            comparable_style_pairs += 1
            if (
                overlap < policy.minimum_adjacent_style_overlap
                and next_step.chosen_strategy is not TransitionStrategy.DELIBERATE_CONTRAST
            ):
                unexplained_contrasts += 1
        if left_item is not None and right_item is not None:
            texture = _texture_similarity(left_item, right_item)
            if texture is not None:
                texture_scores.append(texture)

    non_target_run_fraction = (
        _longest_true_run(target_misses) / len(target_misses)
        if target_misses
        else None
    )
    unexplained_contrast_fraction = (
        unexplained_contrasts / comparable_style_pairs
        if comparable_style_pairs
        else None
    )

    components: dict[str, float | None] = {
        "style_target_fit": _mean(style_fit_scores),
        "style_continuity": _mean(style_continuity_scores),
        "energy_trajectory_fit": _mean(energy_scores),
        "texture_groove_continuity": _mean(texture_scores),
        "structure_phrase_readiness": _mean(structure_scores),
        "contrast_control": (
            None
            if unexplained_contrast_fraction is None
            else 1.0 - unexplained_contrast_fraction
        ),
        "saturation_control": (
            None
            if non_target_run_fraction is None
            else 1.0 - non_target_run_fraction
        ),
        "evidence_completeness": completeness,
    }

    missing_required = bool(
        (policy.require_complete_style_evidence and missing_style)
        or (policy.require_complete_energy_evidence and missing_energy)
    )
    reasons: list[str] = []
    if policy.require_complete_style_evidence and missing_style:
        reasons.append("competitive_missing_style_evidence")
    if policy.require_complete_energy_evidence and missing_energy:
        reasons.append("competitive_missing_energy_evidence")

    score = None if missing_required else _weighted_score(
        components=components,
        policy=policy,
        intent=intent,
    )

    if missing_required:
        status = CompetitiveCurationStatus.NOT_PROVEN_MISSING_EVIDENCE
    else:
        energy_fit = components["energy_trajectory_fit"]
        if (
            energy_fit is not None
            and energy_fit < policy.minimum_energy_trajectory_fit
        ):
            reasons.append("competitive_energy_trajectory_below_floor")
        if (
            non_target_run_fraction is not None
            and non_target_run_fraction > policy.maximum_non_target_run_fraction
        ):
            reasons.append("competitive_non_target_style_run_above_policy")
        if (
            unexplained_contrast_fraction is not None
            and unexplained_contrast_fraction
            > policy.maximum_unexplained_contrast_fraction
        ):
            reasons.append("competitive_unexplained_contrast_above_policy")
        if score is None:
            reasons.append("competitive_score_not_proven")
        elif score < policy.minimum_competitive_score:
            reasons.append("competitive_score_below_policy")

        status = (
            CompetitiveCurationStatus.COMPETITIVE
            if not reasons
            else CompetitiveCurationStatus.INSUFFICIENT
        )
        if status is CompetitiveCurationStatus.COMPETITIVE:
            reasons.append("competitive_curation_policy_pass")

    if all(item is not None and item.vocal_presence is None for item in path_items):
        reasons.append("vocal_evidence_unavailable_not_inferred")

    return PathCurationAssessment(
        path_id=path.path_id,
        source_rank=path.rank,
        score=score,
        status=status,
        component_scores=tuple(components.items()),
        evidence_completeness=completeness,
        non_target_run_fraction=non_target_run_fraction,
        unexplained_contrast_fraction=unexplained_contrast_fraction,
        missing_style_track_ids=missing_style,
        missing_energy_track_ids=missing_energy,
        reason_codes=tuple(reasons),
        source_identity_preserved=True,
        activation_authorized=False,
    )


def compare_competitive_curation_paths(
    *,
    left: SetPathAlternative,
    right: SetPathAlternative,
    intent: PlaylistIntent,
    track_evidence: tuple[TrackCurationEvidence, ...],
    policy: CompetitiveCurationPolicy = CompetitiveCurationPolicy(),
) -> tuple[PathCurationAssessment, PathCurationAssessment, ShadowPathComparison]:
    """Compare two source paths in shadow mode; never rewrite source ranking."""
    left_assessment = assess_competitive_curation_path(
        path=left,
        intent=intent,
        track_evidence=track_evidence,
        policy=policy,
    )
    right_assessment = assess_competitive_curation_path(
        path=right,
        intent=intent,
        track_evidence=track_evidence,
        policy=policy,
    )

    reasons: list[str] = []
    if left_assessment.score is None or right_assessment.score is None:
        preference = ShadowPathPreference.NOT_PROVEN
        delta = None
        reasons.append("shadow_preference_not_proven_missing_evidence")
    else:
        delta = right_assessment.score - left_assessment.score
        if abs(delta) < policy.minimum_pairwise_delta:
            preference = ShadowPathPreference.TIE
            reasons.append("shadow_scores_within_materiality_delta")
        elif delta > 0.0:
            preference = ShadowPathPreference.RIGHT
            reasons.append("shadow_right_path_preferred")
        else:
            preference = ShadowPathPreference.LEFT
            reasons.append("shadow_left_path_preferred")

    comparison = ShadowPathComparison(
        left_path_id=left.path_id,
        right_path_id=right.path_id,
        left_score=left_assessment.score,
        right_score=right_assessment.score,
        right_minus_left=delta,
        preference=preference,
        reason_codes=tuple(reasons),
        activation_authorized=False,
    )
    return left_assessment, right_assessment, comparison


__all__ = [
    "assess_competitive_curation_path",
    "compare_competitive_curation_paths",
    "expand_style_tags",
    "track_curation_evidence_from_music_dna",
]
