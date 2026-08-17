from __future__ import annotations

from dataclasses import replace

import pytest

from core.intelligence.set_contract import SequenceState, SetStep
from core.intelligence.set_optimizer_acceptance_contract import (
    REPRESENTATIVE_BENCHMARK_CATEGORIES_R1,
    CorpusAcceptanceVerdict,
    OptimizerAcceptanceThresholds,
)
from core.intelligence.set_optimizer_contract import (
    SetOptimizerStatus,
    SetPathAlternative,
    SetPathObjective,
)
from core.intelligence.set_optimizer_corpus_manifest import (
    representative_benchmark_expectations_r1,
)
from core.intelligence.set_optimizer_evaluation_contract import (
    AlternativeDiversityDecision,
    BenchmarkStrategy,
    OptimizerBenchmarkComparison,
    OptimizerBenchmarkMetrics,
    SetAlternativeSelection,
)
from services.intelligence.set_optimizer_acceptance import (
    RepresentativeBenchmarkScenario,
    evaluate_representative_benchmark_corpus_r1,
)


def _alternative(path_id: str = "path-1") -> SetPathAlternative:
    root = SetStep(
        order_index=0,
        track_id="root",
        segment_id="root:whole",
        phase_id="phase-1",
    )
    added = SetStep(
        order_index=1,
        track_id="track-b",
        segment_id="track-b:whole",
        phase_id="phase-1",
        incoming_transition_id="transition-1",
        local_projection_score=0.8,
    )
    state = SequenceState(
        state_id=f"state:{path_id}",
        state_version="1",
        selected_steps=(root, added),
        current_track_id="track-b",
        current_segment_id="track-b:whole",
        used_track_ids=("root", "track-b"),
        cumulative_duration_seconds=600.0,
        current_energy_state=0.6,
    )
    return SetPathAlternative(
        path_id=path_id,
        rank=1,
        added_steps=(added,),
        resulting_state=state,
        transition_ids=("transition-1",),
        candidate_scores=(0.8,),
        objective=SetPathObjective(
            depth=1,
            mean_candidate_score=0.8,
            minimum_candidate_score=0.8,
            required_track_completion=1.0,
            remaining_required_count=0,
            target_reached=True,
        ),
        explanation_codes=("fixture",),
        evidence_refs=("evidence:fixture",),
    )


def _metrics(
    *,
    strategy: BenchmarkStrategy,
    status: SetOptimizerStatus,
    target: bool,
    completion: float = 1.0,
    replay: bool = True,
    pruned: int = 0,
    missing: bool = False,
    budget: bool = False,
    alternative_count: int = 1,
) -> OptimizerBenchmarkMetrics:
    return OptimizerBenchmarkMetrics(
        strategy=strategy,
        optimizer_ref=("optimizer", "v1"),
        result_id=f"result:{strategy.value}:{status.value}",
        status=status,
        target_reached=target,
        best_required_track_completion=completion,
        best_mean_candidate_score=0.8 if alternative_count else None,
        best_minimum_candidate_score=0.8 if alternative_count else None,
        deepest_depth=2,
        expanded_candidates=4,
        beam_pruned_candidates=pruned,
        budget_exhausted=budget,
        missing_evidence_detected=missing,
        alternative_count=alternative_count,
        deterministic_replay_match=replay,
    )


def _comparison(scenario_id: str) -> OptimizerBenchmarkComparison:
    greedy_status = SetOptimizerStatus.TARGET_REACHED
    beam_status = SetOptimizerStatus.TARGET_REACHED
    greedy_target = True
    beam_target = True
    greedy_completion = 1.0
    beam_completion = 1.0
    pruned = 0
    missing = False
    budget = False
    selected_alternatives = (_alternative(),)
    decisions: tuple[AlternativeDiversityDecision, ...] = ()

    if scenario_id == "r1-greedy-dead-end":
        greedy_status = SetOptimizerStatus.PATHS_FOUND
        greedy_target = False
    elif scenario_id == "r1-required-tracks":
        greedy_completion = 0.5
    elif scenario_id == "r1-missing-evidence":
        greedy_status = SetOptimizerStatus.NOT_PROVEN_MISSING_EVIDENCE
        beam_status = SetOptimizerStatus.NOT_PROVEN_MISSING_EVIDENCE
        greedy_target = False
        beam_target = False
        missing = True
        selected_alternatives = ()
    elif scenario_id == "r1-budget-truncation":
        greedy_status = SetOptimizerStatus.BUDGET_EXHAUSTED
        beam_status = SetOptimizerStatus.BUDGET_EXHAUSTED
        greedy_target = False
        beam_target = False
        budget = True
    elif scenario_id == "r1-high-branching":
        greedy_status = SetOptimizerStatus.PATHS_FOUND
        beam_status = SetOptimizerStatus.PATHS_FOUND
        greedy_target = False
        beam_target = False
        pruned = 3
    elif scenario_id == "r1-alternative-near-duplicate-pressure":
        decisions = (
            AlternativeDiversityDecision(
                path_id="near-duplicate",
                source_rank=2,
                selected=False,
                nearest_selected_path_id="path-1",
                track_jaccard=1.0,
                shared_prefix_fraction=1.0,
                differing_positions=0,
                reason_codes=("track_jaccard_above_policy",),
            ),
        )

    selection = SetAlternativeSelection(
        selection_id=f"selection:{scenario_id}",
        source_result_id=f"beam:{scenario_id}",
        source_input_fingerprint=f"fingerprint:{scenario_id}",
        policy_ref=("diversity", "v1"),
        selected_alternatives=selected_alternatives,
        decisions=decisions,
        requested_limit=2,
        similarity_fallback_used=False,
    )
    greedy = _metrics(
        strategy=BenchmarkStrategy.GREEDY_RECOMMEND_NEXT,
        status=greedy_status,
        target=greedy_target,
        completion=greedy_completion,
        missing=missing,
        budget=budget,
        alternative_count=0 if not selected_alternatives else 1,
    )
    beam = _metrics(
        strategy=BenchmarkStrategy.BOUNDED_BEAM,
        status=beam_status,
        target=beam_target,
        completion=beam_completion,
        pruned=pruned,
        missing=missing,
        budget=budget,
        alternative_count=0 if not selected_alternatives else 1,
    )
    return OptimizerBenchmarkComparison(
        benchmark_id=f"benchmark:{scenario_id}",
        scenario_fingerprint=f"fingerprint:{scenario_id}",
        contract_version="optimizer-benchmark-v1",
        greedy=greedy,
        beam=beam,
        diverse_beam_selection=selection,
        beam_reaches_target_when_greedy_does_not=(beam_target and not greedy_target),
        required_track_completion_delta=beam_completion - greedy_completion,
        expanded_candidate_delta=2,
        diversity_rejected_count=sum(1 for item in decisions if not item.selected),
        activation_authorized=False,
    )


def _scenarios() -> tuple[RepresentativeBenchmarkScenario, ...]:
    scenarios = []
    for expectation in representative_benchmark_expectations_r1():
        scenarios.append(
            RepresentativeBenchmarkScenario(
                expectation=expectation,
                repository=object(),  # type: ignore[arg-type]
                intent=object(),  # type: ignore[arg-type]
                root_context=object(),  # type: ignore[arg-type]
                root_state=object(),  # type: ignore[arg-type]
                base_transition_context=object(),  # type: ignore[arg-type]
                ranking_policy=object(),  # type: ignore[arg-type]
                beam_policy=object(),  # type: ignore[arg-type]
                diversity_policy=object(),  # type: ignore[arg-type]
                target_duration_seconds_by_track={},
                generated_at=expectation.scenario_id,
            )
        )
    return tuple(scenarios)


def test_r1_manifest_covers_every_required_category_once() -> None:
    expectations = representative_benchmark_expectations_r1()
    assert len(expectations) == 10
    assert tuple(item.category for item in expectations) == REPRESENTATIVE_BENCHMARK_CATEGORIES_R1
    assert len({item.scenario_id for item in expectations}) == len(expectations)


def test_full_r1_corpus_passes_only_after_complete_coverage(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "services.intelligence.set_optimizer_acceptance.benchmark_greedy_vs_beam",
        lambda **kwargs: _comparison(kwargs["generated_at"]),
    )

    result = evaluate_representative_benchmark_corpus_r1(scenarios=_scenarios())

    assert result.verdict is CorpusAcceptanceVerdict.PASS
    assert result.scenario_count == 10
    assert result.missing_categories == ()
    assert result.deterministic_replay_rate == 1.0
    assert result.scenario_failure_count == 0
    assert result.expected_beam_win_count == 1
    assert result.unexpected_missing_evidence_count == 0
    assert result.unexpected_budget_exhaustion_count == 0
    assert result.activation_authorized is False
    assert "musical_quality_not_established_by_r1" in result.explanation_codes


def test_missing_required_category_is_incomplete_not_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "services.intelligence.set_optimizer_acceptance.benchmark_greedy_vs_beam",
        lambda **kwargs: _comparison(kwargs["generated_at"]),
    )

    result = evaluate_representative_benchmark_corpus_r1(scenarios=_scenarios()[:-1])

    assert result.verdict is CorpusAcceptanceVerdict.INCOMPLETE
    assert result.missing_categories
    assert result.activation_authorized is False


def test_replay_regression_fails_acceptance(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_benchmark(**kwargs):
        comparison = _comparison(kwargs["generated_at"])
        if kwargs["generated_at"] == "r1-energy-trajectory":
            comparison = replace(
                comparison,
                beam=replace(comparison.beam, deterministic_replay_match=False),
            )
        return comparison

    monkeypatch.setattr(
        "services.intelligence.set_optimizer_acceptance.benchmark_greedy_vs_beam",
        fake_benchmark,
    )

    result = evaluate_representative_benchmark_corpus_r1(scenarios=_scenarios())

    assert result.verdict is CorpusAcceptanceVerdict.FAIL
    assert result.deterministic_replay_rate < 1.0
    assert result.scenario_failure_count == 1
    observation = next(
        item for item in result.observations if item.scenario_id == "r1-energy-trajectory"
    )
    assert "deterministic_replay_failed" in observation.reason_codes


def test_acceptance_policy_cannot_authorize_activation() -> None:
    with pytest.raises(ValueError, match="cannot authorize activation"):
        OptimizerAcceptanceThresholds(activation_authorized=True)
