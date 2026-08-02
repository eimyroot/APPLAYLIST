from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from data.migrations.registry import (
    MIGRATIONS,
    Migration,
    MigrationConnection,
    MigrationRegistryError,
    plan_migrations,
)
from data.migrations.schema_fingerprint import (
    PROTECTED_LEGACY_TABLES,
    SchemaFingerprint,
    inspect_schema,
    open_sqlite_readonly,
    protected_table_state,
    require_integrity,
    validate_legacy_v0,
)
from data.migrations.sqlite_backup import (
    BackupEvidence,
    create_verified_backup,
    verify_disposable_restore,
)


class MigrationRunnerError(RuntimeError):
    """Raised when migration safety preconditions or execution fail."""


@dataclass(frozen=True)
class DatabaseCheck:
    path: str
    fingerprint: SchemaFingerprint
    protected_table_state: dict[str, dict[str, int | str]]


@dataclass(frozen=True)
class MigrationApplyResult:
    migration_name: str
    from_version: int
    to_version: int
    backup: BackupEvidence
    post_schema_sha256: str


def check_database(
    db_path: str | Path,
    *,
    require_legacy_v0: bool = False,
    protected_tables: tuple[str, ...] = PROTECTED_LEGACY_TABLES,
) -> DatabaseCheck:
    path = Path(db_path).expanduser().resolve()
    conn = open_sqlite_readonly(path)
    try:
        require_integrity(conn)
        fingerprint = inspect_schema(conn)
        if require_legacy_v0:
            validate_legacy_v0(fingerprint)
        state = protected_table_state(conn, protected_tables)
    finally:
        conn.close()
    return DatabaseCheck(
        path=str(path),
        fingerprint=fingerprint,
        protected_table_state=state,
    )


def migration_plan(
    db_path: str | Path,
    migrations: tuple[Migration, ...] = MIGRATIONS,
) -> tuple[Migration, ...]:
    check = check_database(db_path)
    if check.fingerprint.user_version == 0:
        validate_legacy_v0(check.fingerprint)
    try:
        return plan_migrations(check.fingerprint.user_version, migrations)
    except MigrationRegistryError as exc:
        raise MigrationRunnerError(str(exc)) from exc


def apply_next_migration(
    db_path: str | Path,
    backup_dir: str | Path,
    *,
    migrations: tuple[Migration, ...] = MIGRATIONS,
    protected_tables: tuple[str, ...] = PROTECTED_LEGACY_TABLES,
    lock_timeout_seconds: float = 1.0,
    expected_legacy_v0_sha256: str | None = None,
) -> MigrationApplyResult:
    path = Path(db_path).expanduser().resolve()
    if not path.is_file():
        raise MigrationRunnerError(f"database does not exist: {path}")

    before = check_database(
        path,
        require_legacy_v0=False,
        protected_tables=protected_tables,
    )
    if before.fingerprint.user_version == 0:
        validate_legacy_v0(before.fingerprint)

    try:
        plan = plan_migrations(before.fingerprint.user_version, migrations)
    except MigrationRegistryError as exc:
        raise MigrationRunnerError(str(exc)) from exc
    if not plan:
        raise MigrationRunnerError("no registered migration for current user_version")

    migration = plan[0]
    if before.fingerprint.user_version == 0:
        if expected_legacy_v0_sha256 is None:
            raise MigrationRunnerError(
                "legacy-v0 migration requires an explicitly pinned schema SHA-256"
            )
        if before.fingerprint.sha256 != expected_legacy_v0_sha256:
            raise MigrationRunnerError(
                "legacy-v0 schema SHA-256 does not match the pinned baseline"
            )
    backup_root = Path(backup_dir).expanduser().resolve()
    if not backup_root.is_dir():
        raise MigrationRunnerError(f"backup directory does not exist: {backup_root}")
    backup_path = backup_root / (
        f"applaylist-v{migration.from_version}-to-v{migration.to_version}.sqlite3"
    )
    try:
        backup = create_verified_backup(
            path,
            backup_path,
            protected_tables=protected_tables,
        )
        verify_disposable_restore(backup, protected_tables=protected_tables)
    except Exception as exc:
        raise MigrationRunnerError(f"verified backup failed: {exc}") from exc

    timeout = max(0.0, float(lock_timeout_seconds))
    conn = sqlite3.connect(path, timeout=timeout, isolation_level=None)
    try:
        conn.execute(f"PRAGMA busy_timeout = {int(timeout * 1000)}")
        try:
            conn.execute("BEGIN IMMEDIATE")
        except sqlite3.OperationalError as exc:
            raise MigrationRunnerError(f"failed to acquire migration write lock: {exc}") from exc

        try:
            in_tx_schema = inspect_schema(conn)
            if in_tx_schema != before.fingerprint:
                raise MigrationRunnerError("database schema changed after backup verification")
            if in_tx_schema.user_version != migration.from_version:
                raise MigrationRunnerError(
                    "database user_version changed before migration execution"
                )
            in_tx_state = protected_table_state(conn, protected_tables)
            if in_tx_state != before.protected_table_state:
                raise MigrationRunnerError(
                    "protected legacy data changed after backup verification"
                )

            migration.apply(MigrationConnection(conn))
            if not conn.in_transaction:
                raise MigrationRunnerError("migration escaped runner transaction")
            conn.execute(f"PRAGMA user_version = {migration.to_version}")
            conn.execute("COMMIT")
        except Exception as exc:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            if isinstance(exc, MigrationRunnerError):
                raise
            raise MigrationRunnerError(f"migration failed: {exc}") from exc
    except MigrationRunnerError:
        raise
    except Exception as exc:
        raise MigrationRunnerError(f"migration failed: {exc}") from exc
    finally:
        conn.close()

    after = check_database(path, protected_tables=protected_tables)
    if after.fingerprint.user_version != migration.to_version:
        raise MigrationRunnerError("post-migration user_version verification failed")
    if after.protected_table_state != before.protected_table_state:
        raise MigrationRunnerError("protected legacy table state changed during migration")

    return MigrationApplyResult(
        migration_name=migration.name,
        from_version=migration.from_version,
        to_version=migration.to_version,
        backup=backup,
        post_schema_sha256=after.fingerprint.sha256,
    )
