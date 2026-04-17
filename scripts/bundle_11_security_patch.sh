#!/usr/bin/env bash
set -e

echo "== BUNDLE 11: SECURITY + HARDENING =="

########################################
# 1. ENV CONFIG
########################################

mkdir -p data/config

cat << 'EOC' > data/config/security.env
APP_ENV=production
API_KEY=CHANGE_ME_SUPER_SECRET
ENABLE_AUTH=true
RATE_LIMIT_PER_MIN=60
MAX_REQUEST_SIZE_MB=5
CORS_ORIGINS=http://localhost:5173
REQUEST_TIMEOUT_SEC=30
EOC

########################################
# 2. SECURITY MODULE
########################################

mkdir -p api/security

cat << 'EOC' > api/security/security.py
import os
import time
from fastapi import Request, HTTPException
from collections import defaultdict

RATE_LIMIT = int(os.getenv("RATE_LIMIT_PER_MIN", "60"))
ENABLE_AUTH = os.getenv("ENABLE_AUTH", "false").lower() == "true"
API_KEY = os.getenv("API_KEY", "")

requests_store = defaultdict(list)

def check_rate_limit(client_ip: str):
    now = time.time()
    window = 60

    requests_store[client_ip] = [
        t for t in requests_store[client_ip] if now - t < window
    ]

    if len(requests_store[client_ip]) >= RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    requests_store[client_ip].append(now)


def check_auth(request: Request):
    if not ENABLE_AUTH:
        return

    key = request.headers.get("x-api-key")
    if key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")


def enforce_size_limit(request: Request):
    max_mb = int(os.getenv("MAX_REQUEST_SIZE_MB", "5"))
    content_length = request.headers.get("content-length")

    if content_length and int(content_length) > max_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Payload too large")
EOC

########################################
# 3. MIDDLEWARE
########################################

mkdir -p api/middleware

cat << 'EOC' > api/middleware/security_middleware.py
import uuid
import asyncio
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from api.security.security import check_rate_limit, check_auth, enforce_size_limit

class SecurityMiddleware(BaseHTTPMiddleware):

    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        client_ip = request.client.host if request.client else "unknown"

        # SECURITY CHECKS
        check_rate_limit(client_ip)
        check_auth(request)
        enforce_size_limit(request)

        try:
            timeout = int(request.app.state.request_timeout)
            response = await asyncio.wait_for(call_next(request), timeout=timeout)
        except asyncio.TimeoutError:
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=504, content={"error": "Request timeout"})

        response.headers["X-Request-ID"] = request_id
        return response
EOC

########################################
# 4. LOGGING
########################################

mkdir -p api/core

cat << 'EOC' > api/core/logging.py
import logging
import sys

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)]
    )
EOC

########################################
# 5. MAIN PATCH
########################################

python3 << 'EOPY'
from pathlib import Path

main_file = Path("api/main.py")
content = main_file.read_text()

injections = """

# === SECURITY HARDENING ===
from api.middleware.security_middleware import SecurityMiddleware
from api.core.logging import setup_logging
import os

setup_logging()

app.add_middleware(SecurityMiddleware)

app.state.request_timeout = int(os.getenv("REQUEST_TIMEOUT_SEC", "30"))
"""

if "SECURITY HARDENING" not in content:
    content = content.replace("app = FastAPI(", "app = FastAPI(\n") + injections
    main_file.write_text(content)
EOPY

########################################
# 6. CORS HARDENING
########################################

python3 << 'EOPY'
from pathlib import Path
import re

main_file = Path("api/main.py")
content = main_file.read_text()

content = re.sub(r'allow_origins=\["\*"\]', 'allow_origins=os.getenv("CORS_ORIGINS", "").split(",")', content)

main_file.write_text(content)
EOPY

########################################
# 7. PROD RUN SCRIPT
########################################

cat << 'EOC' > run_prod.sh
#!/usr/bin/env bash

cd /Users/eimyna/applaylist

export $(cat data/config/security.env | xargs)

uvicorn api.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 2 \
    --timeout-keep-alive 30
EOC

chmod +x run_prod.sh

echo "== PATCH DONE =="
