from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from data.migrations.registry import Migration, MigrationConnection
from data.migrations.runner import MigrationRunnerError, apply_next_migration, migration_plan
from data.migrations.schema_fingerprint import inspect_schema, open_sqlite_readonly


def _create_legacy_v0(path: Path) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.executescript(
            """
            CREATE TABLE analyses (
                track_id TEXT PRIMARY KEY,
                analysis_version TEXT NOT NULL,
                features_version TEXT NOT NULL,
                extractor_backend TEXT NOT NULL,
                extractor_name TEXT NOT NULL,
                bpm REAL,
                bpm_confidence REAL,
                key TEXT,
                scale TEXT,
                camelot TEXT,
                energy REAL,
                loudness_db REAL,
                duration_seconds REAL,
                harmonic_ratio REAL,
                percussive_ratio REAL
            );
            CREATE TABLE jobs (
                job_id TEXT PRIMARY KEY,
                job_type TEXT NOT NULL,
                status TEXT NOT NULL,
                progress REAL NOT NULL DEFAULT 0,
                error_code TEXT,
                error_detail TEXT
            );
            CREATE TABLE tracks (
                track_id TEXT PRIMARY KEY,
                path TEXT NOT NULL,
                title TEXT,
                artist TEXT,
                album TEXT,
                genre TEXT,
                source TEXT,
                duration_seconds REAL,
                sample_rate_hz INTEGER,
                bitrate_kbps INTEGER
            );
            """
        )
        conn.execute(
            "INSERT INTO analyses VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "track-1",
                "legacy-v1",
                "features-v1",
                "librosa",
                "analyzer",
                128.0,
                None,
                "A",
                "minor",
                "8A",
                0.7,
                -9.0,
                180.0,
                0.4,
                0.6,
            ),
        )
        conn.execute(
            "INSERT INTO jobs VALUES (?, ?, ?, ?, ?, ?)",
            ("job-1", "analysis", "done", 1.0, None, None),
        )
        conn.execute(
            "INSERT INTO tracks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "track-1",
                "/music/track.wav",
                "Track",
                "Artist",
                None,
                None,
                "local",
                180.0,
                44100,
                320,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def _baseline_sha(db: Path) -> str:
    conn = open_sqlite_readonly(db)
    try:
        return inspect_schema(conn).sha256
    finally:
        conn.close()


def _create_marker_table(conn: MigrationConnection) -> None:
    conn.execute("CREATE TABLE migration_marker (id INTEGER PRIMARY KEY)")


def _raise_after_ddl(conn: MigrationConnection) -> None:
    conn.execute("CREATE TABLE should_rollback (id INTEGER PRIMARY KEY)")
    raise RuntimeError("simulated migration failure")


def test_empty_registry_plan_is_empty(tmp_path: Path) -> None:
    db = tmp_path / "legacy.sqlite3"
    _create_legacy_v0(db)
    assert migration_plan(db, ()) == ()


def test_non_contiguous_registry_is_rejected(tmp_path: Path) -> None:
    db = tmp_path / "legacy.sqlite3"
    _create_legacy_v0(db)
    bad = (
        Migration(0, 1, "first", _create_marker_table),
        Migration(2, 3, "skipped", _create_marker_table),
    )
    with pytest.raises(MigrationRunnerError):
        migration_plan(db, bad)


def test_successful_disposable_migration_updates_schema_and_ledger_atomically(
    tmp_path: Path,
) -> None:
    db = tmp_path / "legacy.sqlite3"
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    _create_legacy_v0(db)
    migrations = (Migration(0, 1, "marker", _create_marker_table),)

    result = apply_next_migration(
        db,
        backup_dir,
        migrations=migrations,
        expected_legacy_v0_sha256=_baseline_sha(db),
    )

    conn = open_sqlite_readonly(db)
    try:
        version = int(conn.execute("PRAGMA user_version").fetchone()[0])
        marker = conn.execute(
            "SELECT name FROM sqlite_schema WHERE type='table' AND name='migration_marker'"
        ).fetchone()
    finally:
        conn.close()

    assert result.from_version == 0
    assert result.to_version == 1
    assert version == 1
    assert marker is not None


def test_migration_exception_rolls_back_schema_and_user_version(tmp_path: Path) -> None:
    db = tmp_path / "legacy.sqlite3"
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    _create_legacy_v0(db)
    migrations = (Migration(0, 1, "boom", _raise_after_ddl),)

    with pytest.raises(MigrationRunnerError, match="simulated migration failure"):
        apply_next_migration(
            db,
            backup_dir,
            migrations=migrations,
            expected_legacy_v0_sha256=_baseline_sha(db),
        )

    conn = open_sqlite_readonly(db)
    try:
        version = int(conn.execute("PRAGMA user_version").fetchone()[0])
        rolled_back = conn.execute(
            "SELECT name FROM sqlite_schema WHERE type='table' AND name='should_rollback'"
        ).fetchone()
    finally:
        conn.close()

    assert version == 0
    assert rolled_back is None


def test_lock_contention_fails_closed(tmp_path: Path) -> None:
    db = tmp_path / "legacy.sqlite3"
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    _create_legacy_v0(db)
    migrations = (Migration(0, 1, "marker", _create_marker_table),)

    blocker = sqlite3.connect(db, isolation_level=None)
    blocker.execute("BEGIN IMMEDIATE")
    try:
        with pytest.raises(MigrationRunnerError, match="write lock"):
            apply_next_migration(
                db,
                backup_dir,
                migrations=migrations,
                lock_timeout_seconds=0.01,
                expected_legacy_v0_sha256=_baseline_sha(db),
            )
    finally:
        blocker.execute("ROLLBACK")
        blocker.close()

    conn = open_sqlite_readonly(db)
    try:
        assert int(conn.execute("PRAGMA user_version").fetchone()[0]) == 0
    finally:
        conn.close()


def test_v0_migration_requires_pinned_schema_sha(tmp_path: Path) -> None:
    db = tmp_path / "legacy.sqlite3"
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    _create_legacy_v0(db)
    migrations = (Migration(0, 1, "marker", _create_marker_table),)

    with pytest.raises(MigrationRunnerError, match="pinned schema SHA-256"):
        apply_next_migration(db, backup_dir, migrations=migrations)

    assert list(backup_dir.iterdir()) == []


def test_v0_migration_rejects_wrong_pinned_schema_sha(tmp_path: Path) -> None:
    db = tmp_path / "legacy.sqlite3"
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    _create_legacy_v0(db)
    migrations = (Migration(0, 1, "marker", _create_marker_table),)

    with pytest.raises(MigrationRunnerError, match="does not match"):
        apply_next_migration(
            db,
            backup_dir,
            migrations=migrations,
            expected_legacy_v0_sha256="0" * 64,
        )

    assert list(backup_dir.iterdir()) == []


def test_duplicate_registry_version_is_rejected(tmp_path: Path) -> None:
    db = tmp_path / "legacy.sqlite3"
    _create_legacy_v0(db)
    duplicate = (
        Migration(0, 1, "first", _create_marker_table),
        Migration(0, 1, "duplicate", _create_marker_table),
    )
    with pytest.raises(MigrationRunnerError):
        migration_plan(db, duplicate)
