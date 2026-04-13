from pydantic import BaseModel
from typing import Optional


class TrackFeatures(BaseModel):
    bpm: Optional[float] = None
    bpm_confidence: Optional[float] = None
    key: Optional[str] = None
    scale: Optional[str] = None
    camelot: Optional[str] = None
    energy: Optional[float] = None
    loudness_db: Optional[float] = None
    duration_seconds: Optional[float] = None
    harmonic_ratio: Optional[float] = None
    percussive_ratio: Optional[float] = None


class TrackAnalysis(BaseModel):
    track_id: str
    analysis_version: str
    features_version: str
    extractor_backend: str
    extractor_name: str
    features: TrackFeatures
