# Bundle 50B — Analysis Desktop Transport

## Baseline

- Canonical branch: `feature/bundle-0-bootstrap`
- Canonical baseline SHA: `7c98dbc36dbb73171f01c754f5bbc339de04ba31`
- Predecessor: Bundle 50 backend foundation, PR #108
- Implementation branch: `feature/bundle-50b-analysis-desktop-transport`

## Purpose

Expose the repository-backed Bundle 50 analysis lifecycle and Inspector to the local desktop UI without granting the renderer filesystem, shell, network, SQLite, sidecar-process, or credential authority.

## Authority boundaries

### Renderer

The renderer may invoke only the explicit Tauri commands:

- `library_choose_root`
- `library_import_start`
- `library_import_status`
- `library_import_cancel`
- `analysis_start`
- `analysis_status`
- `analysis_cancel`
- `analysis_inspector_list`
- `analysis_inspector_get`
- `analysis_correct`
- `analysis_reanalyze`

It has no generic filesystem, shell, HTTP, network, or SQLite permission. CSP keeps `connect-src 'none'`.

Renderer-facing analysis jobs use opaque `daj_<uuid>` identifiers. The renderer never receives the persistent Python-side `aj_<uuid>` identifier, sidecar port, secret, nonce, process ID, or an absolute source path.

### Rust / Tauri trusted host

Rust owns:

- renderer command validation,
- the renderer-facing analysis job registry,
- opaque `daj_<uuid>` job identifiers,
- sidecar process lifecycle,
- random sidecar secret and readiness nonce,
- loopback-only authenticated HTTP,
- response schema validation,
- monotonic progress validation,
- cancellation forwarding,
- bounded lifecycle timeout,
- atomic terminal-state publication.

The sidecar executable is resolved through the existing fixed bundled-resource boundary. Debug executable override remains debug-only.

### Python sidecar

The sidecar exposes authenticated explicit endpoints only:

- `POST /v1/analysis/start`
- `POST /v1/analysis/status`
- `POST /v1/analysis/cancel`
- `POST /v1/analysis/inspector/list`
- `POST /v1/analysis/inspector/get`
- `POST /v1/analysis/correct`
- `POST /v1/analysis/reanalyze`

Every endpoint requires the existing sidecar secret and readiness nonce. Requests are bounded JSON objects and reject unexpected fields.

The sidecar accepts stable track IDs, not filesystem paths. It delegates to the already-canonical Bundle 50 services and does not create a second analysis engine or a second Source of Truth.

### Repository-backed backend

The canonical backend remains authoritative for:

- `AnalysisJob` persistence,
- `analysis_job_targets`,
- provider execution through `RoutedAnalysisService`,
- append-only provider evidence,
- append-only manual corrections,
- Inspector read model,
- failed/uncertain/corrected filters,
- re-analysis provenance.

## Job identity model

```text
renderer
  daj_<uuid>
     |
     v
trusted Rust registry
     |
     | authenticated local sidecar session
     v
Python sidecar
  aj_<uuid>
     |
     v
SQLite analysis_jobs + analysis_job_targets + append-only evidence
```

`aj_<uuid>` is trusted-side only. It is never rendered or accepted from the renderer.

## Analysis lifecycle

```text
Start
  -> running
  -> bounded polling
  -> optional cancelling
  -> done | cancelled | failed
```

Progress counters are:

- selected
- completed
- succeeded
- failed
- uncertain

Required invariants:

- `completed = succeeded + failed`
- `completed <= selected`
- `uncertain <= succeeded`
- counters never regress
- selected count never changes during a job
- terminal state is not exposed before Rust publishes the final snapshot atomically

## Inspector

The renderer may request:

- all
- uncertain
- failed
- corrected

Inspector DTOs are strict and path-safe. They contain bounded display metadata and evidence identifiers, but no absolute source path.

Manual correction supports only:

- BPM
- key tonic
- key scale
- Camelot key
- energy

Corrections remain append-only overlays anchored to successful provider evidence.

## Re-analysis

Re-analysis is an explicit user action. It creates a new repository-backed analysis job and new provider evidence. It does not overwrite or delete prior evidence or correction history.

## Security invariants

- no renderer `fetch`, XHR, WebSocket, filesystem, shell, or HTTP plugin access,
- no renderer sidecar endpoint URLs,
- no renderer sidecar credentials,
- no renderer process ID or port,
- no renderer Python `aj_...` job ID,
- track IDs and job IDs reject path-shaped input,
- Rust DTOs use `deny_unknown_fields`,
- sidecar request schemas reject unexpected fields,
- raw provider exceptions are not returned,
- worker failures become bounded error codes,
- sidecar stderr is not exposed to the renderer,
- process kill remains fallback rather than normal cancellation.

## Verification target

Before review-ready status, require exact-head success for:

- Python CI on supported versions,
- full pytest suite,
- Desktop Sidecar Proof on Linux and macOS,
- Desktop Rust rustfmt/check/test,
- PR Guard,
- zero unresolved review threads.

## Out of scope

- Bundle 51 transition intelligence,
- playlist/set optimization,
- cloud analysis,
- concurrent desktop analysis jobs,
- resumable analysis after application restart,
- production-authority promotion of the MIR provider,
- release, signing, notarization, or deployment.
