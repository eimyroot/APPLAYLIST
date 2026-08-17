from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from core.intelligence.set_contract import SequenceState, SetStep

SET_OPTIMIZER_CONTRACT_VERSION = "set-optimizer-v1"
SET_OPTIMIZER_POLICY_VERSION = "bounded-beam-lookahead-v1"


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


class SetOptimizerStatus(StrEnum):
    TARGET_REACHED = "target_reached"
    PATHS_FOUND = "paths_found"
    NO_ELIGIBLE_PATH = "no_eligible_path"
    NOT_PROVEN_MISSING_EVIDENCE = "not_proven_missing_evidence"
    BUDGET_EXHAUSTED = "budget_exhausted"


@dataclass(frozen=True, slots=True)
class SetOptimizerPolicy:
    optimizer_id: str = "bounded-beam-lookahead"
    optimizer_version: str = SET_OPTIMIZER_POLICY_VERSION
    beam_width: int = 8
    max_depth: int = 6
    per_state_candidate_limit: int = 16
    max_expanded_candidates: int = 10000
    alternative_limit: int = 5

    def __post_init__(self) -> None:
        object.__setattr__(self, "optimizer_id", _non_empty(self.optimizer_id, "optimizer_id"))
        object.__setattr__(
            self,
            "optimizer_version",
            _non_empty(self.optimizer_version, "optimizer_version"),
        )
        if not 1 <= self.beam_width <= 128:
            raise ValueError("beam_width must be between 1 and 128")
        if not 1 <= self.max_depth <= 16:
            raise ValueError("max_depth must be between 1 and 16")
        if not 1 <= self.per_state_candidate_limit <= 256:
            raise ValueError("per_state_candidate_limit must be between 1 and 256")
        if not 1 <= self.max_expanded_candidates <= 100000:
            raise ValueError("max_expanded_candidates must be between 1 and 100000")
        if not 1 <= self.alternative_limit <= self.beam_width:
            raise ValueError("alternative_limit must be between 1 and beam_width")


@dataclass(frozen=True, slots=True)
class SetPathObjective:
    depth: int
    mean_candidate_score: float
    minimum_candidate_score: float
    required_track_completion: float
    remaining_required_count: int
    target_reached: bool

    def __post_init__(self) -> None:
        if self.depth <= 0:
            raise ValueError("path objective depth must be positive")
        object.__setattr__(
            self,
            "mean_candidate_score",
            _unit(self.mean_candidate_score, "mean_candidate_score"),
        )
        object.__setattr__(
            self,
            "minimum_candidate_score",
            _unit(self.minimum_candidate_score, "minimum_candidate_score"),
        )
        object.__setattr__(
            self,
            "required_track_completion",
            _unit(self.required_track_completion, "required_track_completion"),
        )
        if self.remaining_required_count < 0:
            raise ValueError("remaining_required_count must be non-negative")


@dataclass(frozen=True, slots=True)
class SetPathAlternative:
    path_id: str
    rank: int
    added_steps: tuple[SetStep, ...]
    resulting_state: SequenceState
    transition_ids: tuple[str, ...]
    candidate_scores: tuple[float, ...]
    objective: SetPathObjective
    explanation_codes: tuple[str, ...]
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "path_id", _non_empty(self.path_id, "path_id"))
        if self.rank <= 0:
            raise ValueError("path rank must be positive")
        steps = tuple(self.added_steps)
        transition_ids = tuple(_non_empty(item, "transition_id") for item in self.transition_ids)
        scores = tuple(_unit(item, "candidate_score") for item in self.candidate_scores)
        if not steps or len(steps) != len(transition_ids) or len(steps) != len(scores):
            raise ValueError("path steps, transition ids and scores must be equally non-empty")
        if self.objective.depth != len(steps):
            raise ValueError("path objective depth must equal added step count")
        object.__setattr__(self, "added_steps", steps)
        object.__setattr__(self, "transition_ids", transition_ids)
        object.__setattr__(self, "candidate_scores", scores)
        object.__setattr__(self, "explanation_codes", tuple(self.explanation_codes))
        object.__setattr__(self, "evidence_refs", tuple(self.evidence_refs))


@dataclass(frozen=True, slots=True)
class SetOptimizerResult:
    result_id: str
    input_fingerprint: str
    optimizer_ref: tuple[str, str]
    intent_ref: tuple[str, str]
    root_state_ref: tuple[str, str]
    base_transition_context_ref: tuple[str, str]
    status: SetOptimizerStatus
    alternatives: tuple[SetPathAlternative, ...]
    deepest_depth: int
    expanded_candidates: int
    beam_pruned_candidates: int
    budget_exhausted: bool
    missing_evidence_detected: bool
    deterministic_ordering: bool
    explanation_codes: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "result_id", _non_empty(self.result_id, "result_id"))
        object.__setattr__(
            self,
            "input_fingerprint",
            _non_empty(self.input_fingerprint, "input_fingerprint"),
        )
        if self.deepest_depth < 0:
            raise ValueError("deepest_depth must be non-negative")
        if self.expanded_candidates < 0 or self.beam_pruned_candidates < 0:
            raise ValueError("optimizer counters must be non-negative")
        alternatives = tuple(self.alternatives)
        if tuple(item.rank for item in alternatives) != tuple(range(1, len(alternatives) + 1)):
            raise ValueError("optimizer alternative ranks must be contiguous from one")
        if self.status in (SetOptimizerStatus.TARGET_REACHED, SetOptimizerStatus.PATHS_FOUND):
            if not alternatives:
                raise ValueError("successful optimizer result requires alternatives")
        elif alternatives and self.status is SetOptimizerStatus.NO_ELIGIBLE_PATH:
            raise ValueError("no-eligible-path result must not contain alternatives")
        object.__setattr__(self, "alternatives", alternatives)
        object.__setattr__(self, "explanation_codes", tuple(self.explanation_codes))
        object.__setattr__(self, "warnings", tuple(self.warnings))


__all__ = [
    "SET_OPTIMIZER_CONTRACT_VERSION",
    "SET_OPTIMIZER_POLICY_VERSION",
    "SetOptimizerPolicy",
    "SetOptimizerResult",
    "SetOptimizerStatus",
    "SetPathAlternative",
    "SetPathObjective",
]
