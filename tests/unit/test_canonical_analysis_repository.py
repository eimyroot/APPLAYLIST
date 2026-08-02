from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from data.migrations.versions.v001_canonical_analyses import (
    apply_v001_canonical_analyses,
)
from data.models.canonical_analysis_record import (
    CanonicalAnalysisPersistenceRecord,
)
from data.repositories.canonical_analysis_repository import (
    CanonicalAnalysisRepository,
    CanonicalAnalysisRepositoryError,
)


def _create_v1_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            """
            CREATE TABLE analyses (
                track_id TEXT PRIMARY KEY,
                payload TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            INSERT INTO analyses (track_id, payload)
            VALUES (?, ?)
            """,
            ("legacy-1", "unchanged"),
        )
        apply_v001_canonical_analyses(conn)
        conn.execute("PRAGMA user_version = 1")
        conn.commit()
    finally:
        conn.close()


def _factory(path: Path):
    def connect() -> sqlite3.Connection:
        return sqlite3.connect(path)

    return connect


def _record(
    *,
    track_id: str = "track-1",
    bpm: float | None = 128.0,
) -> CanonicalAnalysisPersistenceRecord:
    return CanonicalAnalysisPersistenceRecord(
        track_id=track_id,
        provider="essentia",
        provider_version="2.1",
        canonical_analysis_version="canonical-mir-v1",
        source_analysis_version="essentia-profile-v1",
        bpm=bpm,
        bpm_confidence=None,
        key="Am",
        key_confidence=0.9,
        key_system="traditional",
        energy=0.7,
        energy_confidence=None,
        loudness_db=-9.0,
        loudness_integrated_lufs=-10.0,
        duration_seconds=240.0,
        sample_rate_hz=44100,
        channels=2,
        genre_hint="techno",
        analysis_status="complete",
        analyzed_at="2026-08-01T20:00:00+00:00",
        warnings_json='["warning"]',
    )


def _legacy_payload(path: Path) -> tuple[str, str]:
    conn = sqlite3.connect(path)
    try:
        row = conn.execute(
            """
            SELECT track_id, payload
            FROM analyses
            ORDER BY track_id
            """
        ).fetchone()
    finally:
        conn.close()

    assert row is not None
    return row


def test_insert_get_exists_round_trip_and_legacy_unchanged(
    tmp_path: Path,
) -> None:
    db = tmp_path / "repo.sqlite3"
    _create_v1_db(db)
    legacy_before = _legacy_payload(db)

    repo = CanonicalAnalysisRepository(_factory(db))
    expected = _record()
    repo.upsert(expected)

    assert repo.exists("track-1") is True
    actual = repo.get("track-1")
    assert actual is not None
    assert actual.track_id == expected.track_id
    assert actual.bpm == expected.bpm
    assert actual.bpm_confidence is None
    assert actual.warnings_json == expected.warnings_json
    assert _legacy_payload(db) == legacy_before


def test_upsert_updates_same_track_without_duplicate(
    tmp_path: Path,
) -> None:
    db = tmp_path / "repo.sqlite3"
    _create_v1_db(db)
    repo = CanonicalAnalysisRepository(_factory(db))

    repo.upsert(_record(bpm=128.0))
    repo.upsert(_record(bpm=130.0))

    conn = sqlite3.connect(db)
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM canonical_analyses"
        ).fetchone()[0]
    finally:
        conn.close()

    assert count == 1
    actual = repo.get("track-1")
    assert actual is not None
    assert actual.bpm == 130.0


def test_repository_rejects_wrong_payload(tmp_path: Path) -> None:
    db = tmp_path / "repo.sqlite3"
    _create_v1_db(db)
    repo = CanonicalAnalysisRepository(_factory(db))

    with pytest.raises(TypeError):
        repo.upsert({"track_id": "wrong"})  # type: ignore[arg-type]


def test_transaction_rolls_back_on_injected_commit_failure(
    tmp_path: Path,
) -> None:
    db = tmp_path / "repo.sqlite3"
    _create_v1_db(db)

    class FailingCommitConnection(sqlite3.Connection):
        def commit(self) -> None:
            raise sqlite3.OperationalError(
                "injected commit failure"
            )

    def failing_factory() -> sqlite3.Connection:
        return sqlite3.connect(
            db,
            factory=FailingCommitConnection,
        )

    repo = CanonicalAnalysisRepository(failing_factory)

    with pytest.raises(CanonicalAnalysisRepositoryError) as error:
        repo.upsert(_record())

    assert error.value.operation == "upsert"

    conn = sqlite3.connect(db)
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM canonical_analyses"
        ).fetchone()[0]
    finally:
        conn.close()

    assert count == 0
