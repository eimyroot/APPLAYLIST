#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

mkdir -p core/intelligence tests

cat > core/intelligence/track_intelligence.py << 'PY'
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict


@dataclass
class Reason:
    code: str
    label: str
    weight: float


def compute_intelligence(track: Dict) -> Dict:
    bpm = track.get("bpm", 0)
    energy = track.get("energy", 0)
    key = track.get("key", "")

    reasons: List[Reason] = []

    # BPM stability heuristic
    if 120 <= bpm <= 135:
        reasons.append(Reason("bpm_range", "Ideal club BPM range", 0.25))

    # Energy heuristic
    if energy > 0.7:
        reasons.append(Reason("high_energy", "Strong energy presence", 0.35))

    # Key presence
    if key:
        reasons.append(Reason("key_defined", "Harmonic key detected", 0.2))

    score = sum(r.weight for r in reasons)

    return {
        "club_readiness_score": round(score, 2),
        "mixability_score": round(score * 0.9, 2),
        "energy_confidence": round(energy, 2),
        "reasons": [r.__dict__ for r in reasons],
    }
PY

cat > tests/test_track_intelligence.py << 'PY'
from core.intelligence.track_intelligence import compute_intelligence


def test_intelligence_basic():
    track = {
        "bpm": 128,
        "energy": 0.8,
        "key": "10A"
    }

    result = compute_intelligence(track)

    assert "club_readiness_score" in result
    assert result["club_readiness_score"] > 0
    assert len(result["reasons"]) > 0
PY

cat > scripts/verify_bundle_17.sh << 'EOF_VERIFY'
#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "=== VERIFY BUNDLE 17 ==="

echo "[1] branch"
git branch --show-current

echo "[2] compile"
python3 -m py_compile core/intelligence/track_intelligence.py

echo "[3] tests"
pytest -q tests/test_track_intelligence.py

echo "=== VERIFY DONE ==="
EOF_VERIFY
chmod +x scripts/verify_bundle_17.sh

echo "=== BUNDLE 17 PATCH DONE ==="
