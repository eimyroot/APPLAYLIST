#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"

echo "== BUNDLE 11 HOTFIX START =="
echo "ROOT=$ROOT"

mkdir -p api/core api/middleware api/security data/config

touch api/core/__init__.py api/middleware/__init__.py api/security/__init__.py

cat << 'EOC' > api/core/logging_setup.py
import logging
import sys

def setup_logging() -> None:
    root = logging.getLogger()
    if root.handlers:
        return
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
EOC

cat << 'EOC' > api/security/guards.py
from __future__ import annotations

import os
import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import HTTPException, Request

_RATE_LIMIT = int(os.getenv("RATE_LIMIT_PER_MIN", "60"))
_ENABLE_AUTH = os.getenv("ENABLE_AUTH", "false").lower() == "true"
_API_KEY = os.getenv("API_KEY", "")
_MAX_REQUEST_SIZE_MB = int(os.getenv("MAX_REQUEST_SIZE_MB", "5"))

_hits: dict[str, deque[float]] = defaultdict(deque)
_lock = Lock()

def check_rate_limit(client_ip: str) -> None:
    now = time.time()
    window = 60.0
    with _lock:
        q = _hits[client_ip]
        while q and now - q[0] > window:
            q.popleft()
        if len(q) >= _RATE_LIMIT:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        q.append(now)

def check_auth(request: Request) -> None:
    if not _ENABLE_AUTH:
        return
    given = request.headers.get("x-api-key", "")
    if not _API_KEY or given != _API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")

def check_payload_size(request: Request) -> None:
    cl = request.headers.get("content-length")
    if not cl:
        return
    try:
        size = int(cl)
    except ValueError:
        return
    if size > _MAX_REQUEST_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Payload too large")
EOC

cat << 'EOC' > api/middleware/request_hardening.py
from __future__ import annotations

import asyncio
import os
import uuid

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from api.security.guards import check_auth, check_payload_size, check_rate_limit

class RequestHardeningMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        client_ip = request.client.host if request.client else "unknown"

        check_rate_limit(client_ip)
        check_auth(request)
        check_payload_size(request)

        timeout_sec = int(os.getenv("REQUEST_TIMEOUT_SEC", "30"))

        try:
            response = await asyncio.wait_for(call_next(request), timeout=timeout_sec)
        except asyncio.TimeoutError:
            return JSONResponse(
                status_code=504,
                content={"detail": "Request timeout", "request_id": request_id},
            )

        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        return response
EOC

if [ ! -f data/config/security.env ]; then
cat << 'EOC' > data/config/security.env
APP_ENV=production
API_KEY=CHANGE_ME_SUPER_SECRET
ENABLE_AUTH=true
RATE_LIMIT_PER_MIN=60
MAX_REQUEST_SIZE_MB=5
CORS_ORIGINS=http://localhost:5173
REQUEST_TIMEOUT_SEC=30
EOC
fi

python3 << 'PY'
from pathlib import Path
import re

p = Path("api/main.py")
if not p.exists():
    raise SystemExit("api/main.py not found")

text = p.read_text()

if "from api.core.logging_setup import setup_logging" not in text:
    text = "from api.core.logging_setup import setup_logging\n" + text

if "from api.middleware.request_hardening import RequestHardeningMiddleware" not in text:
    text = "from api.middleware.request_hardening import RequestHardeningMiddleware\n" + text

if "import os" not in text:
    text = "import os\n" + text

if "setup_logging()" not in text:
    text = text.replace("app = FastAPI(", "setup_logging()\n\napp = FastAPI(", 1)

if "app.add_middleware(RequestHardeningMiddleware)" not in text:
    marker = "app = FastAPI("
    idx = text.find(marker)
    if idx != -1:
        end_idx = text.find(")", idx)
        if end_idx != -1:
            text = text[: end_idx + 1] + "\n\napp.add_middleware(RequestHardeningMiddleware)\n" + text[end_idx + 1 :]

text = re.sub(
    r'allow_origins\s*=\s*\[[^\]]*\]',
    'allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")',
    text,
)

p.write_text(text)
print("patched api/main.py")
PY

cat << 'EOC' > run_prod.sh
#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"

if [ -f ".venv/bin/activate" ]; then
  . .venv/bin/activate
elif [ -f "venv/bin/activate" ]; then
  . venv/bin/activate
fi

if [ -f "data/config/security.env" ]; then
  set -a
  . data/config/security.env
  set +a
fi

PYTHON_BIN="${PYTHON_BIN:-python3}"

exec "$PYTHON_BIN" -m uvicorn api.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 1 \
  --timeout-keep-alive 30
EOC
chmod +x run_prod.sh

cat << 'EOC' > scripts/verify_bundle_11.sh
#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"

if [ -f ".venv/bin/activate" ]; then
  . .venv/bin/activate
elif [ -f "venv/bin/activate" ]; then
  . venv/bin/activate
fi

PYTHON_BIN="${PYTHON_BIN:-python3}"

echo "== ROOT =="
pwd

echo "== PYTHON =="
which "$PYTHON_BIN" || true
"$PYTHON_BIN" -V

echo "== IMPORT CHECK =="
"$PYTHON_BIN" - << 'PY'
import importlib
mods = [
    "fastapi",
    "uvicorn",
    "starlette",
    "api.main",
    "api.core.logging_setup",
    "api.middleware.request_hardening",
    "api.security.guards",
]
for m in mods:
    importlib.import_module(m)
    print("[OK]", m)
PY

echo "== ROUTE SMOKE =="
"$PYTHON_BIN" - << 'PY'
from api.main import app
print("[OK] app title:", getattr(app, "title", "N/A"))
print("[OK] middleware count:", len(getattr(app, "user_middleware", [])))
PY

echo "== VERIFY DONE =="
EOC
chmod +x scripts/verify_bundle_11.sh

echo "== BUNDLE 11 HOTFIX DONE =="
