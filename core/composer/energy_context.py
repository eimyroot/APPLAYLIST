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
