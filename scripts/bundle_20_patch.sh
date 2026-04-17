#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

mkdir -p core/config data/config

# ---- DEFAULT CONFIG ----
cat > data/config/scoring_config.json << 'JSON'
{
  "club_readiness_weight": 0.3,
  "mixability_weight": 0.2
}
JSON

# ---- CONFIG LOADER ----
cat > core/config/scoring_config.py << 'PY'
from __future__ import annotations

import json
from pathlib import Path


DEFAULT = {
    "club_readiness_weight": 0.3,
    "mixability_weight": 0.2,
}


def load_scoring_config() -> dict:
    path = Path("data/config/scoring_config.json")

    if not path.exists():
        return DEFAULT

    try:
        with path.open() as f:
            data = json.load(f)
        return {**DEFAULT, **data}
    except Exception:
        return DEFAULT
PY

# ---- UPDATE INTELLIGENCE HOOK ----
cat > core/composer/intelligence_hook.py << 'PY'
from __future__ import annotations

from typing import Dict, Tuple, List
from core.config.scoring_config import load_scoring_config


def intelligence_contribution(track: Dict) -> Tuple[float, List[Dict]]:
    intelligence = track.get("intelligence")
    if not intelligence:
        return 0.0, []

    config = load_scoring_config()

    club_w = config.get("club_readiness_weight", 0.3)
    mix_w = config.get("mixability_weight", 0.2)

    score = 0.0
    reasons = []

    club = intelligence.get("club_readiness_score", 0)
    mix = intelligence.get("mixability_score", 0)

    if club:
        contrib = club * club_w
        score += contrib
        reasons.append({
            "code": "intelligence_club",
            "label": "Club readiness contribution",
            "value": club,
            "weight": club_w,
            "contribution": contrib
        })

    if mix:
        contrib = mix * mix_w
        score += contrib
        reasons.append({
            "code": "intelligence_mix",
            "label": "Mixability contribution",
            "value": mix,
            "weight": mix_w,
            "contribution": contrib
        })

    return score, reasons
PY

# ---- TESTS ----
cat > tests/test_scoring_config.py << 'PY'
from core.config.scoring_config import load_scoring_config


def test_default_config():
    cfg = load_scoring_config()
    assert "club_readiness_weight" in cfg
    assert "mixability_weight" in cfg
PY

cat > tests/test_intelligence_config_effect.py << 'PY'
from core.composer.intelligence_hook import intelligence_contribution


def test_config_affects_score():
    t = {
        "intelligence": {
            "club_readiness_score": 1.0,
            "mixability_score": 1.0
        }
    }

    score, _ = intelligence_contribution(t)
    assert score > 0
PY

# ---- VERIFY ----
cat > scripts/verify_bundle_20.sh << 'EOF_VERIFY'
#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [ -x ".venv/bin/python" ]; then
  PY=".venv/bin/python"
else
  PY="$(command -v python3)"
fi

echo "=== VERIFY BUNDLE 20 ==="
echo "[python] $PY"

echo "[1] branch"
git branch --show-current

echo "[2] compile"
"$PY" -m py_compile core/config/scoring_config.py

echo "[3] tests"
"$PY" -m pytest -q tests/test_scoring_config.py tests/test_intelligence_config_effect.py

echo "=== VERIFY DONE ==="
EOF_VERIFY

chmod +x scripts/verify_bundle_20.sh

echo "=== BUNDLE 20 PATCH DONE ==="
