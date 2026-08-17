from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass

from core.intelligence.set_contract import (
    PlaylistContext,
    PlaylistIntent,
    SequenceState,
    SetRankingPolicy,
)
from core.intelligence.set_optimizer_acceptance_contract import (
    REPRESENTATIVE_BENCHMARK_CORPUS_VERSION,
    CorpusAcceptanceVerdict,
    OptimizerAcceptanceThresholds,
    RepresentativeCorpusAcceptance,
    RepresentativeScenarioCategory,
    ScenarioAcceptanceExpectation,
    ScenarioAcceptanceObservation,
)
from core.intelligence.set_optimizer_contract import SetOptimizerPolicy
from core.intelligence.set_optimizer_evaluation_contract import AlternativeDiversityPolicy
from core.intelligence.transition_contract import TransitionContext
from data.repositories.music_intelligence_repository import MusicIntelligenceRepository
from services.intelligence.set_optimizer_benchmark import benchmark_greedy_vs_beam


@dataclass(frozen=True, slots=True)
class RepresentativeBenchmarkScenario:
    expectation: ScenarioAcceptanceExpectation
    repository: MusicIntelligenceRepository
    intent: PlaylistIntent
    root_context: PlaylistContext
    root_state: SequenceState
    base_transition_context: TransitionContext
    ranking_policy: SetRankingPolicy
    beam_policy: SetOptimizerPolicy
    diversity_policy: AlternativeDiversityPolicy
    target_duration_seconds_by_track: Mapping[str, float]
    generated_at: str
    style_tags_by_track: Mapping[str, tuple[str, ...]] | None = None
    critical_warnings_by_track: Mapping[str, tuple[str, ...]] | None = None

    def __post_init__(self) -> None:
        if not str(self.generated_at).strip():
            raise ValueError("generated_at must not be empty")


def _observe(scenario: RepresentativeBenchmarkScenario) -> ScenarioAcceptanceObservation:
    comparison = benchmark_greedy_vs_beam(
        repository=scenario.repository,
        intent=scenario.intent,
        root_context=scenario.root_context,
        root_state=scenario.root_state,
        base_transition_context=scenario.base_transition_context,
        ranking_policy=scenario.ranking_policy,
        beam_policy=scenario.beam_policy,
        diversity_policy=scenario.diversity_policy,
        target_duration_seconds_by_track=scenario.target_duration_seconds_by_track,
        generated_at=scenario.generated_at,
        style_tags_by_track=scenario.style_tags_by_track,
        critical_warnings_by_track=scenario.critical_warnings_by_track,
    )
    expectation = scenario.expectation
    reasons: list[str] = []

    if comparison.beam.status not in expectation.expected_beam_statuses:
        reasons.append("unexpected_beam_status")
    if (
        expectation.require_beam_target_reached is not None
        and comparison.beam.target_reached != expectation.require_beam_target_reached
    ):
        reasons.append("beam_target_reach_expectation_failed")
    if (
        expectation.require_greedy_target_reached is not None
        and comparison.greedy.target_reached != expectation.require_greedy_target_reached
    ):
        reasons.append("greedy_target_reach_expectation_failed")
    if (
        expectation.require_beam_reaches_when_greedy_misses
        and not comparison.beam_reaches_target_when_greedy_does_not
    ):
        reasons.append("expected_beam_win_missing")
    if (
        comparison.beam.best_required_track_completion
        < expectation.minimum_required_track_completion
    ):
        reasons.append("required_track_completion_below_threshold")
    if (
        expectation.require_beam_not_worse_required_completion
        and comparison.beam.best_required_track_completion
        < comparison.greedy.best_required_track_completion
    ):
        reasons.append("beam_required_track_completion_regressed")
    if expectation.require_deterministic_replay and (
        not comparison.greedy.deterministic_replay_match
        or not comparison.beam.deterministic_replay_match
    ):
        reasons.append("deterministic_replay_failed")

    # Evidence gaps are corpus evidence regardless of which benchmark strategy first
    # encounters them. Expected beam status still proves beam-specific semantics where
    # the manifest requires it, but global safety counters must not ignore greedy gaps.
    missing_evidence = (
        comparison.greedy.missing_evidence_detected
        or comparison.beam.missing_evidence_detected
    )
    if expectation.require_missing_evidence and not missing_evidence:
        reasons.append("expected_missing_evidence_not_observed")
    if missing_evidence and not expectation.allow_missing_evidence:
        reasons.append("unexpected_missing_evidence")

    budget_exhausted = comparison.greedy.budget_exhausted or comparison.beam.budget_exhausted
    if expectation.require_budget_exhaustion and not comparison.beam.budget_exhausted:
        reasons.append("expected_budget_exhaustion_not_observed")
    if budget_exhausted and not expectation.allow_budget_exhaustion:
        reasons.append("unexpected_budget_exhaustion")

    if comparison.beam.beam_pruned_candidates < expectation.minimum_beam_pruned_candidates:
        reasons.append("beam_pruning_below_threshold")
    if comparison.diversity_rejected_count < expectation.minimum_diversity_rejected_count:
        reasons.append("diversity_filtering_below_threshold")
    diverse_count = len(comparison.diverse_beam_selection.selected_alternatives)
    if diverse_count < expectation.minimum_diverse_alternatives:
        reasons.append("diverse_alternative_count_below_threshold")

    return ScenarioAcceptanceObservation(
        scenario_id=expectation.scenario_id,
        category=expectation.category,
        benchmark_id=comparison.benchmark_id,
        passed=not reasons,
        greedy_status=comparison.greedy.status,
        beam_status=comparison.beam.status,
        greedy_target_reached=comparison.greedy.target_reached,
        beam_target_reached=comparison.beam.target_reached,
        beam_reaches_target_when_greedy_does_not=(
            comparison.beam_reaches_target_when_greedy_does_not
        ),
        greedy_required_track_completion=(
            comparison.greedy.best_required_track_completion
        ),
        beam_required_track_completion=comparison.beam.best_required_track_completion,
        greedy_deterministic_replay_match=(
            comparison.greedy.deterministic_replay_match
        ),
        beam_deterministic_replay_match=comparison.beam.deterministic_replay_match,
        beam_pruned_candidates=comparison.beam.beam_pruned_candidates,
        diversity_rejected_count=comparison.diversity_rejected_count,
        diverse_alternative_count=diverse_count,
        missing_evidence_detected=missing_evidence,
        budget_exhausted=budget_exhausted,
        reason_codes=("scenario_acceptance_pass",) if not reasons else tuple(reasons),
    )


def evaluate_representative_benchmark_corpus_r1(
    *,
    scenarios: Sequence[RepresentativeBenchmarkScenario],
    thresholds: OptimizerAcceptanceThresholds = OptimizerAcceptanceThresholds(),
) -> RepresentativeCorpusAcceptance:
    """Evaluate the governed R1 optimizer corpus without authorizing activation.

    These are engineering correctness/safety acceptance gates. They intentionally do
    not claim musical superiority, user preference fit, or DJ-quality acceptance.
    """
    scenario_tuple = tuple(scenarios)
    scenario_ids = tuple(item.expectation.scenario_id for item in scenario_tuple)
    if len(set(scenario_ids)) != len(scenario_ids):
        raise ValueError("representative benchmark scenario ids must be unique")

    observations = tuple(_observe(item) for item in scenario_tuple)
    covered = tuple(
        category
        for category in RepresentativeScenarioCategory
        if any(item.category is category for item in observations)
    )
    missing = tuple(
        category for category in thresholds.required_categories if category not in covered
    )

    replay_successes = sum(
        1
        for item in observations
        if item.greedy_deterministic_replay_match
        and item.beam_deterministic_replay_match
    )
    replay_rate = replay_successes / len(observations) if observations else 0.0
    failure_count = sum(1 for item in observations if not item.passed)

    expectation_by_id = {
        item.expectation.scenario_id: item.expectation for item in scenario_tuple
    }
    expected_beam_wins = sum(
        1
        for item in observations
        if expectation_by_id[item.scenario_id].require_beam_reaches_when_greedy_misses
        and item.beam_reaches_target_when_greedy_does_not
    )
    unexpected_missing_evidence = sum(
        1
        for item in observations
        if item.missing_evidence_detected
        and not expectation_by_id[item.scenario_id].allow_missing_evidence
    )
    unexpected_budget_exhaustions = sum(
        1
        for item in observations
        if item.budget_exhausted
        and not expectation_by_id[item.scenario_id].allow_budget_exhaustion
    )

    incomplete = len(observations) < thresholds.minimum_scenarios or bool(missing)
    threshold_failures: list[str] = []
    if replay_rate < thresholds.minimum_deterministic_replay_rate:
        threshold_failures.append("deterministic_replay_rate_below_threshold")
    if failure_count > thresholds.maximum_scenario_failures:
        threshold_failures.append("scenario_failure_count_above_threshold")
    if (
        unexpected_missing_evidence
        > thresholds.maximum_unexpected_missing_evidence
    ):
        threshold_failures.append("unexpected_missing_evidence_above_threshold")
    if (
        unexpected_budget_exhaustions
        > thresholds.maximum_unexpected_budget_exhaustions
    ):
        threshold_failures.append("unexpected_budget_exhaustion_above_threshold")
    if expected_beam_wins < thresholds.minimum_expected_beam_wins:
        threshold_failures.append("expected_beam_win_count_below_threshold")

    # Known correctness failures are stronger evidence than missing coverage. An
    # incomplete corpus may not PASS, but it also must not hide an observed FAIL.
    if threshold_failures:
        verdict = CorpusAcceptanceVerdict.FAIL
    elif incomplete:
        verdict = CorpusAcceptanceVerdict.INCOMPLETE
    else:
        verdict = CorpusAcceptanceVerdict.PASS

    material = {
        "corpus_version": REPRESENTATIVE_BENCHMARK_CORPUS_VERSION,
        "thresholds": asdict(thresholds),
        "scenario_ids": scenario_ids,
        "benchmark_ids": tuple(item.benchmark_id for item in observations),
        "verdict": verdict,
    }
    encoded = json.dumps(material, sort_keys=True, separators=(",", ":"), default=str)
    corpus_id = "sac_" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:32]

    explanation_codes: list[str] = ["representative_optimizer_corpus_r1"]
    if incomplete:
        explanation_codes.append("representative_corpus_coverage_incomplete")
    explanation_codes.extend(threshold_failures)
    if verdict is CorpusAcceptanceVerdict.PASS:
        explanation_codes.append("engineering_acceptance_thresholds_passed")
    explanation_codes.append("musical_quality_not_established_by_r1")
    explanation_codes.append("optimizer_activation_not_authorized")

    return RepresentativeCorpusAcceptance(
        corpus_id=corpus_id,
        corpus_version=REPRESENTATIVE_BENCHMARK_CORPUS_VERSION,
        thresholds_ref=(thresholds.policy_id, thresholds.policy_version),
        scenario_count=len(observations),
        covered_categories=covered,
        missing_categories=missing,
        observations=observations,
        deterministic_replay_rate=replay_rate,
        scenario_failure_count=failure_count,
        expected_beam_win_count=expected_beam_wins,
        unexpected_missing_evidence_count=unexpected_missing_evidence,
        unexpected_budget_exhaustion_count=unexpected_budget_exhaustions,
        verdict=verdict,
        activation_authorized=False,
        explanation_codes=tuple(explanation_codes),
    )


__all__ = [
    "RepresentativeBenchmarkScenario",
    "evaluate_representative_benchmark_corpus_r1",
]
