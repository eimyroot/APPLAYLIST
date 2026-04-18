from __future__ import annotations

from typing import Dict, Any


def compare_provider_outputs(baseline: Dict[str, Any], candidate: Dict[str, Any]) -> Dict[str, Any]:
    bpm_delta = None
    if baseline.get("bpm") is not None and candidate.get("bpm") is not None:
        bpm_delta = abs(float(candidate["bpm"]) - float(baseline["bpm"]))

    same_key = None
    if baseline.get("key") is not None and candidate.get("key") is not None:
        same_key = baseline["key"] == candidate["key"]

    energy_delta = None
    if baseline.get("energy") is not None and candidate.get("energy") is not None:
        energy_delta = round(abs(float(candidate["energy"]) - float(baseline["energy"])), 6)

    return {
        "bpm_delta": bpm_delta,
        "same_key": same_key,
        "energy_delta": energy_delta,
    }
