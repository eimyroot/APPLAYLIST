from __future__ import annotations

import sqlite3

from data.migrations.registry import MIGRATIONS, MigrationConnection


def test_v001_registry_shape() -> None:
    assert len(MIGRATIONS) == 1
    migration = MIGRATIONS[0]
    assert migration.from_version == 0
    assert migration.to_version == 1
    assert migration.name == "v001_canonical_analyses"


def test_v001_creates_only_empty_canonical_table() -> None:
    conn = sqlite3.connect(":memory:")
    try:
        migration = MIGRATIONS[0]
        migration.apply(MigrationConnection(conn))
        columns = conn.execute(
            "PRAGMA table_info(canonical_analyses)"
        ).fetchall()
        assert [row[1] for row in columns] == [
            "track_id",
            "provider",
            "provider_version",
            "canonical_analysis_version",
            "source_analysis_version",
            "bpm",
            "bpm_confidence",
            "key",
            "key_confidence",
            "key_system",
            "energy",
            "energy_confidence",
            "loudness_db",
            "loudness_integrated_lufs",
            "duration_seconds",
            "sample_rate_hz",
            "channels",
            "genre_hint",
            "analysis_status",
            "analyzed_at",
            "warnings_json",
            "persisted_at",
        ]
        assert conn.execute(
            "SELECT COUNT(*) FROM canonical_analyses"
        ).fetchone()[0] == 0
    finally:
        conn.close()
