#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

mkdir -p core/composer

cat > core/composer/intelligence_hook.py << 'PY'
from __future__ import annotations

from typing import Dict, Tuple, List


def intelligence_contribution(track: Dict) -> Tuple[float, List[Dict]]:
    intelligence = track.get("intelligence")

    if not intelligence:
        return 0.0, []

    score = 0.0
    reasons = []

    club = intelligence.get("club_readiness_score", 0)
    mix = intelligence.get("mixability_score", 0)

    if club:
        contrib = club * 0.3
        score += contrib
        reasons.append({
            "code": "intelligence_club",
            "label": "Club readiness contribution",
            "value": club,
            "weight": 0.3,
            "contribution": contrib
        })

    if mix:
        contrib = mix * 0.2
        score += contrib
        reasons.append({
            "code": "intelligence_mix",
            "label": "Mixability contribution",
            "value": mix,
            "weight": 0.2,
            "contribution": contrib
        })

    return score, reasons
PY


cat > tests/test_intelligence_hook.py << 'PY'
from core.composer.intelligence_hook import intelligence_contribution


def test_no_intelligence():
    track = {}
    score, reasons = intelligence_contribution(track)

    assert score == 0
    assert reasons == []


def test_with_intelligence():
    track = {
        "intelligence": {
            "club_readiness_score": 0.8,
            "mixability_score": 0.6
        }
    }

    score, reasons = intelligence_contribution(track)

    assert score > 0
    assert len(reasons) == 2


def test_prefer_higher_intelligence():
    t1 = {
        "intelligence": {
            "club_readiness_score": 0.4,
            "mixability_score": 0.4
        }
    }

    t2 = {
        "intelligence": {
            "club_readiness_score": 0.9,
            "mixability_score": 0.8
        }
    }

    s1, _ = intelligence_contribution(t1)
    s2, _ = intelligence_contribution(t2)

    assert s2 > s1
PY


cat > scripts/verify_bundle_18.sh << 'EOF_VERIFY'
#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [ -x ".venv/bin/python" ]; then
  PY=".venv/bin/python"
else
  PY="$(command -v python3)"
fi

echo "=== VERIFY BUNDLE 18 ==="
echo "[python] $PY"

echo "[1] branch"
git branch --show-current

echo "[2] compile"
"$PY" -m py_compile core/composer/intelligence_hook.py

echo "[3] tests"
"$PY" -m pytest -q tests/test_intelligence_hook.py

echo "=== VERIFY DONE ==="
EOF_VERIFY

chmod +x scripts/verify_bundle_18.sh

echo "=== BUNDLE 18 PATCH DONE ==="
