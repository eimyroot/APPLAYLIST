from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from data.migrations.schema_fingerprint import (
    SchemaFingerprintError,
    inspect_schema,
    open_sqlite_readonly,
    protected_table_state,
    validate_legacy_v0,
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


def test_legacy_v0_fingerprint_is_deterministic(tmp_path: Path) -> None:
    db = tmp_path / "legacy.sqlite3"
    _create_legacy_v0(db)

    first_conn = open_sqlite_readonly(db)
    try:
        first = inspect_schema(first_conn)
        validate_legacy_v0(first)
        first_state = protected_table_state(first_conn)
    finally:
        first_conn.close()

    second_conn = open_sqlite_readonly(db)
    try:
        second = inspect_schema(second_conn)
    finally:
        second_conn.close()

    assert first == second
    assert first.sha256 == second.sha256
    assert first.user_version == 0
    assert set(first_state) == {"analyses", "jobs", "tracks"}
    assert first_state["analyses"]["row_count"] == 1


def test_legacy_v0_rejects_schema_drift(tmp_path: Path) -> None:
    db = tmp_path / "drift.sqlite3"
    _create_legacy_v0(db)
    conn = sqlite3.connect(db)
    try:
        conn.execute("ALTER TABLE tracks ADD COLUMN unexpected TEXT")
        conn.commit()
    finally:
        conn.close()

    read_conn = open_sqlite_readonly(db)
    try:
        fingerprint = inspect_schema(read_conn)
    finally:
        read_conn.close()

    with pytest.raises(SchemaFingerprintError):
        validate_legacy_v0(fingerprint)


def test_readonly_open_does_not_create_missing_database(tmp_path: Path) -> None:
    missing = tmp_path / "missing.sqlite3"
    with pytest.raises(FileNotFoundError):
        open_sqlite_readonly(missing)
    assert not missing.exists()


def test_legacy_v0_rejects_extra_table(tmp_path: Path) -> None:
    db = tmp_path / "extra.sqlite3"
    _create_legacy_v0(db)
    conn = sqlite3.connect(db)
    try:
        conn.execute("CREATE TABLE unexpected (id INTEGER PRIMARY KEY)")
        conn.commit()
    finally:
        conn.close()

    read_conn = open_sqlite_readonly(db)
    try:
        fingerprint = inspect_schema(read_conn)
    finally:
        read_conn.close()

    with pytest.raises(SchemaFingerprintError):
        validate_legacy_v0(fingerprint)


def test_legacy_v0_rejects_nonzero_user_version(tmp_path: Path) -> None:
    db = tmp_path / "versioned.sqlite3"
    _create_legacy_v0(db)
    conn = sqlite3.connect(db)
    try:
        conn.execute("PRAGMA user_version = 1")
        conn.commit()
    finally:
        conn.close()

    read_conn = open_sqlite_readonly(db)
    try:
        fingerprint = inspect_schema(read_conn)
    finally:
        read_conn.close()

    with pytest.raises(SchemaFingerprintError):
        validate_legacy_v0(fingerprint)


def test_legacy_v0_rejects_unexpected_index(tmp_path: Path) -> None:
    db = tmp_path / "index.sqlite3"
    _create_legacy_v0(db)
    conn = sqlite3.connect(db)
    try:
        conn.execute("CREATE INDEX tracks_title_idx ON tracks(title)")
        conn.commit()
    finally:
        conn.close()

    read_conn = open_sqlite_readonly(db)
    try:
        fingerprint = inspect_schema(read_conn)
    finally:
        read_conn.close()

    with pytest.raises(SchemaFingerprintError):
        validate_legacy_v0(fingerprint)
