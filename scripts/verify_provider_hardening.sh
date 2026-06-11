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
  core/analysis/provider_errors.py \
  core/analysis/provider_contracts.py \
  core/analysis/provider_selection.py \
  core/analysis/provider_registry_bridge.py \
  docs/architecture/APPLAYLIST_PROVIDER_HARDENING.md \
  docs/ops/PROVIDER_HARDENING_RUNBOOK.md
do
  test -f "$f" || { echo "ERROR: missing $f"; exit 1; }
  echo "OK: $f"
done

echo "== Import safety check =="
.venv/bin/python - <<PY
import importlib

modules = [
    "core.analysis.normalize",
    "core.analysis.provider_registry",
    "core.analysis.provider_errors",
    "core.analysis.provider_contracts",
    "core.analysis.provider_selection",
    "core.analysis.provider_registry_bridge",
]

for module in modules:
    importlib.import_module(module)
    print(f"OK import: {module}")

print("Provider core imports are safe.")
PY

echo "== Optional dependency visibility check =="
.venv/bin/python - <<PY
import importlib.util

for name in ["librosa", "numba", "llvmlite", "essentia"]:
    print(name + ": " + ("installed" if importlib.util.find_spec(name) else "not installed"))
PY

echo "== Targeted provider tests =="
.venv/bin/python -m pytest \
  tests/unit/test_provider_import_safety.py \
  tests/unit/test_provider_errors.py \
  tests/unit/test_provider_contracts.py \
  tests/unit/test_provider_selection.py \
  tests/unit/test_provider_registry_bridge.py \
  -q

echo "== Full tests =="
.venv/bin/python -m pytest -q

echo "== PROVIDER HARDENING VERIFY PASSED =="
