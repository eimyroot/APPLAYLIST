from __future__ import annotations

import hmac
import json
import os
import socket
import sys
import threading
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import IO, Any, Callable, Mapping

import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.trustedhost import TrustedHostMiddleware

SIDECAR_PROTOCOL_VERSION = "applaylist-desktop-sidecar-v1"
SIDECAR_SERVICE_VERSION = "0.1.0-proof"
SESSION_HEADER = "X-APPLAYLIST-Session"
MIN_SECRET_LENGTH = 32
MIN_NONCE_LENGTH = 24


@dataclass(frozen=True, slots=True)
class SidecarStartupError(ValueError):
    code: str
    detail: str

    def __str__(self) -> str:
        return self.detail


@dataclass(frozen=True, slots=True)
class SidecarStartupConfig:
    protocol_version: str
    process_nonce: str
    session_secret: str
    parent_pid: int

    def __post_init__(self) -> None:
        if self.protocol_version != SIDECAR_PROTOCOL_VERSION:
            raise SidecarStartupError(
                code="protocol_version_mismatch",
                detail="desktop sidecar protocol version is not supported",
            )
        if not isinstance(self.process_nonce, str) or len(self.process_nonce) < MIN_NONCE_LENGTH:
            raise SidecarStartupError(
                code="process_nonce_invalid",
                detail=f"process nonce must contain at least {MIN_NONCE_LENGTH} characters",
            )
        if not isinstance(self.session_secret, str) or len(self.session_secret) < MIN_SECRET_LENGTH:
            raise SidecarStartupError(
                code="session_secret_invalid",
                detail=f"session secret must contain at least {MIN_SECRET_LENGTH} characters",
            )
        if not isinstance(self.parent_pid, int) or isinstance(self.parent_pid, bool):
            raise SidecarStartupError(
                code="parent_pid_invalid",
                detail="parent PID must be an integer",
            )
        if self.parent_pid <= 0:
            raise SidecarStartupError(
                code="parent_pid_invalid",
                detail="parent PID must be positive",
            )


def parse_startup_payload(raw_line: str) -> SidecarStartupConfig:
    if not isinstance(raw_line, str) or not raw_line.strip():
        raise SidecarStartupError(
            code="startup_payload_missing",
            detail="desktop sidecar startup payload is required on stdin",
        )
    if len(raw_line.encode("utf-8")) > 16_384:
        raise SidecarStartupError(
            code="startup_payload_too_large",
            detail="desktop sidecar startup payload is too large",
        )
    try:
        payload = json.loads(raw_line)
    except json.JSONDecodeError as exc:
        raise SidecarStartupError(
            code="startup_payload_invalid_json",
            detail="desktop sidecar startup payload must be valid JSON",
        ) from exc
    if not isinstance(payload, Mapping):
        raise SidecarStartupError(
            code="startup_payload_invalid_shape",
            detail="desktop sidecar startup payload must be an object",
        )

    expected_fields = {
        "protocol_version",
        "process_nonce",
        "session_secret",
        "parent_pid",
    }
    unknown_fields = set(payload) - expected_fields
    missing_fields = expected_fields - set(payload)
    if unknown_fields:
        raise SidecarStartupError(
            code="startup_payload_unknown_fields",
            detail=f"desktop sidecar startup payload contains unknown fields: {sorted(unknown_fields)}",
        )
    if missing_fields:
        raise SidecarStartupError(
            code="startup_payload_missing_fields",
            detail=f"desktop sidecar startup payload is missing fields: {sorted(missing_fields)}",
        )

    return SidecarStartupConfig(
        protocol_version=payload["protocol_version"],
        process_nonce=payload["process_nonce"],
        session_secret=payload["session_secret"],
        parent_pid=payload["parent_pid"],
    )


def bind_loopback_socket() -> socket.socket:
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        listener.bind(("127.0.0.1", 0))
        listener.listen(128)
    except Exception:
        listener.close()
        raise
    return listener


def create_sidecar_app(
    startup: SidecarStartupConfig,
    *,
    request_shutdown: Callable[[], None],
    on_ready: Callable[[], None] | None = None,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        if on_ready is not None:
            on_ready()
        yield

    app = FastAPI(
        title="APPLAYLIST Desktop Sidecar Proof",
        version=SIDECAR_SERVICE_VERSION,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["127.0.0.1", "localhost"],
        www_redirect=False,
    )

    def require_session(
        session_value: str | None = Header(default=None, alias=SESSION_HEADER),
    ) -> None:
        if session_value is None or not hmac.compare_digest(
            session_value,
            startup.session_secret,
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="desktop session authentication failed",
            )

    @app.get("/desktop/v1/health", dependencies=[Depends(require_session)])
    def health() -> dict[str, Any]:
        return {
            "status": "ready",
            "protocol_version": SIDECAR_PROTOCOL_VERSION,
            "service_version": SIDECAR_SERVICE_VERSION,
            "process_nonce": startup.process_nonce,
            "pid": os.getpid(),
            "bind_scope": "loopback",
        }

    @app.post("/desktop/v1/shutdown", dependencies=[Depends(require_session)])
    def shutdown() -> dict[str, str]:
        request_shutdown()
        return {"status": "stopping"}

    return app


def _parent_exists(parent_pid: int) -> bool:
    if parent_pid == os.getpid():
        return True
    try:
        os.kill(parent_pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _watch_parent(
    parent_pid: int,
    server: uvicorn.Server,
    *,
    interval_seconds: float = 1.0,
) -> None:
    while not server.should_exit:
        if not _parent_exists(parent_pid):
            server.should_exit = True
            return
        time.sleep(interval_seconds)


def _readiness_envelope(startup: SidecarStartupConfig, port: int) -> dict[str, Any]:
    return {
        "event": "ready",
        "protocol_version": SIDECAR_PROTOCOL_VERSION,
        "service_version": SIDECAR_SERVICE_VERSION,
        "process_nonce": startup.process_nonce,
        "pid": os.getpid(),
        "host": "127.0.0.1",
        "port": port,
    }


def run_sidecar(
    *,
    stdin: IO[str] = sys.stdin,
    stdout: IO[str] = sys.stdout,
    stderr: IO[str] = sys.stderr,
) -> int:
    try:
        startup = parse_startup_payload(stdin.readline())
    except SidecarStartupError as exc:
        print(
            json.dumps(
                {"event": "startup_error", "code": exc.code, "detail": exc.detail},
                sort_keys=True,
            ),
            file=stderr,
            flush=True,
        )
        return 2

    listener = bind_loopback_socket()
    host, port = listener.getsockname()
    if host != "127.0.0.1":
        listener.close()
        print(
            json.dumps(
                {
                    "event": "startup_error",
                    "code": "non_loopback_bind",
                    "detail": "desktop sidecar refused a non-loopback listener",
                },
                sort_keys=True,
            ),
            file=stderr,
            flush=True,
        )
        return 3

    server_holder: dict[str, uvicorn.Server] = {}

    def request_shutdown() -> None:
        server = server_holder.get("server")
        if server is not None:
            server.should_exit = True

    ready_emitted = threading.Event()

    def emit_ready() -> None:
        if ready_emitted.is_set():
            return
        print(
            json.dumps(_readiness_envelope(startup, port), sort_keys=True),
            file=stdout,
            flush=True,
        )
        ready_emitted.set()

    app = create_sidecar_app(
        startup,
        request_shutdown=request_shutdown,
        on_ready=emit_ready,
    )
    config = uvicorn.Config(
        app=app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
        access_log=False,
        server_header=False,
        date_header=False,
        proxy_headers=False,
        forwarded_allow_ips="",
    )
    server = uvicorn.Server(config=config)
    server_holder["server"] = server

    watchdog = threading.Thread(
        target=_watch_parent,
        args=(startup.parent_pid, server),
        name="applaylist-sidecar-parent-watchdog",
        daemon=True,
    )
    watchdog.start()

    try:
        server.run(sockets=[listener])
    finally:
        listener.close()
    return 0
