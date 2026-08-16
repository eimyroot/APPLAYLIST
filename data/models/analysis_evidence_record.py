from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AnalysisEvidenceRecord:
    evidence_id: str
    track_id: str
    provider: str
    analysis_version: str
    status: str = "succeeded"
    provider_version: str | None = None
    algorithm_version: str | None = None
    bpm: float | None = None
    bpm_confidence: float | None = None
    key_tonic: str | None = None
    key_scale: str | None = None
    camelot: str | None = None
    key_confidence: float | None = None
    energy: float | None = None
    duration_seconds: float | None = None
    warnings: tuple[str, ...] = ()
    error_code: str | None = None
    error_detail: str | None = None
    created_at: str | None = None


@dataclass(frozen=True, slots=True)
class AnalysisCorrectionRecord:
    correction_id: str
    track_id: str
    payload_json: str
    reason: str | None = None
    created_at: str | None = None
