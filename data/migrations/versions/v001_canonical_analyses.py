from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from data.migrations.registry import MigrationConnection


def apply_v001_canonical_analyses(connection: MigrationConnection) -> None:
    connection.execute(
        """
        CREATE TABLE canonical_analyses (
            track_id TEXT PRIMARY KEY,
            provider TEXT NOT NULL,
            provider_version TEXT,
            canonical_analysis_version TEXT NOT NULL,
            source_analysis_version TEXT,
            bpm REAL,
            bpm_confidence REAL,
            key TEXT,
            key_confidence REAL,
            key_system TEXT,
            energy REAL,
            energy_confidence REAL,
            loudness_db REAL,
            loudness_integrated_lufs REAL,
            duration_seconds REAL,
            sample_rate_hz INTEGER,
            channels INTEGER,
            genre_hint TEXT,
            analysis_status TEXT NOT NULL,
            analyzed_at TEXT,
            warnings_json TEXT NOT NULL DEFAULT '[]',
            persisted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
