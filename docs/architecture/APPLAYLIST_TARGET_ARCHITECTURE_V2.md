# APPLAYLIST Target Architecture v2

## Status

Accepted target architecture after Bundle 47.

This document supersedes `APPLAYLIST_TARGET_ARCHITECTURE_V1.md` for new implementation decisions. The v1 document remains historical evidence of the product-first realignment.

## Architectural goal

APPLAYLIST must deliver a complete local DJ preparation workflow while keeping presentation, desktop authority, application orchestration, audio providers, persistence, composition and export independently testable.

## Product topology

```text
┌────────────────────────────────────────────────────────────┐
│ React / TypeScript product UI                              │
│ Library | Analysis | Set Builder | Editor | Export         │
└────────────────────────┬───────────────────────────────────┘
                         │ typed Tauri commands/events
┌────────────────────────▼───────────────────────────────────┐
│ Tauri Rust desktop core                                   │
│ native dialogs | capabilities | sidecar | updates | policy │
└────────────────────────┬───────────────────────────────────┘
                         │ authenticated loopback transport
┌────────────────────────▼───────────────────────────────────┐
│ Python transport and application services                 │
│ FastAPI | import | analysis | composition | edit | export  │
└──────────────┬────────────────────────────┬────────────────┘
               │                            │
┌──────────────▼─────────────┐  ┌───────────▼────────────────┐
│ Provider boundary          │  │ Repository boundary        │
│ metadata / MIR / optional  │  │ tracks / analysis / sets   │
└────────────────────────────┘  └────────────────────────────┘
```

## Runtime modes

### Packaged desktop mode

- React renderer is bundled locally.
- Tauri core owns host authority.
- Python is packaged as a target-specific sidecar.
- Sidecar binds loopback only with per-session authentication.
- SQLite and audio files remain local.
- Product operations flow through typed desktop commands.

### Headless development/integration mode

FastAPI remains available for:

- Python integration tests,
- local development,
- operator automation,
- benchmark tooling,
- future explicitly approved remote/service mode.

Routes must remain transport adapters. Core product behavior cannot exist only in HTTP handlers.

### Future browser mode

A browser/PWA may reuse React presentation and typed application contracts, but it does not receive local host capabilities.

Local scanning, full local analysis, reveal-file and desktop update operations are unavailable unless an explicitly authorized service provides them.

## Layer responsibilities

### React UI

Owns:

- visual presentation,
- table/editor state,
- keyboard and accessibility behavior,
- validation feedback,
- typed product command requests,
- unavailable-capability presentation.

Must not own:

- filesystem traversal or authorization,
- subprocess management,
- audio DSP,
- SQL,
- provider selection policy,
- export serialization,
- updater verification.

### Tauri desktop core

Owns:

- application window lifecycle,
- navigation and external-link policy,
- native file/folder dialogs,
- opaque filesystem capabilities,
- Python sidecar lifecycle,
- sidecar session authentication,
- typed renderer command routing,
- update verification/install flow,
- packaged-mode security invariants.

It must not duplicate APPLAYLIST domain, MIR, composition or repository logic.

### Python transport layer

Owns:

- validated transport schemas,
- request authentication in packaged mode,
- application-service invocation,
- normalized error envelopes,
- progress/event transport.

### Application services

Own use-case orchestration and transaction boundaries:

- `LibraryImportService`,
- `AnalysisJobService`,
- `CanonicalCompositionRunner`,
- `PlaylistEditingService`,
- `PlaylistExportService`.

### Domain contracts

Own immutable data and pure rules:

- track identity,
- metadata and analysis evidence,
- transition scoring,
- composition constraints,
- playlist revisions,
- export preconditions,
- job states.

Domain code must not import React, Tauri, FastAPI, SQLite, Librosa or Essentia.

### Provider boundary

Provider rules:

- lazy optional imports,
- explicit name/version/algorithm provenance,
- raw output never persisted directly,
- controlled availability/runtime/output errors,
- no repository writes,
- no network upload for MVP analysis.

### Repository boundary

Owns:

- transaction boundaries,
- batch persistence,
- read models,
- track/file/metadata history,
- analysis versions and corrections,
- playlist revisions,
- job state,
- export evidence.

### Export adapters

Order:

1. UTF-8 M3U8,
2. JSON evidence,
3. rekordbox XML,
4. Traktor NML.

Adapters never mutate approved playlist revisions.

## Desktop capability boundary

```text
native user selection
  → Tauri validation
  → opaque capability ID
  → named operation
  → resolved authorized path
  → Python application service
```

Initial capability types:

- library root read/scan,
- export destination write,
- reveal APPLAYLIST-owned record.

A renderer-provided path string is never sufficient authorization.

Detailed requirements are defined in `APPLAYLIST_DESKTOP_SECURITY_CONTRACT_V1.md`.

## Sidecar boundary

```text
Tauri starts sidecar
  → private session credential
  → loopback ephemeral port
  → readiness nonce/protocol verification
  → typed command proxy
  → graceful shutdown / bounded forced kill
```

The renderer never receives the sidecar URL or credential.

The proof implementation must establish:

- target-specific binary packaging,
- startup/readiness reliability,
- crash and restart behavior,
- shutdown ownership,
- package-layout verification,
- startup time, idle memory and artifact size.

## Library and analysis flow

```text
LibraryRootCapability
  → bounded scanner
  → stable content identity
  → tagged metadata
  → transactional track persistence
  → typed analysis job
  → lazy provider
  → normalize and validate
  → analysis repository
  → inspector read model
```

Provider authority remains blocked by the MIR benchmark and human review gate.

## Transition and set flow

```text
analyzed source scope
  → transition feature adapter
  → versioned pairwise scores and explanations
  → deterministic transition graph
  → set constraints and dramaturgy mode
  → ordered proposal and trace
  → editable playlist revision
```

Initial set modes:

- smooth journey,
- build to peak,
- wave.

Composition performs no network request.

## Export flow

```text
approved playlist revision
  → path integrity validation
  → export destination capability
  → format adapter
  → temporary output
  → atomic publish
  → export manifest
```

## Security invariants

1. Renderer never receives generic shell or filesystem authority.
2. Renderer never calls the Python sidecar directly.
3. Tauri core owns native dialogs, capabilities and sidecar lifecycle.
4. Sidecar binds loopback only in packaged mode.
5. Every packaged product request is session authenticated.
6. Providers never persist.
7. Optional audio imports never occur on mandatory boot.
8. Only normalized validated analysis is stored.
9. Composition is deterministic for fixed evidence and versions.
10. Manual edits create explicit revisions.
11. Export validates all paths and publishes atomically.
12. Update artifacts are signed and private keys remain outside source control.
13. New desktop commands require named product use cases and negative tests.
14. Default provider/authority changes require benchmark and rollback evidence.

## Packaging stages

### Bundle 48 proof

- minimal React/Tauri shell,
- packaged Python sidecar,
- readiness/authentication/shutdown,
- native folder capability,
- macOS packaged smoke evidence,
- measured footprint.

### Desktop MVP

- signed/notarized macOS application,
- Windows signed installer after macOS acceptance,
- package-layout and clean-machine tests,
- SBOM and third-party notices,
- updater artifacts and signature verification.

### Linux and browser modes

Deferred until the macOS/Windows local workflow is product-accepted.

## Donor policy

IPTVnator contributes principles only:

- shared web UI with explicit desktop-only features,
- hardened renderer/host separation,
- typed host bridge,
- package layout checks,
- packaged smoke tests,
- release and updater discipline.

No IPTV, Angular/NgRx, playback, EPG, proxy or provider code is imported.

## Implementation sequence

Use `docs/roadmap/APPLAYLIST_PRODUCT_ROADMAP_41_54.md`.

## Related decisions

- `ADR_BUNDLE_47_DESKTOP_SHELL.md`
- `APPLAYLIST_DESKTOP_SECURITY_CONTRACT_V1.md`
- `APPLAYLIST_PRODUCT_ROADMAP_41_54.md`
