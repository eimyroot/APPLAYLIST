#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
PY="${APPLAYLIST_PYTHON:-.venv/bin/python}"
BASELINE="tools/quality/mypy-baseline.txt"

[ -x "$PY" ] || { printf 'BLOCKED=PYTHON_MISSING\n' >&2; exit 20; }
test -f "$BASELINE" || { printf 'BLOCKED=MYPY_BASELINE_MISSING\n' >&2; exit 21; }

TMP="$(mktemp "${TMPDIR:-/tmp}/applaylist-mypy.XXXXXX")"
trap 'rm -f "$TMP" "$TMP.sorted"' EXIT

set +e
"$PY" -m mypy api core services data workers \
  --no-error-summary --show-error-codes >"$TMP" 2>&1
RC=$?
set -e

if [ "$RC" -gt 1 ]; then
  cat "$TMP" >&2
  printf 'BLOCKED=MYPY_OPERATIONAL_FAILURE rc=%s\n' "$RC" >&2
  exit 22
fi

LC_ALL=C sort "$TMP" >"$TMP.sorted"

if ! cmp -s "$BASELINE" "$TMP.sorted"; then
  printf 'MYPY_BASELINE_DIFF_BEGIN\n'
  diff -u "$BASELINE" "$TMP.sorted" || true
  printf 'MYPY_BASELINE_DIFF_END\n'
  printf 'BLOCKED=MYPY_BASELINE_REGRESSION\n' >&2
  exit 23
fi

COUNT="$(grep -c ' error:' "$BASELINE" 2>/dev/null || true)"
printf 'TYPE_GATE=PASS_DIFFERENTIAL_BASELINE\n'
printf 'MYPY_BASELINE_ERROR_LINES=%s\n' "$COUNT"
