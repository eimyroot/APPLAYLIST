import pytest

from data.models.playlist_candidate import PlaylistCandidate
from services.composition import (
    CandidateIssueCode,
    CompositionShadowService,
    CompositionStatus,
    ShadowComparisonRequest,
)


class FakeRepository:
    def __init__(self, candidates: list[PlaylistCandidate]) -> None:
        self.candidates = candidates
        self.calls = 0

    def list_playlist_candidates(self) -> list[PlaylistCandidate]:
        self.calls += 1
        return list(self.candidates)


def _candidate(
    track_id: str,
    *,
    bpm: float | None,
    camelot: str | None,
    energy: float | None,
    duration_seconds: float | None = 300.0,
) -> PlaylistCandidate:
    return PlaylistCandidate(
        track_id=track_id,
        path=f"/music/{track_id}.mp3",
        title=track_id,
        artist=f"artist-{track_id}",
        genre="tech house",
        source=f"pool-{track_id}",
        duration_seconds=duration_seconds,
        bpm=bpm,
        camelot=camelot,
        energy=energy,
    )


def test_shadow_report_compares_overlap_and_position_without_mutating_legacy() -> None:
    legacy_ids = ("b", "a")
    repository = FakeRepository(
        [
            _candidate("a", bpm=124.0, camelot="8A", energy=0.25),
            _candidate("b", bpm=125.0, camelot="9A", energy=0.60),
        ]
    )

    report = CompositionShadowService(repository=repository).compare(
        ShadowComparisonRequest(
            legacy_track_ids=legacy_ids,
            target_track_count=2,
            bpm_min=120,
            bpm_max=130,
            mode="club",
            genre="tech house",
        )
    )

    assert legacy_ids == ("b", "a")
    assert report.legacy_track_ids == ("b", "a")
    assert report.canonical_track_ids == ("a", "b")
    assert report.canonical_status == CompositionStatus.SUCCESS
    assert report.overlap_count == 2
    assert report.position_match_count == 0
    assert report.legacy_coverage_ratio == 1.0
    assert report.canonical_coverage_ratio == 1.0
    assert repository.calls == 1


def test_shadow_report_preserves_adapter_rejection_and_fallback_evidence() -> None:
    repository = FakeRepository(
        [
            _candidate(
                "fallback",
                bpm=124.0,
                camelot="8A",
                energy=0.25,
                duration_seconds=None,
            ),
            _candidate("rejected", bpm=None, camelot="9A", energy=0.5),
        ]
    )

    report = CompositionShadowService(repository=repository).compare(
        ShadowComparisonRequest(
            legacy_track_ids=("fallback", "rejected"),
            target_track_count=1,
        )
    )

    assert report.candidate_count == 2
    assert report.adapted_count == 1
    assert report.rejected_count == 1
    assert report.fallback_count == 1
    assert {issue.code for issue in report.adaptation_issues} == {
        CandidateIssueCode.INVALID_BPM,
        CandidateIssueCode.DURATION_FALLBACK,
    }


def test_shadow_uses_requested_bpm_range() -> None:
    repository = FakeRepository(
        [
            _candidate("inside", bpm=126.0, camelot="8A", energy=0.25),
            _candidate("outside", bpm=140.0, camelot="9A", energy=0.50),
        ]
    )

    report = CompositionShadowService(repository=repository).compare(
        ShadowComparisonRequest(
            legacy_track_ids=("outside",),
            target_track_count=1,
            bpm_min=124,
            bpm_max=128,
        )
    )

    assert report.canonical_track_ids == ("inside",)
    assert report.overlap_count == 0
    assert report.legacy_coverage_ratio == 0.0
    assert report.canonical_coverage_ratio == 0.0


def test_invalid_mode_fails_before_repository_access() -> None:
    repository = FakeRepository([])
    service = CompositionShadowService(repository=repository)

    with pytest.raises(ValueError, match="Unsupported composition mode"):
        service.compare(
            ShadowComparisonRequest(
                legacy_track_ids=(),
                target_track_count=1,
                mode="not-a-mode",
            )
        )

    assert repository.calls == 0


def test_empty_legacy_output_has_zero_coverage_ratios() -> None:
    repository = FakeRepository(
        [_candidate("canonical", bpm=124.0, camelot="8A", energy=0.25)]
    )

    report = CompositionShadowService(repository=repository).compare(
        ShadowComparisonRequest(
            legacy_track_ids=(),
            target_track_count=1,
        )
    )

    assert report.overlap_count == 0
    assert report.position_match_count == 0
    assert report.legacy_coverage_ratio == 0.0
    assert report.canonical_coverage_ratio == 0.0
