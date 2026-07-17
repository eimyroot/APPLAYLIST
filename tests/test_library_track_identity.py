from __future__ import annotations

from pathlib import Path

import pytest

from core.library import LibraryScanResult, MetadataOrigin, TrackMetadata
from services.library import (
    ContentTrackIdentityService,
    FilenameFallbackMetadataReader,
    LibraryCandidateImporter,
    MetadataReadError,
    TrackIdentityError,
)


def _scan_result(*paths: Path, complete: bool = True) -> LibraryScanResult:
    ordered = tuple(
        sorted(
            (str(path.resolve()) for path in paths),
            key=lambda value: (value.casefold(), value),
        )
    )
    return LibraryScanResult(
        root=str(paths[0].parent.resolve()) if paths else str(Path("/").resolve()),
        accepted_paths=ordered,
        skipped=(),
        errors=(),
        discovered_entries=len(ordered),
        cancelled=not complete,
    )


def test_same_content_at_different_paths_has_same_track_id(tmp_path: Path) -> None:
    first = tmp_path / "first.wav"
    second = tmp_path / "moved.wav"
    first.write_bytes(b"same-audio-content")
    second.write_bytes(b"same-audio-content")

    service = ContentTrackIdentityService(chunk_size=4)

    first_identity = service.identify(first.resolve())
    second_identity = service.identify(second.resolve())

    assert first_identity.track_id == second_identity.track_id
    assert first_identity.digest_hex == second_identity.digest_hex
    assert first_identity.source_path != second_identity.source_path


def test_changed_content_changes_track_id(tmp_path: Path) -> None:
    track = tmp_path / "track.flac"
    track.write_bytes(b"version-one")
    service = ContentTrackIdentityService(chunk_size=3)

    before = service.identify(track.resolve())
    track.write_bytes(b"version-two")
    after = service.identify(track.resolve())

    assert before.track_id != after.track_id


def test_identity_hashing_uses_configured_chunk_size(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    track = tmp_path / "large.wav"
    track.write_bytes(b"abcdefghij")
    read_sizes: list[int] = []
    original_open = Path.open

    class RecordingReader:
        def __init__(self, wrapped):
            self._wrapped = wrapped

        def __enter__(self):
            self._wrapped.__enter__()
            return self

        def __exit__(self, *args):
            return self._wrapped.__exit__(*args)

        def read(self, size: int = -1):
            read_sizes.append(size)
            return self._wrapped.read(size)

    def recording_open(path: Path, *args, **kwargs):
        return RecordingReader(original_open(path, *args, **kwargs))

    monkeypatch.setattr(Path, "open", recording_open)

    ContentTrackIdentityService(chunk_size=4).identify(track.resolve())

    assert read_sizes
    assert set(read_sizes) == {4}
    assert len(read_sizes) >= 3


def test_identity_rejects_relative_missing_and_directory_paths(tmp_path: Path) -> None:
    service = ContentTrackIdentityService()

    with pytest.raises(TrackIdentityError) as relative:
        service.identify("relative.wav")
    assert relative.value.code == "identity_path_not_absolute"

    with pytest.raises(TrackIdentityError) as missing:
        service.identify((tmp_path / "missing.wav").resolve())
    assert missing.value.code == "identity_file_missing"

    with pytest.raises(TrackIdentityError) as directory:
        service.identify(tmp_path.resolve())
    assert directory.value.code == "identity_not_regular_file"


def test_filename_fallback_is_explicit_and_does_not_invent_artist(tmp_path: Path) -> None:
    track = tmp_path / "Artist - Track_Name.wav"
    track.write_bytes(b"audio")

    metadata = FilenameFallbackMetadataReader().read(track.resolve())

    assert metadata.origin is MetadataOrigin.FILENAME_FALLBACK
    assert metadata.title == "Artist - Track Name"
    assert metadata.artist is None
    assert metadata.album is None
    assert metadata.genre is None
    assert metadata.provider == "filename-fallback"
    assert metadata.warnings == (
        "tagged metadata not read; title derived from filename",
    )


def test_filename_metadata_reader_rejects_invalid_paths(tmp_path: Path) -> None:
    reader = FilenameFallbackMetadataReader()

    with pytest.raises(MetadataReadError) as relative:
        reader.read("track.wav")
    assert relative.value.code == "metadata_path_not_absolute"

    with pytest.raises(MetadataReadError) as missing:
        reader.read((tmp_path / "missing.wav").resolve())
    assert missing.value.code == "metadata_file_missing"


def test_importer_deduplicates_identical_content_deterministically(tmp_path: Path) -> None:
    first = tmp_path / "A.wav"
    second = tmp_path / "B.wav"
    first.write_bytes(b"same")
    second.write_bytes(b"same")

    result = LibraryCandidateImporter().import_scan(_scan_result(second, first))

    assert len(result.candidates) == 1
    assert result.candidates[0].identity.source_path == str(first.resolve())
    assert len(result.issues) == 1
    assert result.issues[0].path == str(second.resolve())
    assert result.issues[0].code == "duplicate_content"


def test_importer_preserves_incomplete_scan_evidence(tmp_path: Path) -> None:
    track = tmp_path / "track.wav"
    track.write_bytes(b"audio")

    result = LibraryCandidateImporter().import_scan(
        _scan_result(track, complete=False)
    )

    assert len(result.candidates) == 1
    assert result.source_scan_complete is False


def test_importer_converts_invalid_metadata_output_to_controlled_issue(
    tmp_path: Path,
) -> None:
    track = tmp_path / "track.wav"
    track.write_bytes(b"audio")

    class WrongPathReader:
        def read(self, path):
            return TrackMetadata(
                source_path=str((tmp_path / "other.wav").resolve()),
                provider="test",
                provider_version="1",
                origin=MetadataOrigin.TAGS,
                title="Track",
            )

    result = LibraryCandidateImporter(metadata_reader=WrongPathReader()).import_scan(
        _scan_result(track)
    )

    assert result.candidates == ()
    assert len(result.issues) == 1
    assert result.issues[0].code == "metadata_output_invalid"


def test_metadata_contract_rejects_non_finite_and_malformed_values(
    tmp_path: Path,
) -> None:
    path = str((tmp_path / "track.wav").resolve())

    with pytest.raises(ValueError, match="finite and positive"):
        TrackMetadata(
            source_path=path,
            provider="test",
            provider_version="1",
            origin=MetadataOrigin.TAGS,
            duration_seconds=float("nan"),
        )

    with pytest.raises(TypeError, match="provider must be a string"):
        TrackMetadata(
            source_path=path,
            provider=123,  # type: ignore[arg-type]
            provider_version="1",
            origin=MetadataOrigin.TAGS,
        )

    with pytest.raises(TypeError, match="warnings must be strings"):
        TrackMetadata(
            source_path=path,
            provider="test",
            provider_version="1",
            origin=MetadataOrigin.TAGS,
            warnings=(123,),  # type: ignore[arg-type]
        )
