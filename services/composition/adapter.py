from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

from data.models.playlist_candidate import PlaylistCandidate
from services.composition.camelot import normalize_camelot
from services.composition.models import CompositionTrack


class CandidateIssueCode(str, Enum):
    INVALID_TRACK_ID = "invalid_track_id"
    INVALID_PATH = "invalid_path"
    INVALID_BPM = "invalid_bpm"
    INVALID_CAMELOT = "invalid_camelot"
    INVALID_ENERGY = "invalid_energy"
    DURATION_FALLBACK = "duration_fallback"


class CandidateIssueSeverity(str, Enum):
    REJECTED = "rejected"
    FALLBACK = "fallback"


@dataclass(frozen=True, slots=True)
class CandidateIssue:
    track_id: str
    code: CandidateIssueCode
    severity: CandidateIssueSeverity


@dataclass(frozen=True, slots=True)
class CandidateAdaptationResult:
    tracks: tuple[CompositionTrack, ...]
    issues: tuple[CandidateIssue, ...]

    @property
    def rejected_count(self) -> int:
        return len(
            {
                issue.track_id
                for issue in self.issues
                if issue.severity == CandidateIssueSeverity.REJECTED
            }
        )

    @property
    def fallback_count(self) -> int:
        return sum(
            issue.severity == CandidateIssueSeverity.FALLBACK
            for issue in self.issues
        )


def adapt_playlist_candidates(
    candidates: list[PlaylistCandidate] | tuple[PlaylistCandidate, ...],
    *,
    duration_fallback_seconds: int = 300,
) -> CandidateAdaptationResult:
    if duration_fallback_seconds <= 0:
        raise ValueError("duration_fallback_seconds must be greater than zero")

    tracks: list[CompositionTrack] = []
    issues: list[CandidateIssue] = []

    for candidate in sorted(candidates, key=lambda item: (item.track_id, item.path)):
        track_id = candidate.track_id.strip()
        path = candidate.path.strip()
        fatal_codes: list[CandidateIssueCode] = []

        if not track_id:
            fatal_codes.append(CandidateIssueCode.INVALID_TRACK_ID)
        if not path:
            fatal_codes.append(CandidateIssueCode.INVALID_PATH)
        if not _finite_positive(candidate.bpm):
            fatal_codes.append(CandidateIssueCode.INVALID_BPM)

        camelot = normalize_camelot(candidate.camelot)
        if camelot is None:
            fatal_codes.append(CandidateIssueCode.INVALID_CAMELOT)

        if not _finite_range(candidate.energy, minimum=0.0, maximum=1.0):
            fatal_codes.append(CandidateIssueCode.INVALID_ENERGY)

        if fatal_codes:
            issue_track_id = track_id or candidate.track_id
            issues.extend(
                CandidateIssue(
                    track_id=issue_track_id,
                    code=code,
                    severity=CandidateIssueSeverity.REJECTED,
                )
                for code in fatal_codes
            )
            continue

        duration = candidate.duration_seconds
        if not _finite_positive(duration):
            duration = float(duration_fallback_seconds)
            issues.append(
                CandidateIssue(
                    track_id=track_id,
                    code=CandidateIssueCode.DURATION_FALLBACK,
                    severity=CandidateIssueSeverity.FALLBACK,
                )
            )

        tracks.append(
            CompositionTrack(
                track_id=track_id,
                path=path,
                title=candidate.title,
                artist=candidate.artist,
                genre=candidate.genre or "",
                source_folder=candidate.source,
                bpm=float(candidate.bpm),
                camelot=camelot,
                energy=float(candidate.energy),
                duration_seconds=max(1, round(float(duration))),
            )
        )

    return CandidateAdaptationResult(
        tracks=tuple(tracks),
        issues=tuple(issues),
    )


def _finite_positive(value: float | int | None) -> bool:
    return value is not None and math.isfinite(float(value)) and float(value) > 0


def _finite_range(
    value: float | int | None,
    *,
    minimum: float,
    maximum: float,
) -> bool:
    return (
        value is not None
        and math.isfinite(float(value))
        and minimum <= float(value) <= maximum
    )
