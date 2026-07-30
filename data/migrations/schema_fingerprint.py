from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote


class SchemaFingerprintError(RuntimeError):
    """Raised when a database does not match a required schema contract."""


@dataclass(frozen=True)
class ColumnFingerprint:
    cid: int
    name: str
    type: str
    notnull: int
    default: str | None
    pk: int


@dataclass(frozen=True)
class IndexColumnFingerprint:
    seqno: int
    cid: int
    name: str | None


@dataclass(frozen=True)
class IndexFingerprint:
    name: str
    unique: int
    origin: str
    partial: int
    columns: tuple[IndexColumnFingerprint, ...]


@dataclass(frozen=True)
class ForeignKeyFingerprint:
    id: int
    seq: int
    table: str
    from_column: str
    to_column: str | None
    on_update: str
    on_delete: str
    match: str


@dataclass(frozen=True)
class TableFingerprint:
    name: str
    sql: str
    columns: tuple[ColumnFingerprint, ...]
    indexes: tuple[IndexFingerprint, ...]
    foreign_keys: tuple[ForeignKeyFingerprint, ...]


@dataclass(frozen=True)
class SchemaFingerprint:
    user_version: int
    application_id: int
    tables: tuple[TableFingerprint, ...]

    def canonical_json(self) -> str:
        return json.dumps(
            asdict(self),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ) + "\n"

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


LEGACY_V0_COLUMNS: dict[str, tuple[tuple[str, str, int, str | None, int], ...]] = {
    "analyses": (
        ("track_id", "TEXT", 0, None, 1),
        ("analysis_version", "TEXT", 1, None, 0),
        ("features_version", "TEXT", 1, None, 0),
        ("extractor_backend", "TEXT", 1, None, 0),
        ("extractor_name", "TEXT", 1, None, 0),
        ("bpm", "REAL", 0, None, 0),
        ("bpm_confidence", "REAL", 0, None, 0),
        ("key", "TEXT", 0, None, 0),
        ("scale", "TEXT", 0, None, 0),
        ("camelot", "TEXT", 0, None, 0),
        ("energy", "REAL", 0, None, 0),
        ("loudness_db", "REAL", 0, None, 0),
        ("duration_seconds", "REAL", 0, None, 0),
        ("harmonic_ratio", "REAL", 0, None, 0),
        ("percussive_ratio", "REAL", 0, None, 0),
    ),
    "jobs": (
        ("job_id", "TEXT", 0, None, 1),
        ("job_type", "TEXT", 1, None, 0),
        ("status", "TEXT", 1, None, 0),
        ("progress", "REAL", 1, "0", 0),
        ("error_code", "TEXT", 0, None, 0),
        ("error_detail", "TEXT", 0, None, 0),
    ),
    "tracks": (
        ("track_id", "TEXT", 0, None, 1),
        ("path", "TEXT", 1, None, 0),
        ("title", "TEXT", 0, None, 0),
        ("artist", "TEXT", 0, None, 0),
        ("album", "TEXT", 0, None, 0),
        ("genre", "TEXT", 0, None, 0),
        ("source", "TEXT", 0, None, 0),
        ("duration_seconds", "REAL", 0, None, 0),
        ("sample_rate_hz", "INTEGER", 0, None, 0),
        ("bitrate_kbps", "INTEGER", 0, None, 0),
    ),
}

PROTECTED_LEGACY_TABLES = ("analyses", "jobs", "tracks")


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _rows_as_dicts(
    conn: sqlite3.Connection,
    sql: str,
    parameters: tuple[Any, ...] = (),
) -> list[dict[str, Any]]:
    cursor = conn.execute(sql, parameters)
    names = tuple(description[0] for description in cursor.description or ())
    return [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]



def _fetch_scalar(conn: sqlite3.Connection, sql: str) -> Any:
    row = conn.execute(sql).fetchone()
    if row is None:
        raise SchemaFingerprintError(f"query returned no row: {sql}")
    return row[0]


def _normalize_sql(sql: str | None) -> str:
    if not sql:
        return ""
    return re.sub(r"\s+", " ", sql.strip())


def open_sqlite_readonly(path: str | Path) -> sqlite3.Connection:
    db_path = Path(path).expanduser().resolve()
    if not db_path.is_file():
        raise FileNotFoundError(f"SQLite database does not exist: {db_path}")
    uri = "file:" + quote(str(db_path), safe="/:") + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.execute("PRAGMA query_only = ON")
    return conn


def inspect_schema(conn: sqlite3.Connection) -> SchemaFingerprint:
    user_version = int(_fetch_scalar(conn, "PRAGMA user_version"))
    application_id = int(_fetch_scalar(conn, "PRAGMA application_id"))
    table_rows = _rows_as_dicts(
        conn,
        "SELECT name, sql FROM sqlite_schema "
        "WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name",
    )

    tables: list[TableFingerprint] = []
    for table_row in table_rows:
        table_name = str(table_row["name"])
        column_rows = _rows_as_dicts(
            conn,
            "SELECT cid, name, type, [notnull], dflt_value, pk FROM pragma_table_info(?)",
            (table_name,),
        )
        columns = tuple(
            ColumnFingerprint(
                cid=int(row["cid"]),
                name=str(row["name"]),
                type=str(row["type"]),
                notnull=int(row["notnull"]),
                default=None if row["dflt_value"] is None else str(row["dflt_value"]),
                pk=int(row["pk"]),
            )
            for row in column_rows
        )

        index_rows = _rows_as_dicts(
            conn,
            "SELECT seq, name, `unique`, origin, partial FROM pragma_index_list(?)",
            (table_name,),
        )
        indexes: list[IndexFingerprint] = []
        for index_row in sorted(index_rows, key=lambda row: str(row["name"])):
            index_name = str(index_row["name"])
            info_rows = _rows_as_dicts(
                conn,
                "SELECT seqno, cid, name FROM pragma_index_info(?)",
                (index_name,),
            )
            indexes.append(
                IndexFingerprint(
                    name=index_name,
                    unique=int(index_row["unique"]),
                    origin=str(index_row["origin"]),
                    partial=int(index_row["partial"]),
                    columns=tuple(
                        IndexColumnFingerprint(
                            seqno=int(row["seqno"]),
                            cid=int(row["cid"]),
                            name=None if row["name"] is None else str(row["name"]),
                        )
                        for row in info_rows
                    ),
                )
            )

        foreign_key_rows = _rows_as_dicts(
            conn,
            "SELECT id, seq, `table`, `from`, `to`, on_update, on_delete, match "
            "FROM pragma_foreign_key_list(?)",
            (table_name,),
        )
        foreign_keys = tuple(
            ForeignKeyFingerprint(
                id=int(row["id"]),
                seq=int(row["seq"]),
                table=str(row["table"]),
                from_column=str(row["from"]),
                to_column=None if row["to"] is None else str(row["to"]),
                on_update=str(row["on_update"]),
                on_delete=str(row["on_delete"]),
                match=str(row["match"]),
            )
            for row in sorted(
                foreign_key_rows,
                key=lambda row: (int(row["id"]), int(row["seq"])),
            )
        )

        tables.append(
            TableFingerprint(
                name=table_name,
                sql=_normalize_sql(str(table_row["sql"])),
                columns=columns,
                indexes=tuple(indexes),
                foreign_keys=foreign_keys,
            )
        )

    return SchemaFingerprint(
        user_version=user_version,
        application_id=application_id,
        tables=tuple(tables),
    )


def validate_legacy_v0(fingerprint: SchemaFingerprint) -> None:
    if fingerprint.user_version != 0:
        raise SchemaFingerprintError(
            f"legacy-v0 requires user_version=0, got {fingerprint.user_version}"
        )
    if fingerprint.application_id != 0:
        raise SchemaFingerprintError(
            "legacy-v0 requires application_id=0, "
            f"got {fingerprint.application_id}"
        )

    actual_names = tuple(table.name for table in fingerprint.tables)
    expected_names = tuple(sorted(LEGACY_V0_COLUMNS))
    if actual_names != expected_names:
        raise SchemaFingerprintError(
            f"legacy-v0 table mismatch: expected={expected_names} actual={actual_names}"
        )

    for table in fingerprint.tables:
        expected_columns = LEGACY_V0_COLUMNS[table.name]
        actual_columns = tuple(
            (column.name, column.type, column.notnull, column.default, column.pk)
            for column in table.columns
        )
        if actual_columns != expected_columns:
            raise SchemaFingerprintError(
                f"legacy-v0 column mismatch for {table.name}: "
                f"expected={expected_columns} actual={actual_columns}"
            )
        if table.foreign_keys:
            raise SchemaFingerprintError(
                f"legacy-v0 unexpected foreign keys for {table.name}: {table.foreign_keys}"
            )
        unexpected_indexes = tuple(
            index for index in table.indexes if index.origin != "pk"
        )
        if unexpected_indexes:
            raise SchemaFingerprintError(
                f"legacy-v0 unexpected indexes for {table.name}: {unexpected_indexes}"
            )


def integrity_status(conn: sqlite3.Connection) -> tuple[tuple[str, ...], tuple[str, ...]]:
    integrity = tuple(str(row[0]) for row in conn.execute("PRAGMA integrity_check"))
    quick = tuple(str(row[0]) for row in conn.execute("PRAGMA quick_check"))
    return integrity, quick


def require_integrity(conn: sqlite3.Connection) -> None:
    integrity, quick = integrity_status(conn)
    if integrity != ("ok",) or quick != ("ok",):
        raise SchemaFingerprintError(
            f"SQLite integrity failure: integrity={integrity} quick={quick}"
        )


def table_row_count(conn: sqlite3.Connection, table: str) -> int:
    quoted = _quote_identifier(table)
    # table is always quoted with SQLite identifier escaping; identifiers cannot be bound.
    return int(_fetch_scalar(conn, f"SELECT COUNT(*) FROM {quoted}"))  # nosec B608


def _json_value(value: Any) -> Any:
    if isinstance(value, bytes):
        return {"__bytes_hex__": value.hex()}
    return value


def logical_table_sha256(conn: sqlite3.Connection, table: str) -> str:
    quoted = _quote_identifier(table)
    column_rows = _rows_as_dicts(
        conn,
        "SELECT cid, name, type, [notnull], dflt_value, pk FROM pragma_table_info(?)",
        (table,),
    )
    if not column_rows:
        raise SchemaFingerprintError(f"table not found: {table}")

    pk_columns = sorted(
        (
            (int(row["pk"]), str(row["name"]))
            for row in column_rows
            if int(row["pk"]) > 0
        ),
        key=lambda item: item[0],
    )
    if not pk_columns:
        raise SchemaFingerprintError(
            f"deterministic logical digest requires primary key: {table}"
        )

    order_sql = ", ".join(_quote_identifier(name) for _, name in pk_columns)
    # table/PK identifiers are read from SQLite metadata and escaped before interpolation.
    cursor = conn.execute(  # nosec B608
        f"SELECT * FROM {quoted} ORDER BY {order_sql}"  # nosec B608
    )
    names = tuple(description[0] for description in cursor.description or ())
    digest = hashlib.sha256()
    for row in cursor:
        payload = {
            name: _json_value(value)
            for name, value in zip(names, row, strict=True)
        }
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        digest.update(encoded)
        digest.update(b"\n")
    return digest.hexdigest()


def protected_table_state(
    conn: sqlite3.Connection,
    tables: tuple[str, ...] = PROTECTED_LEGACY_TABLES,
) -> dict[str, dict[str, int | str]]:
    return {
        table: {
            "row_count": table_row_count(conn, table),
            "logical_sha256": logical_table_sha256(conn, table),
        }
        for table in tables
    }
