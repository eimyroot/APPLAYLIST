from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from data.models.playlist_candidate import PlaylistCandidate
from data.repositories.analysis_repository import AnalysisRepository
from services.composition.adapter import CandidateIssue, adapt_playlist_candidates
from services.composition.engine import DeterministicCompositionEngine
from services.composition.models import (
    CompositionMode,
    CompositionRequest,
    CompositionResult,
    CompositionTrack,
)


class PlaylistCandidateRepository(Protocol):
    def list_playlist_candidates(self) -> list[PlaylistCandidate]: ...


@dataclass(frozen=True, slots=True)
class CanonicalCompositionExecutionRequest:
    target_track_count: int
    bpm_min: float = 1.0
    bpm_max: float = 300.0
    mode: CompositionMode | str = CompositionMode.CLUB
    genre: str | None = None
    start_key: str | None = None
    duration_fallback_seconds: int = 300

    def __post_init__(self) -> None:
        if self.target_track_count <= 0:
            raise ValueError("target_track_count must be greater than zero")
        if self.bpm_min <= 0 or self.bpm_max <= 0:
            raise ValueError("BPM range values must be greater than zero")
        if self.bpm_min > self.bpm_max:
            raise ValueError("bpm_min must be less than or equal to bpm_max")
        if self.duration_fallback_seconds <= 0:
            raise ValueError("duration_fallback_seconds must be greater than zero")


@dataclass(frozen=True, slots=True)
class CanonicalCompositionExecutionResult:
    composition: CompositionResult
    candidate_count: int
    adapted_count: int
    rejected_count: int
    fallback_count: int
    adaptation_issues: tuple[CandidateIssue, ...]

    @property
    def tracks(self) -> tuple[CompositionTrack, ...]:
        return self.composition.tracks


class CanonicalCompositionRunner:
    """Execute canonical composition without exporting or mutating source data."""

    def __init__(
        self,
        *,
        repository: PlaylistCandidateRepository | None = None,
        engine: DeterministicCompositionEngine | None = None,
    ) -> None:
        self._repository = (
            repository if repository is not None else AnalysisRepository()
        )
        self._engine = (
            engine if engine is not None else DeterministicCompositionEngine()
        )

    def run(
        self,
        request: CanonicalCompositionExecutionRequest,
    ) -> CanonicalCompositionExecutionResult:
        mode = parse_composition_mode(request.mode)
        candidates = self._repository.list_playlist_candidates()
        adaptation = adapt_playlist_candidates(
            candidates,
            duration_fallback_seconds=request.duration_fallback_seconds,
        )
        composition = self._engine.compose(
            CompositionRequest(
                tracks=adaptation.tracks,
                target_track_count=request.target_track_count,
                bpm_min=request.bpm_min,
                bpm_max=request.bpm_max,
                mode=mode,
                genre=request.genre,
                start_key=request.start_key,
            )
        )
        return CanonicalCompositionExecutionResult(
            composition=composition,
            candidate_count=len(candidates),
            adapted_count=len(adaptation.tracks),
            rejected_count=adaptation.rejected_count,
            fallback_count=adaptation.fallback_count,
            adaptation_issues=adaptation.issues,
        )


def parse_composition_mode(value: CompositionMode | str) -> CompositionMode:
    if isinstance(value, CompositionMode):
        return value
    if not isinstance(value, str):
        raise ValueError(f"Unsupported composition mode: {value!r}")
    normalized = value.strip().casefold()
    try:
        return CompositionMode(normalized)
    except ValueError as exc:
        allowed = ", ".join(mode.value for mode in CompositionMode)
        raise ValueError(
            f"Unsupported composition mode: {value!r}; allowed: {allowed}"
        ) from exc
