import pytest

from data.models.playlist_candidate import PlaylistCandidate
from services.composition import (
    CandidateIssueCode,
    CandidateIssueSeverity,
    adapt_playlist_candidates,
)


def _candidate(
    track_id: str,
    *,
    path: str | None = None,
    bpm=124.0,
    camelot="8A",
    energy=0.5,
    duration_seconds=320.0,
) -> PlaylistCandidate:
    return PlaylistCandidate(
        track_id=track_id,
        path=path or f"/music/{track_id}.mp3",
        title=f"Track {track_id}",
        artist="Artist",
        genre="tech house",
        source="pool-a",
        duration_seconds=duration_seconds,
        bpm=bpm,
        camelot=camelot,
        energy=energy,
    )


def test_adapter_is_deterministic_and_preserves_metadata() -> None:
    candidates = (
        _candidate("b", bpm=125, camelot="9a", energy=0.6),
        _candidate("a", bpm=124, camelot="8A", energy=0.4),
    )

    result = adapt_playlist_candidates(candidates)

    assert [track.track_id for track in result.tracks] == ["a", "b"]
    assert result.tracks[0].genre == "tech house"
    assert result.tracks[0].source_folder == "pool-a"
    assert result.tracks[1].camelot == "9A"
    assert result.issues == ()


def test_adapter_rejects_invalid_required_metrics_with_stable_codes() -> None:
    candidates = (
        _candidate("bad-bpm", bpm="not-a-number"),
        _candidate("bad-key", camelot="C#m"),
        _candidate("bad-energy", energy=float("inf")),
        _candidate("bad-path", path="   "),
    )

    result = adapt_playlist_candidates(candidates)
    codes = {(issue.track_id, issue.code) for issue in result.issues}

    assert result.tracks == ()
    assert result.rejected_count == 4
    assert codes == {
        ("bad-bpm", CandidateIssueCode.INVALID_BPM),
        ("bad-key", CandidateIssueCode.INVALID_CAMELOT),
        ("bad-energy", CandidateIssueCode.INVALID_ENERGY),
        ("bad-path", CandidateIssueCode.INVALID_PATH),
    }
    assert all(
        issue.severity == CandidateIssueSeverity.REJECTED
        for issue in result.issues
    )


def test_duration_fallback_is_explicit_and_evidenced() -> None:
    result = adapt_playlist_candidates(
        (_candidate("fallback", duration_seconds=None),),
        duration_fallback_seconds=360,
    )

    assert result.tracks[0].duration_seconds == 360
    assert result.fallback_count == 1
    assert result.issues[0].code == CandidateIssueCode.DURATION_FALLBACK
    assert result.issues[0].severity == CandidateIssueSeverity.FALLBACK


def test_invalid_fallback_configuration_is_rejected() -> None:
    with pytest.raises(ValueError, match="duration_fallback_seconds"):
        adapt_playlist_candidates((_candidate("track"),), duration_fallback_seconds=0)


def test_boolean_numeric_values_are_not_accepted_as_metrics() -> None:
    result = adapt_playlist_candidates(
        (
            _candidate("boolean-bpm", bpm=True),
            _candidate("boolean-energy", energy=False),
        )
    )

    assert result.tracks == ()
    assert {(issue.track_id, issue.code) for issue in result.issues} == {
        ("boolean-bpm", CandidateIssueCode.INVALID_BPM),
        ("boolean-energy", CandidateIssueCode.INVALID_ENERGY),
    }
