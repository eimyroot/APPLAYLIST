from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
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


def normalize_source_path(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("source_path must be a non-empty absolute path")
    candidate = Path(os.path.normpath(value.strip()))
    if not candidate.is_absolute():
        raise ValueError("source_path must be an absolute path")
    return str(candidate)


def candidate_is_within_source_path(
    candidate: PlaylistCandidate,
    source_path: str,
) -> bool:
    raw_path = candidate.path
    if not isinstance(raw_path, str) or not raw_path.strip():
        return False
    candidate_path = Path(os.path.normpath(raw_path.strip()))
    if not candidate_path.is_absolute():
        return False
    scope = Path(source_path)
    return candidate_path == scope or scope in candidate_path.parents


@dataclass(frozen=True, slots=True)
class CanonicalCompositionExecutionRequest:
    target_track_count: int
    bpm_min: float = 1.0
    bpm_max: float = 300.0
    mode: CompositionMode | str = CompositionMode.CLUB
    genre: str | None = None
    start_key: str | None = None
    duration_fallback_seconds: int = 300
    source_path: str | None = None

    def __post_init__(self) -> None:
        if self.target_track_count <= 0:
            raise ValueError("target_track_count must be greater than zero")
        if self.bpm_min <= 0 or self.bpm_max <= 0:
            raise ValueError("BPM range values must be greater than zero")
        if self.bpm_min > self.bpm_max:
            raise ValueError("bpm_min must be less than or equal to bpm_max")
        if self.duration_fallback_seconds <= 0:
            raise ValueError("duration_fallback_seconds must be greater than zero")
        if self.source_path is not None:
            object.__setattr__(
                self,
                "source_path",
                normalize_source_path(self.source_path),
            )


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
        if request.source_path is not None:
            candidates = [
                candidate
                for candidate in candidates
                if candidate_is_within_source_path(candidate, request.source_path)
            ]
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
