from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite

from core.analysis.provider_contracts import ProviderMetadata
from core.analysis.rhythm_contracts import BeatGrid, EvidenceStatus
from data.models.analysis_record import AnalysisRecord

DEFAULT_RELATIVE_TOLERANCE = 0.04
WB006C_SHADOW_METHOD = "wb006c-shadow-beat-grid-v1"


class TempoRelationship(StrEnum):
    DIRECT = "direct"
    HALF_TIME = "half_time"
    DOUBLE_TIME = "double_time"
    DIVERGENT = "divergent"
    UNKNOWN = "unknown"


def _optional_confidence(value: float | None, field_name: str) -> float | None:
    if value is None:
        return None
    numeric = float(value)
    if not isfinite(numeric) or not 0.0 <= numeric <= 1.0:
        raise ValueError(f"{field_name} must be between 0 and 1")
    return numeric


@dataclass(frozen=True, slots=True)
class CanonicalTempoEvidence:
    track_id: str
    provider: str
    provider_version: str
    algorithm_version: str
    source_analysis_version: str
    duration_seconds: float | None
    bpm: float | None
    bpm_confidence: float | None

    def __post_init__(self) -> None:
        for field_name in (
            "track_id",
            "provider",
            "provider_version",
            "algorithm_version",
            "source_analysis_version",
        ):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise ValueError(f"{field_name} must not be empty")
            object.__setattr__(self, field_name, value)
        if self.duration_seconds is not None:
            duration = float(self.duration_seconds)
            if not isfinite(duration) or duration <= 0.0:
                raise ValueError("duration_seconds must be finite and positive when present")
            object.__setattr__(self, "duration_seconds", duration)
        if self.bpm is not None:
            bpm = float(self.bpm)
            if not isfinite(bpm) or not 20.0 <= bpm <= 400.0:
                raise ValueError("bpm must be finite and between 20 and 400")
            object.__setattr__(self, "bpm", bpm)
        object.__setattr__(
            self,
            "bpm_confidence",
            _optional_confidence(self.bpm_confidence, "bpm_confidence"),
        )

    @classmethod
    def from_analysis_record(
        cls,
        record: AnalysisRecord,
        *,
        provider_metadata: ProviderMetadata,
    ) -> CanonicalTempoEvidence:
        if not record.extractor_name:
            raise ValueError("analysis record extractor_name must be explicit")
        if not record.analysis_version:
            raise ValueError("analysis record analysis_version must be explicit")
        return cls(
            track_id=record.track_id,
            provider=provider_metadata.name,
            provider_version=provider_metadata.version,
            algorithm_version=record.extractor_name,
            source_analysis_version=record.analysis_version,
            duration_seconds=record.duration_seconds,
            bpm=record.bpm,
            bpm_confidence=record.bpm_confidence,
        )


@dataclass(frozen=True, slots=True)
class ShadowBeatGridReconciliation:
    relationship: TempoRelationship
    within_tolerance: bool
    relative_tolerance: float
    canonical_provider: str
    canonical_provider_version: str
    canonical_algorithm_version: str
    shadow_provider: str
    shadow_provider_version: str
    shadow_algorithm_version: str
    canonical_bpm: float | None
    shadow_bpm: float | None
    direct_relative_error: float | None
    half_time_relative_error: float | None
    double_time_relative_error: float | None
    canonical_confidence: float | None
    shadow_confidence: float | None
    beat_count: int
    warnings: tuple[str, ...] = ()


def _relative_error(observed: float, expected: float) -> float:
    return abs(observed - expected) / max(abs(expected), 1e-12)


def _validated_tolerance(value: float) -> float:
    numeric = float(value)
    if not isfinite(numeric) or not 0.0 <= numeric <= 0.25:
        raise ValueError("relative_tolerance must be finite and between 0 and 0.25")
    return numeric


def _validate_shadow_binding(canonical: CanonicalTempoEvidence, beat_grid: BeatGrid) -> None:
    provenance = beat_grid.provenance
    if provenance.method != WB006C_SHADOW_METHOD:
        raise ValueError("beat-grid provenance is not the WB006C shadow method")
    if provenance.source_analysis_version != canonical.source_analysis_version:
        raise ValueError("shadow source analysis version does not match canonical evidence")


def reconcile_shadow_beat_grid(
    canonical: CanonicalTempoEvidence,
    beat_grid: BeatGrid,
    *,
    relative_tolerance: float = DEFAULT_RELATIVE_TOLERANCE,
) -> ShadowBeatGridReconciliation:
    """Compare independent shadow tempo evidence without granting runtime authority."""
    tolerance = _validated_tolerance(relative_tolerance)
    _validate_shadow_binding(canonical, beat_grid)

    provenance = beat_grid.provenance
    warnings = tuple(beat_grid.warnings)
    common = dict(
        relative_tolerance=tolerance,
        canonical_provider=canonical.provider,
        canonical_provider_version=canonical.provider_version,
        canonical_algorithm_version=canonical.algorithm_version,
        shadow_provider=provenance.provider,
        shadow_provider_version=provenance.provider_version,
        shadow_algorithm_version=provenance.algorithm_version,
        canonical_bpm=canonical.bpm,
        shadow_bpm=beat_grid.tempo_bpm,
        canonical_confidence=canonical.bpm_confidence,
        shadow_confidence=beat_grid.tempo_confidence,
        beat_count=len(beat_grid.beats),
        warnings=warnings,
    )
    if (
        beat_grid.status is EvidenceStatus.UNAVAILABLE
        or canonical.bpm is None
        or beat_grid.tempo_bpm is None
    ):
        return ShadowBeatGridReconciliation(
            relationship=TempoRelationship.UNKNOWN,
            within_tolerance=False,
            direct_relative_error=None,
            half_time_relative_error=None,
            double_time_relative_error=None,
            **common,
        )

    canonical_bpm = float(canonical.bpm)
    shadow_bpm = float(beat_grid.tempo_bpm)
    direct_error = _relative_error(shadow_bpm, canonical_bpm)
    half_time_error = _relative_error(shadow_bpm, canonical_bpm / 2.0)
    double_time_error = _relative_error(shadow_bpm, canonical_bpm * 2.0)
    candidates = (
        (TempoRelationship.DIRECT, direct_error),
        (TempoRelationship.HALF_TIME, half_time_error),
        (TempoRelationship.DOUBLE_TIME, double_time_error),
    )
    relationship, closest_error = min(candidates, key=lambda item: item[1])
    within_tolerance = closest_error <= tolerance
    if not within_tolerance:
        relationship = TempoRelationship.DIVERGENT

    return ShadowBeatGridReconciliation(
        relationship=relationship,
        within_tolerance=within_tolerance,
        direct_relative_error=direct_error,
        half_time_relative_error=half_time_error,
        double_time_relative_error=double_time_error,
        **common,
    )


__all__ = [
    "CanonicalTempoEvidence",
    "DEFAULT_RELATIVE_TOLERANCE",
    "ShadowBeatGridReconciliation",
    "TempoRelationship",
    "WB006C_SHADOW_METHOD",
    "reconcile_shadow_beat_grid",
]
