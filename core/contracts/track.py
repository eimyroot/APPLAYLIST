from pydantic import BaseModel, Field
from typing import Optional


class Track(BaseModel):
    track_id: str = Field(..., description="Canonical internal track identifier")
    path: str
    title: Optional[str] = None
    artist: Optional[str] = None
    album: Optional[str] = None
    genre: Optional[str] = None
    source: Optional[str] = None
    duration_seconds: Optional[float] = None
    sample_rate_hz: Optional[int] = None
    bitrate_kbps: Optional[int] = None
