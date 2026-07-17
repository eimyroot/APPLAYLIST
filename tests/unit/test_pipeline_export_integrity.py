from pathlib import Path

from core.config.settings import get_settings
from data.models.analysis_record import AnalysisRecord
from data.models.track_record import TrackRecord
from data.repositories.analysis_repository import AnalysisRepository
from data.repositories.track_repository import TrackRepository
from services.composer.composer import Composer
from services.export.exporter import Exporter
from services.orchestrator.pipeline import OrchestratorPipeline


def _seed_candidates() -> set[str]:
    analysis_repo = AnalysisRepository()
    track_repo = TrackRepository()
    expected_ids = set()

    for index in range(3):
        track_id = f"joined-{index}"
        expected_ids.add(track_id)
        track_repo.upsert(
            TrackRecord(
                track_id=track_id,
                path=f"/music/{track_id}.wav",
                title=f"Joined Track {index}",
            )
        )
        analysis_repo.upsert(
            AnalysisRecord(
                track_id=track_id,
                analysis_version="1",
                features_version="1",
                extractor_backend="test",
                extractor_name="bundle-26",
                bpm=126 + index,
                camelot="8A",
                energy=0.4 + (index * 0.1),
            )
        )

    analysis_repo.upsert(
        AnalysisRecord(
            track_id="orphan-analysis",
            analysis_version="1",
            features_version="1",
            extractor_backend="test",
            extractor_name="bundle-26",
            bpm=130,
            camelot="9A",
            energy=0.7,
        )
    )

    return expected_ids


def test_pipeline_exports_joined_paths_without_collisions(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'pipeline.db'}")
    get_settings.cache_clear()

    try:
        expected_ids = _seed_candidates()
        pipeline = OrchestratorPipeline(
            composer=Composer(),
            exporter=Exporter(
                exports_dir=tmp_path / "exports",
                artifacts_dir=tmp_path / "artifacts",
            ),
        )

        first = pipeline.run(path="/music", limit=3)
        second = pipeline.run(path="/music", limit=3)

        assert first["count"] == 3
        assert set(first["tracks"]) == expected_ids
        assert "orphan-analysis" not in first["tracks"]
        assert first["export"]["resolved_count"] == first["count"]
        assert first["export"]["skipped_count"] == 0

        assert first["export"]["playlist_id"].startswith("pipeline-")
        assert second["export"]["playlist_id"].startswith("pipeline-")
        assert first["export"]["playlist_id"] != second["export"]["playlist_id"]
        assert first["export"]["m3u_path"] != second["export"]["m3u_path"]

        first_m3u = Path(first["export"]["m3u_path"])
        second_m3u = Path(second["export"]["m3u_path"])
        assert first_m3u.exists()
        assert second_m3u.exists()

        content = first_m3u.read_text(encoding="utf-8")
        for track_id in expected_ids:
            assert f"/music/{track_id}.wav" in content
        assert "orphan-analysis" not in content
    finally:
        get_settings.cache_clear()
