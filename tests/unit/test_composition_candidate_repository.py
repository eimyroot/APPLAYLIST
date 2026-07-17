from pathlib import Path

from core.config.settings import get_settings
from data.models.analysis_record import AnalysisRecord
from data.models.track_record import TrackRecord
from data.repositories.analysis_repository import AnalysisRepository
from data.repositories.track_repository import TrackRepository


def _analysis(track_id: str, *, duration_seconds: float | None) -> AnalysisRecord:
    return AnalysisRecord(
        track_id=track_id,
        analysis_version="1",
        features_version="1",
        extractor_backend="test",
        extractor_name="test",
        bpm=126.0,
        camelot="9A",
        energy=0.65,
        duration_seconds=duration_seconds,
    )


def test_candidate_join_includes_track_metadata_and_prefers_analysis_duration(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'candidates.db'}")
    get_settings.cache_clear()

    try:
        track_repo = TrackRepository()
        analysis_repo = AnalysisRepository()
        track_repo.upsert(
            TrackRecord(
                track_id="analysis-duration",
                path="/music/analysis-duration.mp3",
                title="Analysis Duration",
                artist="Artist A",
                genre="tech house",
                source="pool-a",
                duration_seconds=300.0,
            )
        )
        analysis_repo.upsert(
            _analysis("analysis-duration", duration_seconds=321.5)
        )
        track_repo.upsert(
            TrackRecord(
                track_id="track-duration",
                path="/music/track-duration.mp3",
                title="Track Duration",
                artist="Artist B",
                genre="hypnotic techno",
                source="pool-b",
                duration_seconds=280.0,
            )
        )
        analysis_repo.upsert(_analysis("track-duration", duration_seconds=None))

        candidates = analysis_repo.list_playlist_candidates()

        assert [candidate.track_id for candidate in candidates] == [
            "analysis-duration",
            "track-duration",
        ]
        assert candidates[0].genre == "tech house"
        assert candidates[0].source == "pool-a"
        assert candidates[0].duration_seconds == 321.5
        assert candidates[1].genre == "hypnotic techno"
        assert candidates[1].source == "pool-b"
        assert candidates[1].duration_seconds == 280.0
    finally:
        get_settings.cache_clear()
