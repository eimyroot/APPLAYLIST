# ADR — Bundle 47 Desktop Shell Architecture

## Status

Accepted for proof implementation. This decision does not yet add frontend, Rust, Electron or Qt runtime dependencies.

## Decision

APPLAYLIST will use the following target for its desktop/web hybrid product:

```text
Tauri 2
+ React / TypeScript shared UI
+ Rust desktop core
+ packaged Python sidecar
+ loopback-only authenticated FastAPI service
```

Electron + React remains the documented fallback if the proof bundle cannot meet packaging, WebView compatibility, sidecar supervision or release requirements.

PySide6/QML is not selected for the current product direction because APPLAYLIST requires a reusable web UI and future browser/PWA presentation. It may be reconsidered only if the shared-web requirement is removed.

## Product reason

The first release must provide a professional local workflow:

```text
select folder
→ import library
→ analyze BPM/key/Camelot/energy
→ inspect evidence
→ generate set
→ edit playlist
→ export M3U8
```

The desktop shell must expose this workflow without moving filesystem authority, DSP, SQL or provider selection into frontend code.

## Inputs

The decision uses:

- the accepted APPLAYLIST local-first architecture,
- the existing Python/FastAPI application and service layers,
- Bundle 42–46 library, metadata, MIR and benchmark boundaries,
- IPTVnator as an architectural donor for desktop/web separation and release discipline,
- current official Tauri, Electron and Qt for Python documentation.

IPTVnator product-specific code, Angular state management, IPTV parsing, EPG, playback and remote proxy logic are not donor material.

## Decision matrix

Scores use a 1–5 engineering assessment. They are architecture decisions, not measured release benchmarks. The proof bundle must replace assumptions with packaged evidence.

| Criterion | Weight | Tauri + React + Python | Electron + React + Python | PySide6/QML |
|---|---:|---:|---:|---:|
| Shared desktop/web UI | 20 | 5 | 5 | 1 |
| Least-privilege host bridge | 20 | 5 | 4 | 4 |
| Python service integration | 15 | 4 | 4 | 5 |
| Packaging/signing/updater path | 15 | 4 | 5 | 3 |
| Runtime/installer efficiency | 10 | 5 | 2 | 3 |
| Accessibility/keyboard web tooling | 5 | 5 | 5 | 3 |
| Commercial license simplicity | 5 | 5 | 5 | 2 |
| Team maintainability | 10 | 4 | 4 | 4 |
| **Weighted result / 100** | **100** | **91** | **82** | **62** |

## Why Tauri is selected

### Shared UI

Tauri renders a standard web frontend in the operating system WebView. APPLAYLIST can therefore use one React/TypeScript UI architecture for the desktop shell and a future browser mode while keeping host capabilities in the Rust core.

### Capability model

Tauri 2 supports explicit capability and permission declarations. The frontend must never receive a generic shell execution permission or unrestricted filesystem access.

Only named Rust commands are allowed. The initial command surface is limited to:

- choose library folder,
- start and inspect import,
- start and inspect analysis,
- query library rows,
- create composition request,
- edit playlist revision,
- choose export destination,
- export approved playlist,
- inspect application/update status.

### Python sidecar

Tauri explicitly supports bundled sidecar executables, including Python CLI applications or API servers packaged as platform binaries.

APPLAYLIST already contains a tested FastAPI/service architecture. Reusing it avoids duplicating domain behavior in Rust or TypeScript.

### Distribution

Tauri provides platform-specific installers, signing/notarization guidance and an updater whose artifacts require cryptographic signatures.

### Footprint

Tauri uses the operating system WebView instead of bundling Chromium. This should reduce application footprint compared with Electron, but the proof bundle must measure the actual APPLAYLIST installer and memory use including the packaged Python sidecar.

## Runtime topology

```text
┌──────────────────────────────────────────────────────────┐
│ React / TypeScript renderer                              │
│ Library | Analysis | Set Builder | Editor | Export       │
└───────────────────────┬──────────────────────────────────┘
                        │ typed invoke/event contracts
┌───────────────────────▼──────────────────────────────────┐
│ Tauri Rust core                                          │
│ - window and navigation policy                           │
│ - native dialogs                                         │
│ - capability registry                                    │
│ - Python sidecar supervisor                              │
│ - update ownership                                       │
│ - request correlation and audit                          │
└───────────────────────┬──────────────────────────────────┘
                        │ authenticated loopback channel
┌───────────────────────▼──────────────────────────────────┐
│ Packaged Python sidecar                                  │
│ FastAPI transport → application services                 │
│ library | analysis | composition | playlist | export     │
└───────────────────────┬──────────────────────────────────┘
                        │
┌───────────────────────▼──────────────────────────────────┐
│ Local SQLite + explicitly authorized filesystem roots    │
└──────────────────────────────────────────────────────────┘
```

## Trust boundaries

### Renderer

The renderer is untrusted relative to host resources.

It must not:

- execute shell commands,
- choose arbitrary host paths by text,
- connect directly to SQLite,
- import Python or audio libraries,
- call the sidecar port directly,
- hold update-signing material,
- receive long-lived filesystem authority.

### Tauri core

The Rust core is the desktop policy-enforcement point.

It owns:

- native folder/save dialogs,
- mapping opaque capability IDs to real paths,
- sidecar spawn/readiness/shutdown,
- local session credentials,
- navigation and external-link policy,
- update checks and installation,
- packaged-mode restrictions.

### Python sidecar

The Python service owns product use cases and domain behavior.

It must:

- bind only to `127.0.0.1` or an accepted local IPC replacement,
- use an ephemeral port selected for the current process,
- require a random per-session credential on every non-health request,
- reject non-loopback host/origin assumptions,
- disable public API documentation in packaged mode,
- accept opaque capability references resolved by the desktop core,
- never convert an arbitrary renderer string into filesystem authority,
- terminate when the owning desktop process exits.

## Sidecar lifecycle contract

```text
Tauri startup
  → generate session nonce and request correlation seed
  → spawn target-specific packaged Python sidecar
  → pass startup secret through inherited stdin or equivalent private channel
  → sidecar binds loopback ephemeral port
  → sidecar emits one readiness envelope
  → Rust validates nonce, protocol version and process identity
  → desktop enters READY
```

Required states:

```text
not_started
starting
ready
degraded
stopping
stopped
failed
```

Required failure behavior:

- timeout during startup → kill child and show controlled startup failure,
- malformed readiness envelope → kill child,
- sidecar exits unexpectedly → disable product commands and offer restart,
- protocol version mismatch → fail closed,
- desktop exit → graceful shutdown request, then forced kill after timeout,
- no automatic restart loop without a bounded retry policy.

## Transport decision

For the first proof, the Rust core communicates with the sidecar through authenticated loopback HTTP because the existing FastAPI transport is already tested.

The React renderer does not receive the sidecar base URL or credential. It invokes typed Tauri commands; the Rust core performs the local request.

A later Unix-domain-socket or named-pipe transport may replace HTTP only if it preserves the same application-service contracts and materially improves security or reliability.

## Filesystem capability model

```text
Native folder dialog
  → Rust validates selected path
  → LibraryRootCapability
      - capability_id
      - canonical_path held only by Rust
      - display_label
      - allowed_operations
      - issued_at
      - expires_at/session_id
  → opaque capability_id returned to renderer
```

Initial operations:

- `library.scan`,
- `library.read`,
- `export.write`,
- `file.reveal` for APPLAYLIST-owned records.

Rules:

- no path authority from text fields,
- no implicit parent-directory authority,
- no symlink escape,
- export capability is separate from library-read capability,
- capabilities expire with the desktop session,
- persistent remembered folders require explicit user approval and revalidation,
- the sidecar receives only paths resolved by Rust for an authorized operation.

## Navigation and content policy

Packaged mode loads only bundled application content.

Required controls:

- restrictive Content Security Policy,
- deny arbitrary navigation,
- deny new in-app windows by default,
- open approved `https:` external links in the operating system browser,
- no remote JavaScript,
- no inline secrets,
- sanitize rendered release notes and user-provided metadata,
- no generic URL fetch command in the renderer bridge.

## Desktop/PWA feature matrix

| Capability | Desktop | Future browser/PWA |
|---|---:|---:|
| Native folder selection | yes | no |
| Bounded local library scan | yes | no |
| Full local audio analysis | yes | no by default |
| Library/analysis inspection | yes | possible with remote service |
| Set builder/editor | yes | yes with an authorized service |
| M3U8 local path export | yes | limited download semantics |
| Reveal file/folder | yes | no |
| Local benchmark CLI | external operator tool | no |
| Signed self-update | yes | service-worker/web deployment model |

The UI must show unavailable capabilities explicitly instead of silently degrading.

## Packaging and release contract

Initial target order:

1. signed and notarized macOS application,
2. signed Windows installer,
3. Linux after desktop MVP acceptance.

Each target requires:

- target-specific Tauri shell,
- target-specific packaged Python sidecar,
- package-layout verification,
- clean-machine installation test,
- packaged startup/readiness test,
- folder selection and bounded scan smoke test,
- one real short audio analysis smoke test,
- M3U8 export smoke test,
- dependency lock and SBOM,
- third-party notices,
- installer signature verification.

Tauri update artifacts must be signed. Update private keys must never enter the repository or application bundle.

## Monorepo target layout

The proof implementation should use:

```text
frontend/
├── app/                  React product UI
├── contracts/            generated/shared TypeScript contracts
└── tests/

desktop/
├── src-tauri/
│   ├── capabilities/
│   ├── src/commands/
│   ├── src/sidecar/
│   ├── src/security/
│   └── tauri.conf.json
└── binaries/             generated target sidecars, never hand-edited

api/ core/ services/ data/ workers/
└── existing Python product layers
```

The repository does not adopt Nx solely because IPTVnator uses it. A JavaScript workspace tool may be introduced only when the frontend proof demonstrates a concrete need.

## Alternatives

### Electron + React + Python

Advantages:

- mature Chromium-consistent behavior,
- established packaging and updater ecosystem,
- excellent packaged-app testing options,
- architectural precedent from IPTVnator.

Reasons not selected first:

- ships Chromium and Node runtime,
- larger security/update surface,
- greater memory and installer expectations,
- still requires a secure Python sidecar boundary.

Fallback trigger:

- Tauri WebView differences block declared UI behavior,
- target sidecar packaging is not reliable,
- accessibility or testing requirements cannot be met,
- measured delivery cost is materially higher than Electron.

### PySide6/QML

Advantages:

- direct Python integration,
- mature native UI toolkit,
- official multi-platform deployment tooling.

Reasons rejected for the current target:

- does not naturally share the React/browser UI,
- community distribution requires LGPLv3/GPLv3 compliance or commercial Qt licensing,
- QML creates a second UI technology path,
- future PWA would require another frontend implementation.

## Proof gate before full UI implementation

Bundle 48 must prove only the shell boundary, not the full product UI.

Required proof:

```text
Tauri window
  → typed ping command
  → spawn packaged Python sidecar
  → readiness handshake
  → native folder dialog
  → opaque capability ID
  → sidecar health/status request through Rust
  → graceful shutdown
```

Acceptance evidence:

- no arbitrary shell permission,
- no renderer-to-sidecar direct request,
- no renderer-provided arbitrary filesystem path,
- packaged macOS artifact launches on a clean test account,
- sidecar is terminated on desktop exit,
- package contents and licenses are recorded,
- measured startup time, idle memory and artifact size,
- fallback decision documented if the proof fails.

## Consequences

Positive:

- preserves the existing Python product core,
- enables a professional shared web UI,
- creates an explicit desktop capability boundary,
- keeps Electron available as a controlled fallback,
- aligns release discipline with mature desktop products.

Costs:

- adds Rust and TypeScript toolchains,
- requires per-target Python sidecar builds,
- requires WebView compatibility testing,
- requires two-process lifecycle engineering,
- signing/notarization and updater infrastructure become release-critical.

## Rollback

This ADR can be superseded without data migration because Bundle 47 changes documentation only.

After a Tauri proof implementation begins, rollback means:

- remove the unmerged proof branch, or
- revert the isolated proof squash commit,
- retain Python application services and React contracts,
- execute the documented Electron fallback assessment.

## References

- Tauri process model: https://v2.tauri.app/concept/process-model/
- Tauri external binaries/sidecars: https://v2.tauri.app/develop/sidecar/
- Tauri distribution: https://v2.tauri.app/distribute/
- Tauri updater: https://v2.tauri.app/plugin/updater/
- Tauri architecture and license: https://v2.tauri.app/concept/architecture/
- Electron security: https://www.electronjs.org/docs/latest/tutorial/security
- Electron process model: https://www.electronjs.org/docs/latest/tutorial/process-model
- Electron distribution: https://www.electronjs.org/docs/latest/tutorial/distribution-overview
- Qt for Python: https://doc.qt.io/qtforpython-6/
- Qt for Python deployment: https://doc.qt.io/qtforpython-6/deployment/
- Qt for Python commercial use: https://doc.qt.io/qtforpython-6/commercial/
- IPTVnator Electron security contract: https://github.com/4gray/iptvnator/blob/master/docs/architecture/electron-security.md
