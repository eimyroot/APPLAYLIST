from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import asdict
from typing import Mapping

from core.intelligence.meaningful_diversity_contract import (
    MeaningfulAlternativeDecision,
    MeaningfulDiversityPolicy,
    MeaningfulDiversitySelection,
    MeaningfulDiversityStatus,
    PairwiseMeaningfulDiversity,
    PathCoherenceAssessment,
    TrackMusicalEvidence,
)
from core.intelligence.set_contract import PlaylistIntent, SetPhase, SetStep
from core.intelligence.set_optimizer_contract import SetOptimizerResult, SetPathAlternative


def _tags(items: tuple[str, ...]) -> set[str]:
    return {str(item).strip().lower() for item in items if str(item).strip()}


def _evidence_index(
    evidence: tuple[TrackMusicalEvidence, ...],
) -> dict[str, TrackMusicalEvidence]:
    result: dict[str, TrackMusicalEvidence] = {}
    for item in evidence:
        if item.track_id in result:
            raise ValueError(f"duplicate musical evidence for track: {item.track_id}")
        result[item.track_id] = item
    return result


def _jaccard(left: set[str], right: set[str]) -> float:
    union = left | right
    if not union:
        return 1.0
    return len(left & right) / len(union)


def _style_fit(tags: set[str], phase: SetPhase) -> tuple[float, bool, set[str]]:
    wanted = _tags(phase.style_targets)
    avoided = _tags(phase.style_avoid)
    avoid_hit = bool(tags & avoided)
    if avoid_hit:
        fit = 0.0
    elif wanted:
        fit = len(tags & wanted) / len(wanted)
    else:
        fit = 1.0
    return fit, avoid_hit, tags - wanted


def _normalized_position(intent: PlaylistIntent, step: SetStep) -> float:
    if intent.target_track_count is not None:
        return min(1.0, max(0.0, step.order_index / intent.target_track_count))
    phase = intent.phase(step.phase_id)
    return (phase.target_fraction_start + phase.target_fraction_end) / 2.0


def _energy_fit(intent: PlaylistIntent, step: SetStep, energy: float) -> float:
    position = _normalized_position(intent, step)
    target, tolerance = intent.energy_trajectory.target_at(position)
    distance = abs(energy - target)
    if distance <= tolerance:
        trajectory_fit = 1.0
    else:
        denominator = max(0.05, 1.0 - tolerance)
        trajectory_fit = max(0.0, 1.0 - (distance - tolerance) / denominator)

    phase = intent.phase(step.phase_id)
    if phase.target_energy_band is None:
        return trajectory_fit
    band_fit = phase.target_energy_band.fit(energy)
    if band_fit is None:
        return trajectory_fit
    return (trajectory_fit + band_fit) / 2.0


def _coherence(
    *,
    path: SetPathAlternative,
    intent: PlaylistIntent,
    evidence_by_track: Mapping[str, TrackMusicalEvidence],
    policy: MeaningfulDiversityPolicy,
) -> PathCoherenceAssessment:
    style_scores: list[float] = []
    energy_scores: list[float] = []
    style_sequences: list[set[str] | None] = []
    missing_style: list[str] = []
    missing_energy: list[str] = []
    avoid_hits = 0
    style_known = 0
    non_target_counts: Counter[str] = Counter()

    for step in path.added_steps:
        item = evidence_by_track.get(step.track_id)
        style_set: set[str] | None = None
        if item is None or item.style_tags is None or not item.style_tags:
            missing_style.append(step.track_id)
        else:
            style_set = set(item.style_tags)
            style_known += 1
            phase = intent.phase(step.phase_id)
            fit, avoid_hit, non_target = _style_fit(style_set, phase)
            style_scores.append(fit)
            avoid_hits += int(avoid_hit)
            wanted = _tags(phase.style_targets)
            if wanted:
                non_target_counts.update(non_target)
        style_sequences.append(style_set)

        if item is None or item.energy is None:
            missing_energy.append(step.track_id)
        else:
            energy_scores.append(_energy_fit(intent, step, item.energy))

    adjacent_overlaps: list[float] = []
    drift_count = 0
    for left, right in zip(style_sequences, style_sequences[1:]):
        if left is None or right is None:
            continue
        overlap = _jaccard(left, right)
        adjacent_overlaps.append(overlap)
        if overlap < policy.minimum_adjacent_style_overlap:
            drift_count += 1

    style_components = [*style_scores, *adjacent_overlaps]
    style_coherence = (
        sum(style_components) / len(style_components) if style_components else None
    )
    energy_coherence = (
        sum(energy_scores) / len(energy_scores) if energy_scores else None
    )
    style_drift_fraction = (
        drift_count / len(adjacent_overlaps) if adjacent_overlaps else 0.0
    )
    style_avoid_fraction = avoid_hits / style_known if style_known else None
    non_target_style_concentration = (
        max(non_target_counts.values(), default=0) / style_known
        if style_known
        else None
    )

    reasons: list[str] = []
    if policy.require_complete_style_evidence and missing_style:
        reasons.append("missing_style_evidence")
    if policy.require_complete_energy_evidence and missing_energy:
        reasons.append("missing_energy_evidence")
    if style_coherence is None:
        reasons.append("style_coherence_not_proven")
    elif style_coherence < policy.minimum_style_coherence:
        reasons.append("style_coherence_below_policy")
    if energy_coherence is None:
        reasons.append("energy_coherence_not_proven")
    elif energy_coherence < policy.minimum_energy_coherence:
        reasons.append("energy_coherence_below_policy")
    if style_drift_fraction > policy.maximum_style_drift_fraction:
        reasons.append("style_drift_above_policy")
    if (
        style_avoid_fraction is not None
        and style_avoid_fraction > policy.maximum_style_avoid_fraction
    ):
        reasons.append("style_avoid_fraction_above_policy")
    if (
        non_target_style_concentration is not None
        and non_target_style_concentration
        > policy.maximum_non_target_style_concentration
    ):
        reasons.append("non_target_style_concentration_above_policy")

    coherence_pass = not reasons
    return PathCoherenceAssessment(
        path_id=path.path_id,
        source_rank=path.rank,
        style_coherence=style_coherence,
        energy_coherence=energy_coherence,
        style_drift_fraction=style_drift_fraction,
        style_avoid_fraction=style_avoid_fraction,
        non_target_style_concentration=non_target_style_concentration,
        missing_style_track_ids=tuple(missing_style),
        missing_energy_track_ids=tuple(missing_energy),
        coherence_pass=coherence_pass,
        reason_codes=("coherence_policy_pass",) if coherence_pass else tuple(reasons),
    )


def _technically_different(
    left: SetPathAlternative,
    right: SetPathAlternative,
) -> bool:
    left_tracks = tuple(step.track_id for step in left.added_steps)
    right_tracks = tuple(step.track_id for step in right.added_steps)
    return left_tracks != right_tracks or left.transition_ids != right.transition_ids


def _pairwise(
    *,
    candidate: SetPathAlternative,
    reference: SetPathAlternative,
    evidence_by_track: Mapping[str, TrackMusicalEvidence],
    candidate_coherence: PathCoherenceAssessment,
    reference_coherence: PathCoherenceAssessment,
    policy: MeaningfulDiversityPolicy,
) -> PairwiseMeaningfulDiversity:
    technically_different = _technically_different(candidate, reference)
    reasons: list[str] = []
    if not technically_different:
        reasons.append("technically_identical_path")

    style_distances: list[float] = []
    energy_distances: list[float] = []
    style_missing = bool(
        candidate_coherence.missing_style_track_ids
        or reference_coherence.missing_style_track_ids
    )
    energy_missing = bool(
        candidate_coherence.missing_energy_track_ids
        or reference_coherence.missing_energy_track_ids
    )

    for left_step, right_step in zip(candidate.added_steps, reference.added_steps):
        left = evidence_by_track.get(left_step.track_id)
        right = evidence_by_track.get(right_step.track_id)
        if (
            left is not None
            and right is not None
            and left.style_tags
            and right.style_tags
        ):
            style_distances.append(1.0 - _jaccard(set(left.style_tags), set(right.style_tags)))
        if (
            left is not None
            and right is not None
            and left.energy is not None
            and right.energy is not None
        ):
            energy_distances.append(abs(left.energy - right.energy))

    if len(candidate.added_steps) != len(reference.added_steps):
        reasons.append("path_length_differs")

    style_distance = (
        sum(style_distances) / len(style_distances) if style_distances else None
    )
    energy_distance = (
        sum(energy_distances) / len(energy_distances) if energy_distances else None
    )

    distance_available = True
    if policy.require_complete_style_evidence and style_missing:
        reasons.append("meaningful_distance_missing_style_evidence")
        distance_available = False
    if policy.require_complete_energy_evidence and energy_missing:
        reasons.append("meaningful_distance_missing_energy_evidence")
        distance_available = False
    if policy.style_distance_weight > 0.0 and style_distance is None:
        reasons.append("style_distance_not_proven")
        distance_available = False
    if policy.energy_distance_weight > 0.0 and energy_distance is None:
        reasons.append("energy_distance_not_proven")
        distance_available = False

    meaningful_distance: float | None = None
    if distance_available:
        weighted: list[tuple[float, float]] = []
        if style_distance is not None and policy.style_distance_weight > 0.0:
            weighted.append((style_distance, policy.style_distance_weight))
        if energy_distance is not None and policy.energy_distance_weight > 0.0:
            weighted.append((energy_distance, policy.energy_distance_weight))
        total_weight = sum(weight for _, weight in weighted)
        if total_weight > 0.0:
            meaningful_distance = (
                sum(value * weight for value, weight in weighted) / total_weight
            )

    meaningful = bool(
        technically_different
        and candidate_coherence.coherence_pass
        and reference_coherence.coherence_pass
        and meaningful_distance is not None
        and meaningful_distance >= policy.minimum_meaningful_distance
    )
    if not candidate_coherence.coherence_pass:
        reasons.append("candidate_path_coherence_failed")
    if not reference_coherence.coherence_pass:
        reasons.append("reference_path_coherence_failed")
    if (
        meaningful_distance is not None
        and meaningful_distance < policy.minimum_meaningful_distance
    ):
        reasons.append("insufficient_meaningful_musical_distance")
    if meaningful:
        reasons.append("meaningful_diversity_policy_pass")

    return PairwiseMeaningfulDiversity(
        candidate_path_id=candidate.path_id,
        reference_path_id=reference.path_id,
        technically_different=technically_different,
        style_distance=style_distance,
        energy_distance=energy_distance,
        meaningful_distance=meaningful_distance,
        meaningful=meaningful,
        reason_codes=tuple(dict.fromkeys(reasons)),
    )


def _selection_id(
    *,
    result: SetOptimizerResult,
    intent: PlaylistIntent,
    evidence: tuple[TrackMusicalEvidence, ...],
    policy: MeaningfulDiversityPolicy,
    selected: tuple[SetPathAlternative, ...],
) -> str:
    material = {
        "source_result_id": result.result_id,
        "source_input_fingerprint": result.input_fingerprint,
        "intent": asdict(intent),
        "policy": asdict(policy),
        "evidence": [asdict(item) for item in sorted(evidence, key=lambda item: item.track_id)],
        "selected_path_ids": [item.path_id for item in selected],
    }
    encoded = json.dumps(material, sort_keys=True, separators=(",", ":"), default=str)
    return "mds_" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:32]


def select_meaningfully_diverse_alternatives(
    *,
    result: SetOptimizerResult,
    intent: PlaylistIntent,
    track_evidence: tuple[TrackMusicalEvidence, ...],
    policy: MeaningfulDiversityPolicy = MeaningfulDiversityPolicy(),
) -> MeaningfulDiversitySelection:
    """Evidence-only post-search selection for musically meaningful A/B alternatives.

    The optimizer remains the only path-search and ranking authority. Source rank #1 is
    always preserved as the reference path. This layer never rewrites source path rank,
    candidate score, TransitionAssessment evidence, or activation authority.
    """
    source = tuple(sorted(result.alternatives, key=lambda item: item.rank))
    evidence_by_track = _evidence_index(track_evidence)
    assessments = tuple(
        _coherence(
            path=path,
            intent=intent,
            evidence_by_track=evidence_by_track,
            policy=policy,
        )
        for path in source
    )
    assessment_by_path = {item.path_id: item for item in assessments}

    if not source:
        selected: list[SetPathAlternative] = []
        decisions: list[MeaningfulAlternativeDecision] = []
        comparisons: list[PairwiseMeaningfulDiversity] = []
    else:
        selected = [source[0]]
        first_assessment = assessment_by_path[source[0].path_id]
        decisions = [
            MeaningfulAlternativeDecision(
                path_id=source[0].path_id,
                source_rank=source[0].rank,
                selected=True,
                coherence_pass=first_assessment.coherence_pass,
                comparison_refs=(),
                reason_codes=(
                    "source_rank_1_preserved",
                    *first_assessment.reason_codes,
                ),
            )
        ]
        comparisons = []

        for candidate in source[1:]:
            candidate_assessment = assessment_by_path[candidate.path_id]
            if len(selected) >= policy.alternative_limit:
                decisions.append(
                    MeaningfulAlternativeDecision(
                        path_id=candidate.path_id,
                        source_rank=candidate.rank,
                        selected=False,
                        coherence_pass=candidate_assessment.coherence_pass,
                        comparison_refs=(),
                        reason_codes=("alternative_limit_reached",),
                    )
                )
                continue

            local_comparisons = tuple(
                _pairwise(
                    candidate=candidate,
                    reference=reference,
                    evidence_by_track=evidence_by_track,
                    candidate_coherence=candidate_assessment,
                    reference_coherence=assessment_by_path[reference.path_id],
                    policy=policy,
                )
                for reference in selected
            )
            comparisons.extend(local_comparisons)
            candidate_selected = bool(
                candidate_assessment.coherence_pass
                and local_comparisons
                and all(item.meaningful for item in local_comparisons)
            )
            reason_codes: list[str] = []
            if candidate_selected:
                reason_codes.append("meaningful_alternative_selected")
                selected.append(candidate)
            else:
                reason_codes.extend(candidate_assessment.reason_codes)
                for comparison in local_comparisons:
                    reason_codes.extend(comparison.reason_codes)
                if not reason_codes:
                    reason_codes.append("insufficient_meaningful_diversity")
            decisions.append(
                MeaningfulAlternativeDecision(
                    path_id=candidate.path_id,
                    source_rank=candidate.rank,
                    selected=candidate_selected,
                    coherence_pass=candidate_assessment.coherence_pass,
                    comparison_refs=tuple(
                        f"{item.candidate_path_id}->{item.reference_path_id}"
                        for item in local_comparisons
                    ),
                    reason_codes=tuple(dict.fromkeys(reason_codes)),
                )
            )

    missing_evidence = any(
        (
            policy.require_complete_style_evidence
            and bool(item.missing_style_track_ids)
        )
        or (
            policy.require_complete_energy_evidence
            and bool(item.missing_energy_track_ids)
        )
        for item in assessments
    )
    if missing_evidence:
        status = MeaningfulDiversityStatus.NOT_PROVEN_MISSING_EVIDENCE
    elif (
        len(selected) >= 2
        and all(assessment_by_path[item.path_id].coherence_pass for item in selected)
    ):
        status = MeaningfulDiversityStatus.SUFFICIENT
    else:
        status = MeaningfulDiversityStatus.INSUFFICIENT_MEANINGFUL_DIVERSITY

    selected_tuple = tuple(selected)
    return MeaningfulDiversitySelection(
        selection_id=_selection_id(
            result=result,
            intent=intent,
            evidence=track_evidence,
            policy=policy,
            selected=selected_tuple,
        ),
        source_result_id=result.result_id,
        source_input_fingerprint=result.input_fingerprint,
        policy_ref=(policy.policy_id, policy.policy_version),
        status=status,
        selected_alternatives=selected_tuple,
        coherence_assessments=assessments,
        pairwise_comparisons=tuple(comparisons),
        decisions=tuple(decisions),
        deterministic_ordering=True,
        activation_authorized=False,
    )


__all__ = ["select_meaningfully_diverse_alternatives"]
