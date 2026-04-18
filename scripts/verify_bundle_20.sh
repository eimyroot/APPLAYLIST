#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [ -x ".venv/bin/python" ]; then
  PY=".venv/bin/python"
else
  PY="$(command -v python3)"
fi

echo "=== VERIFY BUNDLE 20 ==="
echo "[python] $PY"

echo "[1] branch"
git branch --show-current

echo "[2] compile"
"$PY" -m py_compile core/config/scoring_config.py

echo "[3] tests"
"$PY" -m pytest -q tests/test_scoring_config.py tests/test_intelligence_config_effect.py

echo "=== VERIFY DONE ==="
