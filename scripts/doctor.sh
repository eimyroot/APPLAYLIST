#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

PY="${APPLAYLIST_PYTHON:-.venv/bin/python}"
[ -x "$PY" ] || {
  printf 'BLOCKED=PROJECT_PYTHON_NOT_EXECUTABLE path=%s\n' "$PY" >&2
  exit 20
}

VERSION="$("$PY" -c 'import sys; print(".".join(map(str, sys.version_info[:3])))')"
case "$VERSION" in
  3.11.*|3.12.*) ;;
  *)
    printf 'BLOCKED=UNSUPPORTED_PROJECT_PYTHON version=%s\n' "$VERSION" >&2
    exit 21
    ;;
esac

test "$(tr -d '[:space:]' < .python-version)" = "3.11" || {
  printf 'BLOCKED=DOT_PYTHON_VERSION_POLICY_CHANGED\n' >&2
  exit 22
}

grep -Fq 'requires-python = ">=3.11,<3.13"' pyproject.toml || {
  printf 'BLOCKED=PYPROJECT_PYTHON_POLICY_CHANGED\n' >&2
  exit 23
}

test -s requirements.lock || {
  printf 'BLOCKED=REQUIREMENTS_LOCK_MISSING\n' >&2
  exit 24
}

grep -q -- '--hash=sha256:' requirements.lock || {
  printf 'BLOCKED=REQUIREMENTS_LOCK_HAS_NO_HASHES\n' >&2
  exit 25
}

"$PY" -m pip check

"$PY" -m ruff --version
"$PY" -m mypy --version
"$PY" -m bandit --version
"$PY" - <<'PY_VERSION'
from importlib.metadata import version

expected = {
    "ruff": "0.15.22",
    "mypy": "2.3.0",
    "bandit": "1.9.4",
    "pip-tools": "7.6.0",
    "pip": "26.1.2",
    "setuptools": "83.0.0",
    "wheel": "0.47.0",
}

for package, wanted in expected.items():
    actual = version(package)
    if actual != wanted:
        print(
            f"BLOCKED=TOOL_VERSION_MISMATCH package={package} "
            f"expected={wanted} actual={actual}"
        )
        raise SystemExit(30)
    print(f"{package} {actual}")
PY_VERSION

printf 'DOCTOR=PASS\n'
printf 'ROOT=%s\n' "$ROOT"
printf 'PYTHON=%s\n' "$PY"
printf 'PYTHON_VERSION=%s\n' "$VERSION"
printf 'LOCK_SHA256=%s\n' "$(shasum -a 256 requirements.lock | awk '{print $1}')"
