from __future__ import annotations

import json
import sqlite3

import pytest

from data.connection import get_sqlite_connection
from data.repositories.analysis_evidence_repository import AnalysisEvidenceRepository
from data.repositories.playlist_revision_repository import PlaylistRevisionRepository
from services.desktop.playlist_editor_transport import (
    DesktopPlaylistEditorTransport,
    DesktopPlaylistEditorTransportError,
)
from services.desktop.set_proposal_transport import DesktopSetProposalTransport
from tests.test_desktop_set_proposal_transport import (
    _configure_database,
    _seed_tracks,
    _start_extended_sidecar,
)
from tests.test_desktop_readiness_sidecar import _finish, _request


def _proposal(track_ids: tuple[str, ...], *, target: int = 3) -> dict[str, object]:
    return DesktopSetProposalTransport().generate(
        track_ids=track_ids,
        seed_track_id=track_ids[0],
        target_track_count=target,
    )


def _accept(editor: DesktopPlaylistEditorTransport, track_ids: tuple[str, ...]) -> dict[str, object]:
    proposal = _proposal(track_ids)
    alternative = proposal["alternatives"][0]
    return editor.accept(
        track_ids=track_ids,
        seed_track_id=track_ids[0],
        target_track_count=3,
        proposal_id=proposal["proposal_id"],
        path_id=alternative["path_id"],
    )


def test_accept_is_replay_verified_deterministic_idempotent_and_path_safe(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _configure_database(monkeypatch, tmp_path)
    track_ids = _seed_tracks(count=5)
    editor = DesktopPlaylistEditorTransport()
    first = _accept(editor, track_ids)
    second = _accept(editor, track_ids)

    assert first == second
    assert first["revision_index"] == 0
    assert first["operation"] == "accept"
    assert first["parent_revision_id"] is None
    assert first["personal_dj_model_training_authorized"] is False
    assert first["production_activation_authorized"] is False
    assert PlaylistRevisionRepository().count_revisions(first["playlist_id"]) == 1

    encoded = json.dumps(first, sort_keys=True)
    assert "/definitely/not-present" not in encoded
    assert "fixture-provider" not in encoded
    assert "evidence_id" not in encoded

    stale_proposal = _proposal(track_ids)
    evidence = AnalysisEvidenceRepository()
    base = evidence.latest_success_for_track(track_ids[1])
    assert base is not None
    evidence.append_correction(
        track_id=track_ids[1],
        base_evidence_id=base.evidence_id,
        values={"bpm": 131.25},
        reason="invalidate displayed proposal identity",
    )
    with pytest.raises(DesktopPlaylistEditorTransportError) as stale:
        editor.accept(
            track_ids=track_ids,
            seed_track_id=track_ids[0],
            target_track_count=3,
            proposal_id=stale_proposal["proposal_id"],
            path_id=stale_proposal["alternatives"][0]["path_id"],
        )
    assert stale.value.code == "playlist_proposal_stale"


def test_reorder_lock_replace_and_stale_parent_are_append_only(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _configure_database(monkeypatch, tmp_path)
    track_ids = _seed_tracks(count=6)
    editor = DesktopPlaylistEditorTransport()
    root = _accept(editor, track_ids)
    root_ids = [item["track_id"] for item in root["sequence"]]

    reordered_ids = [root_ids[1], root_ids[0], *root_ids[2:]]
    reordered = editor.reorder(
        revision_id=root["revision_id"],
        ordered_track_ids=reordered_ids,
    )
    assert reordered["parent_revision_id"] == root["revision_id"]
    assert reordered["revision_index"] == 1
    assert [item["track_id"] for item in reordered["sequence"]] == reordered_ids

    locked_id = reordered_ids[0]
    locked = editor.lock(
        revision_id=reordered["revision_id"],
        locked_track_ids=[locked_id],
    )
    assert locked["revision_index"] == 2
    assert [item["track_id"] for item in locked["sequence"] if item["locked"]] == [locked_id]

    moving_locked = [reordered_ids[1], reordered_ids[0], *reordered_ids[2:]]
    with pytest.raises(DesktopPlaylistEditorTransportError) as blocked:
        editor.reorder(
            revision_id=locked["revision_id"],
            ordered_track_ids=moving_locked,
        )
    assert blocked.value.code == "playlist_revision_locked_track"

    with pytest.raises(DesktopPlaylistEditorTransportError) as stale:
        editor.lock(
            revision_id=reordered["revision_id"],
            locked_track_ids=[],
        )
    assert stale.value.code == "playlist_revision_stale"

    current_ids = {item["track_id"] for item in locked["sequence"]}
    replacement = next(track_id for track_id in track_ids if track_id not in current_ids)
    source = next(item["track_id"] for item in locked["sequence"] if not item["locked"])
    replaced = editor.replace(
        revision_id=locked["revision_id"],
        source_track_id=source,
        replacement_track_id=replacement,
    )
    assert replaced["revision_index"] == 3
    replaced_ids = [item["track_id"] for item in replaced["sequence"]]
    assert source not in replaced_ids
    assert replacement in replaced_ids
    assert len(set(replaced_ids)) == len(replaced_ids)

    history = editor.history(playlist_id=root["playlist_id"])
    assert history["current_revision_id"] == replaced["revision_id"]
    assert [item["operation"] for item in history["revisions"]] == [
        "accept",
        "reorder",
        "lock",
        "replace",
    ]
    assert history["personal_dj_model_training_authorized"] is False
    assert history["production_activation_authorized"] is False


def test_revision_rows_are_immutable_at_sqlite_boundary(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _configure_database(monkeypatch, tmp_path)
    track_ids = _seed_tracks(count=4)
    root = _accept(DesktopPlaylistEditorTransport(), track_ids)

    with get_sqlite_connection() as conn:
        with pytest.raises(sqlite3.DatabaseError, match="playlist revisions are immutable"):
            conn.execute(
                "UPDATE playlist_revisions SET operation = 'lock' WHERE revision_id = ?",
                (root["revision_id"],),
            )
        conn.rollback()
        with pytest.raises(sqlite3.DatabaseError, match="playlist revisions are immutable"):
            conn.execute(
                "DELETE FROM playlist_revision_items WHERE revision_id = ?",
                (root["revision_id"],),
            )


def test_replace_requires_current_complete_success_without_audio_access(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _configure_database(monkeypatch, tmp_path)
    track_ids = _seed_tracks(count=6)
    editor = DesktopPlaylistEditorTransport()
    root = _accept(editor, track_ids)
    members = {item["track_id"] for item in root["sequence"]}
    replacement = next(track_id for track_id in track_ids if track_id not in members)
    source = root["sequence"][0]["track_id"]

    evidence = AnalysisEvidenceRepository()
    evidence.append_evidence(
        track_id=replacement,
        provider="fixture-provider",
        analysis_version="canonical-mir-v1",
        status="failed",
        error_code="fixture_failure",
    )
    with pytest.raises(DesktopPlaylistEditorTransportError) as failed:
        editor.replace(
            revision_id=root["revision_id"],
            source_track_id=source,
            replacement_track_id=replacement,
        )
    assert failed.value.code == "playlist_replacement_analysis_failed"


def test_authenticated_playlist_editor_sidecar_routes_are_strict(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    database = _configure_database(monkeypatch, tmp_path)
    track_ids = _seed_tracks(count=5)
    process, ready = _start_extended_sidecar(database)
    proposal_request = {
        "track_ids": list(track_ids),
        "seed_track_id": track_ids[0],
        "target_track_count": 3,
    }
    try:
        status, proposal = _request(
            ready,
            method="POST",
            path="/v1/set/proposal/generate",
            body=json.dumps(proposal_request).encode("utf-8"),
        )
        assert status == 200
        accept_body = {
            **proposal_request,
            "proposal_id": proposal["proposal_id"],
            "path_id": proposal["alternatives"][0]["path_id"],
        }

        status, payload = _request(
            ready,
            method="POST",
            path="/v1/playlist/editor/accept",
            secret="X" * 48,
            body=json.dumps(accept_body).encode("utf-8"),
        )
        assert status == 401
        assert payload == {"error": "unauthorized"}

        status, payload = _request(
            ready,
            method="POST",
            path="/v1/playlist/editor/accept",
            body=json.dumps({**accept_body, "path": "/must/not/pass"}).encode("utf-8"),
        )
        assert status == 400
        assert payload == {"error": "invalid_playlist_editor_request"}

        status, revision = _request(
            ready,
            method="POST",
            path="/v1/playlist/editor/accept",
            body=json.dumps(accept_body).encode("utf-8"),
        )
        assert status == 200
        assert revision["schema"] == "applaylist-desktop-playlist-revision-r1"

        status, history = _request(
            ready,
            method="POST",
            path="/v1/playlist/editor/history",
            body=json.dumps({"playlist_id": revision["playlist_id"]}).encode("utf-8"),
        )
        assert status == 200
        assert history["current_revision_id"] == revision["revision_id"]
        assert history["production_activation_authorized"] is False

        status, shutdown = _request(ready, method="POST", path="/v1/shutdown")
        assert status == 202
        assert shutdown == {"status": "shutting_down"}
        _finish(process)
    finally:
        if process.poll() is None:
            process.kill()
            _finish(process)
