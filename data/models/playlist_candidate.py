from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True, slots=True)
class PlaylistCandidate:
    """Read model combining track identity/path with analysis features."""

    track_id: str
    path: str
    title: Optional[str] = None
    artist: Optional[str] = None
    bpm: Optional[float] = None
    camelot: Optional[str] = None
    energy: Optional[float] = None
