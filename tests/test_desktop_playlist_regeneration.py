from __future__ import annotations

import json
import sqlite3

import pytest

from data.connection import get_sqlite_connection
from data.repositories.analysis_evidence_repository import AnalysisEvidenceRepository
from data.repositories.playlist_revision_repository import PlaylistRevisionRepository
from services.desktop.playlist_editor_transport import DesktopPlaylistEditorTransport
from services.desktop.playlist_regeneration_service import (
    DesktopPlaylistRegenerationService,
    DesktopPlaylistRegenerationServiceError,
)
from tests.test_desktop_playlist_editor_transport import _accept
from tests.test_desktop_readiness_sidecar import _finish, _request
from tests.test_desktop_set_proposal_transport import (
    _configure_database,
    _seed_tracks,
    _start_extended_sidecar,
)


def _locked_root(
    editor: DesktopPlaylistEditorTransport,
    track_ids: tuple[str, ...],
) -> dict[str, object]:
    root = _accept(editor, track_ids)
    first = root["sequence"][0]["track_id"]
    return editor.lock(
        revision_id=root["revision_id"],
        locked_track_ids=[first],
    )


def test_regeneration_preview_is_deterministic_locked_and_path_safe(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _configure_database(monkeypatch, tmp_path)
    track_ids = _seed_tracks(count=6)
    parent = _locked_root(DesktopPlaylistEditorTransport(), track_ids)
    service = DesktopPlaylistRegenerationService()

    first = service.preview(
        revision_id=parent["revision_id"],
        candidate_track_ids=track_ids,
    )
    second = service.preview(
        revision_id=parent["revision_id"],
        candidate_track_ids=tuple(reversed(track_ids)),
    )

    assert first == second
    assert first["schema"] == "applaylist-desktop-playlist-regeneration-r1"
    assert first["parent_revision_id"] == parent["revision_id"]
    assert first["candidate_pool_count"] == 6
    assert first["locked_positions"] == [
        {"order_index": 0, "track_id": parent["sequence"][0]["track_id"]}
    ]
    assert first["deterministic_ordering"] is True
    assert first["playlist_mutation_authorized"] is False
    assert first["personal_dj_model_training_authorized"] is False
    assert first["production_activation_authorized"] is False
    assert first["alternatives"]
    for alternative in first["alternatives"]:
        assert len(alternative["sequence"]) == len(parent["sequence"])
        assert alternative["sequence"][0]["track_id"] == parent["sequence"][0]["track_id"]
        assert alternative["sequence"][0]["locked"] is True
        assert all(item["locked"] is False for item in alternative["sequence"][1:])

    encoded = json.dumps(first, sort_keys=True)
    assert "/definitely/not-present" not in encoded
    assert "fixture-provider" not in encoded
    assert "payload_json" not in encoded
    assert "content_utf8" not in encoded


def test_regeneration_requires_anchor_and_every_locked_track_in_scope(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _configure_database(monkeypatch, tmp_path)
    track_ids = _seed_tracks(count=6)
    editor = DesktopPlaylistEditorTransport()
    root = _accept(editor, track_ids)
    service = DesktopPlaylistRegenerationService()

    with pytest.raises(DesktopPlaylistRegenerationServiceError) as anchor:
        service.preview(
            revision_id=root["revision_id"],
            candidate_track_ids=track_ids,
        )
    assert anchor.value.code == "playlist_regeneration_anchor_required"

    parent = editor.lock(
        revision_id=root["revision_id"],
        locked_track_ids=[root["sequence"][0]["track_id"]],
    )
    without_anchor = tuple(
        track_id for track_id in track_ids if track_id != parent["sequence"][0]["track_id"]
    )
    with pytest.raises(DesktopPlaylistRegenerationServiceError) as missing:
        service.preview(
            revision_id=parent["revision_id"],
            candidate_track_ids=without_anchor,
        )
    assert missing.value.code == "playlist_regeneration_locked_track_missing"


def test_regeneration_apply_replays_preview_and_appends_one_child_revision(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _configure_database(monkeypatch, tmp_path)
    track_ids = _seed_tracks(count=7)
    parent = _locked_root(DesktopPlaylistEditorTransport(), track_ids)
    service = DesktopPlaylistRegenerationService()
    preview = service.preview(
        revision_id=parent["revision_id"],
        candidate_track_ids=track_ids,
    )
    parent_ids = [item["track_id"] for item in parent["sequence"]]
    alternative = next(
        item
        for item in preview["alternatives"]
        if [step["track_id"] for step in item["sequence"]] != parent_ids
    )

    before = PlaylistRevisionRepository().count_revisions(parent["playlist_id"])
    child = service.apply(
        revision_id=parent["revision_id"],
        candidate_track_ids=track_ids,
        regeneration_id=preview["regeneration_id"],
        path_id=alternative["path_id"],
    )
    after = PlaylistRevisionRepository().count_revisions(parent["playlist_id"])

    assert after == before + 1
    assert child["operation"] == "regenerate"
    assert child["parent_revision_id"] == parent["revision_id"]
    assert child["revision_index"] == parent["revision_index"] + 1
    assert child["sequence"] == alternative["sequence"]
    assert child["sequence"][0]["locked"] is True
    assert child["sequence"][0]["track_id"] == parent["sequence"][0]["track_id"]
    assert child["personal_dj_model_training_authorized"] is False
    assert child["production_activation_authorized"] is False

    with pytest.raises(DesktopPlaylistRegenerationServiceError) as stale_parent:
        service.preview(
            revision_id=parent["revision_id"],
            candidate_track_ids=track_ids,
        )
    assert stale_parent.value.code == "playlist_revision_stale"


def test_regeneration_apply_fails_closed_when_evidence_changes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _configure_database(monkeypatch, tmp_path)
    track_ids = _seed_tracks(count=6)
    parent = _locked_root(DesktopPlaylistEditorTransport(), track_ids)
    service = DesktopPlaylistRegenerationService()
    preview = service.preview(
        revision_id=parent["revision_id"],
        candidate_track_ids=track_ids,
    )
    evidence = AnalysisEvidenceRepository()
    changed_track = track_ids[-1]
    base = evidence.latest_success_for_track(changed_track)
    assert base is not None
    evidence.append_correction(
        track_id=changed_track,
        base_evidence_id=base.evidence_id,
        values={"energy": 0.19},
        reason="invalidate regeneration replay identity",
    )

    with pytest.raises(DesktopPlaylistRegenerationServiceError) as stale:
        service.apply(
            revision_id=parent["revision_id"],
            candidate_track_ids=track_ids,
            regeneration_id=preview["regeneration_id"],
            path_id=preview["alternatives"][0]["path_id"],
        )
    assert stale.value.code == "playlist_regeneration_stale"
    assert PlaylistRevisionRepository().current_revision(parent["playlist_id"])["revision_id"] == parent["revision_id"]


def test_legacy_revision_schema_migrates_without_losing_immutability(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _configure_database(monkeypatch, tmp_path)
    with get_sqlite_connection() as conn:
        conn.executescript(
            """
            PRAGMA foreign_keys = ON;
            CREATE TABLE playlist_revisions (
                revision_id TEXT PRIMARY KEY,
                playlist_id TEXT NOT NULL,
                parent_revision_id TEXT,
                revision_index INTEGER NOT NULL CHECK (revision_index >= 0),
                source_proposal_id TEXT NOT NULL,
                source_path_id TEXT NOT NULL,
                operation TEXT NOT NULL CHECK (operation IN ('accept','reorder','lock','replace')),
                operation_json TEXT NOT NULL,
                content_fingerprint TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                personal_dj_model_training_authorized INTEGER NOT NULL DEFAULT 0 CHECK (personal_dj_model_training_authorized = 0),
                production_activation_authorized INTEGER NOT NULL DEFAULT 0 CHECK (production_activation_authorized = 0),
                UNIQUE (playlist_id, revision_index),
                FOREIGN KEY(parent_revision_id) REFERENCES playlist_revisions(revision_id)
            );
            CREATE TABLE playlist_revision_items (
                revision_id TEXT NOT NULL,
                order_index INTEGER NOT NULL CHECK (order_index >= 0),
                track_id TEXT NOT NULL,
                display_name TEXT NOT NULL,
                locked INTEGER NOT NULL DEFAULT 0 CHECK (locked IN (0,1)),
                PRIMARY KEY (revision_id, order_index),
                UNIQUE (revision_id, track_id),
                FOREIGN KEY(revision_id) REFERENCES playlist_revisions(revision_id)
            );
            CREATE TRIGGER playlist_revisions_no_update BEFORE UPDATE ON playlist_revisions BEGIN SELECT RAISE(ABORT, 'playlist revisions are immutable'); END;
            CREATE TRIGGER playlist_revisions_no_delete BEFORE DELETE ON playlist_revisions BEGIN SELECT RAISE(ABORT, 'playlist revisions are immutable'); END;
            CREATE TRIGGER playlist_revision_items_no_update BEFORE UPDATE ON playlist_revision_items BEGIN SELECT RAISE(ABORT, 'playlist revision items are immutable'); END;
            CREATE TRIGGER playlist_revision_items_no_delete BEFORE DELETE ON playlist_revision_items BEGIN SELECT RAISE(ABORT, 'playlist revision items are immutable'); END;
            INSERT INTO playlist_revisions (
                revision_id, playlist_id, parent_revision_id, revision_index,
                source_proposal_id, source_path_id, operation, operation_json,
                content_fingerprint, personal_dj_model_training_authorized,
                production_activation_authorized
            ) VALUES (
                'prv_legacy', 'plr_legacy', NULL, 0,
                'proposal_legacy', 'path_legacy', 'accept', '{}',
                '0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef', 0, 0
            );
            INSERT INTO playlist_revision_items VALUES ('prv_legacy',0,'track:a','A',1);
            INSERT INTO playlist_revision_items VALUES ('prv_legacy',1,'track:b','B',0);
            INSERT INTO playlist_revision_items VALUES ('prv_legacy',2,'track:c','C',0);
            """
        )
        conn.commit()

    repository = PlaylistRevisionRepository()
    repository.ensure_schema()
    legacy = repository.get_revision("prv_legacy")
    assert legacy is not None
    assert legacy["operation"] == "accept"

    child = repository.append_child(
        parent_revision_id="prv_legacy",
        operation="regenerate",
        items=(("track:a", "A", True), ("track:d", "D", False), ("track:c", "C", False)),
        operation_metadata={"regeneration_id": "regen_test", "path_id": "path_test"},
    )
    assert child["operation"] == "regenerate"

    with get_sqlite_connection() as conn:
        with pytest.raises(sqlite3.DatabaseError, match="playlist revisions are immutable"):
            conn.execute(
                "UPDATE playlist_revisions SET operation='lock' WHERE revision_id=?",
                (child["revision_id"],),
            )


def test_authenticated_regeneration_sidecar_routes_are_strict(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    database = _configure_database(monkeypatch, tmp_path)
    track_ids = _seed_tracks(count=6)
    parent = _locked_root(DesktopPlaylistEditorTransport(), track_ids)
    process, ready = _start_extended_sidecar(database)
    body = {
        "revision_id": parent["revision_id"],
        "candidate_track_ids": list(track_ids),
    }
    try:
        status, payload = _request(
            ready,
            method="POST",
            path="/v1/playlist/editor/regeneration/preview",
            secret="X" * 48,
            body=json.dumps(body).encode("utf-8"),
        )
        assert status == 401
        assert payload == {"error": "unauthorized"}

        status, payload = _request(
            ready,
            method="POST",
            path="/v1/playlist/editor/regeneration/preview",
            body=json.dumps({**body, "path": "/must/not-pass"}).encode("utf-8"),
        )
        assert status == 400
        assert payload == {"error": "invalid_playlist_editor_request"}

        status, preview = _request(
            ready,
            method="POST",
            path="/v1/playlist/editor/regeneration/preview",
            body=json.dumps(body).encode("utf-8"),
        )
        assert status == 200
        assert preview["schema"] == "applaylist-desktop-playlist-regeneration-r1"
        assert preview["parent_revision_id"] == parent["revision_id"]
        assert preview["playlist_mutation_authorized"] is False

        status, shutdown = _request(ready, method="POST", path="/v1/shutdown")
        assert status == 202
        assert shutdown == {"status": "shutting_down"}
        _finish(process)
    finally:
        if process.poll() is None:
            process.kill()
            _finish(process)
