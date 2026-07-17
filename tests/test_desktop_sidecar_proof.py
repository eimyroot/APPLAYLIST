from __future__ import annotations

import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
from fastapi.testclient import TestClient

from services.desktop_sidecar import (
    SIDECAR_PROTOCOL_VERSION,
    SidecarStartupConfig,
    SidecarStartupError,
    create_sidecar_app,
    parse_startup_payload,
)
from services.desktop_sidecar.runtime import SESSION_HEADER, bind_loopback_socket


def _startup() -> SidecarStartupConfig:
    return SidecarStartupConfig(
        protocol_version=SIDECAR_PROTOCOL_VERSION,
        process_nonce=secrets.token_urlsafe(24),
        session_secret=secrets.token_urlsafe(48),
        parent_pid=os.getpid(),
    )


def test_startup_payload_is_strict_and_secret_length_is_enforced() -> None:
    valid = {
        "protocol_version": SIDECAR_PROTOCOL_VERSION,
        "process_nonce": "n" * 32,
        "session_secret": "s" * 48,
        "parent_pid": 123,
    }

    parsed = parse_startup_payload(json.dumps(valid))
    assert parsed.parent_pid == 123

    with pytest.raises(SidecarStartupError) as unknown:
        parse_startup_payload(json.dumps({**valid, "debug": True}))
    assert unknown.value.code == "startup_payload_unknown_fields"

    with pytest.raises(SidecarStartupError) as short_secret:
        parse_startup_payload(json.dumps({**valid, "session_secret": "short"}))
    assert short_secret.value.code == "session_secret_invalid"

    with pytest.raises(SidecarStartupError) as protocol:
        parse_startup_payload(json.dumps({**valid, "protocol_version": "future"}))
    assert protocol.value.code == "protocol_version_mismatch"


def test_listener_is_ipv4_loopback_with_ephemeral_port() -> None:
    listener = bind_loopback_socket()
    try:
        host, port = listener.getsockname()
        assert host == "127.0.0.1"
        assert isinstance(port, int)
        assert port > 0
    finally:
        listener.close()


def test_app_requires_session_for_health_and_shutdown() -> None:
    startup = _startup()
    shutdown_calls: list[bool] = []
    app = create_sidecar_app(
        startup,
        request_shutdown=lambda: shutdown_calls.append(True),
    )

    with TestClient(app, base_url="http://127.0.0.1") as client:
        missing = client.get("/desktop/v1/health")
        assert missing.status_code == 401

        wrong = client.get(
            "/desktop/v1/health",
            headers={SESSION_HEADER: "wrong-secret"},
        )
        assert wrong.status_code == 401

        accepted = client.get(
            "/desktop/v1/health",
            headers={SESSION_HEADER: startup.session_secret},
        )
        assert accepted.status_code == 200
        assert accepted.json()["process_nonce"] == startup.process_nonce
        assert accepted.json()["bind_scope"] == "loopback"

        docs = client.get("/docs")
        assert docs.status_code == 404
        openapi = client.get("/openapi.json")
        assert openapi.status_code == 404

        shutdown = client.post(
            "/desktop/v1/shutdown",
            headers={SESSION_HEADER: startup.session_secret},
        )
        assert shutdown.status_code == 200
        assert shutdown.json() == {"status": "stopping"}
        assert shutdown_calls == [True]


def test_app_rejects_untrusted_host_header() -> None:
    startup = _startup()
    app = create_sidecar_app(startup, request_shutdown=lambda: None)

    with TestClient(app, base_url="http://127.0.0.1") as client:
        response = client.get(
            "/desktop/v1/health",
            headers={
                SESSION_HEADER: startup.session_secret,
                "Host": "attacker.invalid",
            },
        )

    assert response.status_code == 400


def _request_json(
    url: str,
    *,
    method: str,
    secret: str,
    timeout: float = 5.0,
) -> tuple[int, dict[str, object]]:
    request = Request(
        url,
        method=method,
        headers={SESSION_HEADER: secret},
    )
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed loopback URL
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def test_real_sidecar_process_emits_readiness_authenticates_and_stops() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    script = repository_root / "scripts" / "run_desktop_sidecar.py"
    secret = secrets.token_urlsafe(48)
    nonce = secrets.token_urlsafe(24)
    payload = {
        "protocol_version": SIDECAR_PROTOCOL_VERSION,
        "process_nonce": nonce,
        "session_secret": secret,
        "parent_pid": os.getpid(),
    }

    process = subprocess.Popen(
        [sys.executable, str(script)],
        cwd=repository_root,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    assert process.stdin is not None
    assert process.stdout is not None
    assert process.stderr is not None

    try:
        process.stdin.write(json.dumps(payload) + "\n")
        process.stdin.flush()
        process.stdin.close()

        readiness_line = process.stdout.readline().strip()
        assert readiness_line, process.stderr.read()
        readiness = json.loads(readiness_line)
        assert readiness["event"] == "ready"
        assert readiness["host"] == "127.0.0.1"
        assert readiness["process_nonce"] == nonce
        assert readiness["protocol_version"] == SIDECAR_PROTOCOL_VERSION
        port = int(readiness["port"])
        base_url = f"http://127.0.0.1:{port}"

        wrong_status, _ = _request_json(
            f"{base_url}/desktop/v1/health",
            method="GET",
            secret="wrong-secret",
        )
        assert wrong_status == 401

        deadline = time.monotonic() + 5.0
        while True:
            try:
                health_status, health = _request_json(
                    f"{base_url}/desktop/v1/health",
                    method="GET",
                    secret=secret,
                    timeout=1.0,
                )
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.05)

        assert health_status == 200
        assert health["status"] == "ready"
        assert health["process_nonce"] == nonce
        assert health["pid"] == process.pid

        shutdown_status, shutdown = _request_json(
            f"{base_url}/desktop/v1/shutdown",
            method="POST",
            secret=secret,
        )
        assert shutdown_status == 200
        assert shutdown == {"status": "stopping"}

        assert process.wait(timeout=8.0) == 0
        assert secret not in process.stderr.read()
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5.0)
