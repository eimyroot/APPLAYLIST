#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e .
cp -f .env.example .env
python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
