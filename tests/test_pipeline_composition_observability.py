from __future__ import annotations

import logging

import pytest

from core.config.settings import Settings
from data.models.playlist_candidate import PlaylistCandidate
from services.composition.hook import PipelineCompositionComparisonHook
from services.composition.models import CompositionStatus
from services.composition.shadow import CompositionShadowReport
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
    def __init__(self, events: list[str], *, fail: bool = False) -> None:
        self.events = events
        self.fail = fail

    def export_m3u(self, *, playlist_id: str, tracks: list) -> dict:
        self.events.append("export")
        if self.fail:
            raise RuntimeError("export failed")
        return {
            "playlist_id": playlist_id,
            "track_count": len(tracks),
            "m3u_path": f"exports/{playlist_id}.m3u",
        }


class RecordingHook:
    def __init__(self, events: list[str], *, fail: bool = False) -> None:
        self.events = events
        self.fail = fail
        self.calls: list[dict] = []

    def observe(self, **kwargs) -> object:
        self.events.append("observe")
        self.calls.append(kwargs)
        if self.fail:
            raise RuntimeError("comparison failed")
        return object()


class StaticComparisonService:
    def compare(self, request) -> CompositionShadowReport:
        return CompositionShadowReport(
            legacy_track_ids=request.legacy_track_ids,
            canonical_track_ids=request.legacy_track_ids,
            canonical_status=CompositionStatus.SUCCESS,
            canonical_failure_reason=None,
            candidate_count=1,
            adapted_count=1,
            rejected_count=0,
            fallback_count=0,
            overlap_count=1,
            position_match_count=1,
            legacy_coverage_ratio=1.0,
            canonical_coverage_ratio=1.0,
            adaptation_issues=(),
            canonical_warnings=(),
        )


class FailingSink:
    def emit(self, report: CompositionShadowReport) -> None:
        raise RuntimeError("sink failed")


def build_pipeline(
    events: list[str],
    *,
    hook=None,
    enabled: bool,
    export_fail: bool = False,
) -> OrchestratorPipeline:
    return OrchestratorPipeline(
        composer=FakeComposer(events),
        exporter=FakeExporter(events, fail=export_fail),
        run_id_factory=lambda: "pipeline-test",
        comparison_hook=hook,
        comparison_enabled=enabled,
    )


def assert_legacy_result_unchanged(result: dict) -> None:
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
            "track_count": 1,
            "m3u_path": "exports/pipeline-test.m3u",
        },
    }


def test_comparison_is_disabled_by_default_and_hook_is_not_called() -> None:
    assert Settings(_env_file=None).enable_composition_comparison is False

    events: list[str] = []
    hook = RecordingHook(events)
    pipeline = build_pipeline(events, hook=hook, enabled=False)

    result = pipeline.run(
        path="/music",
        limit=1,
        bpm_min=126.0,
        bpm_max=132.0,
        mode="club",
    )

    assert events == ["compose", "export"]
    assert hook.calls == []
    assert_legacy_result_unchanged(result)


def test_enabled_hook_runs_after_export_with_requested_controls() -> None:
    events: list[str] = []
    hook = RecordingHook(events)
    pipeline = build_pipeline(events, hook=hook, enabled=True)

    result = pipeline.run(
        path="/music",
        limit=1,
        bpm_min=126.0,
        bpm_max=132.0,
        mode="club",
    )

    assert events == ["compose", "export", "observe"]
    assert hook.calls == [
        {
            "legacy_track_ids": ("legacy-1",),
            "target_track_count": 1,
            "bpm_min": 126.0,
            "bpm_max": 132.0,
            "mode": "club",
        }
    ]
    assert_legacy_result_unchanged(result)


def test_hook_failure_is_fail_open_and_logged(caplog) -> None:
    events: list[str] = []
    hook = RecordingHook(events, fail=True)
    pipeline = build_pipeline(events, hook=hook, enabled=True)

    with caplog.at_level(logging.WARNING, logger="services.orchestrator.pipeline"):
        result = pipeline.run(
            path="/music",
            limit=1,
            bpm_min=126.0,
            bpm_max=132.0,
            mode="club",
        )

    assert events == ["compose", "export", "observe"]
    assert "legacy export preserved" in caplog.text
    assert_legacy_result_unchanged(result)


def test_sink_failure_is_fail_open() -> None:
    events: list[str] = []
    hook = PipelineCompositionComparisonHook(
        service=StaticComparisonService(),
        sink=FailingSink(),
    )
    pipeline = build_pipeline(events, hook=hook, enabled=True)

    result = pipeline.run(
        path="/music",
        limit=1,
        bpm_min=126.0,
        bpm_max=132.0,
        mode="club",
    )

    assert events == ["compose", "export"]
    assert_legacy_result_unchanged(result)


def test_export_failure_prevents_observability_invocation() -> None:
    events: list[str] = []
    hook = RecordingHook(events)
    pipeline = build_pipeline(
        events,
        hook=hook,
        enabled=True,
        export_fail=True,
    )

    with pytest.raises(RuntimeError, match="export failed"):
        pipeline.run(path="/music", limit=1)

    assert events == ["compose", "export"]
    assert hook.calls == []
