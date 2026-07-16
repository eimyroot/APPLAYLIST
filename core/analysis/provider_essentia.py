from __future__ import annotations

import os
from typing import Any, Dict


def essentia_enabled() -> bool:
    return os.getenv("APPLAYLIST_ENABLE_ESSENTIA", "0") == "1"


def essentia_available() -> bool:
    if not essentia_enabled():
        return False
    try:
        import essentia  # noqa: F401
        return True
    except Exception:
        return False


def analyze_with_essentia(path: str) -> Dict[str, Any]:
    if not essentia_enabled():
        raise RuntimeError("Essentia provider disabled. Set APPLAYLIST_ENABLE_ESSENTIA=1")
    if not essentia_available():
        raise RuntimeError("Essentia provider not available in current environment")

    # Bundle 25: safe integration layer.
    # Rich DSP extraction can be expanded later without changing downstream contract.
    return {
        "provider": "essentia",
        "source_path": path,
        "provider_version": None,
        "rhythm_bpm": None,
        "key_key": None,
        "key_strength": None,
        "loudness_energy": None,
        "warnings": [
            "Essentia provider integration active, but rich extraction is intentionally deferred in this bundle."
        ],
    }
