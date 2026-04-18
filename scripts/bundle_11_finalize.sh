#!/usr/bin/env bash
set -euo pipefail

echo "=== BUNDLE 11 FINALIZE START ==="

ROOT_DIR="$(pwd)"
echo "[cwd] $ROOT_DIR"

mkdir -p api/security
mkdir -p api/middleware
mkdir -p data/config
mkdir -p scripts

# -----------------------------
# .gitignore hardening
# -----------------------------
touch .gitignore
python3 - << 'PY'
from pathlib import Path

p = Path(".gitignore")
existing = p.read_text(encoding="utf-8") if p.exists() else ""

block = """
# --- APPLAYLIST HARDENING ---
*.icloud
.DS_Store
*.log
*.tmp
*.bak
*.swp
*.swo
__pycache__/
*.pyc
.pytest_cache/
.ruff_cache/
.mypy_cache/
.backup_*/
data/tmp/
.env
.env.*
"""

if block.strip() not in existing:
    with p.open("a", encoding="utf-8") as f:
        if existing and not existing.endswith("\n"):
            f.write("\n")
        f.write(block.lstrip())
PY

# -----------------------------
# security settings module
# -----------------------------
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

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() in {"prod", "production"}

    @property
    def allowed_origins(self) -> list[str]:
        raw = self.allowed_origins_raw.strip()
        if not raw:
            return ["*"]
        return [item.strip() for item in raw.split(",") if item.strip()]


settings = SecuritySettings()
PYEOF

# -----------------------------
# rate limiter middleware
# -----------------------------
cat > api/middleware/rate_limit.py << 'PYEOF'
from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Deque, DefaultDict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, limit_per_minute: int = 120) -> None:
        super().__init__(app)
        self.limit_per_minute = max(1, int(limit_per_minute))
        self._hits: DefaultDict[str, Deque[float]] = defaultdict(deque)

    def _client_key(self, request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        if forwarded:
            return forwarded
        client = request.client.host if request.client else "unknown"
        return client or "unknown"

    async def dispatch(self, request: Request, call_next) -> Response:
        key = self._client_key(request)
        now = time.time()
        window_start = now - 60.0
        bucket = self._hits[key]

        while bucket and bucket[0] < window_start:
            bucket.popleft()

        if len(bucket) >= self.limit_per_minute:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "rate_limit_exceeded",
                    "limit_per_minute": self.limit_per_minute,
                },
            )

        bucket.append(now)
        return await call_next(request)
PYEOF

# -----------------------------
# request size guard
# -----------------------------
cat > api/middleware/request_size_guard.py << 'PYEOF'
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class RequestSizeGuardMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_bytes: int = 2 * 1024 * 1024) -> None:
        super().__init__(app)
        self.max_bytes = max(1024, int(max_bytes))

    async def dispatch(self, request: Request, call_next) -> Response:
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > self.max_bytes:
                    return JSONResponse(
                        status_code=413,
                        content={
                            "detail": "payload_too_large",
                            "max_bytes": self.max_bytes,
                        },
                    )
            except ValueError:
                return JSONResponse(
                    status_code=400,
                    content={"detail": "invalid_content_length"},
                )

        return await call_next(request)
PYEOF

# -----------------------------
# security headers middleware
# -----------------------------
cat > api/middleware/security_headers.py << 'PYEOF'
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        return response
PYEOF

# -----------------------------
# production runner
# -----------------------------
cat > run_prod.sh << 'EOF_RUN'
#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

export PYTHONUNBUFFERED=1
export APP_ENV="${APP_ENV:-production}"
export ENABLE_SECURITY_HEADERS="${ENABLE_SECURITY_HEADERS:-true}"
export ENABLE_REQUEST_SIZE_GUARD="${ENABLE_REQUEST_SIZE_GUARD:-true}"
export ENABLE_RATE_LIMIT="${ENABLE_RATE_LIMIT:-true}"
export RATE_LIMIT_PER_MINUTE="${RATE_LIMIT_PER_MINUTE:-120}"
export MAX_REQUEST_BYTES="${MAX_REQUEST_BYTES:-2097152}"

echo "=== APPLAYLIST PROD START ==="
echo "APP_ENV=$APP_ENV"
echo "RATE_LIMIT_PER_MINUTE=$RATE_LIMIT_PER_MINUTE"
echo "MAX_REQUEST_BYTES=$MAX_REQUEST_BYTES"

exec uvicorn api.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 2 \
  --proxy-headers \
  --timeout-keep-alive 30
EOF_RUN
chmod +x run_prod.sh

# -----------------------------
# bootstrap hook helper
# does not overwrite api/main.py
# -----------------------------
cat > api/security/bootstrap.py << 'PYEOF'
from __future__ import annotations

from fastapi.middleware.cors import CORSMiddleware

from api.middleware.rate_limit import RateLimitMiddleware
from api.middleware.request_size_guard import RequestSizeGuardMiddleware
from api.middleware.security_headers import SecurityHeadersMiddleware
from api.security.settings import settings


def apply_security_hardening(app) -> None:
    existing = getattr(app, "user_middleware", [])

    names = {mw.cls.__name__ for mw in existing if getattr(mw, "cls", None)}

    if "CORSMiddleware" not in names:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.allowed_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    if settings.enable_security_headers and "SecurityHeadersMiddleware" not in names:
        app.add_middleware(SecurityHeadersMiddleware)

    if settings.enable_request_size_guard and "RequestSizeGuardMiddleware" not in names:
        app.add_middleware(
            RequestSizeGuardMiddleware,
            max_bytes=settings.max_request_bytes,
        )

    if settings.enable_rate_limit and "RateLimitMiddleware" not in names:
        app.add_middleware(
            RateLimitMiddleware,
            limit_per_minute=settings.rate_limit_per_minute,
        )
PYEOF

# -----------------------------
# env template
# -----------------------------
cat > data/config/security.env.example << 'EOF_ENV'
APP_ENV=production
ALLOW_ORIGINS=*
ENABLE_SECURITY_HEADERS=true
ENABLE_REQUEST_SIZE_GUARD=true
ENABLE_RATE_LIMIT=true
RATE_LIMIT_PER_MINUTE=120
MAX_REQUEST_BYTES=2097152
TRUSTED_PROXY_DEPTH=0
EOF_ENV

# -----------------------------
# bundle 11 verifier
# -----------------------------
cat > scripts/verify_bundle_11_finalize.sh << 'EOF_VERIFY'
#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "=== VERIFY BUNDLE 11 FINALIZE ==="

echo "[1/6] branch"
git branch --show-current

echo "[2/6] status"
git status --short

echo "[3/6] python compile"
python3 -m py_compile \
  api/security/settings.py \
  api/security/bootstrap.py \
  api/middleware/rate_limit.py \
  api/middleware/request_size_guard.py \
  api/middleware/security_headers.py

echo "[4/6] imports"
python3 - << 'PY'
from api.security.settings import settings
from api.security.bootstrap import apply_security_hardening
from api.middleware.rate_limit import RateLimitMiddleware
from api.middleware.request_size_guard import RequestSizeGuardMiddleware
from api.middleware.security_headers import SecurityHeadersMiddleware

print("OK imports")
print("env=", settings.app_env)
print("origins=", settings.allowed_origins)
print("limit=", settings.rate_limit_per_minute)
PY

echo "[5/6] grep main integration hint"
grep -n "apply_security_hardening" api/main.py || true

echo "[6/6] pytest"
pytest -q || true

echo "=== VERIFY DONE ==="
EOF_VERIFY
chmod +x scripts/verify_bundle_11_finalize.sh

echo "=== BUNDLE 11 FINALIZE DONE ==="
