from dataclasses import FrozenInstanceError

import pytest

from data.models.playlist_candidate import PlaylistCandidate
from services.composition import (
    CandidateIssueCode,
    CanonicalCompositionExecutionRequest,
    CanonicalCompositionRunner,
    CompositionMode,
    CompositionResult,
    CompositionStatus,
    CompositionSummary,
)


class FakeRepository:
    def __init__(self, candidates: list[PlaylistCandidate]) -> None:
        self.candidates = candidates
        self.calls = 0

    def list_playlist_candidates(self) -> list[PlaylistCandidate]:
        self.calls += 1
        return list(self.candidates)


def candidate(
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


def test_runner_returns_exportable_tracks_and_quality_evidence() -> None:
    repository = FakeRepository(
        [
            candidate("a", bpm=124.0, camelot="8A", energy=0.3),
            candidate(
                "b",
                bpm=125.0,
                camelot="9A",
                energy=0.6,
                duration_seconds=None,
            ),
            candidate("bad", bpm=None, camelot="10A", energy=0.5),
        ]
    )

    result = CanonicalCompositionRunner(repository=repository).run(
        CanonicalCompositionExecutionRequest(
            target_track_count=2,
            bpm_min=120.0,
            bpm_max=130.0,
            mode="club",
            genre="tech house",
        )
    )

    assert repository.calls == 1
    assert result.composition.status == CompositionStatus.SUCCESS
    assert {track.track_id for track in result.tracks} == {"a", "b"}
    assert all(track.path.startswith("/music/") for track in result.tracks)
    assert result.candidate_count == 3
    assert result.adapted_count == 2
    assert result.rejected_count == 1
    assert result.fallback_count == 1
    assert {issue.code for issue in result.adaptation_issues} == {
        CandidateIssueCode.INVALID_BPM,
        CandidateIssueCode.DURATION_FALLBACK,
    }


def test_invalid_mode_fails_before_repository_access() -> None:
    repository = FakeRepository([])
    runner = CanonicalCompositionRunner(repository=repository)

    with pytest.raises(ValueError, match="Unsupported composition mode"):
        runner.run(
            CanonicalCompositionExecutionRequest(
                target_track_count=1,
                mode="not-a-mode",
            )
        )

    assert repository.calls == 0


class RecordingEngine:
    def __init__(self) -> None:
        self.requests = []

    def compose(self, request) -> CompositionResult:
        self.requests.append(request)
        return CompositionResult(
            status=CompositionStatus.FAILED,
            tracks=(),
            decisions=(),
            summary=CompositionSummary(
                track_count=0,
                total_duration_seconds=0,
                average_bpm=0.0,
                minimum_bpm=0.0,
                maximum_bpm=0.0,
                average_energy=0.0,
            ),
        )


def test_runner_forwards_explicit_controls_to_injected_engine() -> None:
    engine = RecordingEngine()
    runner = CanonicalCompositionRunner(
        repository=FakeRepository([]),
        engine=engine,
    )

    runner.run(
        CanonicalCompositionExecutionRequest(
            target_track_count=7,
            bpm_min=126.0,
            bpm_max=134.0,
            mode=CompositionMode.AFTERHOURS,
            genre="hypnotic techno",
            start_key="8A",
        )
    )

    request = engine.requests[0]
    assert request.target_track_count == 7
    assert request.bpm_min == 126.0
    assert request.bpm_max == 134.0
    assert request.mode == CompositionMode.AFTERHOURS
    assert request.genre == "hypnotic techno"
    assert request.start_key == "8A"


def test_execution_result_is_immutable() -> None:
    result = CanonicalCompositionRunner(repository=FakeRepository([])).run(
        CanonicalCompositionExecutionRequest(target_track_count=1)
    )

    with pytest.raises(FrozenInstanceError):
        result.candidate_count = 99
