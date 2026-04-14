from data.models.track_record import TrackRecord
from data.models.analysis_record import AnalysisRecord
from data.models.job_record import JobRecord
from data.repositories.track_repository import TrackRepository
from data.repositories.analysis_repository import AnalysisRepository
from data.repositories.job_repository import JobRepository


def test_track_repository_upsert_and_get() -> None:
    repo = TrackRepository()
    repo.upsert(
        TrackRecord(
            track_id="track-1",
            path="/tmp/example.mp3",
            title="Example",
            artist="Tester",
        )
    )
    row = repo.get_by_id("track-1")
    assert row is not None
    assert row.track_id == "track-1"
    assert row.title == "Example"


def test_analysis_repository_upsert_and_get() -> None:
    repo = AnalysisRepository()
    repo.upsert(
        AnalysisRecord(
            track_id="track-1",
            analysis_version="0.1.0",
            features_version="0.1.0",
            extractor_backend="librosa",
            extractor_name="bundle-2-test",
            bpm=128.0,
            energy=0.75,
        )
    )
    row = repo.get_by_track_id("track-1")
    assert row is not None
    assert row.track_id == "track-1"
    assert row.bpm == 128.0


def test_job_repository_upsert_and_get() -> None:
    repo = JobRepository()
    repo.upsert(
        JobRecord(
            job_id="job-1",
            job_type="analyze",
            status="pending",
            progress=0.0,
        )
    )
    row = repo.get_by_id("job-1")
    assert row is not None
    assert row.job_id == "job-1"
    assert row.status == "pending"
