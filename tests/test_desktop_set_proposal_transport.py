from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from core.config.settings import get_settings
from data.models.track_record import TrackRecord
from data.repositories.analysis_evidence_repository import AnalysisEvidenceRepository
from data.repositories.track_repository import TrackRepository
from services.desktop.set_proposal_transport import (
    DesktopSetProposalTransport,
    DesktopSetProposalTransportError,
)
from tests.test_desktop_readiness_sidecar import NONCE, SECRET, _finish, _request

ROOT = Path(__file__).resolve().parents[1]


def _track_id(character: str) -> str:
    return f"aptrack:v1:sha256:{character * 64}"


def _configure_database(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    database = (tmp_path / "set-proposal.db").resolve()
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database}")
    get_settings.cache_clear()
    return database


def _seed_tracks(
    *,
    count: int = 4,
    missing_energy_index: int | None = None,
) -> tuple[str, ...]:
    tracks = TrackRepository()
    evidence = AnalysisEvidenceRepository()
    ids: list[str] = []
    for index in range(count):
        character = chr(ord("a") + index)
        track_id = _track_id(character)
        ids.append(track_id)
        tracks.upsert(
            TrackRecord(
                track_id=track_id,
                path=f"/definitely/not-present/audio-{index}.wav",
                title=f"Track {index + 1}",
                artist="Fixture Artist",
                duration_seconds=300.0 + index,
            )
        )
        evidence.append_evidence(
            track_id=track_id,
            provider="fixture-provider",
            analysis_version="canonical-mir-v1",
            provider_version="fixture-1",
            algorithm_version="fixture-algorithm-1",
            bpm=128.0 + index * 0.5,
            bpm_confidence=0.95,
            key_tonic="A",
            key_scale="minor",
            camelot="8A",
            key_confidence=0.9,
            energy=None if missing_energy_index == index else 0.50 + index * 0.04,
            loudness_db=-8.0 + index * 0.2,
            duration_seconds=300.0 + index,
            beat_stability=0.92,
            harmonic_ratio=0.48,
            percussive_ratio=0.76,
        )
    return tuple(ids)


def test_set_proposal_is_deterministic_evidence_only_and_path_safe(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _configure_database(monkeypatch, tmp_path)
    track_ids = _seed_tracks()
    transport = DesktopSetProposalTransport()

    first = transport.generate(
        track_ids=track_ids,
        seed_track_id=track_ids[0],
        target_track_count=3,
    )
    second = transport.generate(
        track_ids=tuple(reversed(track_ids)),
        seed_track_id=track_ids[0],
        target_track_count=3,
    )

    assert first == second
    assert first["schema"] == "applaylist-desktop-set-proposal-r1"
    assert first["status"] == "target_reached"
    assert first["activation_authorized"] is False
    assert first["personal_dj_model_training_authorized"] is False
    assert first["deterministic_ordering"] is True
    assert first["alternatives"]

    sequence = first["alternatives"][0]["sequence"]
    assert sequence[0]["track_id"] == track_ids[0]
    assert len(sequence) == 3

    encoded = json.dumps(first, sort_keys=True)
    assert "/definitely/not-present" not in encoded
    assert "fixture-provider" not in encoded
    assert "fixture-algorithm" not in encoded
    assert "evidence_id" not in encoded
    assert "input_fingerprint" not in encoded
    assert "future_feasibility_not_hard_prune_v1" in encoded


def test_active_correction_changes_revision_without_overwriting_provider_evidence(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _configure_database(monkeypatch, tmp_path)
    track_ids = _seed_tracks()
    transport = DesktopSetProposalTransport()
    evidence = AnalysisEvidenceRepository()

    before = transport.generate(
        track_ids=track_ids,
        seed_track_id=track_ids[0],
        target_track_count=3,
    )
    base = evidence.latest_success_for_track(track_ids[1])
    assert base is not None
    original_bpm = base.bpm

    correction = evidence.append_correction(
        track_id=track_ids[1],
        base_evidence_id=base.evidence_id,
        values={"bpm": 129.25, "energy": 0.61},
        reason="desktop proposal correction fixture",
    )
    assert correction.base_evidence_id == base.evidence_id

    after = transport.generate(
        track_ids=track_ids,
        seed_track_id=track_ids[0],
        target_track_count=3,
    )

    assert after["proposal_id"] != before["proposal_id"]
    persisted_base = evidence.get_evidence(base.evidence_id)
    assert persisted_base is not None
    assert persisted_base.bpm == original_bpm


def test_latest_failed_or_incomplete_analysis_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _configure_database(monkeypatch, tmp_path)
    track_ids = _seed_tracks()
    evidence = AnalysisEvidenceRepository()
    evidence.append_evidence(
        track_id=track_ids[2],
        provider="fixture-provider",
        analysis_version="canonical-mir-v1",
        status="failed",
        error_code="fixture_failure",
        error_detail="bounded fixture failure",
    )

    with pytest.raises(DesktopSetProposalTransportError) as failed:
        DesktopSetProposalTransport().generate(
            track_ids=track_ids,
            seed_track_id=track_ids[0],
            target_track_count=3,
        )
    assert failed.value.code == "set_proposal_analysis_failed"

    get_settings.cache_clear()
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'incomplete.db').resolve()}")
    get_settings.cache_clear()
    incomplete_ids = _seed_tracks(missing_energy_index=1)
    with pytest.raises(DesktopSetProposalTransportError) as incomplete:
        DesktopSetProposalTransport().generate(
            track_ids=incomplete_ids,
            seed_track_id=incomplete_ids[0],
            target_track_count=3,
        )
    assert incomplete.value.code == "set_proposal_analysis_incomplete"


def test_set_proposal_input_bounds_reject_paths_duplicates_and_invalid_target() -> None:
    validate = DesktopSetProposalTransport._validated_track_ids
    with pytest.raises(DesktopSetProposalTransportError):
        validate(["track:a", "track:b", "/Users/example/a.wav"])
    with pytest.raises(DesktopSetProposalTransportError):
        validate(["track:a", "track:a", "track:c"])
    with pytest.raises(DesktopSetProposalTransportError):
        DesktopSetProposalTransport._validated_target_track_count(9, 12)


def _start_extended_sidecar(database: Path) -> tuple[subprocess.Popen[str], dict]:
    process = subprocess.Popen(
        [sys.executable, "-m", "scripts.applaylist_sidecar_entry"],
        cwd=ROOT,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        bufsize=1,
        env={
            **os.environ,
            "DATABASE_URL": f"sqlite:///{database}",
            "PYTHONUNBUFFERED": "1",
        },
    )
    assert process.stdin is not None
    assert process.stdout is not None
    process.stdin.write(
        json.dumps(
            {
                "protocol": "applaylist-sidecar-v1",
                "secret": SECRET,
                "nonce": NONCE,
            },
            separators=(",", ":"),
        )
        + "\n"
    )
    process.stdin.flush()
    ready_line = process.stdout.readline()
    if not ready_line:
        stderr = process.stderr.read() if process.stderr is not None else ""
        raise AssertionError(f"extended sidecar did not become ready: {stderr}")
    return process, json.loads(ready_line)


def test_authenticated_sidecar_set_proposal_endpoint_is_strict_and_path_safe(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    database = _configure_database(monkeypatch, tmp_path)
    track_ids = _seed_tracks()
    process, ready = _start_extended_sidecar(database)
    body = json.dumps(
        {
            "track_ids": list(track_ids),
            "seed_track_id": track_ids[0],
            "target_track_count": 3,
        },
        separators=(",", ":"),
    ).encode("utf-8")
    try:
        status, payload = _request(
            ready,
            method="POST",
            path="/v1/set/proposal/generate",
            secret="X" * 48,
            body=body,
        )
        assert status == 401
        assert payload == {"error": "unauthorized"}

        status, payload = _request(
            ready,
            method="POST",
            path="/v1/set/proposal/generate",
            body=json.dumps(
                {
                    "track_ids": list(track_ids),
                    "seed_track_id": track_ids[0],
                    "target_track_count": 3,
                    "path": "/must/not/pass",
                }
            ).encode("utf-8"),
        )
        assert status == 400
        assert payload == {"error": "invalid_set_proposal_request"}

        status, proposal = _request(
            ready,
            method="POST",
            path="/v1/set/proposal/generate",
            body=body,
        )
        assert status == 200
        assert proposal["schema"] == "applaylist-desktop-set-proposal-r1"
        assert proposal["activation_authorized"] is False

        encoded = json.dumps(proposal, sort_keys=True)
        assert "/definitely/not-present" not in encoded
        assert SECRET not in encoded
        assert NONCE not in encoded
        assert "fixture-provider" not in encoded
        assert "evidence_id" not in encoded

        status, shutdown = _request(ready, method="POST", path="/v1/shutdown")
        assert status == 202
        assert shutdown == {"status": "shutting_down"}
        _finish(process)
    finally:
        if process.poll() is None:
            process.kill()
            _finish(process)
