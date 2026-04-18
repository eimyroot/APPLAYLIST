#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
source .venv/bin/activate

python3 - <<'PY'
from data.repositories.track_repository import TrackRepository
from data.repositories.analysis_repository import AnalysisRepository
from data.repositories.job_repository import JobRepository

TrackRepository().ensure_schema()
AnalysisRepository().ensure_schema()
JobRepository().ensure_schema()

print("OK: local SQLite schema initialized")
PY
