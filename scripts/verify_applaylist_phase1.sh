#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "== APPLAYLIST PHASE 1 VERIFY =="

if [ ! -x ".venv/bin/python" ]; then
  echo "ERROR: .venv/bin/python missing"
  exit 1
fi

.venv/bin/python - <<'PY'
import sys
print(sys.version)
if sys.version_info < (3, 11) or sys.version_info >= (3, 13):
    raise SystemExit("ERROR: APPLAYLIST requires Python >=3.11,<3.13")
PY

for f in \
  .python-version \
  pyproject.toml \
  constraints/audio-stack-py311.txt \
  docs/architecture/APPLAYLIST_PHASE1_ARCHITECTURE.md \
  docs/ops/LOCAL_DEV_RUNBOOK.md
do
  test -f "$f" || { echo "ERROR: missing $f"; exit 1; }
  echo "OK: $f"
done

BAD="$(find . \
  -path './.git' -prune -o \
  -path './.venv' -prune -o \
  -path './.local_backups' -prune -o \
  \( -name '.env' -o -name '*.db' -o -name '*.sqlite' -o -name '*.sqlite3' -o -name '.DS_Store' -o -name '* 2.py' \) \
  -print)"

if [ -n "$BAD" ]; then
  echo "$BAD"
  echo "ERROR: forbidden local/runtime files found"
  exit 1
fi

.venv/bin/python -m pytest -q

echo "== PHASE 1 VERIFY PASSED =="
