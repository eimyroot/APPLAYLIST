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


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
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
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.exceptions import RequestValidationError


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
    request_id = getattr(request.state, "request_id", None)

    try:
        response = await call_next(request)
        duration_ms = round((time.time() - started) * 1000, 2)
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

cat > tests/test_route_wiring_guard.py << 'PYEOF'
from api.main import app


def test_required_routes_present() -> None:
    paths = {getattr(route, "path", None) for route in app.routes}
    required = {
        "/health",
        "/jobs/{job_type}",
        "/jobs/{job_id}",
        "/pipeline/run",
    }
    missing = required - paths
    assert not missing, f"Missing routes: {sorted(missing)}"
PYEOF

cat > scripts/verify_bundle_12.sh << 'EOF_VERIFY'
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

echo "=== VERIFY BUNDLE 12 ==="
echo "[python] $PY"
"$PY" -V

echo "[1/7] branch"
git branch --show-current

echo "[2/7] status"
git status --short

echo "[3/7] compile"
"$PY" -m py_compile \
  api/middleware/request_context.py \
  api/core/observability.py \
  tests/test_route_wiring_guard.py

echo "[4/7] route guard"
"$PY" -m pytest -q tests/test_route_wiring_guard.py

echo "[5/7] full tests"
"$PY" -m pytest -q

echo "[6/7] request id smoke"
"$PY" - << 'PY'
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)
resp = client.get("/health")
rid = resp.headers.get("X-Request-ID")
print("status=", resp.status_code)
print("request_id=", rid)
if not rid:
    raise SystemExit("Missing X-Request-ID header")
PY

echo "[7/7] done"
echo "=== VERIFY DONE ==="
EOF_VERIFY
chmod +x scripts/verify_bundle_12.sh

cat > scripts/patch_main_bundle_12.py << 'PYEOF'
from pathlib import Path

p = Path("api/main.py")
text = p.read_text(encoding="utf-8")

need_imports = [
    "from starlette.exceptions import HTTPException as StarletteHTTPException",
    "from fastapi.exceptions import RequestValidationError",
    "from api.middleware.request_context import RequestContextMiddleware",
    "from api.core.observability import (",
]
obs_import_block = """from api.core.observability import (
    configure_observability,
    http_exception_handler,
    log_request_response,
    unhandled_exception_handler,
    validation_exception_handler,
)"""

if "from api.middleware.request_context import RequestContextMiddleware" not in text:
    lines = text.splitlines()
    insert_at = 0
    for i, line in enumerate(lines):
        if line.startswith("from ") or line.startswith("import "):
            insert_at = i + 1
    block_lines = [
        "from starlette.exceptions import HTTPException as StarletteHTTPException",
        "from fastapi.exceptions import RequestValidationError",
        "from api.middleware.request_context import RequestContextMiddleware",
        obs_import_block,
    ]
    lines[insert_at:insert_at] = block_lines
    text = "\n".join(lines) + "\n"

if "configure_observability()" not in text:
    text = text.replace(
        "app = FastAPI(",
        "configure_observability()\n\napp = FastAPI(",
        1,
    )

if 'app.add_middleware(RequestContextMiddleware)' not in text:
    marker = "apply_security_hardening(app)\n"
    text = text.replace(
        marker,
        marker + "\napp.add_middleware(RequestContextMiddleware)\napp.middleware(\"http\")(log_request_response)\n",
        1,
    )

if "app.add_exception_handler(StarletteHTTPException, http_exception_handler)" not in text:
    text += """
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)
"""

p.write_text(text, encoding="utf-8")
print("api/main.py patched for bundle 12")
PYEOF

.venv/bin/python scripts/patch_main_bundle_12.py 2>/dev/null || python3 scripts/patch_main_bundle_12.py

echo "=== BUNDLE 12 PATCH DONE ==="
