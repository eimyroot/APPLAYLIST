from __future__ import annotations

from core.intelligence.set_optimizer_acceptance_contract import (
    ScenarioAcceptanceExpectation,
    RepresentativeScenarioCategory,
)
from core.intelligence.set_optimizer_contract import SetOptimizerStatus


def representative_benchmark_expectations_r1() -> tuple[ScenarioAcceptanceExpectation, ...]:
    """Return the minimum governed scenario manifest for optimizer acceptance R1.

    The manifest defines engineering expectations only. It does not claim musical
    preference fit or authorize optimizer activation.
    """
    return (
        ScenarioAcceptanceExpectation(
            scenario_id="r1-greedy-dead-end",
            category=RepresentativeScenarioCategory.GREEDY_DEAD_END,
            expected_beam_statuses=(SetOptimizerStatus.TARGET_REACHED,),
            require_beam_target_reached=True,
            require_greedy_target_reached=False,
            require_beam_reaches_when_greedy_misses=True,
        ),
        ScenarioAcceptanceExpectation(
            scenario_id="r1-required-tracks",
            category=RepresentativeScenarioCategory.REQUIRED_TRACKS,
            expected_beam_statuses=(SetOptimizerStatus.TARGET_REACHED,),
            require_beam_target_reached=True,
            minimum_required_track_completion=1.0,
        ),
        ScenarioAcceptanceExpectation(
            scenario_id="r1-phase-transition",
            category=RepresentativeScenarioCategory.PHASE_TRANSITION,
            expected_beam_statuses=(SetOptimizerStatus.TARGET_REACHED,),
            require_beam_target_reached=True,
        ),
        ScenarioAcceptanceExpectation(
            scenario_id="r1-energy-trajectory",
            category=RepresentativeScenarioCategory.ENERGY_TRAJECTORY,
            expected_beam_statuses=(SetOptimizerStatus.TARGET_REACHED,),
            require_beam_target_reached=True,
        ),
        ScenarioAcceptanceExpectation(
            scenario_id="r1-position-locks",
            category=RepresentativeScenarioCategory.POSITION_LOCKS,
            expected_beam_statuses=(SetOptimizerStatus.TARGET_REACHED,),
            require_beam_target_reached=True,
        ),
        ScenarioAcceptanceExpectation(
            scenario_id="r1-hard-gates",
            category=RepresentativeScenarioCategory.HARD_GATES,
            expected_beam_statuses=(SetOptimizerStatus.TARGET_REACHED,),
            require_beam_target_reached=True,
        ),
        ScenarioAcceptanceExpectation(
            scenario_id="r1-missing-evidence",
            category=RepresentativeScenarioCategory.MISSING_EVIDENCE,
            expected_beam_statuses=(SetOptimizerStatus.NOT_PROVEN_MISSING_EVIDENCE,),
            require_beam_target_reached=False,
            allow_missing_evidence=True,
            require_missing_evidence=True,
        ),
        ScenarioAcceptanceExpectation(
            scenario_id="r1-budget-truncation",
            category=RepresentativeScenarioCategory.BUDGET_TRUNCATION,
            expected_beam_statuses=(SetOptimizerStatus.BUDGET_EXHAUSTED,),
            allow_budget_exhaustion=True,
            require_budget_exhaustion=True,
            minimum_diverse_alternatives=1,
        ),
        ScenarioAcceptanceExpectation(
            scenario_id="r1-high-branching",
            category=RepresentativeScenarioCategory.HIGH_BRANCHING,
            expected_beam_statuses=(
                SetOptimizerStatus.PATHS_FOUND,
                SetOptimizerStatus.TARGET_REACHED,
            ),
            minimum_beam_pruned_candidates=1,
        ),
        ScenarioAcceptanceExpectation(
            scenario_id="r1-alternative-near-duplicate-pressure",
            category=(
                RepresentativeScenarioCategory.ALTERNATIVE_NEAR_DUPLICATE_PRESSURE
            ),
            expected_beam_statuses=(SetOptimizerStatus.TARGET_REACHED,),
            require_beam_target_reached=True,
            minimum_diversity_rejected_count=1,
            minimum_diverse_alternatives=1,
        ),
    )


__all__ = ["representative_benchmark_expectations_r1"]
