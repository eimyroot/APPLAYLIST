#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

BOOTSTRAP_PYTHON="${1:-python3.12}"
VENV_DIR="${2:-.venv}"

command -v "$BOOTSTRAP_PYTHON" >/dev/null 2>&1 || {
  printf 'BLOCKED=BOOTSTRAP_PYTHON_NOT_FOUND value=%s\n' "$BOOTSTRAP_PYTHON" >&2
  exit 20
}

VERSION="$("$BOOTSTRAP_PYTHON" -c 'import sys; print(".".join(map(str, sys.version_info[:3])))')"
case "$VERSION" in
  3.11.*|3.12.*) ;;
  *)
    printf 'BLOCKED=UNSUPPORTED_PYTHON version=%s\n' "$VERSION" >&2
    exit 21
    ;;
esac

test -f requirements.lock || {
  printf 'BLOCKED=REQUIREMENTS_LOCK_MISSING\n' >&2
  exit 22
}

if [ -e "$VENV_DIR" ]; then
  printf 'BLOCKED=VENV_ALREADY_EXISTS path=%s\n' "$VENV_DIR" >&2
  exit 23
fi

"$BOOTSTRAP_PYTHON" -m venv "$VENV_DIR"
PY="$VENV_DIR/bin/python"
"$PY" -m pip install --require-hashes -r requirements.lock
"$PY" -m pip install --no-build-isolation --no-deps -e .
"$PY" -m pip check

printf 'BOOTSTRAP=PASS\n'
printf 'PYTHON=%s\n' "$PY"
printf 'PYTHON_VERSION=%s\n' "$VERSION"
