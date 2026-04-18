from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class CanonicalMirAnalysis:
    path: str
    provider: str
    bpm: Optional[float]
    bpm_confidence: Optional[float]
    key: Optional[str]
    key_confidence: Optional[float]
    energy: Optional[float]
    loudness_db: Optional[float]
    duration_seconds: Optional[float]
    genre_hint: Optional[str]
    analysis_status: str
    analysis_version: str = "canonical-mir-v1"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
