# Canonical versus Legacy Comparison Receipts

## Authority boundary

Comparison is observational only. Legacy analysis remains authoritative.
Canonical persistence remains non-authoritative.

The comparison path:

- runs only after a successful canonical shadow write;
- uses the already-mapped canonical persistence record;
- reads the existing legacy analysis for the same `track_id`;
- emits a separate JSONL comparison receipt;
- does not return canonical data to the product path;
- does not backfill or perform a second audio analysis.

## Bounded non-live configuration

```text
APP_ENV=staging
APPLAYLIST_CANONICAL_WRITER_ENABLED=1
APPLAYLIST_CANONICAL_WRITER_RECEIPTS_PATH=./artifacts/writer.jsonl
APPLAYLIST_CANONICAL_COMPARISON_ENABLED=1
APPLAYLIST_CANONICAL_COMPARISON_RECEIPTS_PATH=./artifacts/comparison.jsonl
DATABASE_URL=sqlite:///./artifacts/nonlive-applaylist.sqlite3
```

Production remains fail-closed because comparison cannot enable unless the
bounded canonical writer profile itself is enabled.

## Events

```text
canonical_legacy_comparison_succeeded
canonical_legacy_comparison_mismatch
canonical_legacy_comparison_skipped
canonical_legacy_comparison_failed
canonical_legacy_comparison_receipt_write_failed
```

## Initial deterministic tolerances

```text
BPM_ABSOLUTE_TOLERANCE=1.0
ENERGY_ABSOLUTE_TOLERANCE=0.05
DURATION_SECONDS_TOLERANCE=0.05
```

Missing values are classified explicitly. They are never coerced to zero.
Audio paths and raw provider payloads are excluded from receipts.

## Non-goals

```text
BACKFILL=NONE
CANONICAL_READER_ACTIVATION=NONE
RUNTIME_AUTHORITY=NONE
PRODUCTION_DEFAULT_CHANGE=NONE
PUBLIC_API_CHANGE=NONE
TRANSITION_INTELLIGENCE_ACTIVATION=NONE
WB006D=HOLD
```
