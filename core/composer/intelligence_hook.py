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
