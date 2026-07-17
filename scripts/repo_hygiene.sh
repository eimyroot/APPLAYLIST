#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

if [ -x "$ROOT/.venv/bin/python" ]; then
  PYTHON="$ROOT/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON="$(command -v python3)"
else
  echo "ERROR: python3 was not found" >&2
  exit 127
fi

export PYTHONPYCACHEPREFIX="$ROOT/.repo-hygiene/verify-pycache"
mkdir -p "$PYTHONPYCACHEPREFIX"

cd "$ROOT"
exec "$PYTHON" -m tools.repo_hygiene --root "$ROOT" "$@"
