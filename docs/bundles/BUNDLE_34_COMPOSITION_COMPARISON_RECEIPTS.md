# Bundle 34 — Composition Comparison Receipts

## Status

Implementation candidate. Comparison and local receipt persistence remain disabled by default.

## Goal

Create durable, correlated evidence for legacy-versus-canonical composition comparisons without changing playlist selection, export behavior or API responses.

## Receipt contract

Each receipt contains:

- schema version;
- the same pipeline run ID used as the export playlist ID;
- a timezone-aware UTC creation timestamp;
- requested target count, BPM range and mode;
- legacy and canonical track IDs;
- canonical status and failure reason;
- candidate, adapted, rejected and fallback counts;
- adaptation issues and canonical warnings;
- overlap, position agreement and coverage ratios.

Serialization is deterministic and JSON-safe. Enum values are emitted as stable strings.

## Runtime ordering

1. Legacy composition completes.
2. Legacy export completes.
3. Optional comparison executes.
4. A receipt is built with the export run ID.
5. Configured receipt sinks are invoked.
6. The original pipeline response is returned unchanged.

Any failure in steps 3–5 remains inside the existing fail-open observability boundary.

## Configuration

```text
ENABLE_COMPOSITION_COMPARISON=false
ENABLE_COMPOSITION_RECEIPTS=false
COMPOSITION_RECEIPTS_DIR=./artifacts/composition-comparisons
```

Local receipts are written only when both comparison and receipt persistence are enabled.

## Filesystem contract

The local JSON sink:

- accepts only bounded safe run IDs;
- creates the configured receipt directory when needed;
- writes a uniquely named temporary file;
- atomically replaces the final `<run-id>.json` artifact;
- removes the temporary file on failure;
- never adds receipt paths to the API response.

Generated artifacts remain excluded by `.gitignore` through the existing `artifacts/` rule.

## Rollout

1. Merge with both flags disabled.
2. Enable comparison in a controlled environment.
3. Verify logging-only evidence.
4. Enable local receipts for a bounded test window.
5. Inspect file volume, latency, schema stability and warning rate.
6. Disable receipt persistence before any production anomaly investigation if disk pressure appears.

## Rollback

Set either flag to `false`. No database migration or data repair is required. Existing receipt files may be archived or removed independently of the application.

## Non-goals

- database-backed receipt history;
- external telemetry delivery;
- API receipt endpoints;
- canonical playlist export;
- asynchronous processing;
- automated switching away from the legacy composer.
