from types import MappingProxyType

import pytest

from data.models.playlist_candidate import PlaylistCandidate
from services.orchestrator.composition_authority import (
    PipelineCompositionCommand,
    PipelineCompositionOutcome,
)
from services.orchestrator.pipeline import OrchestratorPipeline


class FakeComposer:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    def compose(self, limit: int) -> list[PlaylistCandidate]:
        self.events.append("compose")
        return [
            PlaylistCandidate(
                track_id="legacy-1",
                path="/music/legacy-1.mp3",
                bpm=128.0,
                camelot="8A",
                energy=0.7,
            )
        ][:limit]


class FakeExporter:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    def export_m3u(self, *, playlist_id: str, tracks: list) -> dict:
        self.events.append("export")
        return {
            "playlist_id": playlist_id,
            "m3u_path": f"exports/{playlist_id}.m3u",
            "resolved_count": len(tracks),
            "skipped_count": 0,
        }


class RecordingAuthority:
    def __init__(self, events: list[str], *, fail: bool = False) -> None:
        self.events = events
        self.fail = fail
        self.commands = []

    def execute(self, command: PipelineCompositionCommand) -> PipelineCompositionOutcome:
        self.events.append("authority")
        self.commands.append(command)
        if self.fail:
            raise RuntimeError("authority failed")
        track = PlaylistCandidate(
            track_id="authority-1",
            path="/music/authority-1.mp3",
            bpm=127.0,
            camelot="9A",
            energy=0.6,
        )
        return PipelineCompositionOutcome(
            run_id="authority-run",
            tracks=(track,),
            export=MappingProxyType(
                {
                    "playlist_id": "authority-run",
                    "m3u_path": "exports/authority-run.m3u",
                    "resolved_count": 1,
                    "skipped_count": 0,
                }
            ),
        )


class RecordingHook:
    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.calls = []

    def observe_run(self, **kwargs) -> None:
        self.events.append("observe")
        self.calls.append(kwargs)


def test_default_legacy_dependencies_preserve_exact_response_and_order() -> None:
    events: list[str] = []
    pipeline = OrchestratorPipeline(
        composer=FakeComposer(events),
        exporter=FakeExporter(events),
        run_id_factory=lambda: "pipeline-test",
        comparison_enabled=False,
    )

    result = pipeline.run(
        path="/music",
        limit=1,
        bpm_min=126.0,
        bpm_max=132.0,
        mode="club",
    )

    assert events == ["compose", "export"]
    assert result == {
        "input": {
            "path": "/music",
            "limit": 1,
            "bpm_min": 126.0,
            "bpm_max": 132.0,
            "mode": "club",
        },
        "tracks": ["legacy-1"],
        "count": 1,
        "export": {
            "playlist_id": "pipeline-test",
            "m3u_path": "exports/pipeline-test.m3u",
            "resolved_count": 1,
            "skipped_count": 0,
        },
    }


def test_injected_authority_receives_controls_and_preserves_response_shape() -> None:
    events: list[str] = []
    authority = RecordingAuthority(events)
    hook = RecordingHook(events)
    pipeline = OrchestratorPipeline(
        composition_authority=authority,
        comparison_hook=hook,
        comparison_enabled=True,
    )

    result = pipeline.run(
        path="/library",
        limit=7,
        bpm_min=124.0,
        bpm_max=130.0,
        mode="afterhours",
    )

    assert events == ["authority", "observe"]
    assert authority.commands == [
        PipelineCompositionCommand(
            path="/library",
            limit=7,
            bpm_min=124.0,
            bpm_max=130.0,
            mode="afterhours",
        )
    ]
    assert result["tracks"] == ["authority-1"]
    assert result["count"] == 1
    assert result["export"]["playlist_id"] == "authority-run"
    assert hook.calls[0]["run_id"] == "authority-run"
    assert hook.calls[0]["legacy_track_ids"] == ("authority-1",)


def test_authority_failure_prevents_observability() -> None:
    events: list[str] = []
    pipeline = OrchestratorPipeline(
        composition_authority=RecordingAuthority(events, fail=True),
        comparison_hook=RecordingHook(events),
        comparison_enabled=True,
    )

    with pytest.raises(RuntimeError, match="authority failed"):
        pipeline.run(path="/music", limit=1)

    assert events == ["authority"]


def test_authority_cannot_be_combined_with_legacy_dependencies() -> None:
    with pytest.raises(ValueError, match="cannot be combined"):
        OrchestratorPipeline(
            composition_authority=RecordingAuthority([]),
            composer=FakeComposer([]),
            comparison_enabled=False,
        )
