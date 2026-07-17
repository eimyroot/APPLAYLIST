from dataclasses import FrozenInstanceError

import pytest

from services.composition import (
    CanonicalCompositionExecutionRequest,
    CanonicalCompositionExecutionResult,
    CanonicalCompositionExportService,
    CompositionResult,
    CompositionStatus,
    CompositionSummary,
    CompositionTrack,
)


def composition_result(
    *,
    status: CompositionStatus,
    tracks: tuple[CompositionTrack, ...],
) -> CompositionResult:
    return CompositionResult(
        status=status,
        tracks=tracks,
        decisions=(),
        summary=CompositionSummary(
            track_count=len(tracks),
            total_duration_seconds=sum(track.duration_seconds for track in tracks),
            average_bpm=(sum(track.bpm for track in tracks) / len(tracks)) if tracks else 0.0,
            minimum_bpm=min((track.bpm for track in tracks), default=0.0),
            maximum_bpm=max((track.bpm for track in tracks), default=0.0),
            average_energy=(sum(track.energy for track in tracks) / len(tracks)) if tracks else 0.0,
        ),
    )


def execution(
    *,
    status: CompositionStatus = CompositionStatus.SUCCESS,
    tracks: tuple[CompositionTrack, ...] | None = None,
) -> CanonicalCompositionExecutionResult:
    resolved_tracks = tracks if tracks is not None else (
        CompositionTrack(
            track_id="canonical-1",
            path="/music/canonical-1.mp3",
            bpm=128.0,
            camelot="8A",
            energy=0.6,
        ),
    )
    return CanonicalCompositionExecutionResult(
        composition=composition_result(status=status, tracks=resolved_tracks),
        candidate_count=len(resolved_tracks),
        adapted_count=len(resolved_tracks),
        rejected_count=0,
        fallback_count=0,
        adaptation_issues=(),
    )


class StaticRunner:
    def __init__(self, value: CanonicalCompositionExecutionResult) -> None:
        self.value = value
        self.requests = []

    def run(self, request) -> CanonicalCompositionExecutionResult:
        self.requests.append(request)
        return self.value


class RecordingExporter:
    def __init__(self, payload: dict | None = None) -> None:
        self.payload = payload
        self.calls = []

    def export_m3u(self, *, playlist_id: str, tracks: list) -> dict:
        self.calls.append({"playlist_id": playlist_id, "tracks": list(tracks)})
        if self.payload is not None:
            return dict(self.payload)
        return {
            "playlist_id": playlist_id,
            "m3u_path": f"exports/{playlist_id}.m3u",
            "manifest_path": f"artifacts/{playlist_id}.manifest.json",
            "warnings_path": f"artifacts/{playlist_id}.warnings.json",
            "audit_path": f"artifacts/{playlist_id}.audit.json",
            "resolved_count": len(tracks),
            "skipped_count": 0,
        }


def test_successful_execution_exports_with_generated_safe_id() -> None:
    runner = StaticRunner(execution())
    exporter = RecordingExporter()
    service = CanonicalCompositionExportService(
        runner=runner,
        exporter=exporter,
        run_id_factory=lambda: "canonical-test",
    )

    result = service.execute(CanonicalCompositionExecutionRequest(target_track_count=1))

    assert result.exported is True
    assert result.run_id == "canonical-test"
    assert result.artifact is not None
    assert result.artifact.playlist_id == "canonical-test"
    assert result.artifact.resolved_count == 1
    assert result.artifact.skipped_count == 0
    assert exporter.calls[0]["playlist_id"] == "canonical-test"
    assert [track.track_id for track in exporter.calls[0]["tracks"]] == ["canonical-1"]


def test_failed_or_empty_execution_does_not_export() -> None:
    exporter = RecordingExporter()
    service = CanonicalCompositionExportService(
        runner=StaticRunner(execution(status=CompositionStatus.FAILED, tracks=())),
        exporter=exporter,
        run_id_factory=lambda: "canonical-unused",
    )

    result = service.execute(CanonicalCompositionExecutionRequest(target_track_count=1))

    assert result.exported is False
    assert result.run_id is None
    assert result.artifact is None
    assert exporter.calls == []


@pytest.mark.parametrize("run_id", ["canonical bad", "legacy-1", "canonical-", ".hidden"])
def test_unsafe_generated_run_id_fails_before_export(run_id: str) -> None:
    exporter = RecordingExporter()
    service = CanonicalCompositionExportService(
        runner=StaticRunner(execution()),
        exporter=exporter,
        run_id_factory=lambda: run_id,
    )

    with pytest.raises(RuntimeError, match="unsafe identifier"):
        service.execute(CanonicalCompositionExecutionRequest(target_track_count=1))

    assert exporter.calls == []


def test_exporter_identity_and_counts_are_fail_closed() -> None:
    bad_payloads = [
        {
            "playlist_id": "canonical-other",
            "m3u_path": "x",
            "manifest_path": "x",
            "warnings_path": "x",
            "audit_path": "x",
            "resolved_count": 1,
            "skipped_count": 0,
        },
        {
            "playlist_id": "canonical-test",
            "m3u_path": "x",
            "manifest_path": "x",
            "warnings_path": "x",
            "audit_path": "x",
            "resolved_count": 0,
            "skipped_count": 1,
        },
    ]

    for payload in bad_payloads:
        service = CanonicalCompositionExportService(
            runner=StaticRunner(execution()),
            exporter=RecordingExporter(payload),
            run_id_factory=lambda: "canonical-test",
        )
        with pytest.raises(RuntimeError):
            service.execute(CanonicalCompositionExecutionRequest(target_track_count=1))


def test_export_result_contract_is_immutable() -> None:
    result = CanonicalCompositionExportService(
        runner=StaticRunner(execution()),
        exporter=RecordingExporter(),
        run_id_factory=lambda: "canonical-test",
    ).execute(CanonicalCompositionExecutionRequest(target_track_count=1))

    with pytest.raises(FrozenInstanceError):
        result.run_id = "canonical-other"
