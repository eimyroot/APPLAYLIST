from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from data.models.track_record import TrackRecord
from data.repositories.playlist_revision_repository import PlaylistRevisionRepository
from data.repositories.track_repository import TrackRepository
from services.desktop.playlist_export_transport import (
    DesktopPlaylistExportTransport,
    DesktopPlaylistExportTransportError,
)
from tests.test_desktop_readiness_sidecar import _finish, _request
from tests.test_desktop_set_proposal_transport import (
    _configure_database,
    _start_extended_sidecar,
    _track_id,
)


def _seed_export_revision(tmp_path: Path) -> tuple[dict[str, object], tuple[Path, ...]]:
    repository = TrackRepository()
    items: list[tuple[str, str]] = []
    paths: list[Path] = []
    for index in range(3):
        path = (tmp_path / f"audio-{index}.wav").resolve()
        path.write_bytes(b"fixture-not-read-by-export")
        paths.append(path)
        track_id = _track_id(chr(ord("a") + index))
        label = f"Fixture Artist – Track {index + 1}"
        repository.upsert(
            TrackRecord(
                track_id=track_id,
                path=str(path),
                title=f"Track {index + 1}",
                artist="Fixture Artist",
                duration_seconds=300.2 + index,
            )
        )
        items.append((track_id, label))
    revision = PlaylistRevisionRepository().append_root(
        source_proposal_id="spr_fixture",
        source_path_id="spp_fixture",
        items=items,
        operation_metadata={"fixture": "bundle58"},
    )
    return revision, tuple(paths)


def test_export_preview_is_renderer_safe_and_material_is_deterministic(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _configure_database(monkeypatch, tmp_path)
    revision, paths = _seed_export_revision(tmp_path)
    transport = DesktopPlaylistExportTransport()
    ledger = PlaylistRevisionRepository()
    before_count = ledger.count_revisions(str(revision["playlist_id"]))

    preview = transport.preview(revision_id=str(revision["revision_id"]))
    first = transport.material(revision_id=str(revision["revision_id"]))
    second = transport.material(revision_id=str(revision["revision_id"]))

    assert first == second
    assert preview["schema"] == "applaylist-desktop-playlist-export-preview-r1"
    assert preview["revision_id"] == revision["revision_id"]
    assert preview["track_count"] == 3
    assert preview["format"] == "m3u8"
    assert str(preview["suggested_filename"]).endswith(".m3u8")
    assert preview["personal_dj_model_training_authorized"] is False
    assert preview["production_activation_authorized"] is False

    preview_json = json.dumps(preview, ensure_ascii=False, sort_keys=True)
    for path in paths:
        assert str(path) not in preview_json
    assert "content_utf8" not in preview_json

    content = str(first["content_utf8"])
    assert content.startswith("#EXTM3U\n")
    assert [line for line in content.splitlines() if not line.startswith("#")] == [
        str(path.resolve()) for path in paths
    ]
    assert "Fixture Artist – Track 1" in content
    assert first["byte_count"] == len(content.encode("utf-8"))
    assert first["content_sha256"] == hashlib.sha256(content.encode("utf-8")).hexdigest()
    assert first["personal_dj_model_training_authorized"] is False
    assert first["production_activation_authorized"] is False
    assert ledger.count_revisions(str(revision["playlist_id"])) == before_count


def test_export_fails_closed_for_missing_revision_track_or_path_injection(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _configure_database(monkeypatch, tmp_path)
    revision, paths = _seed_export_revision(tmp_path)
    transport = DesktopPlaylistExportTransport()

    with pytest.raises(DesktopPlaylistExportTransportError) as missing_revision:
        transport.preview(revision_id="prv_missing")
    assert missing_revision.value.code == "playlist_export_revision_not_found"

    paths[1].unlink()
    with pytest.raises(DesktopPlaylistExportTransportError) as missing_file:
        transport.material(revision_id=str(revision["revision_id"]))
    assert missing_file.value.code == "playlist_export_track_unavailable"

    track_id = str(revision["items"][0]["track_id"])
    record = TrackRepository().get_by_id(track_id)
    assert record is not None
    TrackRepository().upsert(
        TrackRecord(
            track_id=record.track_id,
            path="/tmp/APPLAYLIST-bad\npath.wav",
            title=record.title,
            artist=record.artist,
            duration_seconds=record.duration_seconds,
        )
    )
    with pytest.raises(DesktopPlaylistExportTransportError) as injected:
        transport.material(revision_id=str(revision["revision_id"]))
    assert injected.value.code == "playlist_export_content_invalid"


def test_authenticated_playlist_export_routes_are_strict_and_preview_path_safe(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    database = _configure_database(monkeypatch, tmp_path)
    revision, paths = _seed_export_revision(tmp_path)
    process, ready = _start_extended_sidecar(database)
    body = json.dumps({"revision_id": revision["revision_id"]}).encode("utf-8")
    try:
        status, payload = _request(
            ready,
            method="POST",
            path="/v1/playlist/export/preview",
            secret="X" * 48,
            body=body,
        )
        assert status == 401
        assert payload == {"error": "unauthorized"}

        status, payload = _request(
            ready,
            method="POST",
            path="/v1/playlist/export/preview",
            body=json.dumps(
                {"revision_id": revision["revision_id"], "path": "/must/not/pass"}
            ).encode("utf-8"),
        )
        assert status == 400
        assert payload == {"error": "invalid_playlist_export_request"}

        status, preview = _request(
            ready,
            method="POST",
            path="/v1/playlist/export/preview",
            body=body,
        )
        assert status == 200
        encoded_preview = json.dumps(preview, sort_keys=True)
        for path in paths:
            assert str(path) not in encoded_preview
        assert "content_utf8" not in preview

        status, material = _request(
            ready,
            method="POST",
            path="/v1/playlist/export/material",
            body=body,
        )
        assert status == 200
        assert material["schema"] == "applaylist-desktop-playlist-export-material-r1"
        assert material["revision_id"] == revision["revision_id"]
        assert material["content_utf8"].startswith("#EXTM3U\n")
        assert material["byte_count"] == len(material["content_utf8"].encode("utf-8"))

        status, shutdown = _request(ready, method="POST", path="/v1/shutdown")
        assert status == 202
        assert shutdown == {"status": "shutting_down"}
        _finish(process)
    finally:
        if process.poll() is None:
            process.kill()
            _finish(process)
