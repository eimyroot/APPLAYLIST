from pathlib import Path

from core.config.settings import get_settings
from data.models.analysis_record import AnalysisRecord
from data.models.track_record import TrackRecord
from data.repositories.analysis_repository import AnalysisRepository
from data.repositories.track_repository import TrackRepository
from services.composer.composer import Composer


def seed() -> None:
    analysis_repo = AnalysisRepository()
    track_repo = TrackRepository()

    for index in range(10):
        track_id = f"composer-{index}"
        track_repo.upsert(
            TrackRecord(
                track_id=track_id,
                path=f"/music/{track_id}.mp3",
                title=f"Track {index}",
            )
        )
        analysis_repo.upsert(
            AnalysisRecord(
                track_id=track_id,
                analysis_version="1",
                features_version="1",
                extractor_backend="x",
                extractor_name="x",
                bpm=120 + index,
                camelot="8A",
                energy=index / 10,
            )
        )


def test_compose(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'composer.db'}")
    get_settings.cache_clear()

    try:
        seed()
        playlist = Composer().compose(limit=5)

        assert len(playlist) == 5
        assert all(track.path.startswith("/music/composer-") for track in playlist)
    finally:
        get_settings.cache_clear()
