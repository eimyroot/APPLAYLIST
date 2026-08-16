# Bundle 49C — Bounded Import Progress and Cancellation

## Status

Stacked implementation slice for issue #103 on predecessor PR #102, exact predecessor SHA `1884a874a2c467919959dee17f0257faeb79c944`.

This slice must not merge ahead of PR #102.

## Product value

A large local library import must remain observable and interruptible without granting the renderer direct filesystem, network, shell, SQLite or sidecar authority.

Bundle 49C replaces the renderer-visible blocking import call with an opaque job lifecycle owned by trusted Rust supervision.

## Schema tree

```text
native folder selection
  -> opaque LibraryRootCapability
  -> library_import_start(capability_id)
       -> Rust resolves authorized root
       -> opaque import_job_id: lij_<uuid-simple>
       -> Rust ImportJobRegistry
            -> authenticated per-import sidecar process
            -> POST /v1/library/import/start
            -> bounded GET /v1/library/import/status polling
            -> optional POST /v1/library/import/cancel
            -> cooperative Python cancellation checkpoints
                 -> scanner
                 -> candidate importer
                 -> persistence between per-track transactions
            -> terminal safe DesktopLibraryImportResult
  -> library_import_status(import_job_id)
  -> library_import_cancel(import_job_id)
```

## Renderer-visible states

```text
pending
running
cancelling
succeeded
cancelled
failed
```

Terminal states are `succeeded`, `cancelled`, and `failed`.

## Renderer-visible phases

```text
starting
scanning
importing
persisting
finalizing
```

## Safe progress counters

```text
discovered_entries
accepted
imported
persisted
```

Counters are non-negative and monotonic. Their invariant is:

```text
persisted <= imported <= accepted <= discovered_entries
```

Unknown totals remain unknown; the UI does not invent percentage completion.

## Cancellation semantics

- cancellation is cooperative and idempotent;
- scanner checks the cancellation signal between filesystem entries;
- candidate import checks between tracks;
- persistence checks between candidates, never by interrupting a single repository transaction;
- cancelled persistence work is represented by `cancelled_count`, not fabricated database errors;
- a completed job is not rewritten as cancelled by a late cancel request;
- forced child-process termination remains a bounded supervisor fallback through `SidecarProcess::Drop`, not the primary cancellation path.

## Partial completion

A cancelled import may return already persisted tracks and bounded issues. Partial persisted state is valid because each candidate persistence operation remains transactionally owned by the repository boundary.

`complete=false` is required when scan, import or persistence cancellation prevents full completion.

## Security invariants

- renderer receives only opaque `LibraryRootCapability` and `import_job_id` identifiers;
- renderer never receives an absolute library path;
- renderer never receives sidecar secret, readiness nonce, loopback port or process id;
- renderer has no generic filesystem, shell, HTTP, WebSocket or SQLite authority;
- sidecar binds loopback only and preserves per-session secret + nonce authentication;
- unknown or malformed job identifiers fail closed;
- only one import job may be active in the desktop app for this slice;
- sidecar progress payloads contain bounded state, phase, counters and terminal safe result only;
- raw Python exceptions are not returned to the renderer.

## Compatibility boundary

The Python sidecar temporarily retains `/v1/library/import` for predecessor compatibility, but the Tauri invoke handler and capability no longer authorize renderer access to `library_import_root`. The renderer uses only:

```text
library_choose_root
library_import_start
library_import_status
library_import_cancel
```

The legacy sidecar endpoint shares the same operation lock and therefore cannot create a concurrent import beside the lifecycle job.

## Acceptance evidence

- Python tests cover cancellation accounting and authenticated sidecar lifecycle behavior;
- Rust tests cover fail-closed lifecycle parsing, job-id parsing and idempotent cancellation;
- renderer contract tests lock down the exact command/capability surface, polling, safe DOM sinks and lack of direct network/filesystem authority;
- Desktop Sidecar Proof and standard CI must pass on the exact PR head before review-ready transition.

## Out of scope

- multiple concurrent import jobs;
- resume after application restart;
- persistent/background daemon jobs;
- arbitrary percentage estimates or invented totals;
- Bundle 50 MIR analysis jobs;
- cloud execution or remote library access;
- release signing, notarization or updater work;
- merge, release, deploy or production authorization.
