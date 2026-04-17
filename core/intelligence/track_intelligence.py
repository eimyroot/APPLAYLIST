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
