#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

mkdir -p api/core api/middleware tests

cat > api/middleware/request_context.py << 'PYEOF'
from __future__ import annotations

import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


def ensure_request_id(request: Request) -> str:
    existing = getattr(request.state, "request_id", None)
    if existing:
        return existing

    header_id = request.headers.get("X-Request-ID")
    request_id = header_id or str(uuid.uuid4())
    request.state.request_id = request_id
    return request_id


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = ensure_request_id(request)
        request.state.started_at = time.time()

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
PYEOF

cat > api/core/observability.py << 'PYEOF'
from __future__ import annotations

import json
import logging
import time
from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from api.middleware.request_context import ensure_request_id

logger = logging.getLogger("applaylist.api")


def configure_observability() -> None:
    if logger.handlers:
        return

    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(message)s")
    handler.setFormatter(formatter)

    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    logger.propagate = False


def _log(event: str, **payload: Any) -> None:
    body = {"event": event, **payload}
    logger.info(json.dumps(body, ensure_ascii=False, default=str))


async def log_request_response(request: Request, call_next):
    started = time.time()
    request_id = ensure_request_id(request)

    try:
        response = await call_next(request)
        duration_ms = round((time.time() - started) * 1000, 2)

        if not response.headers.get("X-Request-ID"):
            response.headers["X-Request-ID"] = request_id

        _log(
            "request_complete",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )
        return response
    except Exception as exc:
        duration_ms = round((time.time() - started) * 1000, 2)
        _log(
            "request_exception",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            error=repr(exc),
            duration_ms=duration_ms,
        )
        raise


async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    request_id = ensure_request_id(request)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "type": "http_error",
                "message": exc.detail,
                "status_code": exc.status_code,
                "request_id": request_id,
            }
        },
        headers={"X-Request-ID": request_id},
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    request_id = ensure_request_id(request)
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "type": "validation_error",
                "message": "Request validation failed",
                "status_code": 422,
                "request_id": request_id,
                "details": exc.errors(),
            }
        },
        headers={"X-Request-ID": request_id},
    )


async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id = ensure_request_id(request)
    _log(
        "unhandled_exception",
        request_id=request_id,
        method=request.method,
        path=request.url.path,
        error=repr(exc),
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "type": "internal_error",
                "message": "Internal server error",
                "status_code": 500,
                "request_id": request_id,
            }
        },
        headers={"X-Request-ID": request_id},
    )
PYEOF

cat > api/security/auth_gate.py << 'PYEOF'
from __future__ import annotations

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from api.middleware.request_context import ensure_request_id
from api.security.settings import settings


WRITE_PREFIXES = (
    "/jobs/",
    "/pipeline/run",
)
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


class ApiKeyAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = ensure_request_id(request)

        if not settings.auth_enabled:
            return await call_next(request)

        if request.method in SAFE_METHODS:
            return await call_next(request)

        path = request.url.path
        if not any(path.startswith(prefix) for prefix in WRITE_PREFIXES):
            return await call_next(request)

        supplied = request.headers.get(settings.api_key_header_name)
        expected = settings.api_key

        if not expected:
            return JSONResponse(
                status_code=503,
                content={
                    "error": {
                        "type": "auth_misconfigured",
                        "message": "API auth is enabled but no API key is configured",
                        "status_code": 503,
                        "request_id": request_id,
                    }
                },
                headers={"X-Request-ID": request_id},
            )

        if supplied != expected:
            return JSONResponse(
                status_code=401,
                content={
                    "error": {
                        "type": "unauthorized",
                        "message": "Missing or invalid API key",
                        "status_code": 401,
                        "request_id": request_id,
                    }
                },
                headers={"X-Request-ID": request_id},
            )

        return await call_next(request)
PYEOF

cat > tests/test_request_id_auth_failure.py << 'PYEOF'
import os
from importlib import reload

from fastapi.testclient import TestClient

import api.main as main_module
import api.security.auth_gate as auth_gate_module
import api.security.settings as settings_module


def _reload_app():
    reload(settings_module)
    reload(auth_gate_module)
    reload(main_module)
    return main_module.app


def _clear_auth_env() -> None:
    os.environ.pop("AUTH_ENABLED", None)
    os.environ.pop("API_KEY", None)
    os.environ.pop("API_KEY_HEADER_NAME", None)
    os.environ.pop("APP_ENV", None)


def test_auth_failure_includes_request_id_in_body_and_header() -> None:
    try:
        os.environ["AUTH_ENABLED"] = "true"
        os.environ["API_KEY"] = "bundle14-secret"

        app = _reload_app()
        client = TestClient(app)

        response = client.post("/pipeline/run", json={"path": "/tmp", "limit": 1})

        assert response.status_code == 401
        body = response.json()
        rid_body = body["error"]["request_id"]
        rid_header = response.headers.get("X-Request-ID")

        assert rid_body
        assert rid_header
        assert rid_body == rid_header
    finally:
        _clear_auth_env()
        _reload_app()
PYEOF

cat > tests/test_request_id_exception_path.py << 'PYEOF'
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from api.core.observability import (
    configure_observability,
    http_exception_handler,
    log_request_response,
    unhandled_exception_handler,
    validation_exception_handler,
)
from api.middleware.request_context import RequestContextMiddleware


def build_app() -> FastAPI:
    configure_observability()
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)
    app.middleware("http")(log_request_response)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    @app.get("/boom")
    def boom():
        raise RuntimeError("bundle14 boom")

    return app


def test_exception_path_includes_request_id_header_and_body() -> None:
    app = build_app()
    client = TestClient(app, raise_server_exceptions=False)

    response = client.get("/boom")

    assert response.status_code == 500
    body = response.json()
    rid_body = body["error"]["request_id"]
    rid_header = response.headers.get("X-Request-ID")

    assert rid_body
    assert rid_header
    assert rid_body == rid_header
PYEOF

cat > scripts/verify_bundle_14.sh << 'EOF_VERIFY'
#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [ -x ".venv/bin/python" ]; then
  PY=".venv/bin/python"
elif [ -x "venv/bin/python" ]; then
  PY="venv/bin/python"
else
  PY="$(command -v python3)"
fi

echo "=== VERIFY BUNDLE 14 ==="
echo "[python] $PY"
"$PY" -V

echo "[1/8] branch"
git branch --show-current

echo "[2/8] status"
git status --short

echo "[3/8] compile"
"$PY" -m py_compile \
  api/middleware/request_context.py \
  api/core/observability.py \
  api/security/auth_gate.py \
  tests/test_request_id_auth_failure.py \
  tests/test_request_id_exception_path.py

echo "[4/8] route guard"
AUTH_ENABLED=false API_KEY= "$PY" -m pytest -q tests/test_route_wiring_guard.py

echo "[5/8] request-id auth failure test"
"$PY" -m pytest -q tests/test_request_id_auth_failure.py

echo "[6/8] request-id exception path test"
"$PY" -m pytest -q tests/test_request_id_exception_path.py

echo "[7/8] full tests"
AUTH_ENABLED=false API_KEY= "$PY" -m pytest -q

echo "[8/8] smoke"
AUTH_ENABLED=true API_KEY=smoke-key "$PY" - << 'PY'
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)
resp = client.post("/pipeline/run", json={"path": "/tmp", "limit": 1})
print("status=", resp.status_code)
print("header_request_id=", resp.headers.get("X-Request-ID"))
print("body_request_id=", resp.json().get("error", {}).get("request_id"))
assert resp.status_code == 401
assert resp.headers.get("X-Request-ID")
assert resp.json()["error"]["request_id"] == resp.headers["X-Request-ID"]
PY

echo "=== VERIFY DONE ==="
EOF_VERIFY
chmod +x scripts/verify_bundle_14.sh

echo "=== BUNDLE 14 PATCH DONE ==="
