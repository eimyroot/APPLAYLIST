#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
PY="${APPLAYLIST_PYTHON:-.venv/bin/python}"
BASELINE="tools/quality/bandit-baseline.txt"

[ -x "$PY" ] || { printf 'BLOCKED=PYTHON_MISSING\n' >&2; exit 20; }
test -f "$BASELINE" || { printf 'BLOCKED=BANDIT_BASELINE_MISSING\n' >&2; exit 21; }

SECRET_PATHS="$(mktemp "${TMPDIR:-/tmp}/applaylist-secrets.XXXXXX")"
BANDIT_JSON="$(mktemp "${TMPDIR:-/tmp}/applaylist-bandit.XXXXXX")"
BANDIT_NORM="$(mktemp "${TMPDIR:-/tmp}/applaylist-bandit-norm.XXXXXX")"
trap 'rm -f "$SECRET_PATHS" "$BANDIT_JSON" "$BANDIT_NORM"' EXIT

set +e
git grep -Il -E \
  '(^|[^A-Za-z0-9])(AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9_-]{20,}|BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY)' \
  -- . ':!requirements.lock' >"$SECRET_PATHS" 2>/dev/null
SECRET_RC=$?
set -e

if [ "$SECRET_RC" -eq 0 ] && [ -s "$SECRET_PATHS" ]; then
  printf 'SECRET_LIKE_PATHS_BEGIN\n'
  cat "$SECRET_PATHS"
  printf 'SECRET_LIKE_PATHS_END\n'
  printf 'BLOCKED=HIGH_CONFIDENCE_SECRET_LIKE_PATHS\n' >&2
  exit 22
fi
if [ "$SECRET_RC" -gt 1 ]; then
  printf 'BLOCKED=SECRET_SCAN_OPERATIONAL_FAILURE\n' >&2
  exit 23
fi

set +e
"$PY" -m bandit -r api core services data workers -f json -o "$BANDIT_JSON" >/dev/null 2>&1
BANDIT_RC=$?
set -e
if [ "$BANDIT_RC" -gt 1 ]; then
  printf 'BLOCKED=BANDIT_OPERATIONAL_FAILURE rc=%s\n' "$BANDIT_RC" >&2
  exit 24
fi

"$PY" - "$BANDIT_JSON" "$BANDIT_NORM" <<'PY'
import json
import pathlib
import sys

source = pathlib.Path(sys.argv[1])
target = pathlib.Path(sys.argv[2])
data = json.loads(source.read_text(encoding="utf-8"))
rows = []
high = 0
for item in data.get("results", []):
    severity = str(item.get("issue_severity", "")).upper()
    if severity == "HIGH":
        high += 1
    filename = pathlib.Path(str(item.get("filename", "")))
    try:
        filename = filename.relative_to(pathlib.Path.cwd())
    except ValueError:
        pass
    rows.append(
        f"{filename}:{item.get('line_number')}:{item.get('test_id')}:"
        f"{severity}:{str(item.get('issue_confidence', '')).upper()}"
    )
rows.sort()
target.write_text("\n".join(rows) + ("\n" if rows else ""), encoding="utf-8")
print(f"BANDIT_HIGH_SEVERITY_FINDINGS={high}")
if high:
    raise SystemExit(10)
PY
NORM_RC=$?
if [ "$NORM_RC" -ne 0 ]; then
  printf 'BLOCKED=BANDIT_HIGH_SEVERITY_FINDING\n' >&2
  exit 25
fi

if ! cmp -s "$BASELINE" "$BANDIT_NORM"; then
  printf 'BANDIT_BASELINE_DIFF_BEGIN\n'
  diff -u "$BASELINE" "$BANDIT_NORM" || true
  printf 'BANDIT_BASELINE_DIFF_END\n'
  printf 'BLOCKED=BANDIT_BASELINE_REGRESSION\n' >&2
  exit 26
fi

COUNT="$(wc -l <"$BASELINE" | tr -d ' ')"
printf 'SECURITY_GATE=PASS_DIFFERENTIAL_BASELINE\n'
printf 'HIGH_CONFIDENCE_SECRET_SCAN=PASS\n'
printf 'BANDIT_BASELINE_FINDING_LINES=%s\n' "$COUNT"
