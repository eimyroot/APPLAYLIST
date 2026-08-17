from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from core.intelligence.set_optimizer_contract import SetOptimizerStatus

REPRESENTATIVE_BENCHMARK_CORPUS_VERSION = "representative-benchmark-corpus-r1"
OPTIMIZER_ACCEPTANCE_POLICY_VERSION = "optimizer-acceptance-r1"


def _non_empty(value: str, field_name: str) -> str:
    normalized = str(value).strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    return normalized


def _unit(value: float, field_name: str) -> float:
    numeric = float(value)
    if not math.isfinite(numeric) or not 0.0 <= numeric <= 1.0:
        raise ValueError(f"{field_name} must be between 0 and 1")
    return numeric


class RepresentativeScenarioCategory(StrEnum):
    GREEDY_DEAD_END = "greedy_dead_end"
    REQUIRED_TRACKS = "required_tracks"
    PHASE_TRANSITION = "phase_transition"
    ENERGY_TRAJECTORY = "energy_trajectory"
    POSITION_LOCKS = "position_locks"
    HARD_GATES = "hard_gates"
    MISSING_EVIDENCE = "missing_evidence"
    BUDGET_TRUNCATION = "budget_truncation"
    HIGH_BRANCHING = "high_branching"
    ALTERNATIVE_NEAR_DUPLICATE_PRESSURE = "alternative_near_duplicate_pressure"


REPRESENTATIVE_BENCHMARK_CATEGORIES_R1 = tuple(RepresentativeScenarioCategory)


class CorpusAcceptanceVerdict(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    INCOMPLETE = "incomplete"


@dataclass(frozen=True, slots=True)
class ScenarioAcceptanceExpectation:
    scenario_id: str
    category: RepresentativeScenarioCategory
    expected_beam_statuses: tuple[SetOptimizerStatus, ...]
    require_beam_target_reached: bool | None = None
    require_greedy_target_reached: bool | None = None
    require_beam_reaches_when_greedy_misses: bool = False
    minimum_required_track_completion: float = 0.0
    require_beam_not_worse_required_completion: bool = True
    require_deterministic_replay: bool = True
    allow_missing_evidence: bool = False
    require_missing_evidence: bool = False
    allow_budget_exhaustion: bool = False
    require_budget_exhaustion: bool = False
    minimum_beam_pruned_candidates: int = 0
    minimum_diversity_rejected_count: int = 0
    minimum_diverse_alternatives: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "scenario_id", _non_empty(self.scenario_id, "scenario_id"))
        statuses = tuple(self.expected_beam_statuses)
        if not statuses:
            raise ValueError("expected_beam_statuses must not be empty")
        object.__setattr__(self, "expected_beam_statuses", statuses)
        object.__setattr__(
            self,
            "minimum_required_track_completion",
            _unit(
                self.minimum_required_track_completion,
                "minimum_required_track_completion",
            ),
        )
        for field_name in (
            "minimum_beam_pruned_candidates",
            "minimum_diversity_rejected_count",
            "minimum_diverse_alternatives",
        ):
            value = int(getattr(self, field_name))
            if value < 0:
                raise ValueError(f"{field_name} must be non-negative")
            object.__setattr__(self, field_name, value)
        if self.require_missing_evidence and not self.allow_missing_evidence:
            object.__setattr__(self, "allow_missing_evidence", True)
        if self.require_budget_exhaustion and not self.allow_budget_exhaustion:
            object.__setattr__(self, "allow_budget_exhaustion", True)


@dataclass(frozen=True, slots=True)
class OptimizerAcceptanceThresholds:
    policy_id: str = "optimizer-representative-corpus-acceptance"
    policy_version: str = OPTIMIZER_ACCEPTANCE_POLICY_VERSION
    minimum_scenarios: int = 10
    required_categories: tuple[RepresentativeScenarioCategory, ...] = (
        REPRESENTATIVE_BENCHMARK_CATEGORIES_R1
    )
    minimum_deterministic_replay_rate: float = 1.0
    maximum_scenario_failures: int = 0
    maximum_unexpected_missing_evidence: int = 0
    maximum_unexpected_budget_exhaustions: int = 0
    minimum_expected_beam_wins: int = 1
    activation_authorized: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "policy_id", _non_empty(self.policy_id, "policy_id"))
        object.__setattr__(
            self,
            "policy_version",
            _non_empty(self.policy_version, "policy_version"),
        )
        if self.minimum_scenarios <= 0:
            raise ValueError("minimum_scenarios must be positive")
        categories = tuple(self.required_categories)
        if not categories:
            raise ValueError("required_categories must not be empty")
        if len(set(categories)) != len(categories):
            raise ValueError("required_categories must be unique")
        object.__setattr__(self, "required_categories", categories)
        object.__setattr__(
            self,
            "minimum_deterministic_replay_rate",
            _unit(
                self.minimum_deterministic_replay_rate,
                "minimum_deterministic_replay_rate",
            ),
        )
        for field_name in (
            "maximum_scenario_failures",
            "maximum_unexpected_missing_evidence",
            "maximum_unexpected_budget_exhaustions",
            "minimum_expected_beam_wins",
        ):
            value = int(getattr(self, field_name))
            if value < 0:
                raise ValueError(f"{field_name} must be non-negative")
            object.__setattr__(self, field_name, value)
        if self.activation_authorized:
            raise ValueError(
                "representative corpus R1 is evidence-only and cannot authorize activation"
            )


@dataclass(frozen=True, slots=True)
class ScenarioAcceptanceObservation:
    scenario_id: str
    category: RepresentativeScenarioCategory
    benchmark_id: str
    passed: bool
    greedy_status: SetOptimizerStatus
    beam_status: SetOptimizerStatus
    greedy_target_reached: bool
    beam_target_reached: bool
    beam_reaches_target_when_greedy_does_not: bool
    greedy_required_track_completion: float
    beam_required_track_completion: float
    greedy_deterministic_replay_match: bool
    beam_deterministic_replay_match: bool
    beam_pruned_candidates: int
    diversity_rejected_count: int
    diverse_alternative_count: int
    missing_evidence_detected: bool
    budget_exhausted: bool
    reason_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "scenario_id", _non_empty(self.scenario_id, "scenario_id"))
        object.__setattr__(self, "benchmark_id", _non_empty(self.benchmark_id, "benchmark_id"))
        object.__setattr__(
            self,
            "greedy_required_track_completion",
            _unit(
                self.greedy_required_track_completion,
                "greedy_required_track_completion",
            ),
        )
        object.__setattr__(
            self,
            "beam_required_track_completion",
            _unit(
                self.beam_required_track_completion,
                "beam_required_track_completion",
            ),
        )
        for field_name in (
            "beam_pruned_candidates",
            "diversity_rejected_count",
            "diverse_alternative_count",
        ):
            value = int(getattr(self, field_name))
            if value < 0:
                raise ValueError(f"{field_name} must be non-negative")
            object.__setattr__(self, field_name, value)
        object.__setattr__(self, "reason_codes", tuple(self.reason_codes))


@dataclass(frozen=True, slots=True)
class RepresentativeCorpusAcceptance:
    corpus_id: str
    corpus_version: str
    thresholds_ref: tuple[str, str]
    scenario_count: int
    covered_categories: tuple[RepresentativeScenarioCategory, ...]
    missing_categories: tuple[RepresentativeScenarioCategory, ...]
    observations: tuple[ScenarioAcceptanceObservation, ...]
    deterministic_replay_rate: float
    scenario_failure_count: int
    expected_beam_win_count: int
    unexpected_missing_evidence_count: int
    unexpected_budget_exhaustion_count: int
    verdict: CorpusAcceptanceVerdict
    activation_authorized: bool = False
    explanation_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "corpus_id", _non_empty(self.corpus_id, "corpus_id"))
        object.__setattr__(
            self,
            "corpus_version",
            _non_empty(self.corpus_version, "corpus_version"),
        )
        if self.scenario_count < 0:
            raise ValueError("scenario_count must be non-negative")
        if self.scenario_count != len(self.observations):
            raise ValueError("scenario_count must equal observation count")
        object.__setattr__(
            self,
            "deterministic_replay_rate",
            _unit(self.deterministic_replay_rate, "deterministic_replay_rate"),
        )
        for field_name in (
            "scenario_failure_count",
            "expected_beam_win_count",
            "unexpected_missing_evidence_count",
            "unexpected_budget_exhaustion_count",
        ):
            value = int(getattr(self, field_name))
            if value < 0:
                raise ValueError(f"{field_name} must be non-negative")
            object.__setattr__(self, field_name, value)
        object.__setattr__(self, "covered_categories", tuple(self.covered_categories))
        object.__setattr__(self, "missing_categories", tuple(self.missing_categories))
        object.__setattr__(self, "observations", tuple(self.observations))
        object.__setattr__(self, "explanation_codes", tuple(self.explanation_codes))
        if self.activation_authorized:
            raise ValueError(
                "representative corpus R1 cannot authorize optimizer activation"
            )


__all__ = [
    "OPTIMIZER_ACCEPTANCE_POLICY_VERSION",
    "REPRESENTATIVE_BENCHMARK_CATEGORIES_R1",
    "REPRESENTATIVE_BENCHMARK_CORPUS_VERSION",
    "CorpusAcceptanceVerdict",
    "OptimizerAcceptanceThresholds",
    "RepresentativeCorpusAcceptance",
    "RepresentativeScenarioCategory",
    "ScenarioAcceptanceExpectation",
    "ScenarioAcceptanceObservation",
]
