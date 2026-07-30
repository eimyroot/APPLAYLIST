# Migrations

APPLAYLIST používá pro lokální SQLite schéma dvě oddělené vrstvy:

1. existující repository `ensure_schema()` bootstrap pro legacy tabulky,
2. explicitní migration controls pro budoucí řízené změny schématu.

## Locked rules

- žádné přímé DB zápisy mimo explicitně schválené repository/migration boundary,
- service/analyzer vrstvy nesmí otevírat vlastní `sqlite3.connect(...)`,
- `PRAGMA user_version` je DB migration ledger,
- `Settings.schema_version` není DB migration ledger,
- migrace musí mít exact schema fingerprint preflight,
- před write-capable migrací musí existovat ověřený SQLite backup a disposable restore,
- live restore je destruktivní operace a vyžaduje samostatné explicitní povolení.

## Current state

Legacy bootstrap stále používá `ensure_schema()` a zůstává runtime authority.

WB003C3B zavádí pouze migration safety controls:

- deterministický SQLite schema fingerprint,
- `PRAGMA user_version` ledger abstraction,
- backup přes `sqlite3.Connection.backup()`,
- logical table digests,
- disposable restore verification,
- migration registry/runner.

Produkční migration registry je prázdný. Není registrována ani spuštěna žádná schema migrace.
`canonical_analyses` se v tomto work bundle nevytváří.

## CLI controls

Read-only kontrola:

```bash
python scripts/db_migrate.py check
```

Read-only plán:

```bash
python scripts/db_migrate.py plan
```

Dokud není registrována explicitně schválená migrace, `apply` fail-closed skončí bez DB write:

```bash
python scripts/db_migrate.py apply
```

Backup a restore verification jsou samostatné controls. WB003C3B je ověřuje pouze na disposable
databázích; live DB schema ani `user_version` se tímto bundle nemění.
