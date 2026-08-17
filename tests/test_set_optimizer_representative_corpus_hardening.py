from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.intelligence.set_optimizer_acceptance_contract import (
    CorpusAcceptanceVerdict,
    OptimizerAcceptanceThresholds,
    RepresentativeScenarioCategory,
    ScenarioAcceptanceExpectation,
    ScenarioAcceptanceObservation,
)
from core.intelligence.set_optimizer_contract import SetOptimizerStatus
from core.intelligence.set_optimizer_corpus_manifest import (
    representative_benchmark_expectations_r1,
)
from services.intelligence.set_optimizer_acceptance import (
    RepresentativeBenchmarkScenario,
    _observe,
    evaluate_representative_benchmark_corpus_r1,
)


def _scenario(expectation: ScenarioAcceptanceExpectation) -> RepresentativeBenchmarkScenario:
    return RepresentativeBenchmarkScenario(
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


def _observation(
    expectation: ScenarioAcceptanceExpectation,
    *,
    passed: bool = True,
    beam_win: bool = False,
) -> ScenarioAcceptanceObservation:
    return ScenarioAcceptanceObservation(
        scenario_id=expectation.scenario_id,
        category=expectation.category,
        benchmark_id=f"benchmark:{expectation.scenario_id}",
        passed=passed,
        greedy_status=SetOptimizerStatus.PATHS_FOUND,
        beam_status=SetOptimizerStatus.TARGET_REACHED,
        greedy_target_reached=not beam_win,
        beam_target_reached=True,
        beam_reaches_target_when_greedy_does_not=beam_win,
        greedy_required_track_completion=1.0,
        beam_required_track_completion=1.0,
        greedy_deterministic_replay_match=True,
        beam_deterministic_replay_match=True,
        beam_pruned_candidates=0,
        diversity_rejected_count=0,
        diverse_alternative_count=1,
        missing_evidence_detected=False,
        budget_exhausted=False,
        reason_codes=("scenario_acceptance_pass",) if passed else ("known_failure",),
    )


def test_greedy_only_evidence_gap_is_not_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    expectation = ScenarioAcceptanceExpectation(
        scenario_id="greedy-only-gap",
        category=RepresentativeScenarioCategory.HARD_GATES,
        expected_beam_statuses=(SetOptimizerStatus.TARGET_REACHED,),
        require_beam_target_reached=True,
    )
    comparison = SimpleNamespace(
        benchmark_id="benchmark:greedy-only-gap",
        greedy=SimpleNamespace(
            status=SetOptimizerStatus.PATHS_FOUND,
            target_reached=False,
            best_required_track_completion=1.0,
            deterministic_replay_match=True,
            missing_evidence_detected=True,
            budget_exhausted=False,
        ),
        beam=SimpleNamespace(
            status=SetOptimizerStatus.TARGET_REACHED,
            target_reached=True,
            best_required_track_completion=1.0,
            deterministic_replay_match=True,
            missing_evidence_detected=False,
            budget_exhausted=False,
            beam_pruned_candidates=0,
        ),
        beam_reaches_target_when_greedy_does_not=True,
        diversity_rejected_count=0,
        diverse_beam_selection=SimpleNamespace(selected_alternatives=()),
    )
    monkeypatch.setattr(
        "services.intelligence.set_optimizer_acceptance.benchmark_greedy_vs_beam",
        lambda **kwargs: comparison,
    )

    observed = _observe(_scenario(expectation))

    assert observed.passed is False
    assert observed.missing_evidence_detected is True
    assert "unexpected_missing_evidence" in observed.reason_codes


def test_greedy_only_budget_exhaustion_is_not_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    expectation = ScenarioAcceptanceExpectation(
        scenario_id="greedy-only-budget",
        category=RepresentativeScenarioCategory.HARD_GATES,
        expected_beam_statuses=(SetOptimizerStatus.TARGET_REACHED,),
        require_beam_target_reached=True,
    )
    comparison = SimpleNamespace(
        benchmark_id="benchmark:greedy-only-budget",
        greedy=SimpleNamespace(
            status=SetOptimizerStatus.BUDGET_EXHAUSTED,
            target_reached=False,
            best_required_track_completion=1.0,
            deterministic_replay_match=True,
            missing_evidence_detected=False,
            budget_exhausted=True,
        ),
        beam=SimpleNamespace(
            status=SetOptimizerStatus.TARGET_REACHED,
            target_reached=True,
            best_required_track_completion=1.0,
            deterministic_replay_match=True,
            missing_evidence_detected=False,
            budget_exhausted=False,
            beam_pruned_candidates=0,
        ),
        beam_reaches_target_when_greedy_does_not=True,
        diversity_rejected_count=0,
        diverse_beam_selection=SimpleNamespace(selected_alternatives=()),
    )
    monkeypatch.setattr(
        "services.intelligence.set_optimizer_acceptance.benchmark_greedy_vs_beam",
        lambda **kwargs: comparison,
    )

    observed = _observe(_scenario(expectation))

    assert observed.passed is False
    assert observed.budget_exhausted is True
    assert "unexpected_budget_exhaustion" in observed.reason_codes


def test_known_failure_is_fail_even_when_corpus_is_also_incomplete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expectations = representative_benchmark_expectations_r1()[:-1]
    scenarios = tuple(_scenario(item) for item in expectations)

    def fake_observe(scenario: RepresentativeBenchmarkScenario) -> ScenarioAcceptanceObservation:
        expectation = scenario.expectation
        return _observation(
            expectation,
            passed=expectation.scenario_id != "r1-energy-trajectory",
            beam_win=expectation.require_beam_reaches_when_greedy_misses,
        )

    monkeypatch.setattr(
        "services.intelligence.set_optimizer_acceptance._observe",
        fake_observe,
    )
    thresholds = OptimizerAcceptanceThresholds(minimum_expected_beam_wins=1)

    result = evaluate_representative_benchmark_corpus_r1(
        scenarios=scenarios,
        thresholds=thresholds,
    )

    assert result.missing_categories
    assert result.scenario_failure_count == 1
    assert result.verdict is CorpusAcceptanceVerdict.FAIL
    assert "representative_corpus_coverage_incomplete" in result.explanation_codes
    assert "scenario_failure_count_above_threshold" in result.explanation_codes
