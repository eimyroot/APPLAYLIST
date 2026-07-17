# Bundle 47 — Desktop Shell Architecture and Security ADR

## Status

Implemented on an isolated documentation branch. Not yet merged.

## User value

APPLAYLIST now has one explicit path from the proven Python music core to a professional desktop/web hybrid product, with a fallback decision and enforceable security boundaries before new runtime toolchains are introduced.

## Decision

```text
PRIMARY
Tauri 2
+ React / TypeScript
+ Rust desktop core
+ packaged Python sidecar
+ authenticated loopback FastAPI

FALLBACK
Electron + React / TypeScript + packaged Python sidecar

NOT SELECTED FOR CURRENT DIRECTION
PySide6 / QML
```

## Schema tree

```text
APPLAYLIST
├── React renderer
│   ├── Library
│   ├── Analysis
│   ├── Set Builder
│   ├── Playlist Editor
│   └── Export
│
├── Tauri Rust core
│   ├── typed commands/events
│   ├── navigation policy
│   ├── native dialogs
│   ├── capability registry
│   ├── Python sidecar supervisor
│   └── signed updater ownership
│
├── Packaged Python sidecar
│   ├── loopback-only FastAPI
│   ├── per-session authentication
│   ├── application services
│   └── controlled readiness/shutdown
│
├── Existing Python product core
│   ├── library import
│   ├── metadata/persistence
│   ├── MIR analysis
│   ├── benchmark
│   ├── composition
│   └── export
│
└── Local resources
    ├── capability-authorized audio roots
    ├── SQLite
    └── capability-authorized export destination
```

## Runtime flow

```text
user selects folder in native dialog
  → Rust creates opaque LibraryRootCapability
  → renderer receives capability ID, not host authority
  → typed command reaches Rust
  → Rust resolves authorized path
  → authenticated request reaches Python sidecar
  → LibraryImportService executes
  → progress and controlled results return through Rust
```

## Sidecar lifecycle

```text
not_started
  → starting
  → readiness nonce/protocol validation
  → ready
  → stopping
  → stopped

Failure states:
  degraded / failed
```

Rules:

- renderer never receives the sidecar credential or direct URL,
- packaged sidecar binds loopback only,
- startup timeout or malformed readiness fails closed,
- unexpected sidecar exit disables product commands,
- desktop shutdown owns graceful stop and bounded forced kill.

## Donor selection

From `4gray/iptvnator`, only these principles are retained:

- shared web UI with explicit desktop-only features,
- hardened renderer/desktop separation,
- typed bridge,
- native capability ownership,
- package-layout checks,
- packaged smoke tests,
- updater/release discipline,
- keyboard, theme and i18n readiness.

Rejected donor scope:

- IPTV playback,
- Xtream/Stalker,
- EPG,
- TMDB,
- video players,
- remote proxy/header logic,
- Angular/NgRx adoption by default,
- direct code or branding copy.

## Technology comparison outcome

| Candidate | Outcome | Reason |
|---|---|---|
| Tauri 2 + React + Python sidecar | selected for proof | shared web UI, explicit capabilities, sidecar support, signed updater, OS WebView footprint |
| Electron + React + Python sidecar | fallback | mature packaging and consistent Chromium, but larger runtime/security surface |
| PySide6/QML | rejected_current | direct Python integration but duplicates the future web UI and adds Qt licensing obligations |

## Files changed by Bundle 47

Expected documentation-only scope:

- desktop shell ADR,
- desktop security contract,
- Target Architecture v2,
- roadmap v2 through Bundle 54,
- superseded pointers for architecture v1 and roadmap v1,
- license decision register update,
- README update,
- this status/schema document.

## Out of scope

Bundle 47 does not add:

- React or TypeScript packages,
- Rust crates,
- Tauri configuration,
- Electron packages,
- PySide6,
- a frozen Python executable,
- new API routes,
- sidecar authentication code,
- desktop UI screens,
- updater configuration,
- signing secrets,
- production runtime activation.

## Bundle 48 proof tree

```text
minimal React window
  → typed Tauri ping
  → Rust sidecar supervisor
  → packaged Python readiness service
  → native folder dialog
  → opaque capability ID
  → authenticated health request
  → graceful shutdown
```

Required evidence before product UI:

- target-specific sidecar packaging,
- renderer has no generic shell/filesystem permission,
- wrong credential and readiness nonce fail closed,
- sidecar terminates with desktop exit,
- package layout is verified,
- macOS packaged artifact starts under a clean test account,
- startup time, idle memory and artifact size are recorded,
- licensing/SBOM records include exact frontend, Rust and freeze dependencies,
- Electron fallback assessment is recorded if any blocking gate fails.

## Security invariants

- all host operations are named and typed,
- paths selected in renderer text are not authority,
- library read and export write use separate capabilities,
- no renderer-to-sidecar direct request,
- no public network binding,
- no secrets in logs or repository,
- no remote JavaScript in packaged mode,
- signed updates only,
- no default provider/authority switch from desktop work.

## Verification required

Before merge:

- ahead-only documentation diff from `c780dfeca2b87d9bbe5a325b5e3d0c9f168e2a7b`,
- PR Guard success,
- Python 3.11 and 3.12 install/compile/lint/pytest success,
- no review threads,
- mergeable head unchanged.

## Rollback

Bundle 47 changes documentation only. Revert the isolated future squash commit to restore the prior undecided desktop state. No database, runtime or user-data rollback is required.
