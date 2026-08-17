from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import asdict

from core.intelligence.set_contract import (
    PlaylistContext,
    PlaylistIntent,
    SequenceState,
    SetRankingPolicy,
)
from core.intelligence.set_optimizer_contract import (
    SetOptimizerPolicy,
    SetOptimizerResult,
    SetOptimizerStatus,
)
from core.intelligence.set_optimizer_evaluation_contract import (
    OPTIMIZER_BENCHMARK_CONTRACT_VERSION,
    AlternativeDiversityPolicy,
    BenchmarkStrategy,
    OptimizerBenchmarkComparison,
    OptimizerBenchmarkMetrics,
)
from core.intelligence.transition_contract import TransitionContext
from data.repositories.music_intelligence_repository import MusicIntelligenceRepository
from services.intelligence.alternative_diversity import select_diverse_alternatives
from services.intelligence.set_path_optimizer import optimize_set_lookahead

GREEDY_BENCHMARK_POLICY_VERSION = "greedy-recommend-next-v1"


def _scenario_fingerprint(
    *,
    intent: PlaylistIntent,
    root_context: PlaylistContext,
    root_state: SequenceState,
    base_transition_context: TransitionContext,
    ranking_policy: SetRankingPolicy,
    beam_policy: SetOptimizerPolicy,
    diversity_policy: AlternativeDiversityPolicy,
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
        "beam_policy": asdict(beam_policy),
        "diversity_policy": asdict(diversity_policy),
        "durations": sorted(
            (str(key), float(value))
            for key, value in target_duration_seconds_by_track.items()
        ),
        "style_tags": (
            None
            if style_tags_by_track is None
            else sorted((str(key), tuple(value)) for key, value in style_tags_by_track.items())
        ),
        "critical_warnings": (
            None
            if critical_warnings_by_track is None
            else sorted(
                (str(key), tuple(value))
                for key, value in critical_warnings_by_track.items()
            )
        ),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def greedy_recommend_next_policy_v1(beam_policy: SetOptimizerPolicy) -> SetOptimizerPolicy:
    """Derive a strict greedy baseline from the same horizon/search budget family."""
    return SetOptimizerPolicy(
        optimizer_id="greedy-recommend-next",
        optimizer_version=GREEDY_BENCHMARK_POLICY_VERSION,
        beam_width=1,
        max_depth=beam_policy.max_depth,
        per_state_candidate_limit=1,
        max_expanded_candidates=beam_policy.max_expanded_candidates,
        alternative_limit=1,
    )


def _required_completion(intent: PlaylistIntent, root_state: SequenceState) -> float:
    if not intent.required_track_ids:
        return 1.0
    return 1.0 - (
        len(root_state.remaining_required_track_ids) / len(intent.required_track_ids)
    )


def _metrics(
    *,
    strategy: BenchmarkStrategy,
    result: SetOptimizerResult,
    intent: PlaylistIntent,
    root_state: SequenceState,
    deterministic_replay_match: bool,
) -> OptimizerBenchmarkMetrics:
    if result.alternatives:
        best = result.alternatives[0].objective
        required_completion = best.required_track_completion
        mean_score = best.mean_candidate_score
        minimum_score = best.minimum_candidate_score
        target_reached = best.target_reached
    else:
        required_completion = _required_completion(intent, root_state)
        mean_score = None
        minimum_score = None
        target_reached = result.status is SetOptimizerStatus.TARGET_REACHED

    return OptimizerBenchmarkMetrics(
        strategy=strategy,
        optimizer_ref=result.optimizer_ref,
        result_id=result.result_id,
        status=result.status,
        target_reached=target_reached,
        best_required_track_completion=required_completion,
        best_mean_candidate_score=mean_score,
        best_minimum_candidate_score=minimum_score,
        deepest_depth=result.deepest_depth,
        expanded_candidates=result.expanded_candidates,
        beam_pruned_candidates=result.beam_pruned_candidates,
        budget_exhausted=result.budget_exhausted,
        missing_evidence_detected=result.missing_evidence_detected,
        alternative_count=len(result.alternatives),
        deterministic_replay_match=deterministic_replay_match,
    )


def benchmark_greedy_vs_beam(
    *,
    repository: MusicIntelligenceRepository,
    intent: PlaylistIntent,
    root_context: PlaylistContext,
    root_state: SequenceState,
    base_transition_context: TransitionContext,
    ranking_policy: SetRankingPolicy,
    beam_policy: SetOptimizerPolicy,
    diversity_policy: AlternativeDiversityPolicy,
    target_duration_seconds_by_track: Mapping[str, float],
    generated_at: str,
    style_tags_by_track: Mapping[str, tuple[str, ...]] | None = None,
    critical_warnings_by_track: Mapping[str, tuple[str, ...]] | None = None,
) -> OptimizerBenchmarkComparison:
    """Produce evidence-only greedy-vs-beam benchmark metrics.

    Both strategies consume identical music evidence, intent, context and Set
    Intelligence ranking semantics. Greedy is defined as Top-1 `recommend_next` at
    every depth. Beam uses the supplied bounded policy. The benchmark never changes
    active ranking/search policy and cannot authorize production activation.
    """
    if diversity_policy.alternative_limit > beam_policy.alternative_limit:
        raise ValueError(
            "diversity alternative_limit cannot exceed beam policy alternative_limit"
        )

    common = dict(
        repository=repository,
        intent=intent,
        root_context=root_context,
        root_state=root_state,
        base_transition_context=base_transition_context,
        ranking_policy=ranking_policy,
        target_duration_seconds_by_track=target_duration_seconds_by_track,
        generated_at=generated_at,
        style_tags_by_track=style_tags_by_track,
        critical_warnings_by_track=critical_warnings_by_track,
    )
    greedy_policy = greedy_recommend_next_policy_v1(beam_policy)

    greedy = optimize_set_lookahead(optimizer_policy=greedy_policy, **common)
    greedy_replay = optimize_set_lookahead(optimizer_policy=greedy_policy, **common)
    beam = optimize_set_lookahead(optimizer_policy=beam_policy, **common)
    beam_replay = optimize_set_lookahead(optimizer_policy=beam_policy, **common)

    diverse = select_diverse_alternatives(result=beam, policy=diversity_policy)
    greedy_metrics = _metrics(
        strategy=BenchmarkStrategy.GREEDY_RECOMMEND_NEXT,
        result=greedy,
        intent=intent,
        root_state=root_state,
        deterministic_replay_match=greedy == greedy_replay,
    )
    beam_metrics = _metrics(
        strategy=BenchmarkStrategy.BOUNDED_BEAM,
        result=beam,
        intent=intent,
        root_state=root_state,
        deterministic_replay_match=beam == beam_replay,
    )

    fingerprint = _scenario_fingerprint(
        intent=intent,
        root_context=root_context,
        root_state=root_state,
        base_transition_context=base_transition_context,
        ranking_policy=ranking_policy,
        beam_policy=beam_policy,
        diversity_policy=diversity_policy,
        target_duration_seconds_by_track=target_duration_seconds_by_track,
        style_tags_by_track=style_tags_by_track,
        critical_warnings_by_track=critical_warnings_by_track,
    )
    benchmark_id = "sob_" + hashlib.sha256(
        (
            fingerprint
            + "|"
            + greedy.result_id
            + "|"
            + beam.result_id
            + "|"
            + diverse.selection_id
        ).encode("utf-8")
    ).hexdigest()[:32]

    rejected_count = sum(
        1
        for decision in diverse.decisions
        if not decision.selected and "alternative_limit_reached" not in decision.reason_codes
    )
    explanations = ["evidence_only_optimizer_benchmark_v1"]
    if beam_metrics.target_reached and not greedy_metrics.target_reached:
        explanations.append("beam_reached_target_greedy_missed")
    if rejected_count:
        explanations.append("near_duplicate_alternatives_filtered")
    if not greedy_metrics.deterministic_replay_match:
        explanations.append("greedy_replay_mismatch")
    if not beam_metrics.deterministic_replay_match:
        explanations.append("beam_replay_mismatch")

    return OptimizerBenchmarkComparison(
        benchmark_id=benchmark_id,
        scenario_fingerprint=fingerprint,
        contract_version=OPTIMIZER_BENCHMARK_CONTRACT_VERSION,
        greedy=greedy_metrics,
        beam=beam_metrics,
        diverse_beam_selection=diverse,
        beam_reaches_target_when_greedy_does_not=(
            beam_metrics.target_reached and not greedy_metrics.target_reached
        ),
        required_track_completion_delta=(
            beam_metrics.best_required_track_completion
            - greedy_metrics.best_required_track_completion
        ),
        expanded_candidate_delta=(
            beam_metrics.expanded_candidates - greedy_metrics.expanded_candidates
        ),
        diversity_rejected_count=rejected_count,
        activation_authorized=False,
        explanation_codes=tuple(explanations),
    )


__all__ = [
    "GREEDY_BENCHMARK_POLICY_VERSION",
    "benchmark_greedy_vs_beam",
    "greedy_recommend_next_policy_v1",
]
