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


def _success_evidence(
    repository: AnalysisEvidenceRepository,
    *,
    evidence_id: str,
    track_id: str,
) -> str:
    return repository.append_evidence(
        evidence_id=evidence_id,
        track_id=track_id,
        provider="librosa",
        analysis_version="canonical-mir-v1",
        bpm=140.0,
        bpm_confidence=0.8,
        key_tonic="F#",
        key_scale="minor",
        camelot="11A",
        key_confidence=0.8,
        energy=0.7,
    ).evidence_id


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


def test_analysis_job_persists_scope_progress_and_cancel(
    isolated_database: Path,
) -> None:
    service = AnalysisJobService()
    evidence = AnalysisEvidenceRepository()
    created = service.create_job(
        track_ids=["track-a", "track-b", "track-c"],
        preferred_provider=" Librosa ",
    )

    assert created.job_id.startswith("aj_")
    assert created.status == "pending"
    assert created.preferred_provider == "librosa"
    assert created.counts == AnalysisJobCounts(selected=3)
    assert service.get_targets(created.job_id) == ("track-a", "track-b", "track-c")

    running = service.mark_running(created.job_id)
    assert running.status == "running"

    first_evidence = _success_evidence(
        evidence,
        evidence_id="ae_job_success",
        track_id="track-a",
    )
    first = service.record_success(
        created.job_id,
        track_id="track-a",
        evidence_id=first_evidence,
        uncertain=True,
    )
    assert first.counts == AnalysisJobCounts(
        selected=3,
        completed=1,
        succeeded=1,
        failed=0,
        uncertain=1,
    )

    failed_evidence = evidence.append_evidence(
        evidence_id="ae_job_failure",
        track_id="track-b",
        provider="librosa",
        analysis_version="canonical-mir-v1",
        status="failed",
        error_code="provider_runtime_error",
        error_detail="Analysis provider failed for this track.",
    )
    second = service.record_failure(
        created.job_id,
        track_id="track-b",
        evidence_id=failed_evidence.evidence_id,
        error_code=failed_evidence.error_code or "provider_runtime_error",
    )
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


def test_analysis_job_scope_is_bounded_unique_and_fail_closed(
    isolated_database: Path,
) -> None:
    repository = AnalysisJobRepository()

    with pytest.raises(ValueError, match="at least one track"):
        repository.create_scope(track_ids=[])

    with pytest.raises(ValueError, match="duplicate"):
        repository.create_scope(track_ids=["track-a", "track-a"])

    created = repository.create_scope(track_ids=["track-a", "track-b"], job_id="aj_fixed")
    assert repository.get_targets(created.job_id) == ("track-a", "track-b")

    with pytest.raises(KeyError, match="unknown analysis job"):
        repository.get_targets("aj_missing")

    with pytest.raises(KeyError, match="outside analysis job scope"):
        repository.record_target_outcome(
            created.job_id,
            track_id="track-outside",
            status="succeeded",
            evidence_id="ae_missing",
        )


def test_analysis_job_completes_only_after_all_target_outcomes(
    isolated_database: Path,
) -> None:
    service = AnalysisJobService()
    evidence = AnalysisEvidenceRepository()
    created = service.create_job(track_ids=["track-a", "track-b"])
    service.mark_running(created.job_id)
    service.record_success(
        created.job_id,
        track_id="track-a",
        evidence_id=_success_evidence(
            evidence,
            evidence_id="ae_complete_1",
            track_id="track-a",
        ),
    )

    with pytest.raises(ValueError, match="cannot finish before"):
        service.finish(created.job_id)

    service.record_success(
        created.job_id,
        track_id="track-b",
        evidence_id=_success_evidence(
            evidence,
            evidence_id="ae_complete_2",
            track_id="track-b",
        ),
    )
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


def test_analysis_job_rejects_duplicate_target_outcome(
    isolated_database: Path,
) -> None:
    service = AnalysisJobService()
    evidence = AnalysisEvidenceRepository()
    created = service.create_job(track_ids=["track-a"])
    service.mark_running(created.job_id)
    evidence_id = _success_evidence(
        evidence,
        evidence_id="ae_once",
        track_id="track-a",
    )
    service.record_success(
        created.job_id,
        track_id="track-a",
        evidence_id=evidence_id,
    )

    with pytest.raises(ValueError, match="already complete|already recorded"):
        service.record_success(
            created.job_id,
            track_id="track-a",
            evidence_id=evidence_id,
        )


def test_analysis_evidence_and_corrections_are_append_only_and_anchored(
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
    assert repository.latest_evidence_for_track("track-1") == second
    assert repository.latest_success_for_track("track-1") == second

    correction = repository.append_correction(
        correction_id="ac_0001",
        track_id="track-1",
        base_evidence_id=second.evidence_id,
        values={"bpm": 140.0, "camelot": "11A"},
        reason="confirmed on deck",
    )
    assert json.loads(correction.payload_json) == {"bpm": 140.0, "camelot": "11A"}
    assert correction.base_evidence_id == second.evidence_id
    assert repository.latest_active_correction("track-1", second.evidence_id) == correction

    failed = repository.append_evidence(
        evidence_id="ae_0003",
        track_id="track-1",
        provider="librosa",
        analysis_version="canonical-mir-v1",
        status="failed",
        error_code="provider_runtime_error",
        error_detail="Analysis provider failed for this track.",
    )
    assert repository.latest_evidence_for_track("track-1") == failed
    assert repository.latest_success_for_track("track-1") == second
    assert repository.latest_active_correction("track-1", second.evidence_id) == correction

    with pytest.raises(sqlite3.IntegrityError):
        repository.append_evidence(
            evidence_id="ae_0003",
            track_id="track-1",
            provider="librosa",
            analysis_version="canonical-mir-v1",
        )

    with pytest.raises(ValueError, match="unsupported fields"):
        repository.append_correction(
            track_id="track-1",
            base_evidence_id=second.evidence_id,
            values={"path": "/must/not/be/stored"},
        )

    with pytest.raises(ValueError, match="same track"):
        repository.append_correction(
            track_id="other-track",
            base_evidence_id=second.evidence_id,
            values={"bpm": 140.0},
        )


def test_analysis_evidence_migrates_pre_outcome_schema_before_index_creation(
    isolated_database: Path,
) -> None:
    with sqlite3.connect(isolated_database) as conn:
        conn.executescript(
            '''
            CREATE TABLE analysis_evidence (
                evidence_id TEXT PRIMARY KEY,
                track_id TEXT NOT NULL,
                provider TEXT NOT NULL,
                analysis_version TEXT NOT NULL,
                provider_version TEXT,
                algorithm_version TEXT,
                bpm REAL,
                bpm_confidence REAL,
                key_tonic TEXT,
                key_scale TEXT,
                camelot TEXT,
                key_confidence REAL,
                energy REAL,
                duration_seconds REAL,
                warnings_json TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE analysis_corrections (
                correction_id TEXT PRIMARY KEY,
                track_id TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                reason TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            '''
        )

    repository = AnalysisEvidenceRepository()
    repository.ensure_schema()

    with sqlite3.connect(isolated_database) as conn:
        evidence_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(analysis_evidence)").fetchall()
        }
        correction_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(analysis_corrections)").fetchall()
        }
        indexes = {
            row[1] for row in conn.execute("PRAGMA index_list(analysis_evidence)").fetchall()
        }

    assert {"status", "error_code", "error_detail", "loudness_db"} <= evidence_columns
    assert "base_evidence_id" in correction_columns
    assert "idx_analysis_evidence_status_created" in indexes


def test_generated_evidence_ids_preserve_latest_order_with_timestamp_ties(
    isolated_database: Path,
) -> None:
    repository = AnalysisEvidenceRepository()
    first = repository.append_evidence(
        track_id="track-order",
        provider="librosa",
        analysis_version="canonical-mir-v1",
        bpm=138.0,
        bpm_confidence=0.8,
        key_tonic="F#",
        key_scale="minor",
        camelot="11A",
        key_confidence=0.8,
        energy=0.7,
    )
    second = repository.append_evidence(
        track_id="track-order",
        provider="librosa",
        analysis_version="canonical-mir-v1",
        bpm=140.0,
        bpm_confidence=0.8,
        key_tonic="F#",
        key_scale="minor",
        camelot="11A",
        key_confidence=0.8,
        energy=0.7,
    )

    assert second.evidence_id > first.evidence_id
    assert repository.latest_evidence_for_track("track-order") == second
