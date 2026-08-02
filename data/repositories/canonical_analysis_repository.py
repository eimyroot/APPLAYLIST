from __future__ import annotations

import sqlite3
from collections.abc import Callable
from dataclasses import fields
from typing import Any

from data.connection import get_sqlite_connection
from data.models.canonical_analysis_record import (
    CanonicalAnalysisPersistenceRecord,
)

ConnectionFactory = Callable[[], sqlite3.Connection]


class CanonicalAnalysisRepositoryError(RuntimeError):
    def __init__(self, operation: str, message: str) -> None:
        self.operation = operation
        super().__init__(f"canonical analysis {operation} failed: {message}")


class CanonicalAnalysisRepository:
    def __init__(
        self,
        connection_factory: ConnectionFactory = get_sqlite_connection,
    ) -> None:
        self._connection_factory = connection_factory

    def upsert(self, record: CanonicalAnalysisPersistenceRecord) -> None:
        if not isinstance(record, CanonicalAnalysisPersistenceRecord):
            raise TypeError(
                "record must be CanonicalAnalysisPersistenceRecord"
            )

        conn = self._connection_factory()
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """
                INSERT INTO canonical_analyses (
                    track_id,
                    provider,
                    provider_version,
                    canonical_analysis_version,
                    source_analysis_version,
                    bpm,
                    bpm_confidence,
                    key,
                    key_confidence,
                    key_system,
                    energy,
                    energy_confidence,
                    loudness_db,
                    loudness_integrated_lufs,
                    duration_seconds,
                    sample_rate_hz,
                    channels,
                    genre_hint,
                    analysis_status,
                    analyzed_at,
                    warnings_json
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                ON CONFLICT(track_id) DO UPDATE SET
                    provider = excluded.provider,
                    provider_version = excluded.provider_version,
                    canonical_analysis_version =
                        excluded.canonical_analysis_version,
                    source_analysis_version =
                        excluded.source_analysis_version,
                    bpm = excluded.bpm,
                    bpm_confidence = excluded.bpm_confidence,
                    key = excluded.key,
                    key_confidence = excluded.key_confidence,
                    key_system = excluded.key_system,
                    energy = excluded.energy,
                    energy_confidence = excluded.energy_confidence,
                    loudness_db = excluded.loudness_db,
                    loudness_integrated_lufs =
                        excluded.loudness_integrated_lufs,
                    duration_seconds = excluded.duration_seconds,
                    sample_rate_hz = excluded.sample_rate_hz,
                    channels = excluded.channels,
                    genre_hint = excluded.genre_hint,
                    analysis_status = excluded.analysis_status,
                    analyzed_at = excluded.analyzed_at,
                    warnings_json = excluded.warnings_json,
                    persisted_at = CURRENT_TIMESTAMP
                """,
                (
                    record.track_id,
                    record.provider,
                    record.provider_version,
                    record.canonical_analysis_version,
                    record.source_analysis_version,
                    record.bpm,
                    record.bpm_confidence,
                    record.key,
                    record.key_confidence,
                    record.key_system,
                    record.energy,
                    record.energy_confidence,
                    record.loudness_db,
                    record.loudness_integrated_lufs,
                    record.duration_seconds,
                    record.sample_rate_hz,
                    record.channels,
                    record.genre_hint,
                    record.analysis_status,
                    record.analyzed_at,
                    record.warnings_json,
                ),
            )
            conn.commit()
        except Exception as exc:
            try:
                conn.rollback()
            except sqlite3.Error:
                pass
            raise CanonicalAnalysisRepositoryError(
                "upsert",
                str(exc),
            ) from exc
        finally:
            conn.close()

    def get(
        self,
        track_id: str,
    ) -> CanonicalAnalysisPersistenceRecord | None:
        conn = self._connection_factory()
        try:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT
                    track_id,
                    provider,
                    provider_version,
                    canonical_analysis_version,
                    source_analysis_version,
                    bpm,
                    bpm_confidence,
                    key,
                    key_confidence,
                    key_system,
                    energy,
                    energy_confidence,
                    loudness_db,
                    loudness_integrated_lufs,
                    duration_seconds,
                    sample_rate_hz,
                    channels,
                    genre_hint,
                    analysis_status,
                    analyzed_at,
                    warnings_json,
                    persisted_at
                FROM canonical_analyses
                WHERE track_id = ?
                """,
                (track_id,),
            ).fetchone()
        except Exception as exc:
            raise CanonicalAnalysisRepositoryError(
                "get",
                str(exc),
            ) from exc
        finally:
            conn.close()

        if row is None:
            return None

        allowed = {
            field.name
            for field in fields(CanonicalAnalysisPersistenceRecord)
        }
        payload: dict[str, Any] = {
            key: row[key]
            for key in row.keys()
            if key in allowed
        }
        return CanonicalAnalysisPersistenceRecord(**payload)

    def exists(self, track_id: str) -> bool:
        conn = self._connection_factory()
        try:
            row = conn.execute(
                """
                SELECT 1
                FROM canonical_analyses
                WHERE track_id = ?
                """,
                (track_id,),
            ).fetchone()
        except Exception as exc:
            raise CanonicalAnalysisRepositoryError(
                "exists",
                str(exc),
            ) from exc
        finally:
            conn.close()

        return row is not None
