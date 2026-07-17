from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from services.composition.adapter import CandidateIssue
from services.composition.engine import DeterministicCompositionEngine
from services.composition.models import (
    CompositionFailureReason,
    CompositionMode,
    CompositionStatus,
)
from services.composition.runner import (
    CanonicalCompositionExecutionRequest,
    CanonicalCompositionExecutionResult,
    CanonicalCompositionRunner,
    PlaylistCandidateRepository,
)


class CanonicalCompositionExecutor(Protocol):
    def run(
        self,
        request: CanonicalCompositionExecutionRequest,
    ) -> CanonicalCompositionExecutionResult: ...


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
        runner: CanonicalCompositionExecutor | None = None,
        repository: PlaylistCandidateRepository | None = None,
        engine: DeterministicCompositionEngine | None = None,
    ) -> None:
        if runner is not None and (repository is not None or engine is not None):
            raise ValueError("runner cannot be combined with repository or engine")
        self._runner = (
            runner
            if runner is not None
            else CanonicalCompositionRunner(repository=repository, engine=engine)
        )

    def compare(self, request: ShadowComparisonRequest) -> CompositionShadowReport:
        legacy_ids = tuple(track_id.strip() for track_id in request.legacy_track_ids)
        execution = self._runner.run(
            CanonicalCompositionExecutionRequest(
                target_track_count=request.target_track_count,
                bpm_min=request.bpm_min,
                bpm_max=request.bpm_max,
                mode=request.mode,
                genre=request.genre,
                start_key=request.start_key,
                duration_fallback_seconds=request.duration_fallback_seconds,
            )
        )
        canonical = execution.composition
        canonical_ids = tuple(track.track_id for track in execution.tracks)
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
            candidate_count=execution.candidate_count,
            adapted_count=execution.adapted_count,
            rejected_count=execution.rejected_count,
            fallback_count=execution.fallback_count,
            overlap_count=overlap_count,
            position_match_count=position_match_count,
            legacy_coverage_ratio=_ratio(overlap_count, len(legacy_set)),
            canonical_coverage_ratio=_ratio(overlap_count, len(canonical_set)),
            adaptation_issues=execution.adaptation_issues,
            canonical_warnings=canonical.warnings,
        )


def _ratio(numerator: int, denominator: int) -> float:
    return 0.0 if denominator == 0 else numerator / denominator
