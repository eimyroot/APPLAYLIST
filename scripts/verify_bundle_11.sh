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
