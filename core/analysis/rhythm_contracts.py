from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite

ANALYSIS_VERSION = "canonical-rhythmic-beat-grid-shadow-v1"


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


@dataclass(frozen=True, slots=True)
class BeatEvent:
    index: int
    time_seconds: float
    confidence: float
    is_downbeat: bool | None = None
    downbeat_confidence: float | None = None

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
        if self.is_downbeat is None and downbeat_confidence is not None:
            raise ValueError("unknown downbeat must not carry downbeat_confidence")
        if self.is_downbeat is not None and downbeat_confidence is None:
            raise ValueError("known downbeat requires independent downbeat_confidence")


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
            if not isfinite(tempo) or not 20.0 <= tempo <= 400.0:
                raise ValueError("tempo_bpm must be finite and between 20 and 400")
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
                raise ValueError("unavailable BeatGrid must not carry measured values")
            if not self.unavailable_reason:
                raise ValueError("unavailable BeatGrid requires unavailable_reason")
            return

        if self.unavailable_reason is not None:
            raise ValueError("available BeatGrid must not carry unavailable_reason")
        if len(beats) < 2:
            raise ValueError("available BeatGrid requires at least two beat events")
        if self.tempo_bpm is None or self.tempo_confidence is None:
            raise ValueError("available BeatGrid requires tempo_bpm and tempo_confidence")
        for expected_index, beat in enumerate(beats):
            if beat.index != expected_index:
                raise ValueError("beat indices must be contiguous and zero-based")
        times = [beat.time_seconds for beat in beats]
        if any(current <= previous for previous, current in zip(times, times[1:], strict=False)):
            raise ValueError("beat times must be strictly increasing")


@dataclass(frozen=True, slots=True)
class RhythmicStructureAnalysis:
    track_id: str
    duration_seconds: float
    beat_grid: BeatGrid
    warnings: tuple[str, ...] = ()
    analysis_version: str = ANALYSIS_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "track_id", _required_text(self.track_id, "track_id"))
        duration = _non_negative(self.duration_seconds, "duration_seconds")
        if duration <= 0.0:
            raise ValueError("duration_seconds must be positive")
        object.__setattr__(self, "duration_seconds", duration)
        object.__setattr__(
            self,
            "analysis_version",
            _required_text(self.analysis_version, "analysis_version"),
        )
        object.__setattr__(self, "warnings", tuple(str(item) for item in self.warnings))
        if any(beat.time_seconds > duration for beat in self.beat_grid.beats):
            raise ValueError("beat event exceeds track duration")


__all__ = [
    "ANALYSIS_VERSION",
    "BeatEvent",
    "BeatGrid",
    "EvidenceProvenance",
    "EvidenceStatus",
    "RhythmicStructureAnalysis",
]
