from pydantic import BaseModel
from typing import List, Optional


class PlaylistRequest(BaseModel):
    mode: str = "club"
    bpm_min: Optional[float] = None
    bpm_max: Optional[float] = None
    duration_minutes: Optional[int] = None
    target_track_count: Optional[int] = None


class PlaylistResult(BaseModel):
    playlist_id: str
    track_ids: List[str]
    score: float = 0.0
    issues: List[str] = []
    warnings: List[str] = []
