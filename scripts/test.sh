#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install pytest httpx numpy scipy soundfile "librosa>=0.10,<0.11"
./scripts/init_local_db.sh
pytest -q
