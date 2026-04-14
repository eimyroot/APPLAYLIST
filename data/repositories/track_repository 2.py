from __future__ import annotations

from typing import Optional

from data.connection import get_sqlite_connection
from data.models.track_record import TrackRecord


class TrackRepository:
    def ensure_schema(self) -> None:
        with get_sqlite_connection() as conn:
            conn.execute(
                '''
                CREATE TABLE IF NOT EXISTS tracks (
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
                )
                '''
            )
            conn.commit()

    def upsert(self, record: TrackRecord) -> None:
        self.ensure_schema()
        with get_sqlite_connection() as conn:
            conn.execute(
                '''
                INSERT INTO tracks (
                    track_id, path, title, artist, album, genre, source,
                    duration_seconds, sample_rate_hz, bitrate_kbps
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(track_id) DO UPDATE SET
                    path=excluded.path,
                    title=excluded.title,
                    artist=excluded.artist,
                    album=excluded.album,
                    genre=excluded.genre,
                    source=excluded.source,
                    duration_seconds=excluded.duration_seconds,
                    sample_rate_hz=excluded.sample_rate_hz,
                    bitrate_kbps=excluded.bitrate_kbps
                '''
                ,
                (
                    record.track_id,
                    record.path,
                    record.title,
                    record.artist,
                    record.album,
                    record.genre,
                    record.source,
                    record.duration_seconds,
                    record.sample_rate_hz,
                    record.bitrate_kbps,
                ),
            )
            conn.commit()

    def get_by_id(self, track_id: str) -> Optional[TrackRecord]:
        self.ensure_schema()
        with get_sqlite_connection() as conn:
            row = conn.execute(
                "SELECT * FROM tracks WHERE track_id = ?",
                (track_id,),
            ).fetchone()
            if row is None:
                return None
            return TrackRecord(**dict(row))
