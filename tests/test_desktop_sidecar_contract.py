from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.security.sidecar_session import SidecarSessionAuthMiddleware
from core.desktop.capabilities import LibraryRootCapability
from core.desktop.protocol import (
    DESKTOP_PROTOCOL_VERSION,
    PROCESS_NONCE_HEADER,
    SESSION_HEADER,
    SidecarReadinessEnvelope,
    SidecarSession,
)
from services.desktop.sidecar_supervisor import (
    SidecarState,
    SidecarSupervisor,
    SidecarSupervisorError,
    SupervisorPolicy,
)


class FakeProcess:
    def __init__(self) -> None:
        self._returncode: int | None = None
        self.terminate_calls = 0
        self.kill_calls = 0
        self.wait_calls: list[float | None] = []
        self.pid = 4242

    def poll(self) -> int | None:
        return self._returncode

    def terminate(self) -> None:
        self.terminate_calls += 1
        self._returncode = 0

    def kill(self) -> None:
        self.kill_calls += 1
        self._returncode = -9

    def wait(self, timeout: float | None = None) -> int:
        self.wait_calls.append(timeout)
        if self._returncode is None:
            raise TimeoutError("still running")
        return self._returncode


def test_readiness_envelope_requires_loopback_and_matching_nonce() -> None:
    session = SidecarSession.generate()
    envelope = SidecarReadinessEnvelope(
        protocol_version=DESKTOP_PROTOCOL_VERSION,
        process_nonce=session.process_nonce,
        host="127.0.0.1",
        port=43210,
        service_version="0.14.0",
        ready_state="ready",
    )

    envelope.validate_for_session(session)
    assert envelope.to_renderer_safe_dict() == {
        "protocol_version": DESKTOP_PROTOCOL_VERSION,
        "service_version": "0.14.0",
        "ready_state": "ready",
    }

    with pytest.raises(ValueError, match="loopback"):
        SidecarReadinessEnvelope(
            protocol_version=DESKTOP_PROTOCOL_VERSION,
            process_nonce=session.process_nonce,
            host="0.0.0.0",
            port=43210,
            service_version="0.14.0",
            ready_state="ready",
        )


def test_library_capability_hides_path_and_rejects_other_root(tmp_path: Path) -> None:
    selected = tmp_path / "music"
    other = tmp_path / "other"
    selected.mkdir()
    other.mkdir()
    capability = LibraryRootCapability.issue(
        selected_root=selected.resolve(),
        session_id="desktop-session-1",
    )

    assert capability.authorize_scan(
        requested_root=selected.resolve(),
        session_id="desktop-session-1",
    ) == selected.resolve()
    safe = capability.to_renderer_safe_dict()
    assert "root_path" not in safe
    assert str(selected.resolve()) not in repr(safe)

    with pytest.raises(PermissionError, match="does not match"):
        capability.authorize_scan(
            requested_root=other.resolve(),
            session_id="desktop-session-1",
        )

    with pytest.raises(PermissionError, match="another session"):
        capability.authorize_scan(
            requested_root=selected.resolve(),
            session_id="desktop-session-2",
        )


def test_sidecar_auth_protects_every_non_health_path() -> None:
    session = SidecarSession.generate()
    app = FastAPI()
    app.add_middleware(SidecarSessionAuthMiddleware, session=session)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/ready")
    def ready():
        return {"status": "ready"}

    client = TestClient(app)
    assert client.get("/health").status_code == 200
    assert client.get("/ready").status_code == 401
    assert client.get(
        "/ready",
        headers={
            SESSION_HEADER: session.credential,
            PROCESS_NONCE_HEADER: session.process_nonce,
        },
    ).status_code == 200


def test_supervisor_reaches_ready_and_stops_owned_process() -> None:
    process = FakeProcess()
    sessions: list[SidecarSession] = []

    def spawn(session: SidecarSession) -> FakeProcess:
        sessions.append(session)
        return process

    def probe(session: SidecarSession) -> SidecarReadinessEnvelope:
        return SidecarReadinessEnvelope(
            protocol_version=DESKTOP_PROTOCOL_VERSION,
            process_nonce=session.process_nonce,
            host="127.0.0.1",
            port=32123,
            service_version="0.14.0",
            ready_state="ready",
        )

    supervisor = SidecarSupervisor(
        spawn=spawn,
        readiness_probe=probe,
        request_shutdown=lambda _session: process.terminate(),
        policy=SupervisorPolicy(
            startup_timeout_seconds=1.0,
            poll_interval_seconds=0.01,
            graceful_shutdown_seconds=0.1,
            max_restarts=1,
        ),
    )

    envelope = supervisor.start()
    assert envelope.ready_state == "ready"
    assert supervisor.state is SidecarState.READY
    assert supervisor.pid == 4242
    assert len(sessions) == 1

    supervisor.stop()
    assert supervisor.state is SidecarState.STOPPED
    assert supervisor.pid is None


def test_supervisor_rejects_wrong_nonce_and_enforces_timeout() -> None:
    process = FakeProcess()
    clock = {"now": 0.0}

    def monotonic() -> float:
        return clock["now"]

    def sleep(seconds: float) -> None:
        clock["now"] += seconds

    def probe(_session: SidecarSession) -> SidecarReadinessEnvelope:
        return SidecarReadinessEnvelope(
            protocol_version=DESKTOP_PROTOCOL_VERSION,
            process_nonce="x" * 32,
            host="127.0.0.1",
            port=32123,
            service_version="0.14.0",
            ready_state="ready",
        )

    supervisor = SidecarSupervisor(
        spawn=lambda _session: process,
        readiness_probe=probe,
        request_shutdown=lambda _session: None,
        policy=SupervisorPolicy(
            startup_timeout_seconds=0.03,
            poll_interval_seconds=0.01,
            graceful_shutdown_seconds=0.1,
            max_restarts=0,
        ),
        monotonic=monotonic,
        sleep=sleep,
    )

    with pytest.raises(SidecarSupervisorError, match="timed out"):
        supervisor.start()

    assert supervisor.state is SidecarState.FAILED
    assert process.terminate_calls == 1


def test_supervisor_restart_budget_fails_closed() -> None:
    process = FakeProcess()
    supervisor = SidecarSupervisor(
        spawn=lambda _session: process,
        readiness_probe=lambda session: SidecarReadinessEnvelope(
            protocol_version=DESKTOP_PROTOCOL_VERSION,
            process_nonce=session.process_nonce,
            host="127.0.0.1",
            port=32123,
            service_version="0.14.0",
            ready_state="ready",
        ),
        request_shutdown=lambda _session: process.terminate(),
        policy=SupervisorPolicy(max_restarts=0),
    )

    with pytest.raises(SidecarSupervisorError, match="budget exhausted"):
        supervisor.restart()
    assert supervisor.state is SidecarState.FAILED
