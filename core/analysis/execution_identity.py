from __future__ import annotations

import re
from dataclasses import dataclass


_CONTENT_TRACK_ID_RE = re.compile(r"^aptrack:v1:sha256:[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class AnalysisExecutionIdentity:
    """Identity of one reproducible canonical analysis execution contract.

    This identity is intentionally limited to values that are knowable before the
    provider is executed. Reuse is permitted only when all fields match persisted
    successful evidence exactly.
    """

    provider: str
    analysis_version: str
    provider_version: str
    algorithm_version: str

    def __post_init__(self) -> None:
        for field_name in (
            "provider",
            "analysis_version",
            "provider_version",
            "algorithm_version",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str):
                raise TypeError(f"{field_name} must be text")
            normalized = value.strip()
            if not normalized:
                raise ValueError(f"{field_name} must not be empty")
            if field_name == "provider":
                normalized = normalized.lower()
            object.__setattr__(self, field_name, normalized)


def is_content_addressed_track_id(track_id: str) -> bool:
    """Return True only for canonical byte-addressed APPLAYLIST track identities."""

    return isinstance(track_id, str) and _CONTENT_TRACK_ID_RE.fullmatch(track_id) is not None


__all__ = ["AnalysisExecutionIdentity", "is_content_addressed_track_id"]
