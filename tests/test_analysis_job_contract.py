from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from core.analysis.job_contract import AnalysisJobCounts
from core.config.settings import get_settings
from data.repositories.analysis_evidence_repository import AnalysisEvidenceRepository
from data.repositories.analysis_job_repository import AnalysisJobRepository
from services.analysis.job_service import AnalysisJobService


@pytest.fixture
def isolated_database(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    database_path = tmp_path / "bundle50.sqlite3"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path}")
    get_settings.cache_clear()
    yield database_path
    get_settings.cache_clear()


def test_analysis_job_contract_rejects_invalid_counts() -> None:
    with pytest.raises(ValueError, match="completed must equal"):
        AnalysisJobCounts(selected=2, completed=1, succeeded=0, failed=0)

    with pytest.raises(ValueError, match="uncertain cannot exceed"):
        AnalysisJobCounts(
            selected=2,
            completed=1,
            succeeded=1,
            failed=0,
            uncertain=2,
        )


def test_analysis_job_persists_monotonic_progress_and_cancel(
    isolated_database: Path,
) -> None:
    service = AnalysisJobService()
    created = service.create_job(selected=3, preferred_provider=" Librosa ")

    assert created.job_id.startswith("aj_")
    assert created.status == "pending"
    assert created.preferred_provider == "librosa"
    assert created.counts == AnalysisJobCounts(selected=3)

    running = service.mark_running(created.job_id)
    assert running.status == "running"

    first = service.record_success(created.job_id, uncertain=True)
    assert first.counts == AnalysisJobCounts(
        selected=3,
        completed=1,
        succeeded=1,
        failed=0,
        uncertain=1,
    )

    second = service.record_failure(created.job_id)
    assert second.counts == AnalysisJobCounts(
        selected=3,
        completed=2,
        succeeded=1,
        failed=1,
        uncertain=1,
    )

    cancelling = service.request_cancel(created.job_id)
    assert cancelling.status == "cancelling"
    assert cancelling.cancel_requested is True

    repeated = service.request_cancel(created.job_id)
    assert repeated == cancelling

    cancelled = service.finish(created.job_id)
    assert cancelled.status == "cancelled"
    assert cancelled.counts == second.counts

    persisted = AnalysisJobRepository().get(created.job_id)
    assert persisted == cancelled
    assert isolated_database.exists()


def test_analysis_job_completes_only_after_selected_scope(
    isolated_database: Path,
) -> None:
    service = AnalysisJobService()
    created = service.create_job(selected=2)
    service.mark_running(created.job_id)
    service.record_success(created.job_id)

    with pytest.raises(ValueError, match="cannot finish before"):
        service.finish(created.job_id)

    service.record_success(created.job_id)
    done = service.finish(created.job_id)
    assert done.status == "done"
    assert done.counts == AnalysisJobCounts(
        selected=2,
        completed=2,
        succeeded=2,
        failed=0,
        uncertain=0,
    )

    with pytest.raises(ValueError, match="terminal analysis job state"):
        service.fail_job(
            created.job_id,
            error_code="late_failure",
            error_detail="must not rewrite a completed job",
        )


def test_analysis_job_repository_rejects_regression_and_unknown_job(
    isolated_database: Path,
) -> None:
    repository = AnalysisJobRepository()
    created = repository.create(selected=2, job_id="aj_fixed")
    progressed = repository.update(
        created.job_id,
        status="running",
        counts=AnalysisJobCounts(
            selected=2,
            completed=1,
            succeeded=1,
            failed=0,
            uncertain=0,
        ),
    )
    assert progressed.counts.completed == 1

    with pytest.raises(ValueError, match="must be monotonic"):
        repository.update(
            created.job_id,
            status="running",
            counts=AnalysisJobCounts(selected=2),
        )

    with pytest.raises(KeyError, match="unknown analysis job"):
        repository.update(
            "aj_missing",
            status="running",
            counts=AnalysisJobCounts(selected=1),
        )


def test_analysis_evidence_and_corrections_are_append_only(
    isolated_database: Path,
) -> None:
    repository = AnalysisEvidenceRepository()

    first = repository.append_evidence(
        evidence_id="ae_0001",
        track_id="track-1",
        provider="librosa",
        analysis_version="canonical-mir-v1",
        provider_version="0.10.2",
        algorithm_version="baseline-r1",
        bpm=139.8,
        bpm_confidence=0.82,
        key_tonic="F#",
        key_scale="minor",
        camelot="11A",
        key_confidence=0.74,
        energy=0.71,
        duration_seconds=312.4,
        warnings=("tempo_half_time_possible",),
    )
    second = repository.append_evidence(
        evidence_id="ae_0002",
        track_id="track-1",
        provider="librosa",
        analysis_version="canonical-mir-v1",
        provider_version="0.10.2",
        algorithm_version="baseline-r1",
        bpm=140.1,
        bpm_confidence=0.91,
        key_tonic="F#",
        key_scale="minor",
        camelot="11A",
        key_confidence=0.80,
        energy=0.73,
        duration_seconds=312.4,
    )

    assert first.evidence_id != second.evidence_id
    latest = repository.latest_evidence_for_track("track-1")
    assert latest is not None
    assert latest.evidence_id == "ae_0002"
    assert latest.warnings == ()

    correction = repository.append_correction(
        correction_id="ac_0001",
        track_id="track-1",
        values={"bpm": 140.0, "camelot": "11A"},
        reason="confirmed on deck",
    )
    assert json.loads(correction.payload_json) == {"bpm": 140.0, "camelot": "11A"}
    assert correction.reason == "confirmed on deck"
    assert repository.latest_correction_for_track("track-1") == correction

    with pytest.raises(sqlite3.IntegrityError):
        repository.append_evidence(
            evidence_id="ae_0002",
            track_id="track-1",
            provider="librosa",
            analysis_version="canonical-mir-v1",
        )

    with pytest.raises(ValueError, match="unsupported fields"):
        repository.append_correction(
            track_id="track-1",
            values={"path": "/must/not/be/stored"},
        )
