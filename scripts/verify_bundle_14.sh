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
