from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from services.desktop.sidecar import PROTOCOL_VERSION, read_startup_envelope


SECRET = "S" * 48
NONCE = "N" * 48


def _start_sidecar(*, secret: str = SECRET, nonce: str = NONCE) -> tuple[subprocess.Popen[str], dict]:
    process = subprocess.Popen(
        [sys.executable, "-m", "services.desktop.sidecar"],
        cwd=Path(__file__).resolve().parents[1],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        bufsize=1,
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
    )
    assert process.stdin is not None
    assert process.stdout is not None
    process.stdin.write(
        json.dumps(
            {"protocol": PROTOCOL_VERSION, "secret": secret, "nonce": nonce},
            separators=(",", ":"),
        )
        + "\n"
    )
    process.stdin.flush()
    ready_line = process.stdout.readline()
    if not ready_line:
        stderr = process.stderr.read() if process.stderr is not None else ""
        raise AssertionError(f"sidecar did not become ready: {stderr}")
    return process, json.loads(ready_line)


def _request(
    ready: dict,
    *,
    method: str,
    path: str,
    secret: str = SECRET,
    nonce: str = NONCE,
    body: bytes | None = None,
) -> tuple[int, dict]:
    request = Request(
        f"http://127.0.0.1:{ready['port']}{path}",
        data=body,
        method=method,
        headers={
            "X-APPLAYLIST-Sidecar-Secret": secret,
            "X-APPLAYLIST-Readiness-Nonce": nonce,
        },
    )
    try:
        with urlopen(request, timeout=3) as response:  # noqa: S310 - fixed loopback URL
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def _finish(process: subprocess.Popen[str], *, timeout: float = 5.0) -> tuple[str, str]:
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        stdout, stderr = process.communicate(timeout=timeout)
        raise AssertionError("sidecar did not terminate within timeout")
    return stdout, stderr


def test_startup_envelope_is_strict_and_does_not_accept_extra_fields() -> None:
    from io import StringIO

    valid = read_startup_envelope(
        StringIO(
            json.dumps(
                {"protocol": PROTOCOL_VERSION, "secret": SECRET, "nonce": NONCE}
            )
            + "\n"
        )
    )
    assert valid.secret == SECRET

    with pytest.raises(ValueError, match="unexpected fields"):
        read_startup_envelope(
            StringIO(
                json.dumps(
                    {
                        "protocol": PROTOCOL_VERSION,
                        "secret": SECRET,
                        "nonce": NONCE,
                        "port": 8000,
                    }
                )
                + "\n"
            )
        )


@pytest.mark.parametrize(
    ("secret", "nonce"),
    [
        ("short", NONCE),
        (SECRET, "short"),
        (SECRET, SECRET),
        (SECRET + " ", NONCE),
    ],
)
def test_invalid_startup_fails_without_disclosing_credentials(secret: str, nonce: str) -> None:
    process = subprocess.run(
        [sys.executable, "-m", "services.desktop.sidecar"],
        cwd=Path(__file__).resolve().parents[1],
        input=json.dumps(
            {"protocol": PROTOCOL_VERSION, "secret": secret, "nonce": nonce}
        )
        + "\n",
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=5,
        check=False,
    )

    assert process.returncode == 2
    assert '"event": "startup_error"' in process.stderr
    assert secret not in process.stderr
    assert nonce not in process.stderr


def test_sidecar_authentication_health_and_shutdown_are_fail_closed() -> None:
    process, ready = _start_sidecar()
    try:
        assert ready["event"] == "ready"
        assert ready["protocol"] == PROTOCOL_VERSION
        assert ready["host"] == "127.0.0.1"
        assert isinstance(ready["port"], int) and ready["port"] > 0
        assert ready["nonce_sha256"] == hashlib.sha256(NONCE.encode("ascii")).hexdigest()
        assert SECRET not in json.dumps(ready)
        assert NONCE not in json.dumps(ready)
        assert SECRET not in " ".join(process.args)
        assert NONCE not in " ".join(process.args)

        status, payload = _request(
            ready,
            method="GET",
            path="/v1/health",
            secret="X" * 48,
        )
        assert status == 401
        assert payload == {"error": "unauthorized"}

        status, payload = _request(
            ready,
            method="GET",
            path="/v1/health",
            nonce="Y" * 48,
        )
        assert status == 401
        assert payload == {"error": "unauthorized"}

        status, payload = _request(ready, method="GET", path="/v1/health")
        assert status == 200
        assert payload == {
            "nonce_sha256": hashlib.sha256(NONCE.encode("ascii")).hexdigest(),
            "protocol": PROTOCOL_VERSION,
            "status": "ready",
        }

        status, payload = _request(
            ready,
            method="POST",
            path="/v1/shutdown",
            body=b"not-allowed",
        )
        assert status == 400
        assert payload == {"error": "body_not_allowed"}
        assert process.poll() is None

        status, payload = _request(ready, method="POST", path="/v1/shutdown")
        assert status == 202
        assert payload == {"status": "shutting_down"}

        stdout, stderr = _finish(process)
        assert process.returncode == 0
        assert SECRET not in stdout + stderr
        assert NONCE not in stdout + stderr
    finally:
        if process.poll() is None:
            process.kill()
            _finish(process)


def test_unknown_route_and_method_do_not_expose_server_details() -> None:
    process, ready = _start_sidecar()
    try:
        status, payload = _request(ready, method="GET", path="/unknown")
        assert status == 404
        assert payload == {"error": "not_found"}

        status, payload = _request(ready, method="PUT", path="/v1/health")
        assert status == 405
        assert payload == {"error": "method_not_allowed"}

        status, _ = _request(ready, method="POST", path="/v1/shutdown")
        assert status == 202
        deadline = time.monotonic() + 5
        while process.poll() is None and time.monotonic() < deadline:
            time.sleep(0.02)
        assert process.poll() == 0
    finally:
        if process.poll() is None:
            process.kill()
            _finish(process)
