from __future__ import annotations

from pathlib import Path
import sqlite3
from types import SimpleNamespace

import pytest
from tinytag import TinyTagException

from core.library import (
    LibraryScanResult,
    MetadataOrigin,
    TrackImportBatchResult,
    TrackImportCandidate,
    TrackMetadata,
)
from data.repositories.library_track_repository import LibraryTrackRepository
from services.library import (
    ContentTrackIdentityService,
    LibraryTrackIngestionService,
    MetadataReadError,
    TinyTagMetadataReader,
    TrackImportPersistenceService,
)


def _connection_factory(database_path: Path):
    def connect() -> sqlite3.Connection:
        connection = sqlite3.connect(database_path)
        connection.row_factory = sqlite3.Row
        return connection

    return connect


def _candidate(path: Path, *, title: str = "Track") -> TrackImportCandidate:
    identity = ContentTrackIdentityService(chunk_size=3).identify(path.resolve())
    return TrackImportCandidate(
        identity=identity,
        metadata=TrackMetadata(
            source_path=identity.source_path,
            provider="test-tags",
            provider_version="1",
            origin=MetadataOrigin.TAGS,
            title=title,
            artist="Artist",
            album="Album",
            genre="House",
            duration_seconds=180.0,
            sample_rate_hz=44100,
            bitrate_kbps=320,
            warnings=(),
        ),
    )


def _batch(*candidates: TrackImportCandidate) -> TrackImportBatchResult:
    ordered = tuple(
        sorted(
            candidates,
            key=lambda candidate: (
                candidate.identity.source_path.casefold(),
                candidate.identity.source_path,
            ),
        )
    )
    return TrackImportBatchResult(
        candidates=ordered,
        issues=(),
        source_scan_complete=True,
    )


def test_tinytag_reader_normalizes_tagged_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    track = tmp_path / "track.flac"
    track.write_bytes(b"audio")
    fake_tag = SimpleNamespace(
        title=["  Main   Track  "],
        artist=["Artist A", "Artist B"],
        album="Album",
        genre=["House", "Deep House"],
        duration=240.25,
        samplerate=48000.0,
        bitrate=320.1,
    )
    monkeypatch.setattr("services.library.metadata.TinyTag.get", lambda _path: fake_tag)

    metadata = TinyTagMetadataReader().read(track.resolve())

    assert metadata.provider == "tinytag"
    assert metadata.origin is MetadataOrigin.TAGS
    assert metadata.title == "Main Track"
    assert metadata.artist == "Artist A; Artist B"
    assert metadata.genre == "House; Deep House"
    assert metadata.duration_seconds == 240.25
    assert metadata.sample_rate_hz == 48000
    assert metadata.bitrate_kbps == 320
    assert metadata.warnings == ()


def test_tinytag_reader_uses_explicit_title_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    track = tmp_path / "Fallback_Title.wav"
    track.write_bytes(b"audio")
    fake_tag = SimpleNamespace(
        title=None,
        artist=None,
        album=None,
        genre=None,
        duration=30.0,
        samplerate=44100,
        bitrate=1411,
    )
    monkeypatch.setattr("services.library.metadata.TinyTag.get", lambda _path: fake_tag)

    metadata = TinyTagMetadataReader().read(track.resolve())

    assert metadata.origin is MetadataOrigin.TAGS_WITH_FILENAME_FALLBACK
    assert metadata.title == "Fallback Title"
    assert "title tag missing; title derived from filename" in metadata.warnings
    assert "artist tag missing" in metadata.warnings


def test_tinytag_reader_translates_parser_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    track = tmp_path / "broken.mp3"
    track.write_bytes(b"not-audio")

    def fail(_path):
        raise TinyTagException("broken")

    monkeypatch.setattr("services.library.metadata.TinyTag.get", fail)

    with pytest.raises(MetadataReadError) as error:
        TinyTagMetadataReader().read(track.resolve())

    assert error.value.code == "metadata_parse_failed"


def test_persistence_is_idempotent_and_keeps_legacy_track_projection(
    tmp_path: Path,
) -> None:
    database = tmp_path / "library.sqlite"
    track = tmp_path / "track.wav"
    track.write_bytes(b"same-content")
    candidate = _candidate(track)
    repository = LibraryTrackRepository(
        connection_factory=_connection_factory(database)
    )

    first = repository.persist_candidate(candidate)
    second = repository.persist_candidate(candidate)

    assert first.relinked is False
    assert second.relinked is False
    assert repository.metadata_snapshot_count(candidate.identity.track_id) == 1
    assert repository.list_file_history(candidate.identity.track_id) == (
        (str(track.resolve()), True),
    )

    with _connection_factory(database)() as connection:
        row = connection.execute(
            "SELECT path, title, source FROM tracks WHERE track_id = ?",
            (candidate.identity.track_id,),
        ).fetchone()
    assert row is not None
    assert row["path"] == str(track.resolve())
    assert row["title"] == "Track"
    assert row["source"] == "test-tags"


def test_persistence_records_relink_history_for_same_content(tmp_path: Path) -> None:
    database = tmp_path / "library.sqlite"
    first_path = tmp_path / "first.wav"
    moved_path = tmp_path / "moved.wav"
    first_path.write_bytes(b"same-content")
    moved_path.write_bytes(b"same-content")
    first_candidate = _candidate(first_path)
    moved_candidate = _candidate(moved_path)
    repository = LibraryTrackRepository(
        connection_factory=_connection_factory(database)
    )

    repository.persist_candidate(first_candidate)
    moved = repository.persist_candidate(moved_candidate)

    assert first_candidate.identity.track_id == moved_candidate.identity.track_id
    assert moved.relinked is True
    assert repository.get_current_path(moved.track_id) == str(moved_path.resolve())
    assert repository.list_file_history(moved.track_id) == (
        (str(first_path.resolve()), False),
        (str(moved_path.resolve()), True),
    )


def test_changed_metadata_creates_new_snapshot(tmp_path: Path) -> None:
    database = tmp_path / "library.sqlite"
    track = tmp_path / "track.wav"
    track.write_bytes(b"same-content")
    repository = LibraryTrackRepository(
        connection_factory=_connection_factory(database)
    )

    repository.persist_candidate(_candidate(track, title="First Title"))
    repository.persist_candidate(_candidate(track, title="Second Title"))

    identity = ContentTrackIdentityService().identify(track.resolve())
    assert repository.metadata_snapshot_count(identity.track_id) == 2


def test_transaction_failure_does_not_leave_partial_track_state(tmp_path: Path) -> None:
    database = tmp_path / "library.sqlite"
    first = tmp_path / "first.wav"
    second = tmp_path / "second.wav"
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    repository = LibraryTrackRepository(
        connection_factory=_connection_factory(database)
    )
    repository.persist_candidate(_candidate(first))

    with _connection_factory(database)() as connection:
        connection.execute(
            """
            CREATE TRIGGER fail_track_file_insert
            BEFORE INSERT ON track_files
            BEGIN
                SELECT RAISE(ABORT, 'forced failure');
            END
            """
        )
        connection.commit()

    persistence = TrackImportPersistenceService(repository=repository)
    candidate = _candidate(second)
    result = persistence.persist(_batch(candidate))

    assert result.persisted == ()
    assert result.issues[0].code == "track_persistence_failed"
    with _connection_factory(database)() as connection:
        track_row = connection.execute(
            "SELECT track_id FROM tracks WHERE track_id = ?",
            (candidate.identity.track_id,),
        ).fetchone()
        file_row = connection.execute(
            "SELECT path FROM track_files WHERE track_id = ?",
            (candidate.identity.track_id,),
        ).fetchone()
        metadata_row = connection.execute(
            "SELECT track_id FROM track_metadata_snapshots WHERE track_id = ?",
            (candidate.identity.track_id,),
        ).fetchone()
    assert track_row is None
    assert file_row is None
    assert metadata_row is None


def test_ingestion_service_connects_scan_import_and_persistence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = tmp_path / "library.sqlite"
    track = tmp_path / "track.wav"
    track.write_bytes(b"audio")
    fake_tag = SimpleNamespace(
        title="Tagged Track",
        artist="DJ",
        album=None,
        genre="Techno",
        duration=180.0,
        samplerate=44100,
        bitrate=320,
    )
    monkeypatch.setattr("services.library.metadata.TinyTag.get", lambda _path: fake_tag)
    scan = LibraryScanResult(
        root=str(tmp_path.resolve()),
        accepted_paths=(str(track.resolve()),),
        skipped=(),
        errors=(),
        discovered_entries=1,
    )
    repository = LibraryTrackRepository(
        connection_factory=_connection_factory(database)
    )
    service = LibraryTrackIngestionService(
        persistence=TrackImportPersistenceService(repository=repository)
    )

    result = service.ingest(scan)

    assert result.complete is True
    assert result.import_result.candidates[0].metadata.title == "Tagged Track"
    assert result.persistence_result.persisted[0].current_path == str(track.resolve())
