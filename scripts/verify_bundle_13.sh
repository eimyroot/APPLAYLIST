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
AUTH_ENABLED=false API_KEY= "$PY" -m pytest -q tests/test_route_wiring_guard.py

echo "[5/8] auth tests"
"$PY" -m pytest -q tests/test_auth_gate.py

echo "[6/8] request id tests"
AUTH_ENABLED=false API_KEY= "$PY" -m pytest -q tests/test_request_id_behavior.py

echo "[7/8] full tests"
AUTH_ENABLED=false API_KEY= "$PY" -m pytest -q

echo "[8/8] prod config probe"
AUTH_ENABLED=true API_KEY=probe-key APP_ENV=production "$PY" - << 'PY'
from api.security.settings import settings
print("app_env=", settings.app_env)
print("auth_enabled=", settings.auth_enabled)
print("header=", settings.api_key_header_name)
assert settings.auth_enabled is True
PY

echo "=== VERIFY DONE ==="
