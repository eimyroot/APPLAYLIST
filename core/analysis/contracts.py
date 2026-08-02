from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class CanonicalAnalysisResult:
    """Single canonical MIR result contract.

    Confidence values are evidence fields. Missing provider confidence remains None;
    callers must not synthesize confidence from provider identity or feature presence.
    """

    path: str
    provider: str
    bpm: float | None = None
    bpm_confidence: float | None = None
    key: str | None = None
    key_confidence: float | None = None
    key_system: str | None = None
    energy: float | None = None
    energy_confidence: float | None = None
    loudness_db: float | None = None
    loudness_integrated_lufs: float | None = None
    duration_seconds: float | None = None
    sample_rate_hz: int | None = None
    channels: int | None = None
    genre_hint: str | None = None
    analysis_status: str = "unknown"
    analysis_version: str = "canonical-mir-v1"
    source_analysis_version: str | None = None
    provider_version: str | None = None
    analyzed_at: str | None = None
    track_id: str | None = None
    warnings: tuple[str, ...] = field(default_factory=tuple)
    raw_provider_fields: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# Backward-compatible import name. Both names resolve to the same runtime class.
CanonicalMirAnalysis = CanonicalAnalysisResult
