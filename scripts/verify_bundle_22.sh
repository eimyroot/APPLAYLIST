#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [ -x ".venv/bin/python" ]; then
  PY=".venv/bin/python"
else
  PY="$(command -v python3)"
fi

echo "=== VERIFY BUNDLE 22 ==="
echo "[python] $PY"

echo "[1] branch"
git branch --show-current

echo "[2] compile"
"$PY" -m py_compile core/composer/context_resolver.py

echo "[3] tests"
"$PY" -m pytest -q tests/test_context_resolver.py tests/test_context_integration.py

echo "=== VERIFY DONE ==="
