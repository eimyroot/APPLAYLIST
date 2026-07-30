from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from data.migrations.schema_fingerprint import open_sqlite_readonly, protected_table_state
from data.migrations.sqlite_backup import (
    SQLiteBackupError,
    create_verified_backup,
    verify_disposable_restore,
    write_backup_manifest,
)


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


def test_backup_and_disposable_restore_preserve_logical_state(tmp_path: Path) -> None:
    source = tmp_path / "source.sqlite3"
    backup = tmp_path / "backup.sqlite3"
    _create_legacy_v0(source)

    source_conn = open_sqlite_readonly(source)
    try:
        source_state = protected_table_state(source_conn)
    finally:
        source_conn.close()

    evidence = create_verified_backup(source, backup)
    restored = verify_disposable_restore(evidence)

    assert backup.is_file()
    assert evidence.source_schema_sha256 == evidence.backup_schema_sha256
    assert evidence.source_table_state == evidence.backup_table_state == source_state
    assert restored.restored_schema_sha256 == evidence.source_schema_sha256
    assert restored.restored_table_state == source_state


def test_backup_rejects_existing_destination(tmp_path: Path) -> None:
    source = tmp_path / "source.sqlite3"
    backup = tmp_path / "backup.sqlite3"
    _create_legacy_v0(source)
    backup.write_bytes(b"already exists")

    with pytest.raises(SQLiteBackupError):
        create_verified_backup(source, backup)


def test_corrupted_backup_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "source.sqlite3"
    backup = tmp_path / "backup.sqlite3"
    _create_legacy_v0(source)
    evidence = create_verified_backup(source, backup)

    with backup.open("ab") as handle:
        handle.write(b"corruption")

    with pytest.raises(SQLiteBackupError):
        verify_disposable_restore(evidence)


def test_missing_source_is_rejected_without_creation(tmp_path: Path) -> None:
    source = tmp_path / "missing.sqlite3"
    backup = tmp_path / "backup.sqlite3"

    with pytest.raises(SQLiteBackupError):
        create_verified_backup(source, backup)

    assert not source.exists()
    assert not backup.exists()


def test_backup_manifest_records_repository_and_plan_context(tmp_path: Path) -> None:
    source = tmp_path / "source.sqlite3"
    backup = tmp_path / "backup.sqlite3"
    manifest = tmp_path / "BACKUP_MANIFEST.json"
    _create_legacy_v0(source)
    evidence = create_verified_backup(source, backup)

    written = write_backup_manifest(
        evidence,
        manifest,
        repository_head="abc123",
        migration_from_version=0,
        migration_to_version=1,
    )

    text = written.read_text(encoding="utf-8")
    assert '"repository_head": "abc123"' in text
    assert '"migration_plan_from_version": 0' in text
    assert '"migration_plan_to_version": 1' in text
