from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from core.analysis.contracts import CanonicalAnalysisResult


class CanonicalAnalysisMappingError(ValueError):
    """The canonical result cannot be persisted without inventing data."""


@dataclass(frozen=True, slots=True)
class CanonicalAnalysisPersistenceRecord:
    track_id: str
    provider: str
    provider_version: str | None
    canonical_analysis_version: str
    source_analysis_version: str | None
    bpm: float | None
    bpm_confidence: float | None
    key: str | None
    key_confidence: float | None
    key_system: str | None
    energy: float | None
    energy_confidence: float | None
    loudness_db: float | None
    loudness_integrated_lufs: float | None
    duration_seconds: float | None
    sample_rate_hz: int | None
    channels: int | None
    genre_hint: str | None
    analysis_status: str
    analyzed_at: str | None
    warnings_json: str
    persisted_at: str | None = None

    def warnings(self) -> tuple[str, ...]:
        value = json.loads(self.warnings_json)
        if not isinstance(value, list) or not all(
            isinstance(item, str) for item in value
        ):
            raise CanonicalAnalysisMappingError(
                "warnings_json must contain a JSON string array"
            )
        return tuple(value)


def _required_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CanonicalAnalysisMappingError(
            f"{field_name} must be a non-empty string"
        )
    return value


def map_canonical_analysis_to_persistence(
    result: CanonicalAnalysisResult,
) -> CanonicalAnalysisPersistenceRecord:
    if not isinstance(result, CanonicalAnalysisResult):
        raise TypeError("result must be CanonicalAnalysisResult")

    warnings = tuple(result.warnings)
    if not all(isinstance(item, str) for item in warnings):
        raise CanonicalAnalysisMappingError(
            "warnings must contain only strings"
        )

    return CanonicalAnalysisPersistenceRecord(
        track_id=_required_text(result.track_id, "track_id"),
        provider=_required_text(result.provider, "provider"),
        provider_version=result.provider_version,
        canonical_analysis_version=_required_text(
            result.analysis_version,
            "analysis_version",
        ),
        source_analysis_version=result.source_analysis_version,
        bpm=result.bpm,
        bpm_confidence=result.bpm_confidence,
        key=result.key,
        key_confidence=result.key_confidence,
        key_system=result.key_system,
        energy=result.energy,
        energy_confidence=result.energy_confidence,
        loudness_db=result.loudness_db,
        loudness_integrated_lufs=result.loudness_integrated_lufs,
        duration_seconds=result.duration_seconds,
        sample_rate_hz=result.sample_rate_hz,
        channels=result.channels,
        genre_hint=result.genre_hint,
        analysis_status=_required_text(
            result.analysis_status,
            "analysis_status",
        ),
        analyzed_at=result.analyzed_at,
        warnings_json=json.dumps(
            warnings,
            ensure_ascii=False,
            separators=(",", ":"),
        ),
    )
