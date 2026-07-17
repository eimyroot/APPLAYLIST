import pytest

from services.composition import (
    CanonicalCompositionExecutionResult,
    CanonicalCompositionExportArtifact,
    CanonicalCompositionExportResult,
    CompositionResult,
    CompositionStatus,
    CompositionSummary,
    CompositionTrack,
)
from services.orchestrator.composition_authority import (
    CanonicalCompositionAuthority,
    PipelineCompositionCommand,
)


def execution() -> CanonicalCompositionExecutionResult:
    track = CompositionTrack(
        track_id="canonical-1",
        path="/music/canonical-1.mp3",
        bpm=128.0,
        camelot="8A",
        energy=0.7,
    )
    return CanonicalCompositionExecutionResult(
        composition=CompositionResult(
            status=CompositionStatus.SUCCESS,
            tracks=(track,),
            decisions=(),
            summary=CompositionSummary(
                track_count=1,
                total_duration_seconds=300,
                average_bpm=128.0,
                minimum_bpm=128.0,
                maximum_bpm=128.0,
                average_energy=0.7,
            ),
        ),
        candidate_count=1,
        adapted_count=1,
        rejected_count=0,
        fallback_count=0,
        adaptation_issues=(),
    )


class StaticCanonicalService:
    def __init__(self, result: CanonicalCompositionExportResult) -> None:
        self.result = result
        self.requests = []

    def execute(self, request) -> CanonicalCompositionExportResult:
        self.requests.append(request)
        return self.result


def exported_result() -> CanonicalCompositionExportResult:
    return CanonicalCompositionExportResult(
        execution=execution(),
        run_id="canonical-authority",
        artifact=CanonicalCompositionExportArtifact(
            playlist_id="canonical-authority",
            m3u_path="exports/canonical-authority.m3u",
            manifest_path="artifacts/canonical-authority.manifest.json",
            warnings_path="artifacts/canonical-authority.warnings.json",
            audit_path="artifacts/canonical-authority.audit.json",
            resolved_count=1,
            skipped_count=0,
        ),
    )


def test_canonical_authority_maps_command_to_export_service() -> None:
    service = StaticCanonicalService(exported_result())
    authority = CanonicalCompositionAuthority(service=service)

    outcome = authority.execute(
        PipelineCompositionCommand(
            path="/music/selected",
            limit=5,
            bpm_min=124.0,
            bpm_max=132.0,
            mode="afterhours",
        )
    )

    request = service.requests[0]
    assert request.target_track_count == 5
    assert request.bpm_min == 124.0
    assert request.bpm_max == 132.0
    assert request.mode == "afterhours"
    assert request.source_path == "/music/selected"
    assert outcome.run_id == "canonical-authority"
    assert [track.track_id for track in outcome.tracks] == ["canonical-1"]
    assert outcome.export["playlist_id"] == "canonical-authority"
    assert outcome.export["resolved_count"] == 1
    assert outcome.export["skipped_count"] == 0


def test_canonical_authority_uses_explicit_control_defaults() -> None:
    service = StaticCanonicalService(exported_result())
    authority = CanonicalCompositionAuthority(service=service)

    authority.execute(PipelineCompositionCommand(path="/music", limit=1))

    request = service.requests[0]
    assert request.bpm_min == 1.0
    assert request.bpm_max == 300.0
    assert request.mode == "club"
    assert request.source_path == "/music"


def test_non_exportable_canonical_result_is_fail_closed() -> None:
    service = StaticCanonicalService(
        CanonicalCompositionExportResult(
            execution=execution(),
            run_id=None,
            artifact=None,
        )
    )
    authority = CanonicalCompositionAuthority(service=service)

    with pytest.raises(RuntimeError, match="did not produce"):
        authority.execute(PipelineCompositionCommand(path="/music", limit=1))
