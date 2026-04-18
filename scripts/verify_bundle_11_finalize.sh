#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "=== VERIFY BUNDLE 11 FINALIZE ==="

if [ -x ".venv/bin/python" ]; then
  PY=".venv/bin/python"
elif [ -x "venv/bin/python" ]; then
  PY="venv/bin/python"
else
  PY="$(command -v python3)"
fi

echo "[python] $PY"
"$PY" -V || true

echo "[1/8] branch"
git branch --show-current

echo "[2/8] status"
git status --short

echo "[3/8] compile"
"$PY" -m py_compile \
  api/security/settings.py \
  api/security/bootstrap.py \
  api/middleware/rate_limit.py \
  api/middleware/request_size_guard.py \
  api/middleware/security_headers.py

echo "[4/8] dependency probe"
"$PY" - << 'PY'
import importlib

mods = ["fastapi", "starlette"]
for mod in mods:
    try:
        importlib.import_module(mod)
        print(f"OK dependency: {mod}")
    except Exception as e:
        print(f"MISSING dependency: {mod} -> {e}")
        raise
PY

echo "[5/8] imports"
"$PY" - << 'PY'
from api.security.settings import settings
from api.security.bootstrap import apply_security_hardening
from api.middleware.rate_limit import RateLimitMiddleware
from api.middleware.request_size_guard import RequestSizeGuardMiddleware
from api.middleware.security_headers import SecurityHeadersMiddleware

print("OK imports")
print("env=", settings.app_env)
print("origins=", settings.allowed_origins)
print("limit=", settings.rate_limit_per_minute)
print("max_request_bytes=", settings.max_request_bytes)
PY

echo "[6/8] main integration hint"
grep -n "apply_security_hardening" api/main.py || true

echo "[7/8] app import"
"$PY" - << 'PY'
try:
    from api.main import app
    print("OK app import", app.title if hasattr(app, "title") else "no-title")
except Exception as e:
    print("APP IMPORT FAILED:", repr(e))
    raise
PY

echo "[8/8] pytest"
if "$PY" -m pytest -q; then
  echo "pytest passed"
else
  echo "pytest reported failures"
fi

echo "=== VERIFY DONE ==="
