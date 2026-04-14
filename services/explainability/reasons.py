from __future__ import annotations

from typing import Dict, Any

from core.energy_curve import target_energy
from core.harmonic import camelot_compatible


def explain_transition(a: Any, b: Any, position: float) -> Dict[str, Any]:
    reasons = []

    if getattr(a, "bpm", None) and getattr(b, "bpm", None):
        diff = abs(a.bpm - b.bpm)
        reasons.append({
            "code": "bpm_delta",
            "value": round(diff, 3),
            "good": diff <= 5,
        })

    harmonic_ok = camelot_compatible(getattr(a, "camelot", None), getattr(b, "camelot", None))
    reasons.append({
        "code": "harmonic_compatible",
        "value": harmonic_ok,
        "good": harmonic_ok,
    })

    target = target_energy(position)
    energy = getattr(b, "energy", None)
    if energy is not None:
        reasons.append({
            "code": "energy_target_alignment",
            "value": round(abs(energy - target), 3),
            "good": abs(energy - target) <= 0.25,
        })

    return {
        "position": round(position, 3),
        "target_energy": round(target, 3),
        "reasons": reasons,
    }
