from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from core.intelligence.set_optimizer_contract import SetOptimizerStatus, SetPathAlternative

ALTERNATIVE_DIVERSITY_POLICY_VERSION = "alternative-diversity-v1"
OPTIMIZER_BENCHMARK_CONTRACT_VERSION = "optimizer-benchmark-v1"


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


@dataclass(frozen=True, slots=True)
class AlternativeDiversityPolicy:
    policy_id: str = "set-path-alternative-diversity"
    policy_version: str = ALTERNATIVE_DIVERSITY_POLICY_VERSION
    alternative_limit: int = 5
    max_track_jaccard: float = 0.75
    max_shared_prefix_fraction: float = 0.75
    minimum_differing_positions: int = 1
    allow_similarity_fallback: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "policy_id", _non_empty(self.policy_id, "policy_id"))
        object.__setattr__(
            self,
            "policy_version",
            _non_empty(self.policy_version, "policy_version"),
        )
        if not 1 <= self.alternative_limit <= 128:
            raise ValueError("alternative_limit must be between 1 and 128")
        object.__setattr__(
            self,
            "max_track_jaccard",
            _unit(self.max_track_jaccard, "max_track_jaccard"),
        )
        object.__setattr__(
            self,
            "max_shared_prefix_fraction",
            _unit(self.max_shared_prefix_fraction, "max_shared_prefix_fraction"),
        )
        if self.minimum_differing_positions < 1:
            raise ValueError("minimum_differing_positions must be positive")


@dataclass(frozen=True, slots=True)
class AlternativeDiversityDecision:
    path_id: str
    source_rank: int
    selected: bool
    nearest_selected_path_id: str | None = None
    track_jaccard: float | None = None
    shared_prefix_fraction: float | None = None
    differing_positions: int | None = None
    reason_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "path_id", _non_empty(self.path_id, "path_id"))
        if self.source_rank <= 0:
            raise ValueError("source_rank must be positive")
        if self.track_jaccard is not None:
            object.__setattr__(
                self,
                "track_jaccard",
                _unit(self.track_jaccard, "track_jaccard"),
            )
        if self.shared_prefix_fraction is not None:
            object.__setattr__(
                self,
                "shared_prefix_fraction",
                _unit(self.shared_prefix_fraction, "shared_prefix_fraction"),
            )
        if self.differing_positions is not None and self.differing_positions < 0:
            raise ValueError("differing_positions must be non-negative")
        object.__setattr__(self, "reason_codes", tuple(self.reason_codes))


@dataclass(frozen=True, slots=True)
class SetAlternativeSelection:
    selection_id: str
    source_result_id: str
    source_input_fingerprint: str
    policy_ref: tuple[str, str]
    selected_alternatives: tuple[SetPathAlternative, ...]
    decisions: tuple[AlternativeDiversityDecision, ...]
    requested_limit: int
    similarity_fallback_used: bool
    deterministic_ordering: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "selection_id", _non_empty(self.selection_id, "selection_id"))
        object.__setattr__(
            self,
            "source_result_id",
            _non_empty(self.source_result_id, "source_result_id"),
        )
        object.__setattr__(
            self,
            "source_input_fingerprint",
            _non_empty(self.source_input_fingerprint, "source_input_fingerprint"),
        )
        if self.requested_limit <= 0:
            raise ValueError("requested_limit must be positive")
        selected = tuple(self.selected_alternatives)
        if tuple(item.rank for item in selected) != tuple(range(1, len(selected) + 1)):
            raise ValueError("selected alternative ranks must be contiguous from one")
        object.__setattr__(self, "selected_alternatives", selected)
        object.__setattr__(self, "decisions", tuple(self.decisions))


class BenchmarkStrategy(StrEnum):
    GREEDY_RECOMMEND_NEXT = "greedy_recommend_next"
    BOUNDED_BEAM = "bounded_beam"


@dataclass(frozen=True, slots=True)
class OptimizerBenchmarkMetrics:
    strategy: BenchmarkStrategy
    optimizer_ref: tuple[str, str]
    result_id: str
    status: SetOptimizerStatus
    target_reached: bool
    best_required_track_completion: float
    best_mean_candidate_score: float | None
    best_minimum_candidate_score: float | None
    deepest_depth: int
    expanded_candidates: int
    beam_pruned_candidates: int
    budget_exhausted: bool
    missing_evidence_detected: bool
    alternative_count: int
    deterministic_replay_match: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "result_id", _non_empty(self.result_id, "result_id"))
        object.__setattr__(
            self,
            "best_required_track_completion",
            _unit(self.best_required_track_completion, "best_required_track_completion"),
        )
        if self.best_mean_candidate_score is not None:
            object.__setattr__(
                self,
                "best_mean_candidate_score",
                _unit(self.best_mean_candidate_score, "best_mean_candidate_score"),
            )
        if self.best_minimum_candidate_score is not None:
            object.__setattr__(
                self,
                "best_minimum_candidate_score",
                _unit(self.best_minimum_candidate_score, "best_minimum_candidate_score"),
            )
        if self.deepest_depth < 0:
            raise ValueError("deepest_depth must be non-negative")
        if self.expanded_candidates < 0 or self.beam_pruned_candidates < 0:
            raise ValueError("benchmark counters must be non-negative")
        if self.alternative_count < 0:
            raise ValueError("alternative_count must be non-negative")


@dataclass(frozen=True, slots=True)
class OptimizerBenchmarkComparison:
    benchmark_id: str
    scenario_fingerprint: str
    contract_version: str
    greedy: OptimizerBenchmarkMetrics
    beam: OptimizerBenchmarkMetrics
    diverse_beam_selection: SetAlternativeSelection
    beam_reaches_target_when_greedy_does_not: bool
    required_track_completion_delta: float
    expanded_candidate_delta: int
    diversity_rejected_count: int
    activation_authorized: bool = False
    explanation_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "benchmark_id", _non_empty(self.benchmark_id, "benchmark_id"))
        object.__setattr__(
            self,
            "scenario_fingerprint",
            _non_empty(self.scenario_fingerprint, "scenario_fingerprint"),
        )
        object.__setattr__(
            self,
            "contract_version",
            _non_empty(self.contract_version, "contract_version"),
        )
        if not -1.0 <= self.required_track_completion_delta <= 1.0:
            raise ValueError("required_track_completion_delta must be between -1 and 1")
        if self.diversity_rejected_count < 0:
            raise ValueError("diversity_rejected_count must be non-negative")
        if self.activation_authorized:
            raise ValueError("benchmark v1 is evidence-only and cannot authorize activation")
        object.__setattr__(self, "explanation_codes", tuple(self.explanation_codes))


__all__ = [
    "ALTERNATIVE_DIVERSITY_POLICY_VERSION",
    "OPTIMIZER_BENCHMARK_CONTRACT_VERSION",
    "AlternativeDiversityDecision",
    "AlternativeDiversityPolicy",
    "BenchmarkStrategy",
    "OptimizerBenchmarkComparison",
    "OptimizerBenchmarkMetrics",
    "SetAlternativeSelection",
]
