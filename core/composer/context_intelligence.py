from __future__ import annotations

from typing import Dict, Tuple, List

from core.composer.energy_context import resolve_energy_context
from core.composer.intelligence_hook import intelligence_contribution


def contextual_score(track: Dict, index: int, total: int) -> Tuple[float, List[Dict]]:
    context = resolve_energy_context(track, index, total)
    return intelligence_contribution(track, context=context)
