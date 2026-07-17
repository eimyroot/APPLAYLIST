from __future__ import annotations

from data.models.playlist_candidate import PlaylistCandidate
from services.orchestrator.pipeline import OrchestratorPipeline


class Composer:
    def compose(self, limit: int):
        return [
            PlaylistCandidate(
                track_id="track-1",
                path="/music/track-1.mp3",
                bpm=128.0,
                camelot="8A",
                energy=0.7,
            )
        ][:limit]


class Exporter:
    def export_m3u(self, *, playlist_id: str, tracks: list) -> dict:
        return {"playlist_id": playlist_id, "track_count": len(tracks)}


class CorrelatedHook:
    def __init__(self) -> None:
        self.calls = []

    def observe_run(self, **kwargs) -> object:
        self.calls.append(kwargs)
        return object()


def test_pipeline_uses_same_run_id_for_export_and_receipt_hook() -> None:
    hook = CorrelatedHook()
    pipeline = OrchestratorPipeline(
        composer=Composer(),
        exporter=Exporter(),
        run_id_factory=lambda: "pipeline-correlated",
        comparison_hook=hook,
        comparison_enabled=True,
    )

    result = pipeline.run(path="/music", limit=1, mode="club")

    assert result["export"]["playlist_id"] == "pipeline-correlated"
    assert hook.calls[0]["run_id"] == result["export"]["playlist_id"]
    assert hook.calls[0]["legacy_track_ids"] == ("track-1",)
