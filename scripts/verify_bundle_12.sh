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
