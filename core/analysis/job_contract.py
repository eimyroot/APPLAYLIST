from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

AnalysisJobState = Literal[
    "pending",
    "running",
    "cancelling",
    "done",
    "failed",
    "cancelled",
]

TERMINAL_ANALYSIS_JOB_STATES = frozenset({"done", "failed", "cancelled"})


@dataclass(frozen=True, slots=True)
class AnalysisJobCounts:
    selected: int
    completed: int = 0
    succeeded: int = 0
    failed: int = 0
    uncertain: int = 0

    def __post_init__(self) -> None:
        values = (
            self.selected,
            self.completed,
            self.succeeded,
            self.failed,
            self.uncertain,
        )
        if any(isinstance(value, bool) or not isinstance(value, int) for value in values):
            raise TypeError("Analysis job counts must be integers")
        if any(value < 0 for value in values):
            raise ValueError("Analysis job counts must be non-negative")
        if self.completed != self.succeeded + self.failed:
            raise ValueError("completed must equal succeeded + failed")
        if self.completed > self.selected:
            raise ValueError("completed cannot exceed selected")
        if self.uncertain > self.succeeded:
            raise ValueError("uncertain cannot exceed succeeded")

    def to_dict(self) -> dict[str, int]:
        return asdict(self)

    def has_regressed_from(self, previous: AnalysisJobCounts) -> bool:
        if self.selected != previous.selected:
            return True
        return any(
            current < old
            for current, old in (
                (self.completed, previous.completed),
                (self.succeeded, previous.succeeded),
                (self.failed, previous.failed),
                (self.uncertain, previous.uncertain),
            )
        )


@dataclass(frozen=True, slots=True)
class AnalysisJobSnapshot:
    job_id: str
    status: AnalysisJobState
    counts: AnalysisJobCounts
    preferred_provider: str | None = None
    cancel_requested: bool = False
    error_code: str | None = None
    error_detail: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.job_id, str) or not self.job_id.strip():
            raise ValueError("job_id must be a non-empty string")
        if self.status not in {
            "pending",
            "running",
            "cancelling",
            "done",
            "failed",
            "cancelled",
        }:
            raise ValueError("invalid analysis job state")
        if self.status == "done" and self.counts.completed != self.counts.selected:
            raise ValueError("done jobs must complete the selected scope")
        if self.status == "cancelling" and not self.cancel_requested:
            raise ValueError("cancelling jobs must have cancel_requested=true")

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "status": self.status,
            "counts": self.counts.to_dict(),
            "preferred_provider": self.preferred_provider,
            "cancel_requested": self.cancel_requested,
            "error_code": self.error_code,
            "error_detail": self.error_detail,
        }
