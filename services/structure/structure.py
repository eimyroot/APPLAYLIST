from __future__ import annotations

from dataclasses import dataclass
from typing import List

import librosa
import numpy as np


@dataclass
class StructurePoint:
    time: float
    label: str
    strength: float


@dataclass
class StructureResult:
    intro_end: float
    outro_start: float
    peak_time: float
    drop_candidates: List[StructurePoint]
    section_boundaries: List[StructurePoint]


class StructureAnalyzer:
    def analyze_file(self, path: str) -> StructureResult:
        y, sr = librosa.load(path, sr=22050, mono=True)

        onset_env = librosa.onset.onset_strength(y=y, sr=sr)
        rms = librosa.feature.rms(y=y)[0]
        times = librosa.times_like(onset_env, sr=sr)

        if len(times) == 0:
            return StructureResult(
                intro_end=0.0,
                outro_start=0.0,
                peak_time=0.0,
                drop_candidates=[],
                section_boundaries=[],
            )

        peak_idx = int(np.argmax(rms)) if len(rms) else 0
        peak_time = float(times[min(peak_idx, len(times) - 1)])

        intro_end = float(times[min(max(1, len(times) // 8), len(times) - 1)])
        outro_start = float(times[min(max(1, int(len(times) * 0.85)), len(times) - 1)])

        threshold = float(np.mean(onset_env) + np.std(onset_env)) if len(onset_env) else 0.0
        candidate_indices = [i for i, v in enumerate(onset_env) if v >= threshold]

        drop_candidates = [
            StructurePoint(
                time=float(times[i]),
                label="drop_candidate",
                strength=float(onset_env[i]),
            )
            for i in candidate_indices[:8]
        ]

        boundary_step = max(1, len(times) // 6)
        section_boundaries = []
        for i in range(boundary_step, len(times), boundary_step):
            idx = min(i, len(times) - 1)
            section_boundaries.append(
                StructurePoint(
                    time=float(times[idx]),
                    label="section_boundary",
                    strength=float(onset_env[idx]),
                )
            )

        return StructureResult(
            intro_end=intro_end,
            outro_start=outro_start,
            peak_time=peak_time,
            drop_candidates=drop_candidates,
            section_boundaries=section_boundaries,
        )
