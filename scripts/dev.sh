#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

source .venv/bin/activate
pip install -e ".[dev]"
cp -n .env.example .env || true

uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
