from __future__ import annotations

from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass

from core.intelligence.feasibility_contract import (
    FeasibilityPolicy,
    FeasibilityStatus,
    FutureFeasibilityResult,
)
from core.intelligence.set_contract import PlaylistIntent, SequenceState
from core.intelligence.transition_contract import TransitionAssessment, TransitionContext
from data.repositories.music_intelligence_repository import MusicIntelligenceRepository


@dataclass(frozen=True, slots=True)
class _SearchState:
    depth: int
    track_id: str
    segment_id: str
    reached_required: frozenset[str]
    future_used_tracks: frozenset[str]
    cumulative_duration_seconds: float


def _result(
    *,
    status: FeasibilityStatus,
    requirements: frozenset[str],
    best_reached: frozenset[str],
    expanded_states: int,
    deepest_depth: int,
    budget_exhausted: bool,
    policy: FeasibilityPolicy,
    context: TransitionContext,
    explanation_codes: tuple[str, ...],
) -> FutureFeasibilityResult:
    score = (
        1.0
        if status is FeasibilityStatus.REACHABLE
        else (0.0 if status is FeasibilityStatus.INFEASIBLE else None)
    )
    return FutureFeasibilityResult(
        status=status,
        score=score,
        reached_required_track_ids=tuple(sorted(best_reached)),
        unresolved_required_track_ids=tuple(sorted(requirements - best_reached)),
        expanded_states=expanded_states,
        deepest_expanded_depth=deepest_depth,
        budget_exhausted=budget_exhausted,
        policy_version=policy.policy_version,
        context_ref=(context.context_id, context.context_version),
        explanation_codes=explanation_codes,
    )


def _locked_position_allows(
    *,
    intent: PlaylistIntent,
    position_index: int,
    assessment: TransitionAssessment,
) -> bool:
    for lock in intent.locked_positions:
        if lock.position_index != position_index:
            continue
        if lock.track_id != assessment.identity.target_track_id:
            return False
        if lock.segment_id is not None and lock.segment_id != assessment.identity.target_segment_id:
            return False
        if (
            lock.transition_strategy is not None
            and assessment.preferred_strategy != lock.transition_strategy
        ):
            return False
    return True


def _scope_allows(
    *,
    intent: PlaylistIntent,
    track_id: str,
    style_tags_by_track: Mapping[str, tuple[str, ...]] | None,
) -> tuple[bool, bool]:
    """Return (allowed, evidence_missing)."""
    scope = intent.eligible_library_scope
    if scope.explicit_track_ids is not None and track_id not in scope.explicit_track_ids:
        return False, False
    if not scope.include_tags and not scope.exclude_tags:
        return True, False
    if style_tags_by_track is None or track_id not in style_tags_by_track:
        return False, True
    tags = set(style_tags_by_track[track_id])
    if scope.include_tags and not (tags & set(scope.include_tags)):
        return False, False
    if tags & set(scope.exclude_tags):
        return False, False
    return True, False


def evaluate_future_feasibility(
    *,
    repository: MusicIntelligenceRepository,
    sequence_state: SequenceState,
    intent: PlaylistIntent,
    transition_context: TransitionContext,
    policy: FeasibilityPolicy,
    target_duration_seconds_by_track: Mapping[str, float] | None = None,
    style_tags_by_track: Mapping[str, tuple[str, ...]] | None = None,
) -> FutureFeasibilityResult:
    """Prove or bound future required-track reachability over persisted adjacency.

    V1 evaluates a fixed explicit TransitionContext across the bounded horizon. It
    respects forbidden/repeat/scope/fixed-position locks and target-duration limits
    when the required evidence is supplied. It never turns missing evidence or an
    exhausted search budget into an ``infeasible`` claim.
    """
    if sequence_state.current_track_id is None or sequence_state.current_segment_id is None:
        raise ValueError("future feasibility requires a seeded sequence state")

    requirements = frozenset(sequence_state.remaining_required_track_ids)
    floating_locks = frozenset(
        lock.track_id for lock in intent.locked_positions if lock.position_index is None
    )
    requirements = requirements | floating_locks
    if not requirements:
        return _result(
            status=FeasibilityStatus.REACHABLE,
            requirements=requirements,
            best_reached=frozenset(),
            expanded_states=0,
            deepest_depth=0,
            budget_exhausted=False,
            policy=policy,
            context=transition_context,
            explanation_codes=("no_remaining_required_tracks",),
        )

    if intent.target_duration_seconds is not None and target_duration_seconds_by_track is None:
        return _result(
            status=FeasibilityStatus.NOT_PROVEN_MISSING_EVIDENCE,
            requirements=requirements,
            best_reached=frozenset(),
            expanded_states=0,
            deepest_depth=0,
            budget_exhausted=False,
            policy=policy,
            context=transition_context,
            explanation_codes=("duration_evidence_required_for_bounded_feasibility",),
        )

    if (
        intent.eligible_library_scope.include_tags
        or intent.eligible_library_scope.exclude_tags
    ) and style_tags_by_track is None:
        return _result(
            status=FeasibilityStatus.NOT_PROVEN_MISSING_EVIDENCE,
            requirements=requirements,
            best_reached=frozenset(),
            expanded_states=0,
            deepest_depth=0,
            budget_exhausted=False,
            policy=policy,
            context=transition_context,
            explanation_codes=("style_tag_evidence_required_for_scope_feasibility",),
        )

    initial = _SearchState(
        depth=0,
        track_id=sequence_state.current_track_id,
        segment_id=sequence_state.current_segment_id,
        reached_required=frozenset(),
        future_used_tracks=frozenset(),
        cumulative_duration_seconds=sequence_state.cumulative_duration_seconds,
    )
    queue: deque[_SearchState] = deque((initial,))
    seen: set[tuple[object, ...]] = set()
    expanded = 0
    deepest = 0
    depth_truncated = False
    evidence_gap = False
    best_reached = frozenset[str]()
    existing_used = frozenset(sequence_state.used_track_ids)

    while queue:
        current = queue.popleft()
        if len(current.reached_required) > len(best_reached) or (
            len(current.reached_required) == len(best_reached)
            and tuple(sorted(current.reached_required)) < tuple(sorted(best_reached))
        ):
            best_reached = current.reached_required
        if requirements <= current.reached_required:
            return _result(
                status=FeasibilityStatus.REACHABLE,
                requirements=requirements,
                best_reached=current.reached_required,
                expanded_states=expanded,
                deepest_depth=deepest,
                budget_exhausted=False,
                policy=policy,
                context=transition_context,
                explanation_codes=("all_required_tracks_reachable_within_bounds",),
            )

        if current.depth >= policy.max_depth:
            depth_truncated = True
            continue
        if expanded >= policy.max_expanded_states:
            return _result(
                status=FeasibilityStatus.NOT_PROVEN_WITHIN_BUDGET,
                requirements=requirements,
                best_reached=best_reached,
                expanded_states=expanded,
                deepest_depth=deepest,
                budget_exhausted=True,
                policy=policy,
                context=transition_context,
                explanation_codes=("expanded_state_budget_exhausted",),
            )

        key = (
            current.track_id,
            current.segment_id,
            current.reached_required,
            current.future_used_tracks if not intent.allow_track_repeats else None,
            round(current.cumulative_duration_seconds, 6),
        )
        if key in seen:
            continue
        seen.add(key)
        expanded += 1
        deepest = max(deepest, current.depth)

        outgoing = repository.list_outgoing(
            source_track_id=current.track_id,
            source_segment_id=current.segment_id,
            context_id=transition_context.context_id,
            context_version=transition_context.context_version,
        )
        for assessment in outgoing:
            projection = assessment.contextual_projection
            if projection.blocked_reasons or projection.score is None:
                continue
            target_track = assessment.identity.target_track_id
            target_segment = assessment.identity.target_segment_id
            if target_track in intent.forbidden_track_ids:
                continue
            if not intent.allow_track_repeats and (
                target_track in existing_used or target_track in current.future_used_tracks
            ):
                continue
            position_index = len(sequence_state.selected_steps) + current.depth
            if not _locked_position_allows(
                intent=intent,
                position_index=position_index,
                assessment=assessment,
            ):
                continue
            scope_allowed, scope_evidence_missing = _scope_allows(
                intent=intent,
                track_id=target_track,
                style_tags_by_track=style_tags_by_track,
            )
            if scope_evidence_missing:
                evidence_gap = True
                continue
            if not scope_allowed:
                continue

            duration = 0.0
            if intent.target_duration_seconds is not None:
                assert target_duration_seconds_by_track is not None
                raw_duration = target_duration_seconds_by_track.get(target_track)
                if raw_duration is None or raw_duration <= 0.0:
                    evidence_gap = True
                    continue
                duration = float(raw_duration)
                maximum = intent.target_duration_seconds + intent.duration_tolerance_seconds
                if current.cumulative_duration_seconds + duration > maximum:
                    continue

            reached = current.reached_required
            if target_track in requirements:
                reached = reached | frozenset((target_track,))
            future_used = current.future_used_tracks | frozenset((target_track,))
            queue.append(
                _SearchState(
                    depth=current.depth + 1,
                    track_id=target_track,
                    segment_id=target_segment,
                    reached_required=reached,
                    future_used_tracks=future_used,
                    cumulative_duration_seconds=current.cumulative_duration_seconds + duration,
                )
            )

    if evidence_gap:
        status = FeasibilityStatus.NOT_PROVEN_MISSING_EVIDENCE
        codes = ("candidate_evidence_gap_prevented_complete_feasibility_proof",)
    elif depth_truncated:
        status = FeasibilityStatus.NOT_PROVEN_WITHIN_BUDGET
        codes = ("lookahead_depth_exhausted",)
    else:
        status = FeasibilityStatus.INFEASIBLE
        codes = ("frontier_exhausted_under_supported_hard_constraints",)
    return _result(
        status=status,
        requirements=requirements,
        best_reached=best_reached,
        expanded_states=expanded,
        deepest_depth=deepest,
        budget_exhausted=depth_truncated,
        policy=policy,
        context=transition_context,
        explanation_codes=codes,
    )


__all__ = ["evaluate_future_feasibility"]
