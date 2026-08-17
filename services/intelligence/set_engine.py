from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, replace

from core.intelligence.set_contract import (
    CandidateDescriptor,
    CandidateEligibility,
    CandidateSet,
    MissingFeaturePolicy,
    PlaylistContext,
    PlaylistIntent,
    SequenceState,
    SequenceStatePreview,
    SetCandidate,
    SetCandidateFeatures,
    SetRankingPolicy,
)
from core.intelligence.transition_contract import TRANSITION_POLICY_VERSION


def balanced_set_ranking_policy_v1() -> SetRankingPolicy:
    return SetRankingPolicy(
        ranking_policy_id="balanced-set",
        ranking_policy_version="1",
        feature_weights=(
            ("transition_quality", 3.0),
            ("phase_fit", 1.5),
            ("energy_trajectory_fit", 2.0),
            ("tempo_trajectory_fit", 0.75),
            ("harmonic_policy_fit", 1.0),
            ("style_fit", 1.0),
            ("novelty_fit", 0.5),
            ("artist_spacing_fit", 0.5),
            ("required_track_progress", 1.25),
            ("duration_fit", 0.75),
            ("future_feasibility", 0.0),
            ("uncertainty_penalty", 1.0),
        ),
        missing_feature_policy=MissingFeaturePolicy.EXCLUDE_AND_RENORMALIZE,
        uncertainty_penalty_multiplier=1.0,
    )


def _fingerprint(
    intent: PlaylistIntent,
    context: PlaylistContext,
    state: SequenceState,
    descriptors: tuple[CandidateDescriptor, ...],
    ranking_policy: SetRankingPolicy,
    candidate_limit: int,
) -> str:
    payload = {
        "intent": asdict(intent),
        "context": asdict(context),
        "state": asdict(state),
        "descriptors": [asdict(item) for item in descriptors],
        "ranking_policy": asdict(ranking_policy),
        "candidate_limit": candidate_limit,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _position(intent: PlaylistIntent, context: PlaylistContext, state: SequenceState) -> float:
    if intent.target_track_count is not None:
        return min(1.0, len(state.selected_steps) / intent.target_track_count)
    if intent.target_duration_seconds is not None:
        return min(1.0, state.cumulative_duration_seconds / intent.target_duration_seconds)
    return min(1.0, max(0.0, context.phase_progress))


def _style_fit(
    target_tags: tuple[str, ...] | None,
    wanted: tuple[str, ...],
    avoided: tuple[str, ...],
) -> float | None:
    if not wanted and not avoided:
        return 1.0
    if target_tags is None:
        return None
    tags = set(target_tags)
    if tags & set(avoided):
        return 0.0
    if not wanted:
        return 1.0
    return len(tags & set(wanted)) / len(set(wanted))


def _energy_fit(target_energy: float | None, target: float, tolerance: float) -> float | None:
    if target_energy is None:
        return None
    distance = abs(target_energy - target)
    if distance <= tolerance:
        return 1.0
    denominator = max(0.05, 1.0 - tolerance)
    return max(0.0, 1.0 - (distance - tolerance) / denominator)


def _duration_fit(
    intent: PlaylistIntent,
    state: SequenceState,
    target_duration_seconds: float,
) -> float | None:
    if intent.target_duration_seconds is None:
        return None
    resulting = state.cumulative_duration_seconds + target_duration_seconds
    if resulting <= intent.target_duration_seconds:
        return 1.0
    overshoot = resulting - intent.target_duration_seconds
    if intent.duration_tolerance_seconds <= 0.0:
        return 0.0
    return max(0.0, 1.0 - overshoot / intent.duration_tolerance_seconds)


def _phase_fit(
    descriptor: CandidateDescriptor,
    phase,
) -> float | None:
    components: list[float] = []
    if phase.target_energy_band is not None:
        value = phase.target_energy_band.fit(
            descriptor.transition.energy_effect.target_energy_state
        )
        if value is not None:
            components.append(value)
    style_value = _style_fit(
        descriptor.style_tags, phase.style_targets, phase.style_avoid
    )
    if style_value is not None:
        components.append(style_value)
    if not components:
        return None
    return sum(components) / len(components)


def _hard_block_reasons(
    descriptor: CandidateDescriptor,
    intent: PlaylistIntent,
    context: PlaylistContext,
    state: SequenceState,
) -> tuple[str, ...]:
    assessment = descriptor.transition
    track_id = assessment.identity.target_track_id
    segment_id = assessment.identity.target_segment_id
    reasons: list[str] = []

    if state.current_track_id is not None:
        if assessment.identity.source_track_id != state.current_track_id:
            reasons.append("source_track_mismatch")
        if assessment.identity.source_segment_id != state.current_segment_id:
            reasons.append("source_segment_mismatch")

    if track_id in intent.forbidden_track_ids:
        reasons.append("candidate_forbidden")
    if not intent.allow_track_repeats and track_id in state.used_track_ids:
        reasons.append("candidate_repeat_forbidden")

    explicit_scope = intent.eligible_library_scope.explicit_track_ids
    if explicit_scope is not None and track_id not in explicit_scope:
        reasons.append("candidate_outside_explicit_scope")

    scope = intent.eligible_library_scope
    if (scope.include_tags or scope.exclude_tags) and descriptor.style_tags is None:
        reasons.append("scope_tag_evidence_missing")
    elif descriptor.style_tags is not None:
        target_tags = set(descriptor.style_tags)
        if scope.include_tags and not (target_tags & set(scope.include_tags)):
            reasons.append("candidate_missing_required_scope_tag")
        if target_tags & set(scope.exclude_tags):
            reasons.append("candidate_has_excluded_scope_tag")

    next_position = len(state.selected_steps)
    for lock in intent.locked_positions:
        if lock.position_index == next_position:
            if lock.track_id != track_id:
                reasons.append("locked_next_track_mismatch")
            if lock.segment_id is not None and lock.segment_id != segment_id:
                reasons.append("locked_next_segment_mismatch")
            if (
                lock.transition_strategy is not None
                and assessment.preferred_strategy != lock.transition_strategy
            ):
                reasons.append("locked_next_strategy_mismatch")

    phase = intent.phase(context.current_phase_id)
    if phase.forbidden_transition_strategies:
        allowed_candidates = tuple(
            item
            for item in assessment.candidate_strategies
            if item.strategy not in phase.forbidden_transition_strategies
        )
        if not allowed_candidates:
            reasons.append("phase_has_no_allowed_transition_strategy")

    projection = assessment.contextual_projection
    reasons.extend(f"transition:{item}" for item in projection.blocked_reasons)
    if projection.score is None and not projection.blocked_reasons:
        reasons.append("transition_projection_unscored")

    if intent.reject_critical_warnings and descriptor.critical_warnings:
        reasons.append("critical_analysis_warning")

    if intent.target_duration_seconds is not None:
        resulting = state.cumulative_duration_seconds + descriptor.target_duration_seconds
        maximum = intent.target_duration_seconds + intent.duration_tolerance_seconds
        if resulting > maximum:
            reasons.append("target_duration_exceeded")

    return tuple(dict.fromkeys(reasons))


def _candidate_features(
    descriptor: CandidateDescriptor,
    intent: PlaylistIntent,
    context: PlaylistContext,
    state: SequenceState,
) -> SetCandidateFeatures:
    assessment = descriptor.transition
    phase = intent.phase(context.current_phase_id)
    position = _position(intent, context, state)
    target_energy, tolerance = intent.energy_trajectory.target_at(position)
    energy_fit = _energy_fit(
        assessment.energy_effect.target_energy_state, target_energy, tolerance
    )
    tempo_fit = None
    harmonic_fit = assessment.compatibility_vector.harmonic_fit
    style_fit = _style_fit(descriptor.style_tags, phase.style_targets, phase.style_avoid)
    required_progress = (
        1.0
        if assessment.identity.target_track_id in state.remaining_required_track_ids
        else (1.0 if not state.remaining_required_track_ids else 0.0)
    )
    uncertainty = assessment.risk_vector.uncertainty
    novelty = 0.0 if assessment.identity.target_track_id in state.used_track_ids else 1.0
    return SetCandidateFeatures(
        transition_quality=assessment.contextual_projection.score,
        phase_fit=_phase_fit(descriptor, phase),
        energy_trajectory_fit=energy_fit,
        tempo_trajectory_fit=tempo_fit,
        harmonic_policy_fit=harmonic_fit,
        style_fit=style_fit,
        novelty_fit=novelty,
        artist_spacing_fit=None,
        required_track_progress=required_progress,
        duration_fit=_duration_fit(intent, state, descriptor.target_duration_seconds),
        future_feasibility=None,
        uncertainty_penalty=uncertainty,
    )


def _score(
    features: SetCandidateFeatures,
    ranking_policy: SetRankingPolicy,
) -> tuple[float | None, tuple[str, ...]]:
    available: list[tuple[str, float, float]] = []
    missing: list[str] = []
    for name, weight in ranking_policy.feature_weights:
        if weight <= 0.0:
            continue
        value = getattr(features, name)
        if value is None:
            missing.append(name)
            continue
        if name == "uncertainty_penalty":
            value = 1.0 - min(
                1.0, value * ranking_policy.uncertainty_penalty_multiplier
            )
        available.append((name, value, weight))

    if missing and ranking_policy.missing_feature_policy is MissingFeaturePolicy.HARD_BLOCK:
        return None, tuple(f"ranking_feature_missing:{name}" for name in missing)

    if not available:
        return None, ("ranking_features_unavailable",)

    if (
        missing
        and ranking_policy.missing_feature_policy is MissingFeaturePolicy.UNCERTAINTY_PENALTY
    ):
        penalty_weight = sum(
            weight for name, weight in ranking_policy.feature_weights if name in missing
        )
        if penalty_weight > 0.0:
            available.append(("missing_feature_penalty", 0.0, penalty_weight))

    total_weight = sum(weight for _, _, weight in available)
    score = sum(value * weight for _, value, weight in available) / total_weight
    return max(0.0, min(1.0, score)), ()


def _preview(
    descriptor: CandidateDescriptor,
    intent: PlaylistIntent,
    context: PlaylistContext,
    state: SequenceState,
) -> SequenceStatePreview:
    track_id = descriptor.transition.identity.target_track_id
    remaining = tuple(item for item in state.remaining_required_track_ids if item != track_id)
    return SequenceStatePreview(
        next_position_index=len(state.selected_steps),
        target_track_id=track_id,
        target_segment_id=descriptor.transition.identity.target_segment_id,
        cumulative_duration_seconds=state.cumulative_duration_seconds
        + descriptor.target_duration_seconds,
        remaining_required_track_ids=remaining,
        phase_id=context.current_phase_id,
    )


def _candidate_id(
    descriptor: CandidateDescriptor,
    intent: PlaylistIntent,
    context: PlaylistContext,
    state: SequenceState,
    ranking_policy: SetRankingPolicy,
) -> str:
    material = "|".join(
        (
            descriptor.transition.identity.transition_id,
            intent.intent_id,
            intent.intent_version,
            context.context_id,
            context.context_version,
            state.state_id,
            state.state_version,
            ranking_policy.ranking_policy_id,
            ranking_policy.ranking_policy_version,
        )
    )
    return "sc_" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:32]


def _base_candidate(
    descriptor: CandidateDescriptor,
    intent: PlaylistIntent,
    context: PlaylistContext,
    state: SequenceState,
    ranking_policy: SetRankingPolicy,
) -> SetCandidate:
    assessment = descriptor.transition
    blocked = list(_hard_block_reasons(descriptor, intent, context, state))
    features = _candidate_features(descriptor, intent, context, state)
    score: float | None = None
    if not blocked:
        score, ranking_blocks = _score(features, ranking_policy)
        blocked.extend(ranking_blocks)

    eligibility = (
        CandidateEligibility.BLOCKED if blocked else CandidateEligibility.ELIGIBLE
    )
    explanation_codes = list(assessment.contextual_projection.explanation_codes)
    if eligibility is CandidateEligibility.ELIGIBLE:
        explanation_codes.append("set_candidate_ranked_v1")
        if assessment.identity.target_track_id in state.remaining_required_track_ids:
            explanation_codes.append("required_track_progress")
    else:
        explanation_codes.extend(blocked)

    return SetCandidate(
        candidate_id=_candidate_id(
            descriptor, intent, context, state, ranking_policy
        ),
        target_track_id=assessment.identity.target_track_id,
        target_segment_id=assessment.identity.target_segment_id,
        transition_assessment_id=assessment.identity.transition_id,
        transition_context_id=assessment.contextual_projection.context_id,
        phase_id=context.current_phase_id,
        eligibility=eligibility,
        blocked_reasons=tuple(blocked),
        feature_vector=features,
        score=score if eligibility is CandidateEligibility.ELIGIBLE else None,
        confidence=assessment.confidence.score,
        rank=None,
        explanation_codes=tuple(dict.fromkeys(explanation_codes)),
        evidence_refs=assessment.evidence_refs,
        resulting_state_preview=_preview(descriptor, intent, context, state),
    )


def _operational_cost(descriptor: CandidateDescriptor) -> float:
    cost = descriptor.transition.cost_vector
    available = tuple(
        value
        for value in (
            cost.preparation_complexity,
            cost.time_stretch_cost,
            cost.key_shift_cost,
        )
        if value is not None
    )
    return max(available) if available else 1.0


def _tie_break_key(
    candidate: SetCandidate,
    descriptors_by_transition_id: dict[str, CandidateDescriptor],
) -> tuple[float, float, float, str, str, str]:
    uncertainty = candidate.feature_vector.uncertainty_penalty
    descriptor = descriptors_by_transition_id[candidate.transition_assessment_id]
    return (
        -(candidate.score if candidate.score is not None else -1.0),
        uncertainty if uncertainty is not None else 1.0,
        _operational_cost(descriptor),
        candidate.target_track_id,
        candidate.target_segment_id,
        candidate.transition_assessment_id,
    )


def _validate_request(
    intent: PlaylistIntent,
    context: PlaylistContext,
    state: SequenceState,
) -> None:
    if state.current_track_id is None or state.current_segment_id is None:
        raise ValueError(
            "recommend_next v1 requires a seeded current track and segment"
        )
    if context.current_track_id != state.current_track_id:
        raise ValueError("context current_track_id must match sequence state")
    if context.current_segment_id != state.current_segment_id:
        raise ValueError("context current_segment_id must match sequence state")
    if context.current_position_index != len(state.selected_steps) - 1:
        raise ValueError("context position must match final selected step")
    required = set(intent.required_track_ids)
    satisfied = set(state.satisfied_required_track_ids)
    remaining = set(state.remaining_required_track_ids)
    if satisfied & remaining:
        raise ValueError("required-track state must be disjoint")
    if satisfied | remaining != required:
        raise ValueError("required-track state must reconcile with PlaylistIntent")
    selected = set(state.used_track_ids)
    if not (selected & required).issubset(satisfied):
        raise ValueError("selected required tracks must be marked satisfied")


def recommend_next(
    *,
    intent: PlaylistIntent,
    context: PlaylistContext,
    sequence_state: SequenceState,
    transition_edges: tuple[CandidateDescriptor, ...],
    ranking_policy: SetRankingPolicy,
    candidate_limit: int,
    generated_at: str,
) -> CandidateSet:
    """Return a deterministic Top-N set of eligible next-state expansions."""
    if candidate_limit <= 0:
        raise ValueError("candidate_limit must be positive")
    _validate_request(intent, context, sequence_state)
    intent.phase(context.current_phase_id)

    descriptors = tuple(
        sorted(
            transition_edges,
            key=lambda item: (
                item.transition.identity.target_track_id,
                item.transition.identity.target_segment_id,
                item.transition.identity.transition_id,
            ),
        )
    )
    fingerprint = _fingerprint(
        intent,
        context,
        sequence_state,
        descriptors,
        ranking_policy,
        candidate_limit,
    )
    evaluated = tuple(
        _base_candidate(item, intent, context, sequence_state, ranking_policy)
        for item in descriptors
    )
    descriptors_by_transition_id = {
        item.transition.identity.transition_id: item for item in descriptors
    }
    eligible = sorted(
        (item for item in evaluated if item.eligibility is CandidateEligibility.ELIGIBLE),
        key=lambda item: _tie_break_key(item, descriptors_by_transition_id),
    )
    ranked = tuple(
        replace(item, rank=index)
        for index, item in enumerate(eligible[:candidate_limit], start=1)
    )
    rejected = tuple(
        item for item in evaluated if item.eligibility is CandidateEligibility.BLOCKED
    )
    warnings: list[str] = []
    if len(eligible) > candidate_limit:
        warnings.append("candidate_set_truncated")
    if any(item.feature_vector.future_feasibility is None for item in ranked):
        warnings.append("future_feasibility_not_evaluated_v1")

    return CandidateSet(
        candidate_set_id="cs_" + fingerprint[:32],
        input_fingerprint=fingerprint,
        intent_ref=(intent.intent_id, intent.intent_version),
        context_ref=(context.context_id, context.context_version),
        sequence_state_ref=(sequence_state.state_id, sequence_state.state_version),
        transition_policy_ref=TRANSITION_POLICY_VERSION,
        ranking_policy_ref=(
            ranking_policy.ranking_policy_id,
            ranking_policy.ranking_policy_version,
        ),
        eligible_candidates=ranked,
        rejected_candidates=rejected,
        generated_at=generated_at,
        deterministic_ordering=True,
        warnings=tuple(warnings),
    )


__all__ = ["balanced_set_ranking_policy_v1", "recommend_next"]
