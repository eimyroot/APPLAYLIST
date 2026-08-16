from __future__ import annotations

import json
import re
import time
from pathlib import Path

import pytest

from services.desktop.analysis_transport import (
    DesktopAnalysisTransport,
    DesktopAnalysisTransportError,
)
from tests.test_desktop_readiness_sidecar import (
    NONCE,
    SECRET,
    _finish,
    _request,
    _start_sidecar,
)


def _json(payload: dict[str, object]) -> bytes:
    return json.dumps(payload, separators=(",", ":")).encode("utf-8")


def test_transport_rejects_path_shaped_ids_and_unsupported_correction_fields() -> None:
    with pytest.raises(DesktopAnalysisTransportError, match="track identifier"):
        DesktopAnalysisTransport._validated_track_id("/Users/eimy/Music/a.wav")
    with pytest.raises(DesktopAnalysisTransportError, match="track identifier"):
        DesktopAnalysisTransport._validated_track_id(r"C:\\Users\\eimy\\Music\\a.wav")
    with pytest.raises(DesktopAnalysisTransportError, match="job identifier"):
        DesktopAnalysisTransport._validated_job_id("../../aj_deadbeef")
    with pytest.raises(DesktopAnalysisTransportError, match="correction payload"):
        DesktopAnalysisTransport._validated_correction({"path": "/must/not/pass"})


def test_authenticated_analysis_sidecar_lifecycle_and_inspector_are_path_safe(
    tmp_path: Path,
) -> None:
    database = (tmp_path / "analysis-sidecar.db").resolve()
    process, ready = _start_sidecar(env={"DATABASE_URL": f"sqlite:///{database}"})
    try:
        start_body = _json({"track_ids": ["track-missing"]})

        status, payload = _request(
            ready,
            method="POST",
            path="/v1/analysis/start",
            secret="X" * 48,
            body=start_body,
        )
        assert status == 401
        assert payload == {"error": "unauthorized"}

        status, payload = _request(
            ready,
            method="POST",
            path="/v1/analysis/start",
            body=_json({"track_ids": ["/private/secret/a.wav"]}),
        )
        assert status == 400
        assert payload == {"error": "invalid_track_id"}

        status, snapshot = _request(
            ready,
            method="POST",
            path="/v1/analysis/start",
            body=start_body,
        )
        assert status == 202
        assert re.fullmatch(r"aj_[0-9a-f]{32}", snapshot["job_id"])
        assert snapshot["counts"]["selected"] == 1
        assert snapshot["terminal"] in {False, True}

        job_id = snapshot["job_id"]
        deadline = time.monotonic() + 5.0
        terminal = snapshot
        while not terminal["terminal"] and time.monotonic() < deadline:
            time.sleep(0.02)
            status, terminal = _request(
                ready,
                method="POST",
                path="/v1/analysis/status",
                body=_json({"job_id": job_id}),
            )
            assert status == 200

        assert terminal["terminal"] is True
        assert terminal["status"] == "done"
        assert terminal["counts"] == {
            "selected": 1,
            "completed": 1,
            "succeeded": 0,
            "failed": 1,
            "uncertain": 0,
        }

        status, failed = _request(
            ready,
            method="POST",
            path="/v1/analysis/inspector/list",
            body=_json({"filter": "failed"}),
        )
        assert status == 200
        assert failed["filter"] == "failed"
        assert len(failed["items"]) == 1
        item = failed["items"][0]
        assert item["track_id"] == "track-missing"
        assert item["status"] == "failed"
        assert "path" not in item

        status, detail = _request(
            ready,
            method="POST",
            path="/v1/analysis/inspector/get",
            body=_json({"track_id": "track-missing"}),
        )
        assert status == 200
        assert detail == item

        status, correction = _request(
            ready,
            method="POST",
            path="/v1/analysis/correct",
            body=_json(
                {
                    "track_id": "track-missing",
                    "values": {"path": "/private/secret/a.wav"},
                }
            ),
        )
        assert status == 400
        assert correction == {"error": "invalid_analysis_correction"}

        status, invalid_job = _request(
            ready,
            method="POST",
            path="/v1/analysis/status",
            body=_json({"job_id": "/tmp/aj_bad"}),
        )
        assert status == 400
        assert invalid_job == {"error": "invalid_analysis_job"}

        encoded = json.dumps(
            {"snapshot": terminal, "failed": failed, "detail": detail},
            sort_keys=True,
        )
        assert str(tmp_path) not in encoded
        assert SECRET not in encoded
        assert NONCE not in encoded
        assert "/private/secret" not in encoded

        status, shutdown = _request(ready, method="POST", path="/v1/shutdown")
        assert status == 202
        assert shutdown == {"status": "shutting_down"}
        _finish(process)
    finally:
        if process.poll() is None:
            process.kill()
            _finish(process)
