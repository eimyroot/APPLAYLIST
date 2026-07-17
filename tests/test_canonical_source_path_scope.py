from __future__ import annotations

import pytest

from data.models.playlist_candidate import PlaylistCandidate
from services.composition.export_service import CanonicalCompositionExportService
from services.composition.runner import (
    CanonicalCompositionExecutionRequest,
    CanonicalCompositionRunner,
)
from services.orchestrator.composition_authority import (
    CanonicalCompositionAuthority,
    PipelineCompositionCommand,
)


class FakeRepository:
    def __init__(self, candidates: list[PlaylistCandidate]) -> None:
        self.candidates = candidates
        self.calls = 0

    def list_playlist_candidates(self) -> list[PlaylistCandidate]:
        self.calls += 1
        return list(self.candidates)


class RecordingExporter:
    def __init__(self) -> None:
        self.calls = 0

    def export_m3u(self, *, playlist_id: str, tracks: list) -> dict:
        self.calls += 1
        return {
            "playlist_id": playlist_id,
            "m3u_path": f"exports/{playlist_id}.m3u",
            "manifest_path": f"artifacts/{playlist_id}.manifest.json",
            "warnings_path": f"artifacts/{playlist_id}.warnings.json",
            "audit_path": f"artifacts/{playlist_id}.audit.json",
            "resolved_count": len(tracks),
            "skipped_count": 0,
        }


def candidate(
    track_id: str,
    path: str,
    *,
    bpm: float | None = 128.0,
) -> PlaylistCandidate:
    return PlaylistCandidate(
        track_id=track_id,
        path=path,
        title=track_id,
        artist=f"artist-{track_id}",
        genre="tech house",
        source="scope-test",
        duration_seconds=300.0,
        bpm=bpm,
        camelot="8A",
        energy=0.6,
    )


def test_directory_scope_keeps_only_descendants() -> None:
    repository = FakeRepository(
        [
            candidate("inside-a", "/music/set/inside-a.mp3"),
            candidate("inside-b", "/music/set/deeper/inside-b.mp3"),
            candidate("outside", "/music/other/outside.mp3"),
        ]
    )

    result = CanonicalCompositionRunner(repository=repository).run(
        CanonicalCompositionExecutionRequest(
            target_track_count=2,
            source_path="/music/set",
        )
    )

    assert repository.calls == 1
    assert result.candidate_count == 2
    assert {track.track_id for track in result.tracks} == {"inside-a", "inside-b"}


def test_exact_file_scope_keeps_only_exact_path() -> None:
    repository = FakeRepository(
        [
            candidate("exact", "/music/set/exact.mp3"),
            candidate("sibling", "/music/set/sibling.mp3"),
        ]
    )

    result = CanonicalCompositionRunner(repository=repository).run(
        CanonicalCompositionExecutionRequest(
            target_track_count=1,
            source_path="/music/set/exact.mp3",
        )
    )

    assert result.candidate_count == 1
    assert [track.track_id for track in result.tracks] == ["exact"]


def test_relative_scope_is_rejected_before_repository_access() -> None:
    repository = FakeRepository([])

    with pytest.raises(ValueError, match="absolute path"):
        CanonicalCompositionExecutionRequest(
            target_track_count=1,
            source_path="music/set",
        )

    assert repository.calls == 0


def test_out_of_scope_invalid_candidate_does_not_pollute_evidence() -> None:
    repository = FakeRepository(
        [
            candidate("inside", "/music/set/inside.mp3"),
            candidate("outside-invalid", "/music/other/bad.mp3", bpm=None),
        ]
    )

    result = CanonicalCompositionRunner(repository=repository).run(
        CanonicalCompositionExecutionRequest(
            target_track_count=1,
            source_path="/music/set",
        )
    )

    assert result.candidate_count == 1
    assert result.rejected_count == 0
    assert result.adaptation_issues == ()
    assert [track.track_id for track in result.tracks] == ["inside"]


def test_empty_scope_performs_no_export_and_authority_fails_closed() -> None:
    repository = FakeRepository(
        [candidate("outside", "/music/other/outside.mp3")]
    )
    exporter = RecordingExporter()
    service = CanonicalCompositionExportService(
        runner=CanonicalCompositionRunner(repository=repository),
        exporter=exporter,
        run_id_factory=lambda: "canonical-scope-test",
    )
    authority = CanonicalCompositionAuthority(service=service)

    with pytest.raises(RuntimeError, match="did not produce"):
        authority.execute(
            PipelineCompositionCommand(
                path="/music/set",
                limit=1,
            )
        )

    assert repository.calls == 1
    assert exporter.calls == 0
