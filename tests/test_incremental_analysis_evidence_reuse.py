from __future__ import annotations

from pathlib import Path

import pytest

from core.analysis.execution_identity import AnalysisExecutionIdentity
from core.analysis.provider_contract import CanonicalAnalysisResult
from core.config.settings import get_settings
from data.models.track_record import TrackRecord
from data.repositories.analysis_evidence_repository import AnalysisEvidenceRepository
from data.repositories.track_repository import TrackRepository
from services.analysis.batch_runner import AnalysisBatchRunner
from services.analysis.job_service import AnalysisJobService
from services.analysis.result_store import AnalysisResultStore


@pytest.fixture
def isolated_database(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    database_path = tmp_path / "bundle55-analysis-reuse.sqlite3"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path}")
    get_settings.cache_clear()
    yield database_path
    get_settings.cache_clear()


def _content_track_id(fill: str) -> str:
    return "aptrack:v1:sha256:" + (fill * 64)


def _track(repository: TrackRepository, track_id: str, path: str) -> None:
    repository.upsert(
        TrackRecord(
            track_id=track_id,
            path=path,
            title="Track",
            artist="Test Artist",
            duration_seconds=300.0,
        )
    )


def _identity(*, provider_version: str = "0.10.2") -> AnalysisExecutionIdentity:
    return AnalysisExecutionIdentity(
        provider="librosa",
        analysis_version="canonical-mir-v1",
        provider_version=provider_version,
        algorithm_version="baseline-librosa-mir-v1",
    )


def _result(path: str, *, provider_version: str = "0.10.2") -> CanonicalAnalysisResult:
    return CanonicalAnalysisResult(
        path=path,
        provider="librosa",
        bpm=140.0,
        bpm_confidence=0.90,
        key="11A",
        key_confidence=0.88,
        energy=0.72,
        loudness_db=-10.0,
        duration_seconds=300.0,
        genre_hint=None,
        key_tonic="F#",
        key_scale="minor",
        camelot="11A",
        beat_stability=0.85,
        harmonic_ratio=0.55,
        percussive_ratio=0.45,
        provider_version=provider_version,
        algorithm_version="baseline-librosa-mir-v1",
    )


class IdentityAwareAnalysisService:
    def __init__(
        self,
        identity: AnalysisExecutionIdentity,
        outcomes: dict[str, CanonicalAnalysisResult],
    ) -> None:
        self.identity = identity
        self.outcomes = outcomes
        self.calls: list[str] = []

    def execution_identity(
        self,
        *,
        preferred_provider: str | None = None,
    ) -> AnalysisExecutionIdentity:
        return self.identity

    def analyze_path(
        self,
        path: str,
        *,
        preferred_provider: str | None = None,
    ) -> CanonicalAnalysisResult:
        self.calls.append(path)
        return self.outcomes[path]


class CancellingIdentityAnalysisService(IdentityAwareAnalysisService):
    def __init__(
        self,
        identity: AnalysisExecutionIdentity,
        outcomes: dict[str, CanonicalAnalysisResult],
        jobs: AnalysisJobService,
        job_id: str,
    ) -> None:
        super().__init__(identity, outcomes)
        self.jobs = jobs
        self.job_id = job_id

    def analyze_path(
        self,
        path: str,
        *,
        preferred_provider: str | None = None,
    ) -> CanonicalAnalysisResult:
        result = super().analyze_path(path, preferred_provider=preferred_provider)
        self.jobs.request_cancel(self.job_id)
        return result


def test_exact_content_and_execution_identity_reuses_evidence_without_provider_call(
    isolated_database: Path,
) -> None:
    tracks = TrackRepository()
    jobs = AnalysisJobService()
    evidence = AnalysisEvidenceRepository()
    store = AnalysisResultStore(evidence)
    track_id = _content_track_id("a")
    path = "/library/a.wav"
    _track(tracks, track_id, path)

    original = store.persist_success(track_id=track_id, result=_result(path))
    service = IdentityAwareAnalysisService(_identity(), {path: _result(path)})
    job = jobs.create_job(track_ids=[track_id], preferred_provider="librosa")

    terminal = AnalysisBatchRunner(
        analysis_service=service,  # type: ignore[arg-type]
        job_service=jobs,
        result_store=store,
        track_repository=tracks,
    ).run(job.job_id)

    assert terminal.status == "done"
    assert terminal.counts.completed == 1
    assert terminal.counts.succeeded == 1
    assert service.calls == []
    assert evidence.latest_success_for_track(track_id) == original
    assert evidence.list_latest_attempts() == [original]


def test_provider_version_drift_forces_fresh_analysis(
    isolated_database: Path,
) -> None:
    tracks = TrackRepository()
    jobs = AnalysisJobService()
    evidence = AnalysisEvidenceRepository()
    store = AnalysisResultStore(evidence)
    track_id = _content_track_id("b")
    path = "/library/b.wav"
    _track(tracks, track_id, path)

    old = store.persist_success(track_id=track_id, result=_result(path, provider_version="0.10.2"))
    service = IdentityAwareAnalysisService(
        _identity(provider_version="0.10.3"),
        {path: _result(path, provider_version="0.10.3")},
    )
    job = jobs.create_job(track_ids=[track_id], preferred_provider="librosa")

    terminal = AnalysisBatchRunner(
        analysis_service=service,  # type: ignore[arg-type]
        job_service=jobs,
        result_store=store,
        track_repository=tracks,
    ).run(job.job_id)

    latest = evidence.latest_success_for_track(track_id)
    assert terminal.status == "done"
    assert service.calls == [path]
    assert latest is not None
    assert latest.evidence_id != old.evidence_id
    assert latest.provider_version == "0.10.3"


def test_legacy_track_id_never_reuses_evidence(
    isolated_database: Path,
) -> None:
    tracks = TrackRepository()
    jobs = AnalysisJobService()
    evidence = AnalysisEvidenceRepository()
    store = AnalysisResultStore(evidence)
    track_id = "legacy-track-a"
    path = "/library/legacy.wav"
    _track(tracks, track_id, path)

    store.persist_success(track_id=track_id, result=_result(path))
    service = IdentityAwareAnalysisService(_identity(), {path: _result(path)})
    job = jobs.create_job(track_ids=[track_id], preferred_provider="librosa")

    AnalysisBatchRunner(
        analysis_service=service,  # type: ignore[arg-type]
        job_service=jobs,
        result_store=store,
        track_repository=tracks,
    ).run(job.job_id)

    assert service.calls == [path]


def test_new_job_resumes_from_persisted_exact_evidence_after_cancellation(
    isolated_database: Path,
) -> None:
    tracks = TrackRepository()
    jobs = AnalysisJobService()
    evidence = AnalysisEvidenceRepository()
    store = AnalysisResultStore(evidence)
    track_a = _content_track_id("c")
    track_b = _content_track_id("d")
    path_a = "/library/c.wav"
    path_b = "/library/d.wav"
    _track(tracks, track_a, path_a)
    _track(tracks, track_b, path_b)

    first_job = jobs.create_job(track_ids=[track_a, track_b], preferred_provider="librosa")
    first_service = CancellingIdentityAnalysisService(
        _identity(),
        {path_a: _result(path_a), path_b: _result(path_b)},
        jobs,
        first_job.job_id,
    )
    first_terminal = AnalysisBatchRunner(
        analysis_service=first_service,  # type: ignore[arg-type]
        job_service=jobs,
        result_store=store,
        track_repository=tracks,
    ).run(first_job.job_id)

    assert first_terminal.status == "cancelled"
    assert first_service.calls == [path_a]
    first_evidence = evidence.latest_success_for_track(track_a)
    assert first_evidence is not None
    assert evidence.latest_success_for_track(track_b) is None

    second_job = jobs.create_job(track_ids=[track_a, track_b], preferred_provider="librosa")
    second_service = IdentityAwareAnalysisService(
        _identity(),
        {path_a: _result(path_a), path_b: _result(path_b)},
    )
    second_terminal = AnalysisBatchRunner(
        analysis_service=second_service,  # type: ignore[arg-type]
        job_service=jobs,
        result_store=store,
        track_repository=tracks,
    ).run(second_job.job_id)

    assert second_terminal.status == "done"
    assert second_terminal.counts.completed == 2
    assert second_terminal.counts.succeeded == 2
    assert second_service.calls == [path_b]
    assert evidence.latest_success_for_track(track_a) == first_evidence
    assert evidence.latest_success_for_track(track_b) is not None
