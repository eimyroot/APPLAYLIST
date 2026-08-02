from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from data.migrations.schema_fingerprint import (
    PROTECTED_LEGACY_TABLES,
    inspect_schema,
    open_sqlite_readonly,
    protected_table_state,
    require_integrity,
)


class SQLiteBackupError(RuntimeError):
    """Raised when backup creation or verification fails."""


@dataclass(frozen=True)
class BackupEvidence:
    source_path: str
    source_user_version: int
    source_schema_sha256: str
    source_table_state: dict[str, dict[str, int | str]]
    backup_path: str
    backup_sha256: str
    backup_size_bytes: int
    backup_user_version: int
    backup_schema_sha256: str
    backup_table_state: dict[str, dict[str, int | str]]
    created_at_utc: str


@dataclass(frozen=True)
class RestoreVerification:
    backup_path: str
    restored_user_version: int
    restored_schema_sha256: str
    restored_table_state: dict[str, dict[str, int | str]]


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def create_verified_backup(
    source_path: str | Path,
    backup_path: str | Path,
    *,
    protected_tables: tuple[str, ...] = PROTECTED_LEGACY_TABLES,
) -> BackupEvidence:
    source = Path(source_path).expanduser().resolve()
    destination = Path(backup_path).expanduser().resolve()
    if not source.is_file():
        raise SQLiteBackupError(f"source database does not exist: {source}")
    if destination.exists():
        raise SQLiteBackupError(f"backup destination already exists: {destination}")
    if not destination.parent.is_dir():
        raise SQLiteBackupError(
            f"backup destination parent does not exist: {destination.parent}"
        )

    source_conn = open_sqlite_readonly(source)
    try:
        require_integrity(source_conn)
        source_schema = inspect_schema(source_conn)
        source_state = protected_table_state(source_conn, protected_tables)
        destination_conn = sqlite3.connect(destination)
        try:
            source_conn.backup(destination_conn)
        finally:
            destination_conn.close()
    finally:
        source_conn.close()

    backup_conn = open_sqlite_readonly(destination)
    try:
        require_integrity(backup_conn)
        backup_schema = inspect_schema(backup_conn)
        backup_state = protected_table_state(backup_conn, protected_tables)
    finally:
        backup_conn.close()

    if backup_schema != source_schema:
        raise SQLiteBackupError("backup schema fingerprint does not match source")
    if backup_state != source_state:
        raise SQLiteBackupError("backup protected table state does not match source")

    return BackupEvidence(
        source_path=str(source),
        source_user_version=source_schema.user_version,
        source_schema_sha256=source_schema.sha256,
        source_table_state=source_state,
        backup_path=str(destination),
        backup_sha256=file_sha256(destination),
        backup_size_bytes=destination.stat().st_size,
        backup_user_version=backup_schema.user_version,
        backup_schema_sha256=backup_schema.sha256,
        backup_table_state=backup_state,
        created_at_utc=datetime.now(UTC).isoformat(),
    )


def verify_disposable_restore(
    evidence: BackupEvidence,
    *,
    protected_tables: tuple[str, ...] = PROTECTED_LEGACY_TABLES,
) -> RestoreVerification:
    backup = Path(evidence.backup_path).resolve()
    if not backup.is_file():
        raise SQLiteBackupError(f"backup database does not exist: {backup}")
    if file_sha256(backup) != evidence.backup_sha256:
        raise SQLiteBackupError("backup SHA-256 does not match evidence")

    with tempfile.TemporaryDirectory(prefix="applaylist-db-restore-") as tmp:
        restored = Path(tmp) / "restored.sqlite3"
        source_conn = open_sqlite_readonly(backup)
        try:
            destination_conn = sqlite3.connect(restored)
            try:
                source_conn.backup(destination_conn)
            finally:
                destination_conn.close()
        finally:
            source_conn.close()

        restored_conn = open_sqlite_readonly(restored)
        try:
            require_integrity(restored_conn)
            restored_schema = inspect_schema(restored_conn)
            restored_state = protected_table_state(restored_conn, protected_tables)
        finally:
            restored_conn.close()

    if restored_schema.sha256 != evidence.source_schema_sha256:
        raise SQLiteBackupError("restored schema fingerprint does not match source")
    if restored_schema.user_version != evidence.source_user_version:
        raise SQLiteBackupError("restored user_version does not match source")
    if restored_state != evidence.source_table_state:
        raise SQLiteBackupError("restored protected table state does not match source")

    return RestoreVerification(
        backup_path=str(backup),
        restored_user_version=restored_schema.user_version,
        restored_schema_sha256=restored_schema.sha256,
        restored_table_state=restored_state,
    )


def write_backup_manifest(
    evidence: BackupEvidence,
    manifest_path: str | Path,
    *,
    repository_head: str,
    migration_from_version: int | None,
    migration_to_version: int | None,
) -> Path:
    path = Path(manifest_path).expanduser().resolve()
    if path.exists():
        raise SQLiteBackupError(f"backup manifest already exists: {path}")
    if not path.parent.is_dir():
        raise SQLiteBackupError(f"manifest parent does not exist: {path.parent}")

    payload: dict[str, Any] = asdict(evidence)
    payload.update(
        {
            "repository_head": repository_head,
            "migration_plan_from_version": migration_from_version,
            "migration_plan_to_version": migration_to_version,
        }
    )
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path
