from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from math import isfinite
from types import MappingProxyType
from typing import Any

from core.analysis.provider_contract import CanonicalAnalysisResult

ANALYSIS_VERSION = "canonical-rhythmic-structure-v1"


def _required_text(value: str, field_name: str) -> str:
    normalized = str(value).strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    return normalized


def _confidence(value: float | None, field_name: str) -> float | None:
    if value is None:
        return None
    numeric = float(value)
    if not isfinite(numeric) or not 0.0 <= numeric <= 1.0:
        raise ValueError(f"{field_name} must be between 0 and 1")
    return numeric


def _non_negative(value: float, field_name: str) -> float:
    numeric = float(value)
    if not isfinite(numeric) or numeric < 0.0:
        raise ValueError(f"{field_name} must be finite and non-negative")
    return numeric


class EvidenceStatus(StrEnum):
    MEASURED = "measured"
    DERIVED = "derived"
    UNAVAILABLE = "unavailable"


class StructuralLabel(StrEnum):
    INTRO = "intro"
    GROOVE = "groove"
    BUILDUP = "buildup"
    BREAKDOWN = "breakdown"
    DROP = "drop"
    OUTRO = "outro"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class EvidenceProvenance:
    provider: str
    provider_version: str
    algorithm_version: str
    method: str
    source_analysis_version: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "provider", _required_text(self.provider, "provider"))
        object.__setattr__(
            self,
            "provider_version",
            _required_text(self.provider_version, "provider_version"),
        )
        object.__setattr__(
            self,
            "algorithm_version",
            _required_text(self.algorithm_version, "algorithm_version"),
        )
        object.__setattr__(self, "method", _required_text(self.method, "method"))
        object.__setattr__(
            self,
            "source_analysis_version",
            _required_text(self.source_analysis_version, "source_analysis_version"),
        )

    @classmethod
    def from_canonical_analysis(
        cls,
        result: CanonicalAnalysisResult,
        *,
        method: str,
    ) -> EvidenceProvenance:
        if result.provider_version is None:
            raise ValueError("canonical analysis provider_version must be explicit")
        if result.algorithm_version is None:
            raise ValueError("canonical analysis algorithm_version must be explicit")
        return cls(
            provider=result.provider,
            provider_version=result.provider_version,
            algorithm_version=result.algorithm_version,
            method=method,
            source_analysis_version=result.analysis_version,
        )


@dataclass(frozen=True, slots=True)
class BeatEvent:
    index: int
    time_seconds: float
    confidence: float
    is_downbeat: bool | None
    downbeat_confidence: float | None = None
    bar_index: int | None = None
    beat_in_bar: int | None = None

    def __post_init__(self) -> None:
        if self.index < 0:
            raise ValueError("index must be non-negative")
        object.__setattr__(
            self,
            "time_seconds",
            _non_negative(self.time_seconds, "time_seconds"),
        )
        confidence = _confidence(self.confidence, "confidence")
        if confidence is None:
            raise ValueError("BeatEvent confidence must be explicit")
        object.__setattr__(self, "confidence", confidence)
        downbeat_confidence = _confidence(
            self.downbeat_confidence,
            "downbeat_confidence",
        )
        object.__setattr__(self, "downbeat_confidence", downbeat_confidence)

        if self.bar_index is not None and self.bar_index < 0:
            raise ValueError("bar_index must be non-negative when present")
        if self.beat_in_bar is not None and self.beat_in_bar <= 0:
            raise ValueError("beat_in_bar must be positive when present")
        if (self.bar_index is None) != (self.beat_in_bar is None):
            raise ValueError("bar_index and beat_in_bar must be present together")

        if self.is_downbeat is None:
            if downbeat_confidence is not None:
                raise ValueError("unknown downbeat must not carry downbeat_confidence")
            if self.bar_index is not None or self.beat_in_bar is not None:
                raise ValueError("unknown downbeat must not carry bar-position evidence")
            return

        if downbeat_confidence is None:
            raise ValueError("known downbeat state requires downbeat_confidence")
        if self.is_downbeat and self.beat_in_bar not in (None, 1):
            raise ValueError("downbeats must use beat_in_bar=1 when bar position is known")
        if not self.is_downbeat and self.beat_in_bar == 1:
            raise ValueError("beat_in_bar=1 must be marked as a downbeat")


@dataclass(frozen=True, slots=True)
class BeatGrid:
    status: EvidenceStatus
    beats: tuple[BeatEvent, ...]
    provenance: EvidenceProvenance
    tempo_bpm: float | None = None
    tempo_confidence: float | None = None
    meter_beats_per_bar: int | None = None
    meter_confidence: float | None = None
    warnings: tuple[str, ...] = ()
    unavailable_reason: str | None = None

    def __post_init__(self) -> None:
        beats = tuple(self.beats)
        object.__setattr__(self, "beats", beats)
        object.__setattr__(self, "warnings", tuple(str(item) for item in self.warnings))
        object.__setattr__(
            self,
            "tempo_confidence",
            _confidence(self.tempo_confidence, "tempo_confidence"),
        )
        object.__setattr__(
            self,
            "meter_confidence",
            _confidence(self.meter_confidence, "meter_confidence"),
        )
        if self.tempo_bpm is not None:
            tempo = float(self.tempo_bpm)
            if not isfinite(tempo) or tempo <= 0.0:
                raise ValueError("tempo_bpm must be finite and positive when present")
            object.__setattr__(self, "tempo_bpm", tempo)
        if self.meter_beats_per_bar is not None and self.meter_beats_per_bar <= 0:
            raise ValueError("meter_beats_per_bar must be positive when present")
        if (self.meter_beats_per_bar is None) != (self.meter_confidence is None):
            raise ValueError("meter value and meter confidence must be present together")

        if self.status is EvidenceStatus.UNAVAILABLE:
            if (
                beats
                or self.tempo_bpm is not None
                or self.tempo_confidence is not None
                or self.meter_beats_per_bar is not None
                or self.meter_confidence is not None
            ):
                raise ValueError(
                    "unavailable BeatGrid must not carry measured beat, tempo, or meter values"
                )
            if not self.unavailable_reason:
                raise ValueError("unavailable BeatGrid requires unavailable_reason")
            return

        if self.unavailable_reason is not None:
            raise ValueError("available BeatGrid must not carry unavailable_reason")
        if not beats:
            raise ValueError("measured or derived BeatGrid requires beat events")
        if self.tempo_bpm is None or self.tempo_confidence is None:
            raise ValueError("available BeatGrid requires tempo_bpm and tempo_confidence")
        for expected_index, beat in enumerate(beats):
            if beat.index != expected_index:
                raise ValueError("beat indices must be contiguous and zero-based")
        times = [beat.time_seconds for beat in beats]
        if any(current <= previous for previous, current in zip(times, times[1:], strict=False)):
            raise ValueError("beat times must be strictly increasing")


@dataclass(frozen=True, slots=True)
class PhraseBoundary:
    beat_index: int
    time_seconds: float
    phrase_length_beats: int
    confidence: float
    provenance: EvidenceProvenance
    evidence_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.beat_index < 0:
            raise ValueError("beat_index must be non-negative")
        object.__setattr__(
            self,
            "time_seconds",
            _non_negative(self.time_seconds, "time_seconds"),
        )
        if self.phrase_length_beats not in {8, 16, 32}:
            raise ValueError("phrase_length_beats must be one of 8, 16, or 32")
        confidence = _confidence(self.confidence, "confidence")
        if confidence is None:
            raise ValueError("PhraseBoundary confidence must be explicit")
        object.__setattr__(self, "confidence", confidence)
        codes = tuple(code.strip() for code in self.evidence_codes if code.strip())
        if not codes:
            raise ValueError("evidence_codes must not be empty")
        object.__setattr__(self, "evidence_codes", codes)


@dataclass(frozen=True, slots=True)
class StructuralSegment:
    start_seconds: float
    end_seconds: float
    label: StructuralLabel
    confidence: float
    provenance: EvidenceProvenance
    evidence_codes: tuple[str, ...]
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        start = _non_negative(self.start_seconds, "start_seconds")
        end = _non_negative(self.end_seconds, "end_seconds")
        if end <= start:
            raise ValueError("end_seconds must be greater than start_seconds")
        confidence = _confidence(self.confidence, "confidence")
        if confidence is None:
            raise ValueError("StructuralSegment confidence must be explicit")
        codes = tuple(code.strip() for code in self.evidence_codes if code.strip())
        if not codes:
            raise ValueError("evidence_codes must not be empty")
        object.__setattr__(self, "start_seconds", start)
        object.__setattr__(self, "end_seconds", end)
        object.__setattr__(self, "confidence", confidence)
        object.__setattr__(self, "evidence_codes", codes)
        object.__setattr__(self, "details", MappingProxyType(dict(self.details)))


@dataclass(frozen=True, slots=True)
class DirectionalOverlapWindow:
    source_start_beat: int
    source_end_beat: int
    target_start_beat: int
    target_end_beat: int
    overlap_beats: int
    confidence: float
    provenance: EvidenceProvenance
    evidence_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        values = (
            self.source_start_beat,
            self.source_end_beat,
            self.target_start_beat,
            self.target_end_beat,
        )
        if any(value < 0 for value in values):
            raise ValueError("overlap beat indices must be non-negative")
        if self.source_end_beat <= self.source_start_beat:
            raise ValueError("source beat window must have positive length")
        if self.target_end_beat <= self.target_start_beat:
            raise ValueError("target beat window must have positive length")
        source_length = self.source_end_beat - self.source_start_beat
        target_length = self.target_end_beat - self.target_start_beat
        if (
            self.overlap_beats <= 0
            or self.overlap_beats != source_length
            or self.overlap_beats != target_length
        ):
            raise ValueError("overlap_beats must equal both directional window lengths")
        confidence = _confidence(self.confidence, "confidence")
        if confidence is None:
            raise ValueError("DirectionalOverlapWindow confidence must be explicit")
        object.__setattr__(self, "confidence", confidence)
        codes = tuple(code.strip() for code in self.evidence_codes if code.strip())
        if not codes:
            raise ValueError("evidence_codes must not be empty")
        object.__setattr__(self, "evidence_codes", codes)


@dataclass(frozen=True, slots=True)
class RhythmicStructureAnalysis:
    track_id: str
    duration_seconds: float
    beat_grid: BeatGrid
    phrase_boundaries: tuple[PhraseBoundary, ...] = ()
    segments: tuple[StructuralSegment, ...] = ()
    warnings: tuple[str, ...] = ()
    analysis_version: str = ANALYSIS_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "track_id", _required_text(self.track_id, "track_id"))
        duration = _non_negative(self.duration_seconds, "duration_seconds")
        object.__setattr__(self, "duration_seconds", duration)
        object.__setattr__(
            self,
            "analysis_version",
            _required_text(self.analysis_version, "analysis_version"),
        )
        boundaries = tuple(self.phrase_boundaries)
        segments = tuple(self.segments)
        object.__setattr__(self, "phrase_boundaries", boundaries)
        object.__setattr__(self, "segments", segments)
        object.__setattr__(self, "warnings", tuple(str(item) for item in self.warnings))
        boundary_times = [item.time_seconds for item in boundaries]
        if any(
            current <= previous
            for previous, current in zip(boundary_times, boundary_times[1:], strict=False)
        ):
            raise ValueError("phrase boundaries must be strictly increasing")
        if any(item.time_seconds > duration for item in boundaries):
            raise ValueError("phrase boundary exceeds track duration")
        if any(item.end_seconds > duration for item in segments):
            raise ValueError("structural segment exceeds track duration")


__all__ = [
    "ANALYSIS_VERSION",
    "BeatEvent",
    "BeatGrid",
    "DirectionalOverlapWindow",
    "EvidenceProvenance",
    "EvidenceStatus",
    "PhraseBoundary",
    "RhythmicStructureAnalysis",
    "StructuralLabel",
    "StructuralSegment",
]
