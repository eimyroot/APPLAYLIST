from __future__ import annotations

from services.composer.composer import Composer
from services.export.exporter import Exporter


class OrchestratorPipeline:
    def __init__(self) -> None:
        self.composer = Composer()
        self.exporter = Exporter()

    def run(
        self,
        path: str,
        limit: int = 10,
        bpm_min: float | None = None,
        bpm_max: float | None = None,
        mode: str | None = None,
    ) -> dict:
        # current clean MVP behavior:
        # compose from precomputed DB analyses, then export
        playlist = self.composer.compose(limit=limit)

        export = self.exporter.export_m3u(
            playlist_id="pipeline_run",
            tracks=playlist,
        )

        return {
            "input": {
                "path": path,
                "limit": limit,
                "bpm_min": bpm_min,
                "bpm_max": bpm_max,
                "mode": mode,
            },
            "tracks": [t.track_id for t in playlist],
            "count": len(playlist),
            "export": export,
        }
