from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from data.models.track_record import TrackRecord
from data.repositories.playlist_revision_repository import PlaylistRevisionRepository
from data.repositories.track_repository import TrackRepository
from services.desktop.playlist_vendor_interop_transport import (
    DesktopPlaylistVendorInteropError,
    DesktopPlaylistVendorInteropTransport,
)
from tests.test_desktop_playlist_export_transport import _seed_export_revision
from tests.test_desktop_readiness_sidecar import _finish, _request
from tests.test_desktop_set_proposal_transport import (
    _configure_database,
    _start_extended_sidecar,
)


def test_vendor_preview_is_capability_gated_path_safe_and_non_mutating(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _configure_database(monkeypatch, tmp_path)
    revision, paths = _seed_export_revision(tmp_path)
    ledger = PlaylistRevisionRepository()
    before = ledger.count_revisions(str(revision["playlist_id"]))

    preview = DesktopPlaylistVendorInteropTransport().preview(
        revision_id=str(revision["revision_id"])
    )

    assert preview["schema"] == "applaylist-desktop-vendor-interop-preview-r1"
    assert preview["catalog_version"] == "vendor-interop-catalog-r1"
    assert preview["verified_at"] == "2026-08-19"
    assert preview["revision_id"] == revision["revision_id"]
    assert preview["track_count"] == 3
    assert preview["m3u8_path_valid"] is True
    assert preview["personal_dj_model_training_authorized"] is False
    assert preview["production_activation_authorized"] is False

    capabilities = preview["capabilities"]
    assert [item["vendor"] for item in capabilities] == ["rekordbox", "traktor", "serato"]
    assert [item["status"] for item in capabilities] == [
        "documented_format_export",
        "guidance_only_nml_required",
        "guidance_only_files_crate",
    ]
    assert [item["artifact_export_available"] for item in capabilities] == [True, False, False]
    assert all(item["vendor_database_mutation_authorized"] is False for item in capabilities)

    encoded = json.dumps(preview, sort_keys=True)
    for path in paths:
        assert str(path) not in encoded
    assert "content_utf8" not in encoded
    assert ledger.count_revisions(str(revision["playlist_id"])) == before


def test_rekordbox_xml_is_deterministic_ordered_escaped_and_uri_encoded(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _configure_database(monkeypatch, tmp_path)
    revision, _ = _seed_export_revision(tmp_path)
    tracks = TrackRepository()

    first_item = revision["items"][0]
    first_record = tracks.get_by_id(str(first_item["track_id"]))
    assert first_record is not None
    spaced_path = (tmp_path / "audio space & one.wav").resolve()
    spaced_path.write_bytes(b"fixture-not-read-by-vendor-export")
    tracks.upsert(
        TrackRecord(
            track_id=first_record.track_id,
            path=str(spaced_path),
            title=first_record.title,
            artist=first_record.artist,
            duration_seconds=first_record.duration_seconds,
        )
    )

    escaped_revision = PlaylistRevisionRepository().append_root(
        source_proposal_id="spr_vendor_escape",
        source_path_id="spp_vendor_escape",
        items=[
            (str(item["track_id"]), "A & <B>" if index == 0 else str(item["display_name"]))
            for index, item in enumerate(revision["items"])
        ],
        operation_metadata={"fixture": "bundle60"},
    )

    transport = DesktopPlaylistVendorInteropTransport()
    first = transport.rekordbox_material(revision_id=str(escaped_revision["revision_id"]))
    second = transport.rekordbox_material(revision_id=str(escaped_revision["revision_id"]))

    assert first == second
    assert first["schema"] == "applaylist-desktop-vendor-interop-material-r1"
    assert first["vendor"] == "rekordbox"
    assert first["format"] == "rekordbox_xml"
    assert first["vendor_database_mutation_authorized"] is False
    assert first["personal_dj_model_training_authorized"] is False
    assert first["production_activation_authorized"] is False

    content = str(first["content_utf8"])
    encoded = content.encode("utf-8")
    assert content.startswith('<?xml version="1.0" encoding="UTF-8" ?>\n')
    assert "A &amp; &lt;B&gt;" in content
    assert "file://localhost/" in content
    assert "%20" in content
    assert "%26" in content
    assert first["byte_count"] == len(encoded)
    assert first["content_sha256"] == hashlib.sha256(encoded).hexdigest()

    root = ET.fromstring(content)
    assert root.tag == "DJ_PLAYLISTS"
    assert root.attrib == {"Version": "1.0.0"}
    collection = root.find("COLLECTION")
    assert collection is not None
    tracks_xml = collection.findall("TRACK")
    assert [item.attrib["TrackID"] for item in tracks_xml] == ["1", "2", "3"]
    assert tracks_xml[0].attrib["Name"] == "A & <B>"
    assert tracks_xml[0].attrib["Location"].startswith("file://localhost/")

    playlist = root.find("./PLAYLISTS/NODE/NODE")
    assert playlist is not None
    assert playlist.attrib["Type"] == "1"
    assert playlist.attrib["KeyType"] == "0"
    assert playlist.attrib["Entries"] == "3"
    assert [item.attrib["Key"] for item in playlist.findall("TRACK")] == ["1", "2", "3"]


def test_vendor_interop_fails_closed_when_bundle58_path_verification_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _configure_database(monkeypatch, tmp_path)
    revision, paths = _seed_export_revision(tmp_path)
    paths[1].unlink()

    with pytest.raises(DesktopPlaylistVendorInteropError) as exc_info:
        DesktopPlaylistVendorInteropTransport().preview(
            revision_id=str(revision["revision_id"])
        )
    assert exc_info.value.code == "playlist_export_track_unavailable"


def test_authenticated_vendor_routes_are_strict_and_preview_never_leaks_paths(
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
            path="/v1/playlist/vendor/preview",
            secret="X" * 48,
            body=body,
        )
        assert status == 401
        assert payload == {"error": "unauthorized"}

        status, payload = _request(
            ready,
            method="POST",
            path="/v1/playlist/vendor/preview",
            body=json.dumps(
                {"revision_id": revision["revision_id"], "vendor": "rekordbox"}
            ).encode("utf-8"),
        )
        assert status == 400
        assert payload == {"error": "invalid_playlist_vendor_interop_request"}

        status, preview = _request(
            ready,
            method="POST",
            path="/v1/playlist/vendor/preview",
            body=body,
        )
        assert status == 200
        assert preview["schema"] == "applaylist-desktop-vendor-interop-preview-r1"
        encoded_preview = json.dumps(preview, sort_keys=True)
        for path in paths:
            assert str(path) not in encoded_preview
        assert "content_utf8" not in preview

        status, material = _request(
            ready,
            method="POST",
            path="/v1/playlist/vendor/rekordbox/material",
            body=body,
        )
        assert status == 200
        assert material["vendor"] == "rekordbox"
        assert material["format"] == "rekordbox_xml"
        assert material["content_utf8"].startswith("<?xml")

        status, shutdown = _request(ready, method="POST", path="/v1/shutdown")
        assert status == 202
        assert shutdown == {"status": "shutting_down"}
        _finish(process)
    finally:
        if process.poll() is None:
            process.kill()
            _finish(process)
