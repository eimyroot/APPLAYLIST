#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

# ---- CONFIG UPDATE ----
cat > data/config/scoring_config.json << 'JSON'
{
  "default": {
    "club_readiness_weight": 0.3,
    "mixability_weight": 0.2
  },
  "warmup": {
    "club_readiness_weight": 0.15,
    "mixability_weight": 0.25
  },
  "peak": {
    "club_readiness_weight": 0.5,
    "mixability_weight": 0.2
  },
  "closing": {
    "club_readiness_weight": 0.2,
    "mixability_weight": 0.3
  }
}
JSON

# ---- CONFIG LOADER ----
cat > core/config/scoring_config.py << 'PY'
from __future__ import annotations

import json
from pathlib import Path


DEFAULT_CONTEXT = "default"

DEFAULT = {
    "default": {
        "club_readiness_weight": 0.3,
        "mixability_weight": 0.2,
    }
}


def load_scoring_config(context: str | None = None) -> dict:
    path = Path("data/config/scoring_config.json")

    if not path.exists():
        cfg = DEFAULT
    else:
        try:
            with path.open() as f:
                cfg = json.load(f)
        except Exception:
            cfg = DEFAULT

    ctx = context or DEFAULT_CONTEXT

    if ctx in cfg:
        return cfg[ctx]

    return cfg.get("default", DEFAULT["default"])
PY

# ---- UPDATE HOOK ----
cat > core/composer/intelligence_hook.py << 'PY'
from __future__ import annotations

from typing import Dict, Tuple, List
from core.config.scoring_config import load_scoring_config


def intelligence_contribution(track: Dict, context: str | None = None) -> Tuple[float, List[Dict]]:
    intelligence = track.get("intelligence")
    if not intelligence:
        return 0.0, []

    cfg = load_scoring_config(context)

    club_w = cfg.get("club_readiness_weight", 0.3)
    mix_w = cfg.get("mixability_weight", 0.2)

    score = 0.0
    reasons = []

    club = intelligence.get("club_readiness_score", 0)
    mix = intelligence.get("mixability_score", 0)

    if club:
        contrib = club * club_w
        score += contrib
        reasons.append({
            "code": "intelligence_club",
            "label": f"Club readiness ({context or 'default'})",
            "value": club,
            "weight": club_w,
            "contribution": contrib
        })

    if mix:
        contrib = mix * mix_w
        score += contrib
        reasons.append({
            "code": "intelligence_mix",
            "label": f"Mixability ({context or 'default'})",
            "value": mix,
            "weight": mix_w,
            "contribution": contrib
        })

    return score, reasons
PY

# ---- TESTS ----
cat > tests/test_context_scoring.py << 'PY'
from core.composer.intelligence_hook import intelligence_contribution


def test_default_context():
    t = {"intelligence": {"club_readiness_score": 1.0, "mixability_score": 1.0}}
    score, _ = intelligence_contribution(t)
    assert score > 0


def test_peak_vs_warmup():
    t = {"intelligence": {"club_readiness_score": 1.0, "mixability_score": 1.0}}

    s_peak, _ = intelligence_contribution(t, context="peak")
    s_warm, _ = intelligence_contribution(t, context="warmup")

    assert s_peak > s_warm
PY

# ---- VERIFY ----
cat > scripts/verify_bundle_21.sh << 'EOF_VERIFY'
#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [ -x ".venv/bin/python" ]; then
  PY=".venv/bin/python"
else
  PY="$(command -v python3)"
fi

echo "=== VERIFY BUNDLE 21 ==="
echo "[python] $PY"

echo "[1] branch"
git branch --show-current

echo "[2] compile"
"$PY" -m py_compile core/config/scoring_config.py

echo "[3] tests"
"$PY" -m pytest -q tests/test_context_scoring.py

echo "=== VERIFY DONE ==="
EOF_VERIFY

chmod +x scripts/verify_bundle_21.sh

echo "=== BUNDLE 21 PATCH DONE ==="
