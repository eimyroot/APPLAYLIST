from __future__ import annotations

from math import sqrt
from typing import List, Optional

from data.models.analysis_record import AnalysisRecord


def _camelot_to_number(value: Optional[str]) -> float:
    if not value:
        return 0.0
    try:
        num = int(value[:-1])
        mode = value[-1]
        mode_val = 0.0 if mode == "A" else 1.0
        return (num / 12.0) + mode_val
    except Exception:
        return 0.0


def build_embedding(record: AnalysisRecord) -> List[float]:
    bpm = (record.bpm or 0.0) / 200.0
    energy = record.energy or 0.0
    duration = (record.duration_seconds or 0.0) / 600.0
    camelot = _camelot_to_number(record.camelot)

    harmonic_ratio = (record.harmonic_ratio or 0.0)
    percussive_ratio = (record.percussive_ratio or 0.0)

    vector = [
        round(bpm, 6),
        round(energy, 6),
        round(duration, 6),
        round(camelot, 6),
        round(harmonic_ratio, 6),
        round(percussive_ratio, 6),
    ]
    return vector


def cosine_similarity(a: List[float], b: List[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0

    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sqrt(sum(x * x for x in a))
    norm_b = sqrt(sum(y * y for y in b))

    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0

    return dot / (norm_a * norm_b)
