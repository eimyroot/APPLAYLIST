from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

AnalysisInspectorFilter = Literal["all", "uncertain", "failed", "corrected"]
AnalysisInspectorSource = Literal["provider", "manual-correction"]


@dataclass(frozen=True, slots=True)
class AnalysisInspectorItem:
    track_id: str
    title: str
    artist: str | None
    status: Literal["succeeded", "failed"]
    bpm: float | None
    bpm_confidence: float | None
    key_tonic: str | None
    key_scale: str | None
    camelot: str | None
    key_confidence: float | None
    energy: float | None
    duration_seconds: float | None
    provider: str
    provider_version: str | None
    analysis_version: str
    algorithm_version: str | None
    warnings: tuple[str, ...]
    source: AnalysisInspectorSource
    uncertain: bool
    corrected: bool
    attempt_evidence_id: str
    effective_evidence_id: str | None
    correction_id: str | None = None
    correction_reason: str | None = None
    error_code: str | None = None
    error_detail: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
