from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from data.models.playlist_candidate import PlaylistCandidate
from data.repositories.analysis_repository import AnalysisRepository
from services.composition.adapter import (
    CandidateIssue,
    adapt_playlist_candidates,
)
from services.composition.engine import DeterministicCompositionEngine
from services.composition.models import (
    CompositionFailureReason,
    CompositionMode,
    CompositionRequest,
    CompositionStatus,
)


class PlaylistCandidateRepository(Protocol):
    def list_playlist_candidates(self) -> list[PlaylistCandidate]: ...


@dataclass(frozen=True, slots=True)
class ShadowComparisonRequest:
    legacy_track_ids: tuple[str, ...]
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
        for track_id in self.legacy_track_ids:
            if not isinstance(track_id, str) or not track_id.strip():
                raise ValueError("legacy_track_ids must contain non-empty strings")


@dataclass(frozen=True, slots=True)
class CompositionShadowReport:
    legacy_track_ids: tuple[str, ...]
    canonical_track_ids: tuple[str, ...]
    canonical_status: CompositionStatus
    canonical_failure_reason: CompositionFailureReason | None
    candidate_count: int
    adapted_count: int
    rejected_count: int
    fallback_count: int
    overlap_count: int
    position_match_count: int
    legacy_coverage_ratio: float
    canonical_coverage_ratio: float
    adaptation_issues: tuple[CandidateIssue, ...]
    canonical_warnings: tuple[str, ...]


class CompositionShadowService:
    """Read-only comparator. It never changes legacy output or writes artifacts."""

    def __init__(
        self,
        *,
        repository: PlaylistCandidateRepository | None = None,
        engine: DeterministicCompositionEngine | None = None,
    ) -> None:
        self._repository = repository or AnalysisRepository()
        self._engine = engine or DeterministicCompositionEngine()

    def compare(self, request: ShadowComparisonRequest) -> CompositionShadowReport:
        legacy_ids = tuple(track_id.strip() for track_id in request.legacy_track_ids)
        candidates = self._repository.list_playlist_candidates()
        adaptation = adapt_playlist_candidates(
            candidates,
            duration_fallback_seconds=request.duration_fallback_seconds,
        )
        mode = _parse_mode(request.mode)
        canonical = self._engine.compose(
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
        canonical_ids = tuple(track.track_id for track in canonical.tracks)
        legacy_set = set(legacy_ids)
        canonical_set = set(canonical_ids)
        overlap_count = len(legacy_set & canonical_set)
        position_match_count = sum(
            left == right
            for left, right in zip(legacy_ids, canonical_ids, strict=False)
        )

        return CompositionShadowReport(
            legacy_track_ids=legacy_ids,
            canonical_track_ids=canonical_ids,
            canonical_status=canonical.status,
            canonical_failure_reason=canonical.failure_reason,
            candidate_count=len(candidates),
            adapted_count=len(adaptation.tracks),
            rejected_count=adaptation.rejected_count,
            fallback_count=adaptation.fallback_count,
            overlap_count=overlap_count,
            position_match_count=position_match_count,
            legacy_coverage_ratio=_ratio(overlap_count, len(legacy_set)),
            canonical_coverage_ratio=_ratio(overlap_count, len(canonical_set)),
            adaptation_issues=adaptation.issues,
            canonical_warnings=canonical.warnings,
        )


def _parse_mode(value: CompositionMode | str) -> CompositionMode:
    if isinstance(value, CompositionMode):
        return value
    normalized = value.strip().casefold()
    try:
        return CompositionMode(normalized)
    except ValueError as exc:
        allowed = ", ".join(mode.value for mode in CompositionMode)
        raise ValueError(f"Unsupported composition mode: {value!r}; allowed: {allowed}") from exc


def _ratio(numerator: int, denominator: int) -> float:
    return 0.0 if denominator == 0 else numerator / denominator
