from pathlib import Path

from core.config.settings import get_settings
from data.models.analysis_record import AnalysisRecord
from data.models.track_record import TrackRecord
from data.repositories.analysis_repository import AnalysisRepository
from data.repositories.track_repository import TrackRepository
from services.composition.export_service import CanonicalCompositionExportService
from services.composition.runner import (
    CanonicalCompositionExecutionRequest,
    CanonicalCompositionRunner,
)
from services.export.exporter import Exporter


def seed_candidate(track_id: str, path: str, bpm: float, energy: float) -> None:
    TrackRepository().upsert(
        TrackRecord(
            track_id=track_id,
            path=path,
            title=track_id,
            artist=f"artist-{track_id}",
            genre="tech house",
            source="scope-integration",
            duration_seconds=300.0,
        )
    )
    AnalysisRepository().upsert(
        AnalysisRecord(
            track_id=track_id,
            analysis_version="1",
            features_version="1",
            extractor_backend="test",
            extractor_name="bundle-39",
            bpm=bpm,
            camelot="8A",
            energy=energy,
            duration_seconds=300.0,
        )
    )


def test_real_repository_and_exporter_never_emit_out_of_scope_track(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'scope.db'}")
    get_settings.cache_clear()

    try:
        seed_candidate("inside-a", "/music/selected/inside-a.mp3", 126.0, 0.4)
        seed_candidate("inside-b", "/music/selected/deeper/inside-b.mp3", 127.0, 0.6)
        seed_candidate("outside", "/music/other/outside.mp3", 128.0, 0.8)

        exports_dir = tmp_path / "exports"
        service = CanonicalCompositionExportService(
            runner=CanonicalCompositionRunner(repository=AnalysisRepository()),
            exporter=Exporter(
                exports_dir=exports_dir,
                artifacts_dir=tmp_path / "artifacts",
            ),
            run_id_factory=lambda: "canonical-scope-integration",
        )

        result = service.execute(
            CanonicalCompositionExecutionRequest(
                target_track_count=2,
                source_path="/music/selected",
            )
        )

        assert result.exported is True
        assert result.artifact is not None
        assert result.artifact.resolved_count == 2
        assert {track.track_id for track in result.execution.tracks} == {
            "inside-a",
            "inside-b",
        }

        m3u = (exports_dir / "canonical-scope-integration.m3u").read_text(
            encoding="utf-8"
        )
        assert "/music/selected/inside-a.mp3" in m3u
        assert "/music/selected/deeper/inside-b.mp3" in m3u
        assert "/music/other/outside.mp3" not in m3u
    finally:
        get_settings.cache_clear()
