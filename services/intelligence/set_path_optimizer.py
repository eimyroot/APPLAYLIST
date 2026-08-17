from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass

from core.intelligence.set_contract import (
    CandidateDescriptor,
    PlaylistContext,
    PlaylistIntent,
    SequenceState,
    SetRankingPolicy,
    SetStep,
)
from core.intelligence.set_optimizer_contract import (
    SetOptimizerPolicy,
    SetOptimizerResult,
    SetOptimizerStatus,
    SetPathAlternative,
    SetPathObjective,
)
from core.intelligence.transition_contract import TransitionContext
from data.repositories.music_intelligence_repository import MusicIntelligenceRepository
from services.intelligence.phase_context import transition_context_for_phase
from services.intelligence.set_engine import recommend_next


@dataclass(frozen=True, slots=True)
class _PathNode:
    state: SequenceState
    added_steps: tuple[SetStep, ...]
    transition_ids: tuple[str, ...]
    candidate_scores: tuple[float, ...]
    explanation_codes: tuple[str, ...]
    evidence_refs: tuple[str, ...]


def _fingerprint(
    *,
    intent: PlaylistIntent,
    root_context: PlaylistContext,
    root_state: SequenceState,
    base_transition_context: TransitionContext,
    ranking_policy: SetRankingPolicy,
    optimizer_policy: SetOptimizerPolicy,
    target_duration_seconds_by_track: Mapping[str, float],
    style_tags_by_track: Mapping[str, tuple[str, ...]] | None,
    critical_warnings_by_track: Mapping[str, tuple[str, ...]] | None,
) -> str:
    payload = {
        "intent": asdict(intent),
        "root_context": asdict(root_context),
        "root_state": asdict(root_state),
        "base_transition_context": asdict(base_transition_context),
        "ranking_policy": asdict(ranking_policy),
        "optimizer_policy": asdict(optimizer_policy),
        "durations": sorted((str(key), float(value)) for key, value in target_duration_seconds_by_track.items()),
        "style_tags": (
            None
            if style_tags_by_track is None
            else sorted((str(key), tuple(value)) for key, value in style_tags_by_track.items())
        ),
        "critical_warnings": (
            None
            if critical_warnings_by_track is None
            else sorted((str(key), tuple(value)) for key, value in critical_warnings_by_track.items())
        ),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _normalized_position(intent: PlaylistIntent, state: SequenceState, root_context: PlaylistContext) -> float:
    if intent.target_track_count is not None:
        return min(1.0, len(state.selected_steps) / intent.target_track_count)
    if intent.target_duration_seconds is not None:
        return min(1.0, state.cumulative_duration_seconds / intent.target_duration_seconds)
    return min(1.0, max(0.0, root_context.phase_progress))


def _phase_for_state(intent: PlaylistIntent, state: SequenceState, root_context: PlaylistContext):
    position = _normalized_position(intent, state, root_context)
    for index, phase in enumerate(intent.phase_plan):
        is_last = index == len(intent.phase_plan) - 1
        if phase.target_fraction_start <= position < phase.target_fraction_end:
            return phase, position
        if is_last and position == 1.0 and phase.target_fraction_end == 1.0:
            return phase, position
    raise ValueError("phase plan does not cover optimizer position")


def _context_for_state(
    *,
    intent: PlaylistIntent,
    root_context: PlaylistContext,
    state: SequenceState,
) -> PlaylistContext:
    phase, position = _phase_for_state(intent, state, root_context)
    phase_span = phase.target_fraction_end - phase.target_fraction_start
    phase_progress = min(1.0, max(0.0, (position - phase.target_fraction_start) / phase_span))
    remaining_duration = None
    if intent.target_duration_seconds is not None:
        remaining_duration = max(0.0, intent.target_duration_seconds - state.cumulative_duration_seconds)
    remaining_track_count = None
    if intent.target_track_count is not None:
        remaining_track_count = max(0, intent.target_track_count - len(state.selected_steps))
    return PlaylistContext(
        context_id=f"{root_context.context_id}:optimizer",
        context_version=(
            f"{root_context.context_version}:phase:{phase.phase_id}:position:{len(state.selected_steps) - 1}"
        ),
        current_phase_id=phase.phase_id,
        current_position_index=len(state.selected_steps) - 1,
        elapsed_duration_seconds=state.cumulative_duration_seconds,
        phase_progress=phase_progress,
        current_track_id=state.current_track_id,
        current_segment_id=state.current_segment_id,
        current_energy_state=state.current_energy_state,
        remaining_duration_seconds=remaining_duration,
        remaining_track_count=remaining_track_count,
        context_evidence_refs=root_context.context_evidence_refs,
    )


def _descriptors_for_state(
    *,
    repository: MusicIntelligenceRepository,
    state: SequenceState,
    transition_context: TransitionContext,
    target_duration_seconds_by_track: Mapping[str, float],
    style_tags_by_track: Mapping[str, tuple[str, ...]] | None,
    critical_warnings_by_track: Mapping[str, tuple[str, ...]] | None,
) -> tuple[tuple[CandidateDescriptor, ...], bool]:
    assert state.current_track_id is not None and state.current_segment_id is not None
    outgoing = repository.list_outgoing(
        source_track_id=state.current_track_id,
        source_segment_id=state.current_segment_id,
        context_id=transition_context.context_id,
        context_version=transition_context.context_version,
    )
    descriptors: list[CandidateDescriptor] = []
    missing_duration_evidence = False
    for assessment in outgoing:
        track_id = assessment.identity.target_track_id
        raw_duration = target_duration_seconds_by_track.get(track_id)
        if raw_duration is None or float(raw_duration) <= 0.0:
            missing_duration_evidence = True
            continue
        descriptors.append(
            CandidateDescriptor(
                transition=assessment,
                target_duration_seconds=float(raw_duration),
                style_tags=(None if style_tags_by_track is None else style_tags_by_track.get(track_id)),
                critical_warnings=(
                    ()
                    if critical_warnings_by_track is None
                    else critical_warnings_by_track.get(track_id, ())
                ),
            )
        )
    return tuple(descriptors), missing_duration_evidence


def _state_version(root_state: SequenceState, transition_ids: tuple[str, ...]) -> str:
    material = "|".join((root_state.state_id, root_state.state_version, *transition_ids))
    return "optimizer-state-v1:" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:24]


def _advance_state(
    *,
    root_state: SequenceState,
    node: _PathNode,
    candidate,
    descriptor: CandidateDescriptor,
) -> _PathNode:
    assessment = descriptor.transition
    score = candidate.score
    if score is None:
        raise RuntimeError("eligible optimizer candidate must carry a score")
    order_index = len(node.state.selected_steps)
    step = SetStep(
        order_index=order_index,
        track_id=candidate.target_track_id,
        segment_id=candidate.target_segment_id,
        phase_id=candidate.phase_id,
        incoming_transition_id=assessment.identity.transition_id,
        chosen_strategy=assessment.preferred_strategy,
        local_projection_score=score,
        explanation_codes=candidate.explanation_codes,
        evidence_refs=candidate.evidence_refs,
    )
    selected_steps = node.state.selected_steps + (step,)
    used_tracks = node.state.used_track_ids + (candidate.target_track_id,)
    satisfied = tuple(
        item
        for item in root_state.remaining_required_track_ids
        if item in set(used_tracks)
    )
    already_satisfied = tuple(
        item
        for item in root_state.satisfied_required_track_ids
        if item not in satisfied
    )
    satisfied_all = tuple(dict.fromkeys((*already_satisfied, *satisfied)))
    remaining = tuple(
        item
        for item in node.state.remaining_required_track_ids
        if item != candidate.target_track_id
    )
    transition_ids = node.transition_ids + (assessment.identity.transition_id,)
    evidence_refs = tuple(
        sorted(set((*node.evidence_refs, *candidate.evidence_refs)))
    )
    explanations = tuple(
        dict.fromkeys((*node.explanation_codes, *candidate.explanation_codes))
    )
    next_state = SequenceState(
        state_id=root_state.state_id,
        state_version=_state_version(root_state, transition_ids),
        selected_steps=selected_steps,
        current_track_id=candidate.target_track_id,
        current_segment_id=candidate.target_segment_id,
        used_track_ids=used_tracks,
        cumulative_duration_seconds=candidate.resulting_state_preview.cumulative_duration_seconds,
        current_energy_state=(
            assessment.energy_effect.target_energy_state
            if assessment.energy_effect.target_energy_state is not None
            else node.state.current_energy_state
        ),
        satisfied_required_track_ids=satisfied_all,
        remaining_required_track_ids=remaining,
        warnings=node.state.warnings,
        evidence_refs=evidence_refs,
    )
    return _PathNode(
        state=next_state,
        added_steps=node.added_steps + (step,),
        transition_ids=transition_ids,
        candidate_scores=node.candidate_scores + (float(score),),
        explanation_codes=explanations,
        evidence_refs=evidence_refs,
    )


def _target_boundary_reached(intent: PlaylistIntent, state: SequenceState) -> bool:
    checks: list[bool] = []
    if intent.target_track_count is not None:
        checks.append(len(state.selected_steps) >= intent.target_track_count)
    if intent.target_duration_seconds is not None:
        minimum = max(0.0, intent.target_duration_seconds - intent.duration_tolerance_seconds)
        checks.append(state.cumulative_duration_seconds >= minimum)
    return bool(checks) and all(checks)


def _target_reached(intent: PlaylistIntent, state: SequenceState) -> bool:
    return _target_boundary_reached(intent, state) and not state.remaining_required_track_ids


def _required_completion(intent: PlaylistIntent, state: SequenceState) -> float:
    if not intent.required_track_ids:
        return 1.0
    return 1.0 - (len(state.remaining_required_track_ids) / len(intent.required_track_ids))


def _objective(intent: PlaylistIntent, node: _PathNode) -> SetPathObjective:
    scores = node.candidate_scores
    return SetPathObjective(
        depth=len(scores),
        mean_candidate_score=sum(scores) / len(scores),
        minimum_candidate_score=min(scores),
        required_track_completion=_required_completion(intent, node.state),
        remaining_required_count=len(node.state.remaining_required_track_ids),
        target_reached=_target_reached(intent, node.state),
    )


def _node_sort_key(intent: PlaylistIntent, node: _PathNode):
    objective = _objective(intent, node)
    return (
        0 if objective.target_reached else 1,
        objective.remaining_required_count,
        -objective.required_track_completion,
        -objective.mean_candidate_score,
        -objective.minimum_candidate_score,
        node.transition_ids,
        tuple(step.track_id for step in node.added_steps),
        tuple(step.segment_id for step in node.added_steps),
    )


def _path_id(fingerprint: str, transition_ids: tuple[str, ...]) -> str:
    material = "|".join((fingerprint, *transition_ids))
    return "sp_" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:32]


def _alternative(
    *,
    fingerprint: str,
    intent: PlaylistIntent,
    node: _PathNode,
    rank: int,
) -> SetPathAlternative:
    objective = _objective(intent, node)
    codes = list(node.explanation_codes)
    codes.append("bounded_beam_lookahead_v1")
    if objective.target_reached:
        codes.append("set_target_reached")
    if not node.state.remaining_required_track_ids:
        codes.append("required_tracks_satisfied")
    return SetPathAlternative(
        path_id=_path_id(fingerprint, node.transition_ids),
        rank=rank,
        added_steps=node.added_steps,
        resulting_state=node.state,
        transition_ids=node.transition_ids,
        candidate_scores=node.candidate_scores,
        objective=objective,
        explanation_codes=tuple(dict.fromkeys(codes)),
        evidence_refs=node.evidence_refs,
    )


def optimize_set_lookahead(
    *,
    repository: MusicIntelligenceRepository,
    intent: PlaylistIntent,
    root_context: PlaylistContext,
    root_state: SequenceState,
    base_transition_context: TransitionContext,
    ranking_policy: SetRankingPolicy,
    optimizer_policy: SetOptimizerPolicy,
    target_duration_seconds_by_track: Mapping[str, float],
    generated_at: str,
    style_tags_by_track: Mapping[str, tuple[str, ...]] | None = None,
    critical_warnings_by_track: Mapping[str, tuple[str, ...]] | None = None,
) -> SetOptimizerResult:
    """Run deterministic bounded beam/lookahead over persisted TransitionAssessment edges.

    V1 deliberately reuses ``recommend_next`` as the single candidate eligibility and
    Set Intelligence ranking authority. The optimizer owns sequence search only. It
    does not remeasure music, reinterpret TransitionAssessment evidence, or require a
    graph/vector database.
    """
    if root_state.current_track_id is None or root_state.current_segment_id is None:
        raise ValueError("set optimizer requires a seeded sequence state")
    if root_context.current_track_id != root_state.current_track_id:
        raise ValueError("root context track must match root state")
    if root_context.current_segment_id != root_state.current_segment_id:
        raise ValueError("root context segment must match root state")
    if root_context.current_position_index != len(root_state.selected_steps) - 1:
        raise ValueError("root context position must match root state")
    if not str(generated_at).strip():
        raise ValueError("generated_at must not be empty")

    fingerprint = _fingerprint(
        intent=intent,
        root_context=root_context,
        root_state=root_state,
        base_transition_context=base_transition_context,
        ranking_policy=ranking_policy,
        optimizer_policy=optimizer_policy,
        target_duration_seconds_by_track=target_duration_seconds_by_track,
        style_tags_by_track=style_tags_by_track,
        critical_warnings_by_track=critical_warnings_by_track,
    )
    root = _PathNode(
        state=root_state,
        added_steps=(),
        transition_ids=(),
        candidate_scores=(),
        explanation_codes=(),
        evidence_refs=root_state.evidence_refs,
    )
    frontier: tuple[_PathNode, ...] = (root,)
    deepest_nodes: tuple[_PathNode, ...] = ()
    completed_nodes: list[_PathNode] = []
    deepest_depth = 0
    expanded_candidates = 0
    beam_pruned_candidates = 0
    budget_exhausted = False
    missing_evidence = False

    for depth in range(1, optimizer_policy.max_depth + 1):
        expansions: list[_PathNode] = []
        for node in frontier:
            if _target_reached(intent, node.state):
                completed_nodes.append(node)
                continue
            if _target_boundary_reached(intent, node.state):
                continue

            set_context = _context_for_state(
                intent=intent,
                root_context=root_context,
                state=node.state,
            )
            phase = intent.phase(set_context.current_phase_id)
            transition_context = transition_context_for_phase(
                phase=phase,
                base_context=base_transition_context,
            )
            descriptors, evidence_gap = _descriptors_for_state(
                repository=repository,
                state=node.state,
                transition_context=transition_context,
                target_duration_seconds_by_track=target_duration_seconds_by_track,
                style_tags_by_track=style_tags_by_track,
                critical_warnings_by_track=critical_warnings_by_track,
            )
            missing_evidence = missing_evidence or evidence_gap
            if not descriptors:
                continue

            candidate_set = recommend_next(
                intent=intent,
                context=set_context,
                sequence_state=node.state,
                transition_edges=descriptors,
                ranking_policy=ranking_policy,
                candidate_limit=optimizer_policy.per_state_candidate_limit,
                generated_at=generated_at,
            )
            descriptors_by_transition_id = {
                item.transition.identity.transition_id: item for item in descriptors
            }
            for candidate in candidate_set.eligible_candidates:
                if expanded_candidates >= optimizer_policy.max_expanded_candidates:
                    budget_exhausted = True
                    break
                descriptor = descriptors_by_transition_id[candidate.transition_assessment_id]
                child = _advance_state(
                    root_state=root_state,
                    node=node,
                    candidate=candidate,
                    descriptor=descriptor,
                )
                expanded_candidates += 1
                if _target_reached(intent, child.state):
                    completed_nodes.append(child)
                else:
                    expansions.append(child)
            if budget_exhausted:
                break
        if budget_exhausted:
            break
        if completed_nodes:
            best_completed_depth = max(len(item.added_steps) for item in completed_nodes)
            deepest_depth = max(deepest_depth, best_completed_depth)
        if not expansions:
            break
        expansions.sort(key=lambda item: _node_sort_key(intent, item))
        if len(expansions) > optimizer_policy.beam_width:
            beam_pruned_candidates += len(expansions) - optimizer_policy.beam_width
        frontier = tuple(expansions[: optimizer_policy.beam_width])
        deepest_nodes = frontier
        deepest_depth = depth

    if completed_nodes:
        pool = sorted(completed_nodes, key=lambda item: _node_sort_key(intent, item))
        status = SetOptimizerStatus.TARGET_REACHED
    elif deepest_nodes:
        pool = sorted(deepest_nodes, key=lambda item: _node_sort_key(intent, item))
        status = (
            SetOptimizerStatus.BUDGET_EXHAUSTED
            if budget_exhausted
            else SetOptimizerStatus.PATHS_FOUND
        )
    else:
        pool = []
        if budget_exhausted:
            status = SetOptimizerStatus.BUDGET_EXHAUSTED
        elif missing_evidence:
            status = SetOptimizerStatus.NOT_PROVEN_MISSING_EVIDENCE
        else:
            status = SetOptimizerStatus.NO_ELIGIBLE_PATH

    selected = pool[: optimizer_policy.alternative_limit]
    alternatives = tuple(
        _alternative(fingerprint=fingerprint, intent=intent, node=node, rank=index + 1)
        for index, node in enumerate(selected)
    )
    explanation_codes: list[str] = ["deterministic_bounded_beam_search_v1"]
    if beam_pruned_candidates:
        explanation_codes.append("beam_width_pruned_frontier")
    if budget_exhausted:
        explanation_codes.append("expanded_candidate_budget_exhausted")
    if missing_evidence:
        explanation_codes.append("candidate_duration_evidence_missing")
    if status is SetOptimizerStatus.NO_ELIGIBLE_PATH:
        explanation_codes.append("no_eligible_persisted_path_within_horizon")

    warnings: list[str] = []
    if beam_pruned_candidates:
        warnings.append("bounded search intentionally pruned lower-priority frontier states")
    if missing_evidence:
        warnings.append("one or more persisted outgoing edges lacked target duration evidence")
    warnings.append(
        "future feasibility is not a hard beam prune in optimizer v1 because its current contract uses one fixed TransitionContext across the evaluated horizon"
    )

    result_id = "sor_" + hashlib.sha256(
        (fingerprint + "|" + optimizer_policy.optimizer_version).encode("utf-8")
    ).hexdigest()[:32]
    return SetOptimizerResult(
        result_id=result_id,
        input_fingerprint=fingerprint,
        optimizer_ref=(optimizer_policy.optimizer_id, optimizer_policy.optimizer_version),
        intent_ref=(intent.intent_id, intent.intent_version),
        root_state_ref=(root_state.state_id, root_state.state_version),
        base_transition_context_ref=(
            base_transition_context.context_id,
            base_transition_context.context_version,
        ),
        status=status,
        alternatives=alternatives,
        deepest_depth=deepest_depth,
        expanded_candidates=expanded_candidates,
        beam_pruned_candidates=beam_pruned_candidates,
        budget_exhausted=budget_exhausted,
        missing_evidence_detected=missing_evidence,
        deterministic_ordering=True,
        explanation_codes=tuple(explanation_codes),
        warnings=tuple(warnings),
    )


__all__ = ["optimize_set_lookahead"]
