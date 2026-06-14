#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "== APPLAYLIST PROVIDER ROLLOUT READINESS VERIFY =="
echo "Root: $ROOT"

echo "== Required files =="
for f in \
  core/analysis/provider_feature_flags.py \
  services/analysis/routed_analysis_service.py \
  services/analysis/provider_analysis_service.py \
  core/analysis/provider_orchestrator.py \
  docs/architecture/APPLAYLIST_PROVIDER_ANALYSIS_ROLLOUT.md \
  docs/ops/PROVIDER_ANALYSIS_ROLLOUT_RUNBOOK.md \
  scripts/verify_provider_hardening.sh
do
  test -f "$f" || { echo "ERROR: missing $f"; exit 1; }
  echo "OK: $f"
done

echo "== Feature flag default safety =="
.venv/bin/python - <<PY
from core.analysis.provider_feature_flags import provider_analysis_mode

assert provider_analysis_mode({}) == "legacy"
assert provider_analysis_mode({"APPLAYLIST_PROVIDER_ANALYSIS_ENABLED": "0"}) == "legacy"
assert provider_analysis_mode({"APPLAYLIST_PROVIDER_ANALYSIS_ENABLED": "maybe"}) == "legacy"
assert provider_analysis_mode({"APPLAYLIST_PROVIDER_ANALYSIS_ENABLED": "1"}) == "provider"

print("Feature flag default safety passed.")
PY

echo "== Routed service import check =="
.venv/bin/python - <<PY
import importlib

for module in [
    "services.analysis.routed_analysis_service",
    "services.analysis.provider_analysis_service",
    "core.analysis.provider_orchestrator",
]:
    importlib.import_module(module)
    print(f"OK import: {module}")

print("Routed service import check passed.")
PY

echo "== Targeted rollout tests =="
.venv/bin/python -m pytest \
  tests/unit/test_provider_feature_flags.py \
  tests/unit/test_routed_analysis_service.py \
  tests/unit/test_provider_analysis_service.py \
  tests/unit/test_provider_orchestrator.py \
  -q

echo "== Provider hardening verify =="
scripts/verify_provider_hardening.sh

echo "== Full tests =="
.venv/bin/python -m pytest -q

echo "== PROVIDER ROLLOUT READINESS PASSED =="
