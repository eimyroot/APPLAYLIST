from __future__ import annotations

from collections.abc import Callable
import hashlib
import json
import sqlite3

from core.library.persistence import PersistedTrack
from core.library.track_metadata import TrackImportCandidate
from data.connection import get_sqlite_connection


class LibraryTrackRepository:
    def __init__(
        self,
        *,
        connection_factory: Callable[[], sqlite3.Connection] = get_sqlite_connection,
    ) -> None:
        self._connection_factory = connection_factory

    @staticmethod
    def _ensure_schema(conn: sqlite3.Connection) -> None:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(
            """
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
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS track_files (
                track_id TEXT NOT NULL,
                path TEXT NOT NULL,
                size_bytes INTEGER NOT NULL CHECK(size_bytes >= 0),
                mtime_ns INTEGER NOT NULL CHECK(mtime_ns >= 0),
                is_current INTEGER NOT NULL CHECK(is_current IN (0, 1)),
                first_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (track_id, path),
                FOREIGN KEY (track_id) REFERENCES tracks(track_id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_track_files_current
            ON track_files(track_id, is_current)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_track_files_path
            ON track_files(path, is_current)
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS track_metadata_snapshots (
                track_id TEXT NOT NULL,
                snapshot_digest TEXT NOT NULL,
                provider TEXT NOT NULL,
                provider_version TEXT NOT NULL,
                origin TEXT NOT NULL,
                title TEXT,
                artist TEXT,
                album TEXT,
                genre TEXT,
                duration_seconds REAL,
                sample_rate_hz INTEGER,
                bitrate_kbps INTEGER,
                warnings_json TEXT NOT NULL,
                is_current INTEGER NOT NULL CHECK(is_current IN (0, 1)),
                first_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (track_id, snapshot_digest),
                FOREIGN KEY (track_id) REFERENCES tracks(track_id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_track_metadata_current
            ON track_metadata_snapshots(track_id, is_current)
            """
        )

    @staticmethod
    def _metadata_payload(candidate: TrackImportCandidate) -> dict[str, object]:
        metadata = candidate.metadata
        return {
            "provider": metadata.provider,
            "provider_version": metadata.provider_version,
            "origin": metadata.origin.value,
            "title": metadata.title,
            "artist": metadata.artist,
            "album": metadata.album,
            "genre": metadata.genre,
            "duration_seconds": metadata.duration_seconds,
            "sample_rate_hz": metadata.sample_rate_hz,
            "bitrate_kbps": metadata.bitrate_kbps,
            "warnings": list(metadata.warnings),
        }

    @classmethod
    def _metadata_digest(cls, candidate: TrackImportCandidate) -> str:
        payload = json.dumps(
            cls._metadata_payload(candidate),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def persist_candidate(self, candidate: TrackImportCandidate) -> PersistedTrack:
        identity = candidate.identity
        metadata = candidate.metadata
        snapshot_digest = self._metadata_digest(candidate)

        with self._connection_factory() as conn:
            self._ensure_schema(conn)
            current_row = conn.execute(
                """
                SELECT path
                FROM track_files
                WHERE track_id = ? AND is_current = 1
                ORDER BY last_seen_at DESC, path ASC
                LIMIT 1
                """,
                (identity.track_id,),
            ).fetchone()
            previous_path = None if current_row is None else str(current_row["path"])
            relinked = previous_path is not None and previous_path != identity.source_path

            conn.execute(
                """
                INSERT INTO tracks (
                    track_id, path, title, artist, album, genre, source,
                    duration_seconds, sample_rate_hz, bitrate_kbps
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(track_id) DO UPDATE SET
                    path = excluded.path,
                    title = excluded.title,
                    artist = excluded.artist,
                    album = excluded.album,
                    genre = excluded.genre,
                    source = excluded.source,
                    duration_seconds = excluded.duration_seconds,
                    sample_rate_hz = excluded.sample_rate_hz,
                    bitrate_kbps = excluded.bitrate_kbps
                """,
                (
                    identity.track_id,
                    identity.source_path,
                    metadata.title,
                    metadata.artist,
                    metadata.album,
                    metadata.genre,
                    metadata.provider,
                    metadata.duration_seconds,
                    metadata.sample_rate_hz,
                    metadata.bitrate_kbps,
                ),
            )

            conn.execute(
                "UPDATE track_files SET is_current = 0 WHERE track_id = ?",
                (identity.track_id,),
            )
            conn.execute(
                "UPDATE track_files SET is_current = 0 WHERE path = ? AND track_id <> ?",
                (identity.source_path, identity.track_id),
            )
            conn.execute(
                """
                INSERT INTO track_files (
                    track_id, path, size_bytes, mtime_ns, is_current
                )
                VALUES (?, ?, ?, ?, 1)
                ON CONFLICT(track_id, path) DO UPDATE SET
                    size_bytes = excluded.size_bytes,
                    mtime_ns = excluded.mtime_ns,
                    is_current = 1,
                    last_seen_at = CURRENT_TIMESTAMP
                """,
                (
                    identity.track_id,
                    identity.source_path,
                    identity.size_bytes,
                    identity.mtime_ns,
                ),
            )

            conn.execute(
                "UPDATE track_metadata_snapshots SET is_current = 0 WHERE track_id = ?",
                (identity.track_id,),
            )
            payload = self._metadata_payload(candidate)
            conn.execute(
                """
                INSERT INTO track_metadata_snapshots (
                    track_id, snapshot_digest, provider, provider_version, origin,
                    title, artist, album, genre, duration_seconds,
                    sample_rate_hz, bitrate_kbps, warnings_json, is_current
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                ON CONFLICT(track_id, snapshot_digest) DO UPDATE SET
                    is_current = 1,
                    last_seen_at = CURRENT_TIMESTAMP
                """,
                (
                    identity.track_id,
                    snapshot_digest,
                    payload["provider"],
                    payload["provider_version"],
                    payload["origin"],
                    payload["title"],
                    payload["artist"],
                    payload["album"],
                    payload["genre"],
                    payload["duration_seconds"],
                    payload["sample_rate_hz"],
                    payload["bitrate_kbps"],
                    json.dumps(payload["warnings"], ensure_ascii=False),
                ),
            )

        return PersistedTrack(
            track_id=identity.track_id,
            current_path=identity.source_path,
            metadata_provider=metadata.provider,
            metadata_provider_version=metadata.provider_version,
            metadata_origin=metadata.origin,
            relinked=relinked,
        )

    def get_current_path(self, track_id: str) -> str | None:
        with self._connection_factory() as conn:
            self._ensure_schema(conn)
            row = conn.execute(
                """
                SELECT path
                FROM track_files
                WHERE track_id = ? AND is_current = 1
                ORDER BY last_seen_at DESC, path ASC
                LIMIT 1
                """,
                (track_id,),
            ).fetchone()
            return None if row is None else str(row["path"])

    def list_file_history(self, track_id: str) -> tuple[tuple[str, bool], ...]:
        with self._connection_factory() as conn:
            self._ensure_schema(conn)
            rows = conn.execute(
                """
                SELECT path, is_current
                FROM track_files
                WHERE track_id = ?
                ORDER BY path COLLATE NOCASE, path
                """,
                (track_id,),
            ).fetchall()
            return tuple((str(row["path"]), bool(row["is_current"])) for row in rows)

    def metadata_snapshot_count(self, track_id: str) -> int:
        with self._connection_factory() as conn:
            self._ensure_schema(conn)
            row = conn.execute(
                "SELECT COUNT(*) AS count FROM track_metadata_snapshots WHERE track_id = ?",
                (track_id,),
            ).fetchone()
            return int(row["count"])
