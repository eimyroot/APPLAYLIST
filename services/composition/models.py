from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class CompositionStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


class CompositionFailureReason(str, Enum):
    NO_CANDIDATES = "no_candidates"
    INVALID_REQUEST = "invalid_request"
    COMPOSITION_STALLED = "composition_stalled"


class CompositionMode(str, Enum):
    WARMUP = "warmup"
    CLUB = "club"
    FESTIVAL = "festival"
    AFTERHOURS = "afterhours"
    CUSTOM = "custom"


class EnergyStage(str, Enum):
    INTRO = "intro"
    WARMUP = "warmup"
    GROOVE = "groove"
    LIFT = "lift"
    PEAK = "peak"
    AFTERGLOW = "afterglow"
    CLOSING = "closing"


@dataclass(frozen=True, slots=True)
class CompositionTrack:
    track_id: str
    path: str
    bpm: float
    camelot: str
    energy: float
    duration_seconds: int = 300
    genre: str = ""
    title: Optional[str] = None
    artist: Optional[str] = None
    label: Optional[str] = None
    source_folder: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.track_id.strip():
            raise ValueError("track_id must not be empty")
        if not self.path.strip():
            raise ValueError("path must not be empty")
        if self.bpm <= 0:
            raise ValueError("bpm must be greater than zero")
        if not 0.0 <= self.energy <= 1.0:
            raise ValueError("energy must be between 0 and 1")
        if self.duration_seconds <= 0:
            raise ValueError("duration_seconds must be greater than zero")


@dataclass(frozen=True, slots=True)
class CompositionConstraints:
    bpm_jump_max: float = 3.0
    bpm_jump_max_peak: float = 5.0
    same_artist_min_gap: int = 3
    same_label_min_gap: int = 2
    same_source_folder_max_consecutive: int = 2
    allow_same_key: bool = True
    allow_adjacent_camelot: bool = True
    allow_relative_key: bool = True

    def __post_init__(self) -> None:
        if self.bpm_jump_max <= 0 or self.bpm_jump_max_peak <= 0:
            raise ValueError("BPM jump limits must be greater than zero")
        if self.same_artist_min_gap < 0 or self.same_label_min_gap < 0:
            raise ValueError("spacing gaps must not be negative")
        if self.same_source_folder_max_consecutive < 1:
            raise ValueError("source folder consecutive limit must be at least one")


@dataclass(frozen=True, slots=True)
class EnergyTarget:
    stage: EnergyStage
    target: float
    tolerance: float = 0.15

    def __post_init__(self) -> None:
        if not 0.0 <= self.target <= 1.0:
            raise ValueError("energy target must be between 0 and 1")
        if not 0.0 <= self.tolerance <= 1.0:
            raise ValueError("energy tolerance must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class CompositionRequest:
    tracks: tuple[CompositionTrack, ...]
    target_track_count: int
    mode: CompositionMode = CompositionMode.CLUB
    bpm_min: float = 1.0
    bpm_max: float = 300.0
    genre: Optional[str] = None
    start_key: Optional[str] = None
    energy_curve: tuple[EnergyTarget, ...] = ()
    constraints: CompositionConstraints = field(default_factory=CompositionConstraints)

    def __post_init__(self) -> None:
        if self.target_track_count <= 0:
            raise ValueError("target_track_count must be greater than zero")
        if self.bpm_min <= 0 or self.bpm_max <= 0:
            raise ValueError("BPM range values must be greater than zero")
        if self.bpm_min > self.bpm_max:
            raise ValueError("bpm_min must be less than or equal to bpm_max")


@dataclass(frozen=True, slots=True)
class TransitionReason:
    code: str
    value: float
    weight: float
    contribution: float
    passed: bool


@dataclass(frozen=True, slots=True)
class TransitionScore:
    total: float
    eligible: bool
    bpm_delta: float
    harmonic_compatible: bool
    energy_distance: float
    artist_spacing_ok: bool
    label_spacing_ok: bool
    source_rotation_ok: bool
    reasons: tuple[TransitionReason, ...] = ()


@dataclass(frozen=True, slots=True)
class CompositionDecision:
    order_index: int
    track_id: str
    stage: EnergyStage
    score: TransitionScore


@dataclass(frozen=True, slots=True)
class CompositionSummary:
    track_count: int
    total_duration_seconds: int
    average_bpm: float
    minimum_bpm: float
    maximum_bpm: float
    average_energy: float


@dataclass(frozen=True, slots=True)
class CompositionResult:
    status: CompositionStatus
    tracks: tuple[CompositionTrack, ...]
    decisions: tuple[CompositionDecision, ...]
    summary: CompositionSummary
    failure_reason: Optional[CompositionFailureReason] = None
    warnings: tuple[str, ...] = ()
