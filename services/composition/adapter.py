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
    ordered = sorted(
        candidates,
        key=lambda item: (
            _clean_text(item.track_id),
            _clean_text(item.path),
        ),
    )

    for candidate in ordered:
        track_id = _clean_text(candidate.track_id)
        path = _clean_text(candidate.path)
        bpm = _as_finite_float(candidate.bpm)
        energy = _as_finite_float(candidate.energy)
        camelot = normalize_camelot(
            _clean_text(candidate.camelot) if candidate.camelot is not None else None
        )
        fatal_codes: list[CandidateIssueCode] = []

        if not track_id:
            fatal_codes.append(CandidateIssueCode.INVALID_TRACK_ID)
        if not path:
            fatal_codes.append(CandidateIssueCode.INVALID_PATH)
        if bpm is None or bpm <= 0:
            fatal_codes.append(CandidateIssueCode.INVALID_BPM)
        if camelot is None:
            fatal_codes.append(CandidateIssueCode.INVALID_CAMELOT)
        if energy is None or not 0.0 <= energy <= 1.0:
            fatal_codes.append(CandidateIssueCode.INVALID_ENERGY)

        if fatal_codes:
            issues.extend(
                CandidateIssue(
                    track_id=track_id,
                    code=code,
                    severity=CandidateIssueSeverity.REJECTED,
                )
                for code in fatal_codes
            )
            continue

        duration = _as_finite_float(candidate.duration_seconds)
        if duration is None or duration <= 0:
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
                bpm=bpm,
                camelot=camelot,
                energy=energy,
                duration_seconds=max(1, round(duration)),
            )
        )

    return CandidateAdaptationResult(
        tracks=tuple(tracks),
        issues=tuple(issues),
    )


def _clean_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _as_finite_float(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        converted = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return converted if math.isfinite(converted) else None
