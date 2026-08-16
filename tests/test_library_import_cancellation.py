from __future__ import annotations

import json
import time
from pathlib import Path

from core.library.contracts import LibraryScanResult
from core.library.persistence import (
    LibraryTrackIngestionResult,
    TrackPersistenceBatchResult,
)
from core.library.track_metadata import (
    MetadataOrigin,
    TrackIdentity,
    TrackImportBatchResult,
    TrackImportCandidate,
    TrackMetadata,
)
from services.desktop.library_import import DesktopLibraryImportService
from services.library.importer import LibraryCandidateImporter
from services.library.persistence import TrackImportPersistenceService
from tests.test_desktop_readiness_sidecar import (
    NONCE,
    SECRET,
    _finish,
    _request,
    _start_sidecar,
)


def _candidate(path: Path, digest_character: str) -> TrackImportCandidate:
    resolved = path.resolve()
    digest = digest_character * 64
    return TrackImportCandidate(
        identity=TrackIdentity(
            track_id=f"aptrack:v1:sha256:{digest}",
            digest_algorithm="sha256",
            digest_hex=digest,
            source_path=str(resolved),
            size_bytes=resolved.stat().st_size,
            mtime_ns=resolved.stat().st_mtime_ns,
        ),
        metadata=TrackMetadata(
            source_path=str(resolved),
            provider="test-tags",
            provider_version="1",
            origin=MetadataOrigin.TAGS,
            title=resolved.stem,
        ),
    )


class _MetadataReader:
    def read(self, path: str | Path) -> TrackMetadata:
        resolved = Path(path).resolve()
        return TrackMetadata(
            source_path=str(resolved),
            provider="test-tags",
            provider_version="1",
            origin=MetadataOrigin.TAGS,
            title=resolved.stem,
        )


class _Repository:
    def __init__(self) -> None:
        self.persisted_paths: list[str] = []

    def persist_candidate(self, candidate: TrackImportCandidate):
        from core.library.persistence import PersistedTrack

        path = candidate.identity.source_path
        self.persisted_paths.append(path)
        return PersistedTrack(
            track_id=candidate.identity.track_id,
            current_path=path,
            metadata_provider=candidate.metadata.provider,
            metadata_provider_version=candidate.metadata.provider_version,
            metadata_origin=candidate.metadata.origin,
            relinked=False,
        )


class _IngestionStub:
    def __init__(self, result: LibraryTrackIngestionResult) -> None:
        self._result = result

    def ingest(self, _scan_result: LibraryScanResult) -> LibraryTrackIngestionResult:
        return self._result


def test_importer_stops_between_candidates_without_fabricating_issue(tmp_path: Path) -> None:
    first = tmp_path / "a.wav"
    second = tmp_path / "b.wav"
    first.write_bytes(b"a")
    second.write_bytes(b"b")
    cancelled = False

    def request_cancel_after_first(imported: int) -> None:
        nonlocal cancelled
        if imported == 1:
            cancelled = True

    importer = LibraryCandidateImporter(
        metadata_reader=_MetadataReader(),
        cancel_requested=lambda: cancelled,
        progress_updated=request_cancel_after_first,
    )
    scan = LibraryScanResult(
        root=str(tmp_path.resolve()),
        accepted_paths=(str(first.resolve()), str(second.resolve())),
        skipped=(),
        errors=(),
        discovered_entries=2,
    )

    result = importer.import_scan(scan)

    assert result.cancelled is True
    assert len(result.candidates) == 1
    assert result.candidates[0].identity.source_path == str(first.resolve())
    assert result.issues == ()


def test_persistence_accounts_for_cancelled_candidates_without_fake_errors(
    tmp_path: Path,
) -> None:
    first = tmp_path / "a.wav"
    second = tmp_path / "b.wav"
    first.write_bytes(b"a")
    second.write_bytes(b"b")
    candidates = (_candidate(first, "a"), _candidate(second, "b"))
    cancelled = False

    def request_cancel_after_first(persisted: int) -> None:
        nonlocal cancelled
        if persisted == 1:
            cancelled = True

    repository = _Repository()
    service = TrackImportPersistenceService(
        repository=repository,
        cancel_requested=lambda: cancelled,
        progress_updated=request_cancel_after_first,
    )
    batch = TrackImportBatchResult(
        candidates=candidates,
        issues=(),
        source_scan_complete=True,
    )

    result = service.persist(batch)

    assert len(result.persisted) == 1
    assert result.issues == ()
    assert result.cancelled_count == 1
    assert result.requested_count == 2
    assert result.complete is False


def test_desktop_result_marks_import_or_persistence_cancellation(tmp_path: Path) -> None:
    root = (tmp_path / "Music").resolve()
    root.mkdir()
    track = root / "a.wav"
    track.write_bytes(b"a")
    candidate = _candidate(track, "a")
    ingestion = LibraryTrackIngestionResult(
        import_result=TrackImportBatchResult(
            candidates=(candidate,),
            issues=(),
            source_scan_complete=True,
            cancelled=True,
        ),
        persistence_result=TrackPersistenceBatchResult(
            persisted=(),
            issues=(),
            requested_count=1,
            cancelled_count=1,
        ),
    )
    service = DesktopLibraryImportService(ingestion=_IngestionStub(ingestion))

    result = service.import_folder(root)

    assert result.cancelled is True
    assert result.complete is False
    assert result.imported_count == 1
    assert result.persisted_count == 0
    assert result.issues == ()


def test_sidecar_lifecycle_cancel_is_authenticated_idempotent_and_path_safe(
    tmp_path: Path,
) -> None:
    root = (tmp_path / "Music").resolve()
    root.mkdir()
    for index in range(2_000):
        (root / f"note-{index:04d}.txt").write_text("x", encoding="utf-8")
    database = (tmp_path / "sidecar-lifecycle.db").resolve()
    process, ready = _start_sidecar(env={"DATABASE_URL": f"sqlite:///{database}"})
    try:
        status, payload = _request(
            ready,
            method="GET",
            path="/v1/library/import/status",
        )
        assert status == 409
        assert payload == {"error": "library_import_not_started"}

        request_body = json.dumps(
            {"folder": str(root)},
            separators=(",", ":"),
        ).encode("utf-8")
        status, payload = _request(
            ready,
            method="POST",
            path="/v1/library/import/start",
            body=request_body,
        )
        assert status == 202
        assert payload["state"] in {"running", "succeeded"}

        status, payload = _request(
            ready,
            method="POST",
            path="/v1/library/import/cancel",
            body=b"",
        )
        assert status == 202
        assert payload["state"] in {"cancelling", "cancelled", "succeeded"}

        status, second_cancel = _request(
            ready,
            method="POST",
            path="/v1/library/import/cancel",
            body=b"",
        )
        assert status == 202
        assert second_cancel["state"] in {"cancelling", "cancelled", "succeeded"}

        deadline = time.monotonic() + 5.0
        terminal = second_cancel
        while not terminal["terminal"] and time.monotonic() < deadline:
            time.sleep(0.02)
            status, terminal = _request(
                ready,
                method="GET",
                path="/v1/library/import/status",
            )
            assert status == 200

        assert terminal["terminal"] is True
        assert terminal["state"] in {"cancelled", "succeeded"}
        assert terminal["phase"] in {
            "scanning",
            "importing",
            "persisting",
            "finalizing",
        }
        counts = terminal["counts"]
        assert 0 <= counts["persisted"] <= counts["imported"] <= counts["accepted"]
        assert counts["accepted"] <= counts["discovered_entries"]

        encoded = json.dumps(terminal, sort_keys=True)
        assert str(root) not in encoded
        assert SECRET not in encoded
        assert NONCE not in encoded

        status, shutdown = _request(ready, method="POST", path="/v1/shutdown")
        assert status == 202
        assert shutdown == {"status": "shutting_down"}
        _finish(process)
    finally:
        if process.poll() is None:
            process.kill()
            _finish(process)