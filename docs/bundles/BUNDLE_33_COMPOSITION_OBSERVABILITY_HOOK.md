# Bundle 33 — Composition Observability Hook

## Status

Implementation candidate. Production comparison remains disabled by default.

## Goal

Attach the read-only composition comparison service to the legacy pipeline without changing which tracks are exported or what the API returns.

## Runtime contract

The pipeline remains ordered as follows:

1. legacy composer selects tracks;
2. exporter writes the legacy playlist;
3. the optional comparison hook observes the completed legacy result;
4. the existing pipeline response is returned unchanged.

Comparison is controlled by:

```text
ENABLE_COMPOSITION_COMPARISON=false
```

The default is `false`.

## Fail-open boundary

The comparison hook is observability-only. Exceptions from:

- request validation,
- candidate repository reads,
- adaptation,
- canonical composition,
- report sinks,
- logging adapters,

are caught at the pipeline boundary. The already completed legacy export remains authoritative and the existing response is returned.

Export failures are not hidden. When export fails, the comparison hook is not invoked.

## Data handling

The hook receives only:

- legacy track IDs,
- requested target count,
- requested BPM range,
- requested mode.

The comparison report is sent to an injected sink. Bundle 33 provides a standard logging sink and introduces no database table, artifact file, API field or external telemetry backend.

## Rollout

1. Keep the flag disabled after merge.
2. Enable only in a controlled environment.
3. Inspect comparison status, overlap, positional agreement, rejection and fallback counts.
4. Disable immediately if latency or warning volume is unacceptable.
5. Do not use comparison results to alter export behavior in this bundle.

## Rollback

Set:

```text
ENABLE_COMPOSITION_COMPARISON=false
```

No restart-time data repair or database rollback is required. The code change can also be reverted as one squash commit.

## Non-goals

- canonical export;
- automatic playlist switching;
- API response changes;
- persistent comparison history;
- asynchronous execution;
- removal of the legacy composer.
