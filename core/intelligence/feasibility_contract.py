from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

FUTURE_FEASIBILITY_POLICY_VERSION = "future-feasibility-v1"


class FeasibilityStatus(StrEnum):
    REACHABLE = "reachable"
    INFEASIBLE = "infeasible"
    NOT_PROVEN_WITHIN_BUDGET = "not_proven_within_budget"
    NOT_PROVEN_MISSING_EVIDENCE = "not_proven_missing_evidence"
    NOT_PROVEN_UNSUPPORTED_CONSTRAINT = "not_proven_unsupported_constraint"


@dataclass(frozen=True, slots=True)
class FeasibilityPolicy:
    policy_version: str = FUTURE_FEASIBILITY_POLICY_VERSION
    max_depth: int = 4
    max_expanded_states: int = 2_000

    def __post_init__(self) -> None:
        version = str(self.policy_version).strip()
        if not version:
            raise ValueError("feasibility policy_version must not be empty")
        if isinstance(self.max_depth, bool) or not isinstance(self.max_depth, int):
            raise TypeError("max_depth must be an integer")
        if isinstance(self.max_expanded_states, bool) or not isinstance(
            self.max_expanded_states, int
        ):
            raise TypeError("max_expanded_states must be an integer")
        if not 1 <= self.max_depth <= 16:
            raise ValueError("max_depth must be between 1 and 16")
        if not 1 <= self.max_expanded_states <= 100_000:
            raise ValueError("max_expanded_states must be between 1 and 100000")
        object.__setattr__(self, "policy_version", version)


@dataclass(frozen=True, slots=True)
class FutureFeasibilityResult:
    status: FeasibilityStatus
    score: float | None
    reached_required_track_ids: tuple[str, ...]
    unresolved_required_track_ids: tuple[str, ...]
    expanded_states: int
    deepest_expanded_depth: int
    budget_exhausted: bool
    policy_version: str
    context_ref: tuple[str, str]
    explanation_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.score is not None and not 0.0 <= float(self.score) <= 1.0:
            raise ValueError("feasibility score must be between 0 and 1")
        if self.status is FeasibilityStatus.REACHABLE and self.score != 1.0:
            raise ValueError("reachable feasibility must carry score 1.0")
        if self.status is FeasibilityStatus.INFEASIBLE and self.score != 0.0:
            raise ValueError("infeasible feasibility must carry score 0.0")
        if self.status not in {FeasibilityStatus.REACHABLE, FeasibilityStatus.INFEASIBLE}:
            if self.score is not None:
                raise ValueError("not-proven feasibility must not carry a score")
        if self.expanded_states < 0 or self.deepest_expanded_depth < 0:
            raise ValueError("feasibility counters must be non-negative")
        if len(self.context_ref) != 2 or any(not str(item).strip() for item in self.context_ref):
            raise ValueError("context_ref requires context id and version")
        if not str(self.policy_version).strip():
            raise ValueError("policy_version must not be empty")
        reached = tuple(dict.fromkeys(str(item) for item in self.reached_required_track_ids))
        unresolved = tuple(dict.fromkeys(str(item) for item in self.unresolved_required_track_ids))
        if set(reached) & set(unresolved):
            raise ValueError("reached and unresolved required tracks must be disjoint")
        object.__setattr__(self, "reached_required_track_ids", reached)
        object.__setattr__(self, "unresolved_required_track_ids", unresolved)
        object.__setattr__(self, "explanation_codes", tuple(self.explanation_codes))


__all__ = [
    "FUTURE_FEASIBILITY_POLICY_VERSION",
    "FeasibilityPolicy",
    "FeasibilityStatus",
    "FutureFeasibilityResult",
]
