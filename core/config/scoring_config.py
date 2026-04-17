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
