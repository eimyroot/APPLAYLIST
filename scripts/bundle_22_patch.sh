#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

mkdir -p core/composer

# ---- CONTEXT RESOLVER ----
cat > core/composer/context_resolver.py << 'PY'
from __future__ import annotations


def resolve_context(index: int, total: int) -> str:
    if total <= 0:
        return "default"

    ratio = index / total

    if ratio < 0.3:
        return "warmup"
    elif ratio < 0.75:
        return "peak"
    else:
        return "closing"
PY

# ---- INTEGRATION WRAPPER ----
cat > core/composer/context_intelligence.py << 'PY'
from __future__ import annotations

from typing import Dict, Tuple, List

from core.composer.context_resolver import resolve_context
from core.composer.intelligence_hook import intelligence_contribution


def contextual_score(track: Dict, index: int, total: int) -> Tuple[float, List[Dict]]:
    context = resolve_context(index, total)
    return intelligence_contribution(track, context=context)
PY

# ---- TESTS ----
cat > tests/test_context_resolver.py << 'PY'
from core.composer.context_resolver import resolve_context


def test_warmup():
    assert resolve_context(1, 10) == "warmup"


def test_peak():
    assert resolve_context(5, 10) == "peak"


def test_closing():
    assert resolve_context(9, 10) == "closing"
PY

cat > tests/test_context_integration.py << 'PY'
from core.composer.context_intelligence import contextual_score


def test_context_changes_score():
    t = {
        "intelligence": {
            "club_readiness_score": 1.0,
            "mixability_score": 1.0
        }
    }

    s1, _ = contextual_score(t, 1, 10)
    s2, _ = contextual_score(t, 9, 10)

    assert s1 != s2
PY

# ---- VERIFY ----
cat > scripts/verify_bundle_22.sh << 'EOF_VERIFY'
#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [ -x ".venv/bin/python" ]; then
  PY=".venv/bin/python"
else
  PY="$(command -v python3)"
fi

echo "=== VERIFY BUNDLE 22 ==="
echo "[python] $PY"

echo "[1] branch"
git branch --show-current

echo "[2] compile"
"$PY" -m py_compile core/composer/context_resolver.py

echo "[3] tests"
"$PY" -m pytest -q tests/test_context_resolver.py tests/test_context_integration.py

echo "=== VERIFY DONE ==="
EOF_VERIFY

chmod +x scripts/verify_bundle_22.sh

echo "=== BUNDLE 22 PATCH DONE ==="
