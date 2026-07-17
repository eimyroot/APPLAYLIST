from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import signal
import sys
import threading
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, TextIO


PROTOCOL_VERSION = "applaylist-sidecar-v1"
MAX_STARTUP_BYTES = 8_192
MAX_HEADER_BYTES = 512
SECRET_HEADER = "X-APPLAYLIST-Sidecar-Secret"
NONCE_HEADER = "X-APPLAYLIST-Readiness-Nonce"


class SidecarStartupError(ValueError):
    """Raised when the supervisor startup envelope is malformed or unsafe."""


@dataclass(frozen=True, slots=True)
class SidecarStartup:
    protocol: str
    secret: str
    nonce: str


@dataclass(frozen=True, slots=True)
class SidecarReady:
    protocol: str
    host: str
    port: int
    nonce_sha256: str
    process_id: int

    def to_json(self) -> str:
        return json.dumps(
            {
                "event": "ready",
                "protocol": self.protocol,
                "host": self.host,
                "port": self.port,
                "nonce_sha256": self.nonce_sha256,
                "process_id": self.process_id,
            },
            sort_keys=True,
            separators=(",", ":"),
        )


def read_startup_envelope(stream: TextIO) -> SidecarStartup:
    line = stream.readline(MAX_STARTUP_BYTES + 1)
    if not line:
        raise SidecarStartupError("startup envelope is required")
    if len(line.encode("utf-8")) > MAX_STARTUP_BYTES:
        raise SidecarStartupError("startup envelope exceeds size limit")
    if not line.endswith("\n"):
        raise SidecarStartupError("startup envelope must be newline terminated")

    try:
        payload = json.loads(line)
    except json.JSONDecodeError as exc:
        raise SidecarStartupError("startup envelope must be valid JSON") from exc
    if not isinstance(payload, dict):
        raise SidecarStartupError("startup envelope must be an object")
    if set(payload) != {"protocol", "secret", "nonce"}:
        raise SidecarStartupError("startup envelope contains unexpected fields")

    protocol = _required_text(payload.get("protocol"), "protocol", minimum=1, maximum=64)
    secret = _required_text(payload.get("secret"), "secret", minimum=32, maximum=256)
    nonce = _required_text(payload.get("nonce"), "nonce", minimum=32, maximum=256)
    if protocol != PROTOCOL_VERSION:
        raise SidecarStartupError("unsupported sidecar protocol")
    if hmac.compare_digest(secret, nonce):
        raise SidecarStartupError("secret and nonce must be distinct")
    return SidecarStartup(protocol=protocol, secret=secret, nonce=nonce)


def _required_text(value: Any, field: str, *, minimum: int, maximum: int) -> str:
    if not isinstance(value, str):
        raise SidecarStartupError(f"{field} must be text")
    if value != value.strip():
        raise SidecarStartupError(f"{field} must not contain surrounding whitespace")
    if not minimum <= len(value) <= maximum:
        raise SidecarStartupError(
            f"{field} length must be between {minimum} and {maximum} characters"
        )
    if any(ord(character) < 33 or ord(character) > 126 for character in value):
        raise SidecarStartupError(f"{field} must contain printable ASCII without spaces")
    return value


class _SidecarHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False

    def __init__(self, startup: SidecarStartup) -> None:
        self.startup = startup
        self.shutdown_requested = threading.Event()
        super().__init__(("127.0.0.1", 0), _SidecarRequestHandler)


class _SidecarRequestHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "APPLAYLISTSidecar"
    sys_version = ""

    @property
    def sidecar_server(self) -> _SidecarHTTPServer:
        server = self.server
        if not isinstance(server, _SidecarHTTPServer):
            raise RuntimeError("invalid sidecar server")
        return server

    def do_GET(self) -> None:  # noqa: N802
        if self.path != "/v1/health":
            self._write_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        if not self._authorized():
            self._write_json(HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"})
            return
        self._write_json(
            HTTPStatus.OK,
            {
                "status": "ready",
                "protocol": PROTOCOL_VERSION,
                "nonce_sha256": _sha256(self.sidecar_server.startup.nonce),
            },
        )

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/v1/shutdown":
            self._write_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        if not self._authorized():
            self._write_json(HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"})
            return
        if not self._empty_body():
            self._write_json(HTTPStatus.BAD_REQUEST, {"error": "body_not_allowed"})
            return

        self.sidecar_server.shutdown_requested.set()
        self._write_json(HTTPStatus.ACCEPTED, {"status": "shutting_down"})
        threading.Thread(
            target=self.sidecar_server.shutdown,
            name="applaylist-sidecar-shutdown",
            daemon=True,
        ).start()

    def do_PUT(self) -> None:  # noqa: N802
        self._method_not_allowed()

    def do_DELETE(self) -> None:  # noqa: N802
        self._method_not_allowed()

    def do_PATCH(self) -> None:  # noqa: N802
        self._method_not_allowed()

    def log_message(self, _format: str, *_args: object) -> None:
        return

    def _authorized(self) -> bool:
        secret = self.headers.get(SECRET_HEADER)
        nonce = self.headers.get(NONCE_HEADER)
        if secret is None or nonce is None:
            return False
        if len(secret) > MAX_HEADER_BYTES or len(nonce) > MAX_HEADER_BYTES:
            return False
        startup = self.sidecar_server.startup
        return hmac.compare_digest(secret, startup.secret) and hmac.compare_digest(
            nonce, startup.nonce
        )

    def _empty_body(self) -> bool:
        raw_length = self.headers.get("Content-Length", "0")
        try:
            length = int(raw_length)
        except ValueError:
            return False
        if length != 0:
            if 0 < length <= MAX_STARTUP_BYTES:
                self.rfile.read(length)
            return False
        return True

    def _method_not_allowed(self) -> None:
        self._write_json(HTTPStatus.METHOD_NOT_ALLOWED, {"error": "method_not_allowed"})

    def _write_json(self, status: HTTPStatus, payload: dict[str, object]) -> None:
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        self.send_response(status.value)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(encoded)
        self.close_connection = True


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("ascii")).hexdigest()


def run_sidecar(
    *,
    stdin: TextIO = sys.stdin,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
) -> int:
    try:
        startup = read_startup_envelope(stdin)
    except SidecarStartupError as exc:
        print(
            json.dumps({"event": "startup_error", "error": str(exc)}, sort_keys=True),
            file=stderr,
            flush=True,
        )
        return 2

    server = _SidecarHTTPServer(startup)
    host, port = server.server_address
    ready = SidecarReady(
        protocol=PROTOCOL_VERSION,
        host=str(host),
        port=int(port),
        nonce_sha256=_sha256(startup.nonce),
        process_id=_process_id(),
    )
    print(ready.to_json(), file=stdout, flush=True)

    stop_requested = threading.Event()

    def request_stop(_signum: int, _frame: object) -> None:
        if stop_requested.is_set():
            return
        stop_requested.set()
        threading.Thread(target=server.shutdown, daemon=True).start()

    previous_sigterm = signal.signal(signal.SIGTERM, request_stop)
    previous_sigint = signal.signal(signal.SIGINT, request_stop)
    try:
        server.serve_forever(poll_interval=0.1)
    finally:
        server.server_close()
        signal.signal(signal.SIGTERM, previous_sigterm)
        signal.signal(signal.SIGINT, previous_sigint)
    return 0


def _process_id() -> int:
    import os

    return os.getpid()


def main() -> int:
    return run_sidecar()


if __name__ == "__main__":
    raise SystemExit(main())
