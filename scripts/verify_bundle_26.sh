#!/usr/bin/env bash
set -euo pipefail

REPO="/Users/eimy/APPLAYLIST!"
cd "$REPO"

echo "[python] $(command -v python3 || true)"
if [ -d ".venv" ]; then
  . .venv/bin/activate
elif [ -d "venv" ]; then
  . venv/bin/activate
fi

echo "[1] compile"
python3 -m compileall core/analysis

echo "[2] tests"
python3 -m pytest -q \
  tests/unit/test_provider_essentia.py \
  tests/unit/test_provider_registry.py \
  tests/unit/test_analysis_normalize_essentia.py \
  tests/unit/test_benchmark_compare.py

echo "=== VERIFY DONE ==="
