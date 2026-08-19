from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from data.connection import get_sqlite_connection
from data.repositories.analysis_evidence_repository import AnalysisEvidenceRepository
from data.repositories.music_intelligence_repository import MusicIntelligenceRepository
from data.repositories.playlist_revision_repository import PlaylistRevisionRepository
from services.desktop.playlist_evidence_export_transport import (
    DesktopPlaylistEvidenceExportError,
    DesktopPlaylistEvidenceExportTransport,
)
from tests.test_desktop_playlist_export_transport import _seed_export_revision
from tests.test_desktop_readiness_sidecar import _finish, _request
from tests.test_desktop_set_proposal_transport import (
    _configure_database,
    _start_extended_sidecar,
)


def _seed_analysis_and_transition(revision: dict[str, object]) -> None:
    analysis = AnalysisEvidenceRepository()
    items = revision["items"]
    assert isinstance(items, tuple)
    first_evidence_id = None
    for index, item in enumerate(items):
        track_id = str(item["track_id"])
        evidence = analysis.append_evidence(
            track_id=track_id,
            provider="fixture-provider",
            analysis_version="fixture-v1",
            provider_version="1.0",
            algorithm_version="algo-1",
            bpm=128.0 + index,
            bpm_confidence=0.9,
            key_tonic="C",
            key_scale="minor",
            camelot="5A",
            key_confidence=0.8,
            energy=0.5 + index * 0.1,
            duration_seconds=300.0 + index,
            warnings=("fixture_warning",),
        )
        if index == 0:
            first_evidence_id = evidence.evidence_id
            analysis.append_correction(
                track_id=track_id,
                base_evidence_id=evidence.evidence_id,
                values={"bpm": 129.0},
                reason="fixture correction",
            )
    assert first_evidence_id is not None

    source = str(items[0]["track_id"])
    target = str(items[1]["track_id"])
    MusicIntelligenceRepository().ensure_schema()
    payload = json.dumps(
        {"fixture": "bundle59", "source": source, "target": target},
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    with get_sqlite_connection() as conn:
        conn.execute(
            '''
            INSERT INTO transition_assessment_snapshots (
                snapshot_id, transition_id, source_track_id, source_segment_id,
                target_track_id, target_segment_id, assessment_version, policy_version,
                context_id, context_version, payload_json, payload_sha256
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                "tas_fixture_bundle59",
                "tr_fixture_bundle59",
                source,
                f"seg:{source}",
                target,
                f"seg:{target}",
                "transition-assessment-r1",
                "transition-policy-r1",
                "ctx_fixture",
                "ctx-v1",
                payload,
                digest,
            ),
        )
        conn.commit()


def test_json_evidence_material_is_deterministic_path_safe_and_revision_immutable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _configure_database(monkeypatch, tmp_path)
    revision, paths = _seed_export_revision(tmp_path)
    _seed_analysis_and_transition(revision)
    transport = DesktopPlaylistEvidenceExportTransport()
    ledger = PlaylistRevisionRepository()
    before = ledger.count_revisions(str(revision["playlist_id"]))

    preview = transport.preview(revision_id=str(revision["revision_id"]))
    first = transport.material(revision_id=str(revision["revision_id"]))
    second = transport.material(revision_id=str(revision["revision_id"]))

    assert first == second
    assert preview["schema"] == "applaylist-desktop-playlist-evidence-preview-r1"
    assert preview["m3u8_path_valid"] is True
    assert preview["track_count"] == 3
    assert preview["analysis_evidence_count"] == 3
    assert preview["transition_pair_count"] == 2
    assert preview["transition_evidence_pair_count"] == 1
    assert preview["personal_dj_model_training_authorized"] is False
    assert preview["production_activation_authorized"] is False

    content = str(first["content_utf8"])
    assert first["byte_count"] == len(content.encode("utf-8"))
    assert first["content_sha256"] == hashlib.sha256(content.encode("utf-8")).hexdigest()
    document = json.loads(content)
    assert document["schema"] == "applaylist-playlist-revision-evidence-r1"
    assert document["revision"]["revision_id"] == revision["revision_id"]
    assert document["lineage"][-1]["revision_id"] == revision["revision_id"]
    assert document["tracks"][0]["analysis"]["status"] == "present"
    assert document["tracks"][0]["analysis"]["active_correction"]["payload"] == {"bpm": 129.0}
    assert document["adjacent_transitions"][0]["status"] == "present"
    assert document["adjacent_transitions"][0]["snapshots"][0]["snapshot_id"] == "tas_fixture_bundle59"
    assert document["adjacent_transitions"][1]["status"] == "missing"
    assert document["m3u8_verification"]["path_valid"] is True
    assert document["m3u8_verification"]["content_sha256"] == first["m3u8_content_sha256"]
    assert document["personal_dj_model_training_authorized"] is False
    assert document["production_activation_authorized"] is False

    for path in paths:
        assert str(path) not in content
    assert "content_utf8" not in document
    assert ledger.count_revisions(str(revision["playlist_id"])) == before


def test_json_evidence_export_fails_closed_when_m3u8_path_verification_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _configure_database(monkeypatch, tmp_path)
    revision, paths = _seed_export_revision(tmp_path)
    paths[1].unlink()

    with pytest.raises(DesktopPlaylistEvidenceExportError) as exc_info:
        DesktopPlaylistEvidenceExportTransport().material(
            revision_id=str(revision["revision_id"])
        )
    assert exc_info.value.code == "playlist_export_track_unavailable"


def test_json_evidence_export_keeps_missing_analysis_and_transition_explicit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _configure_database(monkeypatch, tmp_path)
    revision, _ = _seed_export_revision(tmp_path)
    material = DesktopPlaylistEvidenceExportTransport().material(
        revision_id=str(revision["revision_id"])
    )
    document = json.loads(str(material["content_utf8"]))
    assert [item["analysis"]["status"] for item in document["tracks"]] == [
        "missing",
        "missing",
        "missing",
    ]
    assert [item["status"] for item in document["adjacent_transitions"]] == [
        "missing",
        "missing",
    ]


def test_authenticated_json_evidence_routes_are_strict_and_path_safe(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    database = _configure_database(monkeypatch, tmp_path)
    revision, paths = _seed_export_revision(tmp_path)
    _seed_analysis_and_transition(revision)
    process, ready = _start_extended_sidecar(database)
    body = json.dumps({"revision_id": revision["revision_id"]}).encode("utf-8")
    try:
        status, payload = _request(
            ready,
            method="POST",
            path="/v1/playlist/evidence/preview",
            secret="X" * 48,
            body=body,
        )
        assert status == 401
        assert payload == {"error": "unauthorized"}

        status, payload = _request(
            ready,
            method="POST",
            path="/v1/playlist/evidence/preview",
            body=json.dumps(
                {"revision_id": revision["revision_id"], "path": "/must/not/pass"}
            ).encode("utf-8"),
        )
        assert status == 400
        assert payload == {"error": "invalid_playlist_evidence_export_request"}

        status, preview = _request(
            ready,
            method="POST",
            path="/v1/playlist/evidence/preview",
            body=body,
        )
        assert status == 200
        encoded_preview = json.dumps(preview, sort_keys=True)
        for path in paths:
            assert str(path) not in encoded_preview
        assert preview["m3u8_path_valid"] is True

        status, material = _request(
            ready,
            method="POST",
            path="/v1/playlist/evidence/material",
            body=body,
        )
        assert status == 200
        assert material["schema"] == "applaylist-desktop-playlist-evidence-material-r1"
        document = json.loads(material["content_utf8"])
        for path in paths:
            assert str(path) not in material["content_utf8"]
        assert document["revision"]["revision_id"] == revision["revision_id"]
        assert document["m3u8_verification"]["path_valid"] is True

        status, shutdown = _request(ready, method="POST", path="/v1/shutdown")
        assert status == 202
        assert shutdown == {"status": "shutting_down"}
        _finish(process)
    finally:
        if process.poll() is None:
            process.kill()
            _finish(process)
