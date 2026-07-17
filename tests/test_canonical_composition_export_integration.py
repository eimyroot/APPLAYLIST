import json

from services.composition import (
    CanonicalCompositionExecutionRequest,
    CanonicalCompositionExecutionResult,
    CanonicalCompositionExportService,
    CompositionResult,
    CompositionStatus,
    CompositionSummary,
    CompositionTrack,
)
from services.export.exporter import Exporter


class StaticRunner:
    def run(self, request) -> CanonicalCompositionExecutionResult:
        tracks = (
            CompositionTrack(
                track_id="canonical-a",
                path="/music/canonical-a.mp3",
                bpm=126.0,
                camelot="8A",
                energy=0.4,
            ),
            CompositionTrack(
                track_id="canonical-b",
                path="/music/canonical-b.mp3",
                bpm=128.0,
                camelot="9A",
                energy=0.7,
            ),
        )
        return CanonicalCompositionExecutionResult(
            composition=CompositionResult(
                status=CompositionStatus.SUCCESS,
                tracks=tracks,
                decisions=(),
                summary=CompositionSummary(
                    track_count=2,
                    total_duration_seconds=600,
                    average_bpm=127.0,
                    minimum_bpm=126.0,
                    maximum_bpm=128.0,
                    average_energy=0.55,
                ),
            ),
            candidate_count=2,
            adapted_count=2,
            rejected_count=0,
            fallback_count=0,
            adaptation_issues=(),
        )


def test_real_exporter_materializes_canonical_playlist_and_evidence(tmp_path) -> None:
    exports_dir = tmp_path / "exports"
    artifacts_dir = tmp_path / "artifacts"
    service = CanonicalCompositionExportService(
        runner=StaticRunner(),
        exporter=Exporter(
            exports_dir=exports_dir,
            artifacts_dir=artifacts_dir,
        ),
        run_id_factory=lambda: "canonical-integration",
    )

    result = service.execute(
        CanonicalCompositionExecutionRequest(target_track_count=2)
    )

    assert result.artifact is not None
    artifact = result.artifact
    assert artifact.resolved_count == 2
    assert artifact.skipped_count == 0

    m3u = (exports_dir / "canonical-integration.m3u").read_text(encoding="utf-8")
    assert "/music/canonical-a.mp3" in m3u
    assert "/music/canonical-b.mp3" in m3u

    manifest = json.loads(
        (artifacts_dir / "canonical-integration.manifest.json").read_text(
            encoding="utf-8"
        )
    )
    audit = json.loads(
        (artifacts_dir / "canonical-integration.audit.json").read_text(
            encoding="utf-8"
        )
    )
    warnings = json.loads(
        (artifacts_dir / "canonical-integration.warnings.json").read_text(
            encoding="utf-8"
        )
    )

    assert manifest["playlist_id"] == "canonical-integration"
    assert manifest["resolved_count"] == 2
    assert manifest["skipped_count"] == 0
    assert [item["track_id"] for item in audit["resolved"]] == [
        "canonical-a",
        "canonical-b",
    ]
    assert audit["skipped"] == []
    assert warnings == []
