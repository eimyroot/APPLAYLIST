#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

mkdir -p api/security api/core api/middleware tests data/config

cat > api/security/auth_gate.py << 'PYEOF'
from __future__ import annotations

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from api.security.settings import settings


WRITE_PREFIXES = (
    "/jobs/",
    "/pipeline/run",
)
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


class ApiKeyAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
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
                        "request_id": getattr(request.state, "request_id", None),
                    }
                },
            )

        if supplied != expected:
            return JSONResponse(
                status_code=401,
                content={
                    "error": {
                        "type": "unauthorized",
                        "message": "Missing or invalid API key",
                        "status_code": 401,
                        "request_id": getattr(request.state, "request_id", None),
                    }
                },
            )

        return await call_next(request)
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

    try:
        response = await call_next(request)
        duration_ms = round((time.time() - started) * 1000, 2)
        request_id = getattr(request.state, "request_id", None)
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
        request_id = getattr(request.state, "request_id", None)
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
    request_id = getattr(request.state, "request_id", None)
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
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    request_id = getattr(request.state, "request_id", None)
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
    )


async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", None)
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
    )
PYEOF

cat > api/security/settings.py << 'PYEOF'
from __future__ import annotations

import os
from dataclasses import dataclass


def _as_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _as_int(value: str | None, default: int) -> int:
    try:
        return int(value) if value is not None else default
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class SecuritySettings:
    app_env: str = os.getenv("APP_ENV", os.getenv("ENV", "development"))
    allowed_origins_raw: str = os.getenv("ALLOW_ORIGINS", "*")
    rate_limit_per_minute: int = _as_int(os.getenv("RATE_LIMIT_PER_MINUTE"), 120)
    max_request_bytes: int = _as_int(os.getenv("MAX_REQUEST_BYTES"), 2 * 1024 * 1024)
    trusted_proxy_depth: int = _as_int(os.getenv("TRUSTED_PROXY_DEPTH"), 0)
    enable_security_headers: bool = _as_bool(os.getenv("ENABLE_SECURITY_HEADERS"), True)
    enable_request_size_guard: bool = _as_bool(os.getenv("ENABLE_REQUEST_SIZE_GUARD"), True)
    enable_rate_limit: bool = _as_bool(os.getenv("ENABLE_RATE_LIMIT"), True)

    # Bundle 13
    auth_enabled_raw: bool = _as_bool(os.getenv("AUTH_ENABLED"), False)
    api_key: str = os.getenv("API_KEY", "")
    api_key_header_name: str = os.getenv("API_KEY_HEADER_NAME", "X-API-Key")

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() in {"prod", "production"}

    @property
    def allowed_origins(self) -> list[str]:
        raw = self.allowed_origins_raw.strip()
        if not raw:
            return ["*"]
        return [item.strip() for item in raw.split(",") if item.strip()]

    @property
    def auth_enabled(self) -> bool:
        if self.is_production:
            return True if self.auth_enabled_raw or self.api_key else False
        return self.auth_enabled_raw


settings = SecuritySettings()
PYEOF

cat > data/config/security.env.example << 'EOF_ENV'
APP_ENV=production
ALLOW_ORIGINS=*
ENABLE_SECURITY_HEADERS=true
ENABLE_REQUEST_SIZE_GUARD=true
ENABLE_RATE_LIMIT=true
RATE_LIMIT_PER_MINUTE=120
MAX_REQUEST_BYTES=2097152
TRUSTED_PROXY_DEPTH=0

# Bundle 13
AUTH_ENABLED=true
API_KEY=change-me
API_KEY_HEADER_NAME=X-API-Key
EOF_ENV

cat > tests/test_auth_gate.py << 'PYEOF'
import os
from importlib import reload

from fastapi.testclient import TestClient

import api.security.settings as settings_module
import api.security.auth_gate as auth_gate_module
import api.main as main_module


def _reload_app():
    reload(settings_module)
    reload(auth_gate_module)
    reload(main_module)
    return main_module.app


def test_write_endpoint_rejects_missing_api_key_when_auth_enabled() -> None:
    os.environ["AUTH_ENABLED"] = "true"
    os.environ["API_KEY"] = "secret-test-key"

    app = _reload_app()
    client = TestClient(app)

    response = client.post("/pipeline/run", json={"path": "/tmp", "limit": 1})
    assert response.status_code == 401
    body = response.json()
    assert body["error"]["type"] == "unauthorized"


def test_write_endpoint_accepts_valid_api_key_when_auth_enabled() -> None:
    os.environ["AUTH_ENABLED"] = "true"
    os.environ["API_KEY"] = "secret-test-key"

    app = _reload_app()
    client = TestClient(app)

    response = client.post(
        "/pipeline/run",
        json={"path": "/tmp", "limit": 1},
        headers={"X-API-Key": "secret-test-key"},
    )
    assert response.status_code == 200


def test_get_endpoint_does_not_require_api_key() -> None:
    os.environ["AUTH_ENABLED"] = "true"
    os.environ["API_KEY"] = "secret-test-key"

    app = _reload_app()
    client = TestClient(app)

    response = client.get("/health")
    assert response.status_code == 200
PYEOF

cat > tests/test_request_id_behavior.py << 'PYEOF'
from fastapi.testclient import TestClient

from api.main import app


def test_health_response_contains_request_id_header() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")


def test_health_preserves_supplied_request_id() -> None:
    client = TestClient(app)
    response = client.get("/health", headers={"X-Request-ID": "bundle-13-test-id"})
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") == "bundle-13-test-id"
PYEOF

cat > scripts/patch_main_bundle_13.py << 'PYEOF'
from pathlib import Path

p = Path("api/main.py")
text = p.read_text(encoding="utf-8")

imports = [
    "from api.security.auth_gate import ApiKeyAuthMiddleware",
]

for imp in imports:
    if imp not in text:
        lines = text.splitlines()
        insert_at = 0
        for i, line in enumerate(lines):
            if line.startswith("from ") or line.startswith("import "):
                insert_at = i + 1
        lines.insert(insert_at, imp)
        text = "\n".join(lines) + "\n"

marker = 'app.add_middleware(RequestContextMiddleware)\n'
if marker in text and 'app.add_middleware(ApiKeyAuthMiddleware)\n' not in text:
    text = text.replace(
        marker,
        marker + "app.add_middleware(ApiKeyAuthMiddleware)\n",
        1,
    )

p.write_text(text, encoding="utf-8")
print("api/main.py patched for bundle 13")
PYEOF

PY=".venv/bin/python"
if [ ! -x "$PY" ]; then
  PY="$(command -v python3)"
fi

"$PY" scripts/patch_main_bundle_13.py

cat > scripts/verify_bundle_13.sh << 'EOF_VERIFY'
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

echo "=== VERIFY BUNDLE 13 ==="
echo "[python] $PY"
"$PY" -V

echo "[1/8] branch"
git branch --show-current

echo "[2/8] status"
git status --short

echo "[3/8] compile"
"$PY" -m py_compile \
  api/security/auth_gate.py \
  api/security/settings.py \
  api/core/observability.py \
  tests/test_auth_gate.py \
  tests/test_request_id_behavior.py

echo "[4/8] route guard"
"$PY" -m pytest -q tests/test_route_wiring_guard.py

echo "[5/8] auth tests"
"$PY" -m pytest -q tests/test_auth_gate.py

echo "[6/8] request id tests"
"$PY" -m pytest -q tests/test_request_id_behavior.py

echo "[7/8] full tests"
"$PY" -m pytest -q

echo "[8/8] prod config probe"
AUTH_ENABLED=true API_KEY=probe-key APP_ENV=production "$PY" - << 'PY'
from api.security.settings import settings
print("app_env=", settings.app_env)
print("auth_enabled=", settings.auth_enabled)
print("header=", settings.api_key_header_name)
assert settings.auth_enabled is True
PY

echo "=== VERIFY DONE ==="
EOF_VERIFY
chmod +x scripts/verify_bundle_13.sh

echo "=== BUNDLE 13 PATCH DONE ==="
