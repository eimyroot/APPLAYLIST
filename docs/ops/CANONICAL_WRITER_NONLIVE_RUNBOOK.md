# Canonical Writer — Bounded Non-Live Profile

## Safety boundary

The canonical writer is non-authoritative and defaults to disabled. Production
and `prod` environments fail closed even when the writer flag is set.

## Required non-live configuration

```text
APP_ENV=staging
APPLAYLIST_PROVIDER_ANALYSIS_ENABLED=1
APPLAYLIST_CANONICAL_WRITER_ENABLED=1
APPLAYLIST_CANONICAL_WRITER_RECEIPTS_PATH=./artifacts/canonical-writer-receipts.jsonl
DATABASE_URL=sqlite:///./artifacts/nonlive-applaylist.sqlite3
```

Use a dedicated non-live database. Do not point this profile at the live DB.

## Receipt fields

Each attempted canonical write emits one JSONL receipt containing:

- stable event name and outcome,
- unique attempt ID,
- write duration in milliseconds,
- provider and canonical analysis version,
- track ID,
- error type for failed writes,
- UTC timestamp.

Audio paths and raw provider payloads are intentionally excluded.

## Authority

Legacy persistence remains authoritative. The canonical reader, backfill,
authority switch, Transition Intelligence, and WB006D remain disabled.

## Rollback

Unset `APPLAYLIST_CANONICAL_WRITER_ENABLED` or set it to `0`, then restart the
non-live runtime. Existing canonical rows are not deleted automatically.
