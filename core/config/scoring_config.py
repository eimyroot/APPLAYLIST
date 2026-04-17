from __future__ import annotations

import json
from pathlib import Path


DEFAULT_CONTEXT = "default"

DEFAULT = {
    "default": {
        "club_readiness_weight": 0.3,
        "mixability_weight": 0.2,
    }
}


def load_scoring_config(context: str | None = None) -> dict:
    path = Path("data/config/scoring_config.json")

    if not path.exists():
        cfg = DEFAULT
    else:
        try:
            with path.open() as f:
                cfg = json.load(f)
        except Exception:
            cfg = DEFAULT

    ctx = context or DEFAULT_CONTEXT

    if ctx in cfg:
        return cfg[ctx]

    return cfg.get("default", DEFAULT["default"])
