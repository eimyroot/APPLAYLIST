from __future__ import annotations

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


class MigrationRegistryError(RuntimeError):
    """Raised when a migration registry is malformed."""


class MigrationConnection:
    """Narrow migration connection that intentionally exposes no commit method."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def execute(
        self,
        sql: str,
        parameters: tuple[Any, ...] = (),
    ) -> sqlite3.Cursor:
        return self._connection.execute(sql, parameters)

    def executemany(
        self,
        sql: str,
        seq_of_parameters: list[tuple[Any, ...]],
    ) -> sqlite3.Cursor:
        return self._connection.executemany(sql, seq_of_parameters)


@dataclass(frozen=True)
class Migration:
    from_version: int
    to_version: int
    name: str
    apply: Callable[[MigrationConnection], None]


MIGRATIONS: tuple[Migration, ...] = ()


def validate_registry(migrations: tuple[Migration, ...]) -> None:
    seen_from: set[int] = set()
    seen_to: set[int] = set()
    previous_to: int | None = None

    for migration in migrations:
        if migration.from_version < 0:
            raise MigrationRegistryError("migration from_version must be non-negative")
        if migration.to_version != migration.from_version + 1:
            raise MigrationRegistryError(
                f"migration must advance exactly one version: {migration}"
            )
        if not migration.name.strip():
            raise MigrationRegistryError("migration name must be non-empty")
        if migration.from_version in seen_from:
            raise MigrationRegistryError(
                f"duplicate from_version: {migration.from_version}"
            )
        if migration.to_version in seen_to:
            raise MigrationRegistryError(f"duplicate to_version: {migration.to_version}")
        if previous_to is not None and migration.from_version != previous_to:
            raise MigrationRegistryError(
                "migration registry must be contiguous: "
                f"expected from_version={previous_to}, got {migration.from_version}"
            )
        seen_from.add(migration.from_version)
        seen_to.add(migration.to_version)
        previous_to = migration.to_version


def plan_migrations(
    current_version: int,
    migrations: tuple[Migration, ...] = MIGRATIONS,
) -> tuple[Migration, ...]:
    validate_registry(migrations)
    if current_version < 0:
        raise MigrationRegistryError("current_version must be non-negative")

    remaining = tuple(
        migration for migration in migrations if migration.from_version >= current_version
    )
    if not remaining:
        return ()
    if remaining[0].from_version != current_version:
        raise MigrationRegistryError(
            f"no contiguous migration starts at user_version={current_version}"
        )
    return remaining
