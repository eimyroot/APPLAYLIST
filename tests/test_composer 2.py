from services.composer.composer import Composer
from data.repositories.analysis_repository import AnalysisRepository
from data.models.analysis_record import AnalysisRecord


def seed():
    repo = AnalysisRepository()

    for i in range(10):
        repo.upsert(
            AnalysisRecord(
                track_id=f"t{i}",
                analysis_version="1",
                features_version="1",
                extractor_backend="x",
                extractor_name="x",
                bpm=120 + i,
                camelot="8A",
                energy=i / 10,
            )
        )


def test_compose():
    seed()
    composer = Composer()
    playlist = composer.compose(limit=5)

    assert len(playlist) == 5
