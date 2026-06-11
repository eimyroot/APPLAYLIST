#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "== APPLAYLIST PROVIDER HARDENING VERIFY =="
echo "Root: $ROOT"

echo "== Required provider files =="
for f in \
  core/analysis/normalize.py \
  core/analysis/provider_registry.py \
  core/analysis/provider_essentia.py \
  docs/architecture/APPLAYLIST_PROVIDER_HARDENING.md \
  docs/ops/PROVIDER_HARDENING_RUNBOOK.md
do
  test -f "$f" || { echo "ERROR: missing $f"; exit 1; }
  echo "OK: $f"
done

echo "== Import safety check =="
.venv/bin/python -c "import importlib; importlib.import_module("core.analysis.normalize"); importlib.import_module("core.analysis.provider_registry"); print("Provider registry core imports are safe.")"

echo "== Optional dependency visibility check =="
.venv/bin/python -c "import importlib.util; names=["librosa","numba","llvmlite"]; [print(name + ": " + ("installed" if importlib.util.find_spec(name) else "not installed")) for name in names]"

echo "== Tests =="
.venv/bin/python -m pytest -q

echo "== PROVIDER HARDENING VERIFY PASSED =="
