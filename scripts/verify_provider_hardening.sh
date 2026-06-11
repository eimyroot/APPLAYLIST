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
  core/analysis/provider_baseline.py \
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
    "core.analysis.provider_baseline",
]

for module in modules:
    importlib.import_module(module)
    print(f"OK import: {module}")

print("Provider core imports are safe.")
PY

echo "== Registry availability and metadata smoke check =="
.venv/bin/python - <<PY
from core.analysis import provider_registry

availability = provider_registry.get_provider_availability(["baseline"])
assert availability[0].provider == "baseline"
assert availability[0].is_available is True

metadata = provider_registry.get_provider_metadata(["baseline"])
assert metadata[0].name == "baseline"
assert metadata[0].optional_dependencies == ()

selection = provider_registry.select_available_provider(
    requested_provider=None,
    configured_default=None,
    safe_baseline="baseline",
    provider_names=["baseline"],
)
assert selection.provider == "baseline"

print("Registry availability and metadata smoke check passed.")
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
  tests/unit/test_provider_registry_availability.py \
  tests/unit/test_provider_registry_metadata.py \
  tests/unit/test_provider_baseline.py \
  tests/unit/test_provider_baseline_import_safety.py \
  -q

echo "== Full tests =="
.venv/bin/python -m pytest -q

echo "== PROVIDER HARDENING VERIFY PASSED =="
