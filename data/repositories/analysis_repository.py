from __future__ import annotations

from typing import Optional

from data.connection import get_sqlite_connection
from data.models.analysis_record import AnalysisRecord
from data.models.playlist_candidate import PlaylistCandidate
from data.repositories.track_repository import TrackRepository


class AnalysisRepository:
    def ensure_schema(self) -> None:
        with get_sqlite_connection() as conn:
            conn.execute(
                '''
                CREATE TABLE IF NOT EXISTS analyses (
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
                )
                '''
            )
            conn.commit()

    def upsert(self, record: AnalysisRecord) -> None:
        self.ensure_schema()
        with get_sqlite_connection() as conn:
            conn.execute(
                '''
                INSERT INTO analyses (
                    track_id, analysis_version, features_version,
                    extractor_backend, extractor_name,
                    bpm, bpm_confidence, key, scale, camelot, energy,
                    loudness_db, duration_seconds, harmonic_ratio, percussive_ratio
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(track_id) DO UPDATE SET
                    analysis_version=excluded.analysis_version,
                    features_version=excluded.features_version,
                    extractor_backend=excluded.extractor_backend,
                    extractor_name=excluded.extractor_name,
                    bpm=excluded.bpm,
                    bpm_confidence=excluded.bpm_confidence,
                    key=excluded.key,
                    scale=excluded.scale,
                    camelot=excluded.camelot,
                    energy=excluded.energy,
                    loudness_db=excluded.loudness_db,
                    duration_seconds=excluded.duration_seconds,
                    harmonic_ratio=excluded.harmonic_ratio,
                    percussive_ratio=excluded.percussive_ratio
                '''
                ,
                (
                    record.track_id,
                    record.analysis_version,
                    record.features_version,
                    record.extractor_backend,
                    record.extractor_name,
                    record.bpm,
                    record.bpm_confidence,
                    record.key,
                    record.scale,
                    record.camelot,
                    record.energy,
                    record.loudness_db,
                    record.duration_seconds,
                    record.harmonic_ratio,
                    record.percussive_ratio,
                ),
            )
            conn.commit()

    def get_by_track_id(self, track_id: str) -> Optional[AnalysisRecord]:
        self.ensure_schema()
        with get_sqlite_connection() as conn:
            row = conn.execute(
                "SELECT * FROM analyses WHERE track_id = ?",
                (track_id,),
            ).fetchone()
            if row is None:
                return None
            return AnalysisRecord(**dict(row))

    def list_playlist_candidates(self) -> list[PlaylistCandidate]:
        """Return only analyses that have a non-empty resolvable track path."""
        self.ensure_schema()
        TrackRepository().ensure_schema()

        with get_sqlite_connection() as conn:
            rows = conn.execute(
                '''
                SELECT
                    analyses.track_id,
                    tracks.path,
                    tracks.title,
                    tracks.artist,
                    analyses.bpm,
                    analyses.camelot,
                    analyses.energy
                FROM analyses
                INNER JOIN tracks ON tracks.track_id = analyses.track_id
                WHERE NULLIF(TRIM(tracks.path), '') IS NOT NULL
                ORDER BY analyses.track_id
                '''
            ).fetchall()

        return [PlaylistCandidate(**dict(row)) for row in rows]
