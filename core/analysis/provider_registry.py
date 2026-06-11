from __future__ import annotations

from typing import Callable, Dict

from core.analysis.provider_essentia import analyze_with_essentia, essentia_available, essentia_enabled


def provider_capabilities() -> Dict[str, dict]:
    return {
        "essentia": {
            "enabled": essentia_enabled(),
            "available": essentia_available(),
            "canonical_mapping_ready": True,
            "extracts": ["bpm", "key", "energy", "lufs", "duration", "sample_rate"],
        }
    }


def provider_registry() -> Dict[str, Callable[[str], dict]]:
    registry: Dict[str, Callable[[str], dict]] = {}
    if essentia_enabled() and essentia_available():
        registry["essentia"] = analyze_with_essentia
    return registry
