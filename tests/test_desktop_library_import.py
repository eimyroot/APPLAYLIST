from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.library.contracts import LibraryScanPolicy, LibraryScanResult
from core.library.persistence import (
    LibraryTrackIngestionResult,
    PersistedTrack,
    TrackPersistenceBatchResult,
    TrackPersistenceIssue,
)
from core.library.track_metadata import (
    MetadataOrigin,
    TrackIdentity,
    TrackImportBatchResult,
    TrackImportCandidate,
    TrackMetadata,
)
from services.desktop.library_import import (
    DesktopLibraryImportError,
    DesktopLibraryImportService,
    DesktopLibraryIssueStage,
)
from services.library.scanner import LibraryScanner


def _candidate(path: Path, *, digest: str = "a" * 64) -> TrackImportCandidate:
    resolved = path.resolve()
    identity = TrackIdentity(
        track_id=f"aptrack:v1:sha256:{digest}",
        digest_algorithm="sha256",
        digest_hex=digest,
        source_path=str(resolved),
        size_bytes=resolved.stat().st_size,
        mtime_ns=resolved.stat().st_mtime_ns,
    )
    metadata = TrackMetadata(
        source_path=str(resolved),
        provider="test-tags",
        provider_version="1",
        origin=MetadataOrigin.TAGS,
        title="Visible Track",
        artist="DJ",
        album="Set",
        genre="Techno",
        duration_seconds=180.0,
        sample_rate_hz=44_100,
        bitrate_kbps=320,
    )
    return TrackImportCandidate(identity=identity, metadata=metadata)


def _success_result(
    candidate: TrackImportCandidate,
    *,
    source_scan_complete: bool = True,
) -> LibraryTrackIngestionResult:
    persisted = PersistedTrack(
        track_id=candidate.identity.track_id,
        current_path=candidate.identity.source_path,
        metadata_provider=candidate.metadata.provider,
        metadata_provider_version=candidate.metadata.provider_version,
        metadata_origin=candidate.metadata.origin,
        relinked=False,
    )
    return LibraryTrackIngestionResult(
        import_result=TrackImportBatchResult(
            candidates=(candidate,),
            issues=(),
            source_scan_complete=source_scan_complete,
        ),
        persistence_result=TrackPersistenceBatchResult(
            persisted=(persisted,),
            issues=(),
            requested_count=1,
        ),
    )


class _IngestionStub:
    def __init__(self, result: LibraryTrackIngestionResult) -> None:
        self.result = result
        self.seen_scan: LibraryScanResult | None = None

    def ingest(self, scan_result: LibraryScanResult) -> LibraryTrackIngestionResult:
        self.seen_scan = scan_result
        return self.result


def test_import_folder_scans_and_returns_safe_visible_track(tmp_path: Path) -> None:
    root = (tmp_path / "Music").resolve()
    root.mkdir()
    track = root / "Track.WAV"
    track.write_bytes(b"audio")

    candidate = _candidate(track)
    ingestion = _IngestionStub(_success_result(candidate))
    service = DesktopLibraryImportService(ingestion=ingestion)

    result = service.import_folder(root)
    payload = result.to_payload()
    encoded = json.dumps(payload, sort_keys=True)

    assert ingestion.seen_scan is not None
    assert ingestion.seen_scan.accepted_paths == (str(track.resolve()),)
    assert result.complete is True
    assert result.folder_name == "Music"
    assert result.accepted_count == 1
    assert result.imported_count == 1
    assert result.persisted_count == 1
    assert result.tracks[0].file_name == "Track.WAV"
    assert result.tracks[0].title == "Visible Track"
    assert result.tracks[0].artist == "DJ"
    assert result.tracks[0].metadata_origin == "tags"
    assert str(root) not in encoded
    assert str(track.resolve()) not in encoded


def test_scan_skip_is_safe_and_does_not_expose_absolute_path(tmp_path: Path) -> None:
    root = (tmp_path / "Music").resolve()
    root.mkdir()
    notes = root / "notes.txt"
    notes.write_text("not audio", encoding="utf-8")

    empty = LibraryTrackIngestionResult(
        import_result=TrackImportBatchResult(
            candidates=(),
            issues=(),
            source_scan_complete=True,
        ),
        persistence_result=TrackPersistenceBatchResult(
            persisted=(),
            issues=(),
            requested_count=0,
        ),
    )
    service = DesktopLibraryImportService(ingestion=_IngestionStub(empty))

    result = service.import_folder(root)
    encoded = json.dumps(result.to_payload(), sort_keys=True)

    assert result.complete is True
    assert result.tracks == ()
    assert result.issues[0].stage is DesktopLibraryIssueStage.SCAN_SKIPPED
    assert result.issues[0].code == "unsupported_extension"
    assert result.issues[0].file_name == "notes.txt"
    assert str(root) not in encoded
    assert str(notes) not in encoded


def test_persistence_failure_is_reported_without_returning_track(tmp_path: Path) -> None:
    root = (tmp_path / "Music").resolve()
    root.mkdir()
    track = root / "track.wav"
    track.write_bytes(b"audio")
    candidate = _candidate(track)

    failed = LibraryTrackIngestionResult(
        import_result=TrackImportBatchResult(
            candidates=(candidate,),
            issues=(),
            source_scan_complete=True,
        ),
        persistence_result=TrackPersistenceBatchResult(
            persisted=(),
            issues=(
                TrackPersistenceIssue(
                    path=str(track.resolve()),
                    track_id=candidate.identity.track_id,
                    code="track_persistence_failed",
                    detail="database unavailable",
                ),
            ),
            requested_count=1,
        ),
    )
    service = DesktopLibraryImportService(ingestion=_IngestionStub(failed))

    result = service.import_folder(root)
    encoded = json.dumps(result.to_payload(), sort_keys=True)

    assert result.complete is False
    assert result.persisted_count == 0
    assert result.tracks == ()
    assert len(result.issues) == 1
    assert result.issues[0].stage is DesktopLibraryIssueStage.PERSISTENCE
    assert result.issues[0].code == "track_persistence_failed"
    assert result.issues[0].file_name == "track.wav"
    assert "database unavailable" not in encoded
    assert str(root) not in encoded


def test_partial_bounded_scan_is_preserved_in_desktop_result(tmp_path: Path) -> None:
    root = (tmp_path / "Music").resolve()
    root.mkdir()
    first = root / "a.wav"
    second = root / "b.wav"
    first.write_bytes(b"a")
    second.write_bytes(b"b")

    candidate = _candidate(first)
    ingestion = _IngestionStub(
        _success_result(candidate, source_scan_complete=False)
    )
    service = DesktopLibraryImportService(
        scanner=LibraryScanner(policy=LibraryScanPolicy(max_files=1)),
        ingestion=ingestion,
    )

    result = service.import_folder(root)

    assert ingestion.seen_scan is not None
    assert ingestion.seen_scan.file_limit_reached is True
    assert result.complete is False
    assert result.file_limit_reached is True
    assert result.accepted_count == 1
    assert any(issue.code == "file_limit_reached" for issue in result.issues)


def test_relative_folder_is_rejected_before_scanning() -> None:
    service = DesktopLibraryImportService()

    with pytest.raises(DesktopLibraryImportError, match="absolute"):
        service.import_folder("relative/music")
