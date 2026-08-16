from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class AnalysisJobRecord:
    job_id: str
    status: str
    selected: int
    completed: int = 0
    succeeded: int = 0
    failed: int = 0
    uncertain: int = 0
    preferred_provider: str | None = None
    cancel_requested: bool = False
    error_code: str | None = None
    error_detail: str | None = None
