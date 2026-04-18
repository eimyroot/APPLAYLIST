#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

mkdir -p core/composer tests

# ---- ENERGY CONTEXT ----
cat > core/composer/energy_context.py << 'PY'
from __future__ import annotations

from typing import Dict
from core.composer.context_resolver import resolve_context


def resolve_energy_context(track: Dict, index: int, total: int) -> str:
    intelligence = track.get("intelligence", {})
    energy = intelligence.get("energy_score")

    if energy is None:
        return resolve_context(index, total)

    if energy < 0.4:
        return "warmup"
    if energy < 0.75:
        return "peak"
    return "peak"
PY

# ---- INTEGRATION ----
cat > core/composer/context_intelligence.py << 'PY'
from __future__ import annotations

from typing import Dict, Tuple, List

from core.composer.energy_context import resolve_energy_context
from core.composer.intelligence_hook import intelligence_contribution


def contextual_score(track: Dict, index: int, total: int) -> Tuple[float, List[Dict]]:
    context = resolve_energy_context(track, index, total)
    return intelligence_contribution(track, context=context)
PY

# ---- TESTS ----
cat > tests/test_energy_context.py << 'PY'
from core.composer.energy_context import resolve_energy_context


def test_low_energy():
    t = {"intelligence": {"energy_score": 0.2}}
    assert resolve_energy_context(t, 5, 10) == "warmup"


def test_mid_energy():
    t = {"intelligence": {"energy_score": 0.5}}
    assert resolve_energy_context(t, 5, 10) == "peak"


def test_high_energy():
    t = {"intelligence": {"energy_score": 0.9}}
    assert resolve_energy_context(t, 5, 10) == "peak"


def test_fallback():
    t = {}
    ctx = resolve_energy_context(t, 9, 10)
    assert ctx in ["warmup", "peak", "closing"]
PY

# ---- VERIFY ----
cat > scripts/verify_bundle_23.sh << 'EOF_VERIFY'
#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [ -x ".venv/bin/python" ]; then
  PY=".venv/bin/python"
else
  PY="$(command -v python3)"
fi

echo "=== VERIFY BUNDLE 23 ==="
echo "[python] $PY"

echo "[1] branch"
git branch --show-current

echo "[2] compile"
"$PY" -m py_compile core/composer/energy_context.py

echo "[3] tests"
"$PY" -m pytest -q tests/test_energy_context.py

echo "=== VERIFY DONE ==="
EOF_VERIFY

chmod +x scripts/verify_bundle_23.sh

echo "=== BUNDLE 23 PATCH DONE ==="
