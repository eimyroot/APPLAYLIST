from __future__ import annotations

from collections.abc import Callable
from uuid import uuid4

from services.composer.composer import Composer
from services.export.exporter import Exporter


def _new_pipeline_run_id() -> str:
    return f"pipeline-{uuid4().hex}"


class OrchestratorPipeline:
    def __init__(
        self,
        *,
        composer: Composer | None = None,
        exporter: Exporter | None = None,
        run_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self.composer = composer or Composer()
        self.exporter = exporter or Exporter()
        self._run_id_factory = run_id_factory or _new_pipeline_run_id

    def run(
        self,
        path: str,
        limit: int = 10,
        bpm_min: float | None = None,
        bpm_max: float | None = None,
        mode: str | None = None,
    ) -> dict:
        # Current clean MVP behavior:
        # compose from precomputed DB analyses joined to track paths, then export.
        playlist = self.composer.compose(limit=limit)
        playlist_id = self._run_id_factory()

        if not isinstance(playlist_id, str) or not playlist_id.strip():
            raise RuntimeError("Pipeline run ID factory returned an invalid identifier")

        export = self.exporter.export_m3u(
            playlist_id=playlist_id.strip(),
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
            "tracks": [track.track_id for track in playlist],
            "count": len(playlist),
            "export": export,
        }
