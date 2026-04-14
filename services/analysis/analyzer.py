from __future__ import annotations

from pathlib import Path
from typing import Optional

import librosa
import numpy as np

from data.models.analysis_record import AnalysisRecord
from data.repositories.analysis_repository import AnalysisRepository


NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

CAMELOT_MAP = {
    ("Ab", "minor"): "1A", ("B", "major"): "1B",
    ("Eb", "minor"): "2A", ("F#", "major"): "2B",
    ("Bb", "minor"): "3A", ("Db", "major"): "3B",
    ("F", "minor"): "4A", ("Ab", "major"): "4B",
    ("C", "minor"): "5A", ("Eb", "major"): "5B",
    ("G", "minor"): "6A", ("Bb", "major"): "6B",
    ("D", "minor"): "7A", ("F", "major"): "7B",
    ("A", "minor"): "8A", ("C", "major"): "8B",
    ("E", "minor"): "9A", ("G", "major"): "9B",
    ("B", "minor"): "10A", ("D", "major"): "10B",
    ("F#", "minor"): "11A", ("A", "major"): "11B",
    ("C#", "minor"): "12A", ("E", "major"): "12B",
}

FLAT_EQUIV = {
    "G#": "Ab",
    "D#": "Eb",
    "A#": "Bb",
    "C#": "Db",
    "F#": "F#",
}


class AudioAnalyzer:
    def __init__(self) -> None:
        self.repo = AnalysisRepository()

    def _estimate_key_and_scale(self, chroma: np.ndarray) -> tuple[Optional[str], Optional[str], Optional[str]]:
        chroma_mean = chroma.mean(axis=1)
        if chroma_mean.size != 12:
            return None, None, None

        major_template = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
        minor_template = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])

        major_scores = []
        minor_scores = []
        for i in range(12):
            major_scores.append(float(np.dot(np.roll(chroma_mean, -i), major_template)))
            minor_scores.append(float(np.dot(np.roll(chroma_mean, -i), minor_template)))

        best_major = int(np.argmax(major_scores))
        best_minor = int(np.argmax(minor_scores))

        if max(major_scores) >= max(minor_scores):
            note = NOTE_NAMES[best_major]
            scale = "major"
        else:
            note = NOTE_NAMES[best_minor]
            scale = "minor"

        camelot_note = FLAT_EQUIV.get(note, note)
        camelot = CAMELOT_MAP.get((camelot_note, scale))
        return note, scale, camelot

    def analyze_file(self, track_id: str, path: str) -> AnalysisRecord:
        audio_path = Path(path)
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {path}")

        y, sr = librosa.load(str(audio_path), sr=22050, mono=True)

        tempo, _beats = librosa.beat.beat_track(y=y, sr=sr)
        rms = librosa.feature.rms(y=y)[0]
        centroid = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
        zcr = librosa.feature.zero_crossing_rate(y)[0]
        chroma = librosa.feature.chroma_cqt(y=y, sr=sr)

        key, scale, camelot = self._estimate_key_and_scale(chroma)

        rms_mean = float(np.mean(rms)) if rms.size else 0.0
        centroid_mean = float(np.mean(centroid)) if centroid.size else 0.0
        zcr_mean = float(np.mean(zcr)) if zcr.size else 0.0

        energy = max(0.0, min(1.0, (rms_mean * 4.0) + min(centroid_mean / 5000.0, 1.0) * 0.35))

        record = AnalysisRecord(
            track_id=track_id,
            analysis_version="0.1.0",
            features_version="0.1.0",
            extractor_backend="librosa",
            extractor_name="bundle-4-audio-analyzer",
            bpm=float(tempo) if tempo is not None else None,
            bpm_confidence=None,
            key=key,
            scale=scale,
            camelot=camelot,
            energy=energy,
            loudness_db=None,
            duration_seconds=float(librosa.get_duration(y=y, sr=sr)),
            harmonic_ratio=None,
            percussive_ratio=None,
        )

        self.repo.upsert(record)
        return record
