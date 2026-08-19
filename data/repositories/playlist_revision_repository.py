from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence

from data.connection import get_sqlite_connection

_MAX_ITEMS = 8
_MAX_HISTORY = 100
_OPERATIONS = {"accept", "reorder", "lock", "replace", "regenerate"}


class PlaylistRevisionRepositoryError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class PlaylistRevisionRepository:
    """Append-only immutable local playlist revision ledger."""

    def ensure_schema(self) -> None:
        with get_sqlite_connection() as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            self._create_schema(conn)
            row = conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='playlist_revisions'"
            ).fetchone()
            table_sql = "" if row is None else str(row["sql"] or "")
            if "regenerate" not in table_sql:
                conn.commit()
                self._migrate_revision_operations(conn)
            conn.commit()

    @staticmethod
    def _create_schema(conn: object) -> None:
        conn.executescript(  # type: ignore[attr-defined]
            """
            CREATE TABLE IF NOT EXISTS playlist_revisions (
                revision_id TEXT PRIMARY KEY,
                playlist_id TEXT NOT NULL,
                parent_revision_id TEXT,
                revision_index INTEGER NOT NULL CHECK (revision_index >= 0),
                source_proposal_id TEXT NOT NULL,
                source_path_id TEXT NOT NULL,
                operation TEXT NOT NULL CHECK (operation IN ('accept','reorder','lock','replace','regenerate')),
                operation_json TEXT NOT NULL,
                content_fingerprint TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                personal_dj_model_training_authorized INTEGER NOT NULL DEFAULT 0 CHECK (personal_dj_model_training_authorized = 0),
                production_activation_authorized INTEGER NOT NULL DEFAULT 0 CHECK (production_activation_authorized = 0),
                UNIQUE (playlist_id, revision_index),
                FOREIGN KEY(parent_revision_id) REFERENCES playlist_revisions(revision_id)
            );
            CREATE TABLE IF NOT EXISTS playlist_revision_items (
                revision_id TEXT NOT NULL,
                order_index INTEGER NOT NULL CHECK (order_index >= 0),
                track_id TEXT NOT NULL,
                display_name TEXT NOT NULL,
                locked INTEGER NOT NULL DEFAULT 0 CHECK (locked IN (0,1)),
                PRIMARY KEY (revision_id, order_index),
                UNIQUE (revision_id, track_id),
                FOREIGN KEY(revision_id) REFERENCES playlist_revisions(revision_id)
            );
            CREATE INDEX IF NOT EXISTS idx_playlist_revision_head ON playlist_revisions(playlist_id, revision_index);
            CREATE TRIGGER IF NOT EXISTS playlist_revisions_no_update BEFORE UPDATE ON playlist_revisions BEGIN SELECT RAISE(ABORT, 'playlist revisions are immutable'); END;
            CREATE TRIGGER IF NOT EXISTS playlist_revisions_no_delete BEFORE DELETE ON playlist_revisions BEGIN SELECT RAISE(ABORT, 'playlist revisions are immutable'); END;
            CREATE TRIGGER IF NOT EXISTS playlist_revision_items_no_update BEFORE UPDATE ON playlist_revision_items BEGIN SELECT RAISE(ABORT, 'playlist revision items are immutable'); END;
            CREATE TRIGGER IF NOT EXISTS playlist_revision_items_no_delete BEFORE DELETE ON playlist_revision_items BEGIN SELECT RAISE(ABORT, 'playlist revision items are immutable'); END;
            """
        )

    @staticmethod
    def _migrate_revision_operations(conn: object) -> None:
        conn.execute("PRAGMA foreign_keys = OFF")  # type: ignore[attr-defined]
        try:
            conn.execute("BEGIN IMMEDIATE")  # type: ignore[attr-defined]
            conn.execute("DROP TRIGGER IF EXISTS playlist_revisions_no_update")  # type: ignore[attr-defined]
            conn.execute("DROP TRIGGER IF EXISTS playlist_revisions_no_delete")  # type: ignore[attr-defined]
            conn.execute("DROP TABLE IF EXISTS playlist_revisions_next")  # type: ignore[attr-defined]
            conn.execute(  # type: ignore[attr-defined]
                """
                CREATE TABLE playlist_revisions_next (
                    revision_id TEXT PRIMARY KEY,
                    playlist_id TEXT NOT NULL,
                    parent_revision_id TEXT,
                    revision_index INTEGER NOT NULL CHECK (revision_index >= 0),
                    source_proposal_id TEXT NOT NULL,
                    source_path_id TEXT NOT NULL,
                    operation TEXT NOT NULL CHECK (operation IN ('accept','reorder','lock','replace','regenerate')),
                    operation_json TEXT NOT NULL,
                    content_fingerprint TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    personal_dj_model_training_authorized INTEGER NOT NULL DEFAULT 0 CHECK (personal_dj_model_training_authorized = 0),
                    production_activation_authorized INTEGER NOT NULL DEFAULT 0 CHECK (production_activation_authorized = 0),
                    UNIQUE (playlist_id, revision_index),
                    FOREIGN KEY(parent_revision_id) REFERENCES playlist_revisions_next(revision_id)
                )
                """
            )
            conn.execute(  # type: ignore[attr-defined]
                """
                INSERT INTO playlist_revisions_next (
                    revision_id, playlist_id, parent_revision_id, revision_index,
                    source_proposal_id, source_path_id, operation, operation_json,
                    content_fingerprint, created_at,
                    personal_dj_model_training_authorized, production_activation_authorized
                )
                SELECT
                    revision_id, playlist_id, parent_revision_id, revision_index,
                    source_proposal_id, source_path_id, operation, operation_json,
                    content_fingerprint, created_at,
                    personal_dj_model_training_authorized, production_activation_authorized
                FROM playlist_revisions
                """
            )
            conn.execute("DROP TABLE playlist_revisions")  # type: ignore[attr-defined]
            conn.execute("ALTER TABLE playlist_revisions_next RENAME TO playlist_revisions")  # type: ignore[attr-defined]
            conn.execute(  # type: ignore[attr-defined]
                "CREATE INDEX IF NOT EXISTS idx_playlist_revision_head ON playlist_revisions(playlist_id, revision_index)"
            )
            conn.execute(  # type: ignore[attr-defined]
                "CREATE TRIGGER IF NOT EXISTS playlist_revisions_no_update BEFORE UPDATE ON playlist_revisions BEGIN SELECT RAISE(ABORT, 'playlist revisions are immutable'); END"
            )
            conn.execute(  # type: ignore[attr-defined]
                "CREATE TRIGGER IF NOT EXISTS playlist_revisions_no_delete BEFORE DELETE ON playlist_revisions BEGIN SELECT RAISE(ABORT, 'playlist revisions are immutable'); END"
            )
            conn.commit()  # type: ignore[attr-defined]
        except Exception:
            conn.rollback()  # type: ignore[attr-defined]
            raise
        finally:
            conn.execute("PRAGMA foreign_keys = ON")  # type: ignore[attr-defined]
        violation = conn.execute("PRAGMA foreign_key_check").fetchone()  # type: ignore[attr-defined]
        if violation is not None:
            raise RuntimeError("playlist revision schema migration failed foreign-key verification")

    def append_root(
        self,
        *,
        source_proposal_id: str,
        source_path_id: str,
        items: Sequence[tuple[str, str]],
        operation_metadata: Mapping[str, object] | None = None,
    ) -> dict[str, object]:
        proposal = self._token(source_proposal_id)
        path = self._token(source_path_id)
        normalized = self._items((track, label, False) for track, label in items)
        metadata = self._metadata(operation_metadata or {})
        playlist_id = self._id("plr", {"proposal": proposal, "path": path})
        fingerprint = self._fingerprint(playlist_id, None, proposal, path, "accept", normalized, metadata)
        revision_id = f"prv_{fingerprint[:32]}"
        self.ensure_schema()
        with get_sqlite_connection() as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("BEGIN IMMEDIATE")
            existing = self._get(conn, revision_id)
            if existing is not None:
                self._same(existing, fingerprint)
                conn.commit()
                return existing
            if conn.execute("SELECT 1 FROM playlist_revisions WHERE playlist_id=?", (playlist_id,)).fetchone():
                conn.rollback()
                raise PlaylistRevisionRepositoryError("playlist_revision_conflict", "A different root already exists.")
            self._insert(conn, revision_id, playlist_id, None, 0, proposal, path, "accept", metadata, fingerprint, normalized)
            conn.commit()
            result = self._get(conn, revision_id)
        if result is None:
            raise RuntimeError("playlist revision insert was not observable")
        return result

    def append_child(
        self,
        *,
        parent_revision_id: str,
        operation: str,
        items: Sequence[tuple[str, str, bool]],
        operation_metadata: Mapping[str, object],
    ) -> dict[str, object]:
        parent_id = self._token(parent_revision_id)
        op = operation.strip().lower() if isinstance(operation, str) else ""
        if op not in _OPERATIONS - {"accept"}:
            raise PlaylistRevisionRepositoryError("invalid_playlist_revision_request", "Unsupported child operation.")
        normalized = self._items(items)
        metadata = self._metadata(operation_metadata)
        self.ensure_schema()
        with get_sqlite_connection() as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("BEGIN IMMEDIATE")
            parent = self._get(conn, parent_id)
            if parent is None:
                conn.rollback()
                raise PlaylistRevisionRepositoryError("playlist_revision_not_found", "Parent revision not found.")
            fingerprint = self._fingerprint(
                str(parent["playlist_id"]), parent_id, str(parent["source_proposal_id"]),
                str(parent["source_path_id"]), op, normalized, metadata,
            )
            revision_id = f"prv_{fingerprint[:32]}"
            existing = self._get(conn, revision_id)
            if existing is not None:
                self._same(existing, fingerprint)
                conn.commit()
                return existing
            head = self._current(conn, str(parent["playlist_id"]))
            if head is None or head["revision_id"] != parent_id:
                conn.rollback()
                raise PlaylistRevisionRepositoryError("playlist_revision_stale", "Parent revision is stale.")
            self._insert(
                conn, revision_id, str(parent["playlist_id"]), parent_id,
                int(parent["revision_index"]) + 1, str(parent["source_proposal_id"]),
                str(parent["source_path_id"]), op, metadata, fingerprint, normalized,
            )
            conn.commit()
            result = self._get(conn, revision_id)
        if result is None:
            raise RuntimeError("playlist revision insert was not observable")
        return result

    def get_revision(self, revision_id: str) -> dict[str, object] | None:
        self.ensure_schema()
        with get_sqlite_connection() as conn:
            return self._get(conn, self._token(revision_id))

    def current_revision(self, playlist_id: str) -> dict[str, object] | None:
        self.ensure_schema()
        with get_sqlite_connection() as conn:
            return self._current(conn, self._token(playlist_id))

    def list_revisions(self, playlist_id: str, *, limit: int = _MAX_HISTORY) -> tuple[dict[str, object], ...]:
        playlist = self._token(playlist_id)
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= _MAX_HISTORY:
            raise ValueError("history limit must be 1..100")
        self.ensure_schema()
        with get_sqlite_connection() as conn:
            rows = conn.execute(
                "SELECT revision_id FROM playlist_revisions WHERE playlist_id=? ORDER BY revision_index DESC LIMIT ?",
                (playlist, limit),
            ).fetchall()
            records = [self._get(conn, str(row["revision_id"])) for row in reversed(rows)]
        return tuple(record for record in records if record is not None)

    def count_revisions(self, playlist_id: str) -> int:
        self.ensure_schema()
        with get_sqlite_connection() as conn:
            row = conn.execute("SELECT COUNT(*) AS n FROM playlist_revisions WHERE playlist_id=?", (self._token(playlist_id),)).fetchone()
        return int(row["n"]) if row else 0

    @classmethod
    def _items(cls, values: Sequence[tuple[str, str, bool]] | object) -> tuple[tuple[str, str, bool], ...]:
        try:
            normalized = tuple((cls._track(track), cls._label(label), cls._bool(locked)) for track, label, locked in values)  # type: ignore[misc]
        except (TypeError, ValueError) as exc:
            if isinstance(exc, PlaylistRevisionRepositoryError):
                raise
            raise PlaylistRevisionRepositoryError("invalid_playlist_revision_request", "Invalid revision items.") from exc
        if not 3 <= len(normalized) <= _MAX_ITEMS:
            raise PlaylistRevisionRepositoryError("invalid_playlist_revision_request", "Revision must contain 3..8 tracks.")
        ids = [item[0] for item in normalized]
        if len(ids) != len(set(ids)):
            raise PlaylistRevisionRepositoryError("playlist_revision_duplicate_track", "Duplicate tracks are forbidden.")
        return normalized

    @staticmethod
    def _bool(value: object) -> bool:
        if not isinstance(value, bool):
            raise PlaylistRevisionRepositoryError("invalid_playlist_revision_request", "Lock state must be boolean.")
        return value

    @classmethod
    def _track(cls, value: str) -> str:
        return cls._token(value)

    @staticmethod
    def _label(value: str) -> str:
        if not isinstance(value, str) or not value or value.strip() != value or len(value) > 512:
            raise PlaylistRevisionRepositoryError("invalid_playlist_revision_request", "Invalid display label.")
        if any(ord(ch) < 32 or ord(ch) == 127 for ch in value) or value.startswith(("/", "\\\\")):
            raise PlaylistRevisionRepositoryError("invalid_playlist_revision_request", "Invalid display label.")
        if len(value) >= 3 and value[0].isalpha() and value[1:3] in {":\\", ":/"}:
            raise PlaylistRevisionRepositoryError("invalid_playlist_revision_request", "Invalid display label.")
        return value

    @staticmethod
    def _token(value: str) -> str:
        if not isinstance(value, str) or not value or value.strip() != value or len(value) > 256:
            raise PlaylistRevisionRepositoryError("invalid_playlist_revision_request", "Invalid identity token.")
        if "/" in value or "\\" in value or any(ch.isspace() or ord(ch) < 32 for ch in value):
            raise PlaylistRevisionRepositoryError("invalid_playlist_revision_request", "Invalid identity token.")
        return value

    @staticmethod
    def _metadata(values: Mapping[str, object]) -> dict[str, object]:
        if not isinstance(values, Mapping):
            raise PlaylistRevisionRepositoryError("invalid_playlist_revision_request", "Operation metadata must be an object.")
        result = dict(values)
        try:
            encoded = json.dumps(result, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        except (TypeError, ValueError) as exc:
            raise PlaylistRevisionRepositoryError("invalid_playlist_revision_request", "Operation metadata must be JSON-safe.") from exc
        if len(encoded.encode()) > 4096:
            raise PlaylistRevisionRepositoryError("invalid_playlist_revision_request", "Operation metadata is too large.")
        return result

    @staticmethod
    def _id(prefix: str, material: object) -> str:
        encoded = json.dumps(material, sort_keys=True, separators=(",", ":")).encode()
        return f"{prefix}_{hashlib.sha256(encoded).hexdigest()[:32]}"

    @staticmethod
    def _fingerprint(
        playlist_id: str, parent_revision_id: str | None, proposal_id: str, path_id: str,
        operation: str, items: Sequence[tuple[str, str, bool]], metadata: Mapping[str, object],
    ) -> str:
        material = {
            "playlist_id": playlist_id, "parent_revision_id": parent_revision_id,
            "source_proposal_id": proposal_id, "source_path_id": path_id, "operation": operation,
            "items": [{"order_index": i, "track_id": t, "display_name": n, "locked": l} for i, (t, n, l) in enumerate(items)],
            "operation_metadata": dict(metadata),
            "personal_dj_model_training_authorized": False,
            "production_activation_authorized": False,
        }
        return hashlib.sha256(json.dumps(material, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()

    @staticmethod
    def _same(record: Mapping[str, object], fingerprint: str) -> None:
        if record["content_fingerprint"] != fingerprint:
            raise PlaylistRevisionRepositoryError("playlist_revision_conflict", "Revision identity collision.")

    @staticmethod
    def _insert(conn: object, revision_id: str, playlist_id: str, parent_id: str | None, revision_index: int,
                proposal_id: str, path_id: str, operation: str, metadata: Mapping[str, object], fingerprint: str,
                items: Sequence[tuple[str, str, bool]]) -> None:
        conn.execute(  # type: ignore[attr-defined]
            "INSERT INTO playlist_revisions (revision_id,playlist_id,parent_revision_id,revision_index,source_proposal_id,source_path_id,operation,operation_json,content_fingerprint,personal_dj_model_training_authorized,production_activation_authorized) VALUES (?,?,?,?,?,?,?,?,?,0,0)",
            (revision_id, playlist_id, parent_id, revision_index, proposal_id, path_id, operation,
             json.dumps(dict(metadata), sort_keys=True, separators=(",", ":"), ensure_ascii=False), fingerprint),
        )
        conn.executemany(  # type: ignore[attr-defined]
            "INSERT INTO playlist_revision_items (revision_id,order_index,track_id,display_name,locked) VALUES (?,?,?,?,?)",
            [(revision_id, i, track, label, int(locked)) for i, (track, label, locked) in enumerate(items)],
        )

    @classmethod
    def _get(cls, conn: object, revision_id: str) -> dict[str, object] | None:
        row = conn.execute("SELECT * FROM playlist_revisions WHERE revision_id=?", (revision_id,)).fetchone()  # type: ignore[attr-defined]
        if row is None:
            return None
        items = conn.execute(  # type: ignore[attr-defined]
            "SELECT order_index,track_id,display_name,locked FROM playlist_revision_items WHERE revision_id=? ORDER BY order_index",
            (revision_id,),
        ).fetchall()
        return {
            "revision_id": str(row["revision_id"]), "playlist_id": str(row["playlist_id"]),
            "parent_revision_id": None if row["parent_revision_id"] is None else str(row["parent_revision_id"]),
            "revision_index": int(row["revision_index"]), "source_proposal_id": str(row["source_proposal_id"]),
            "source_path_id": str(row["source_path_id"]), "operation": str(row["operation"]),
            "operation_json": str(row["operation_json"]), "content_fingerprint": str(row["content_fingerprint"]),
            "created_at": str(row["created_at"]), "personal_dj_model_training_authorized": False,
            "production_activation_authorized": False,
            "items": tuple({"order_index": int(item["order_index"]), "track_id": str(item["track_id"]),
                            "display_name": str(item["display_name"]), "locked": bool(item["locked"])} for item in items),
        }

    @classmethod
    def _current(cls, conn: object, playlist_id: str) -> dict[str, object] | None:
        row = conn.execute(  # type: ignore[attr-defined]
            "SELECT revision_id FROM playlist_revisions WHERE playlist_id=? ORDER BY revision_index DESC LIMIT 1",
            (playlist_id,),
        ).fetchone()
        return None if row is None else cls._get(conn, str(row["revision_id"]))
