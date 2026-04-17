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
