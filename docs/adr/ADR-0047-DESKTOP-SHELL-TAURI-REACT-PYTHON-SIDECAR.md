# ADR-0047 — Desktop Shell: Tauri 2 + React/TypeScript + Local Python Sidecar

## Status

Accepted for implementation planning. No desktop runtime is activated by this ADR.

## Context

APPLAYLIST is a local-first DJ application that must:

- scan user-selected music folders,
- analyze audio locally,
- persist track and analysis evidence,
- build explainable playlists,
- support keyboard-heavy professional workflows,
- export interoperable local files,
- run on macOS and Windows first,
- retain a reusable web UI surface where browser limitations are explicit.

The current backend, analysis, persistence, composition and export domains are Python. A desktop shell must not duplicate those domains or give renderer code unrestricted host access.

The evaluated options were:

1. Tauri 2 + React/TypeScript + local Python sidecar
2. Electron + React/TypeScript + local Python sidecar
3. PySide6/QML direct Python desktop

IPTVnator was reviewed as an architectural donor for desktop/web separation, typed bridges, security boundaries, feature matrices, packaging verification and operator UX. No IPTV-specific code or Angular/Electron implementation is adopted.

## Decision

APPLAYLIST will target:

```text
Tauri 2 desktop shell
+ React / TypeScript frontend
+ typed capability bridge
+ authenticated local Python sidecar
+ existing Python application services and SQLite
```

The browser/PWA build may reuse React components but will expose only browser-safe capabilities. It will not pretend to support unrestricted local-library scanning or local DJ-software integration.

## Why Tauri

### Advantages

- Uses the operating system web renderer instead of bundling Chromium.
- Provides explicit capability files for desktop permissions.
- Supports bundled sidecar executables.
- Supports CSP and a narrow command surface.
- Provides updater and signing-oriented release workflows.
- Preserves a React/TypeScript UI that can be reused for a limited web/PWA mode.
- Creates a smaller host-runtime and dependency surface than Electron.

### Accepted costs

- Rust becomes a required build/release toolchain.
- Python sidecar packaging and lifecycle must be engineered explicitly.
- Platform webview differences require packaged end-to-end tests.
- Sidecar authentication, readiness, restart and shutdown are APPLAYLIST responsibilities.

## Why not Electron as the primary choice

Electron is mature and has strong tooling, a clear process model and established auto-update options. IPTVnator demonstrates that it can be hardened professionally.

It is not selected as the primary target because:

- Chromium and Node are bundled with the application,
- the dependency and patching surface is larger,
- memory and installer size are expected to be higher,
- renderer/main/preload security discipline must be continuously maintained,
- APPLAYLIST does not currently need Electron-specific APIs that justify that cost.

Electron remains the fallback if the Tauri/Python sidecar prototype fails packaged lifecycle or platform-webview acceptance tests.

## Why not PySide6/QML as the primary choice

PySide6 offers the simplest direct integration with Python and strong native desktop APIs.

It is not selected as the primary target because:

- UI reuse with a future browser/PWA mode would be weak,
- QML introduces a separate UI ecosystem from the selected React direction,
- Qt deployment and plugin packaging add significant release complexity,
- LGPL/commercial compliance requires a dedicated distribution decision,
- updater behavior is not supplied as one integrated cross-platform product flow.

PySide6 remains a fallback for a Python-only internal operator tool, not the primary customer product.

## Trust boundaries

```text
Untrusted / lower trust
└── React renderer
    └── typed APPLAYLIST DesktopBridge
        └── Tauri commands and capabilities
            └── PythonSidecarSupervisor
                └── authenticated loopback channel
                    └── Python application services
                        ├── library ingestion
                        ├── metadata and persistence
                        ├── MIR analysis
                        ├── composition
                        └── export
```

Renderer payloads are requests, not authorization.

## Capability model

Initial capabilities are intentionally narrow:

```text
library.select_root
library.scan_selected_root
library.read_track_summary
analysis.start_selected_tracks
analysis.read_job_status
playlist.compose
playlist.edit
export.select_destination
export.write_authorized_destination
system.reveal_authorized_file
```

Rules:

- arbitrary shell execution is prohibited,
- arbitrary filesystem paths from React are not accepted as authority,
- a native picker creates a scoped capability,
- read capability is limited to an explicitly selected library root,
- export capability is limited to an explicitly selected destination,
- capabilities are operation-specific and revocable,
- desktop command arguments are schema validated,
- unknown commands fail closed.

## Python sidecar lifecycle

```text
Tauri application start
  -> choose free loopback port
  -> generate per-launch random bearer secret
  -> launch packaged Python sidecar
  -> pass port and secret through inherited process environment
  -> poll /health then /ready with bounded timeout
  -> expose desktop features only after readiness
  -> monitor child process
  -> controlled restart policy
  -> graceful shutdown
  -> forced termination after bounded deadline
```

Required invariants:

- sidecar listens only on loopback,
- every non-health request requires the per-launch secret,
- secret is not stored in repository or persistent settings,
- sidecar process ID and executable path are owned by the supervisor,
- stale sidecars are not silently reused,
- startup failure produces a recoverable UI state,
- automatic restart is bounded to prevent crash loops,
- app exit terminates the owned sidecar.

## Desktop and browser feature matrix

| Capability | Desktop | Browser/PWA |
|---|---:|---:|
| Select local library root | Yes | No |
| Bounded recursive scan | Yes | No |
| Local bulk MIR analysis | Yes | No |
| Playlist composition over synced data | Yes | Optional |
| Manual playlist editor | Yes | Yes |
| M3U8 export to selected destination | Yes | Browser download only |
| Rekordbox XML integration | Yes | Browser download only |
| Reveal file in OS | Yes | No |
| Local benchmark runner | CLI only | No |
| Auto-update | Desktop process | PWA service worker/deployment |

Unsupported capabilities must be hidden or explicitly disabled with an explanation. Silent partial behavior is prohibited.

## Target repository tree

```text
APPLAYLIST/
├── api/                         # Python local service
├── core/
├── data/
├── services/
├── workers/
├── frontend/
│   ├── package.json
│   ├── src/
│   │   ├── app/
│   │   ├── features/
│   │   │   ├── library/
│   │   │   ├── analysis/
│   │   │   ├── set-builder/
│   │   │   ├── playlist-editor/
│   │   │   └── export/
│   │   ├── shared/
│   │   │   ├── contracts/
│   │   │   ├── components/
│   │   │   ├── keyboard/
│   │   │   └── themes/
│   │   └── platform/
│   │       ├── desktop-bridge.ts
│   │       └── browser-bridge.ts
│   └── tests/
├── desktop/
│   ├── src-tauri/
│   │   ├── capabilities/
│   │   ├── src/
│   │   │   ├── commands/
│   │   │   ├── sidecar/
│   │   │   ├── filesystem/
│   │   │   ├── updates/
│   │   │   └── security/
│   │   └── tauri.conf.json
│   └── tests/
├── deploy/
│   ├── desktop/
│   └── compose/
└── docs/
```

The tree is a target shape. Bundle 47 does not create empty implementation directories merely to imitate it.

## Packaging and release requirements

A desktop release is not complete until CI verifies:

- frontend typecheck, lint and unit tests,
- Rust formatting, lint and tests,
- Python 3.11/3.12 backend tests,
- sidecar executable layout,
- packaged application launch,
- sidecar readiness in packaged mode,
- folder picker and scoped scan smoke test,
- export to a selected temporary destination,
- application shutdown without orphan sidecar,
- installer artifact inventory,
- macOS signing and notarization,
- Windows signing,
- updater metadata integrity,
- SBOM and third-party license inventory.

## Initial implementation slices

```text
Bundle 48 — Desktop contract and sidecar supervisor prototype
Bundle 49 — React desktop library shell
Bundle 50 — Analysis inspector and job progress
Bundle 51 — Explainable set builder
Bundle 52 — Manual playlist editor
Bundle 53 — M3U8/Rekordbox export vertical slice
Bundle 54 — Packaged smoke, signing and updater gate
```

A real provider benchmark run remains required before analysis values are declared production-authoritative.

## Security invariants

- No direct host-runtime access from React.
- No broad `shell` or filesystem capability.
- No remote web content inside privileged windows.
- CSP is mandatory in packaged builds.
- Navigation is restricted to packaged application content.
- External URLs open in the operating system browser after scheme validation.
- Python sidecar never binds to a non-loopback interface by default.
- Sidecar bearer credentials are per launch and memory-only.
- Update installation requires a verified signed artifact.
- Development escape hatches are disabled in production builds.

## Consequences

### Positive

- Strong fit for local-first file capabilities.
- Reusable modern web UI.
- Existing Python domain remains canonical.
- Smaller desktop runtime than Electron is achievable.
- Capability boundaries are explicit and reviewable.

### Negative

- Multi-language build stack: Python, TypeScript and Rust.
- Sidecar packaging is a critical release dependency.
- Platform-webview behavior requires broader E2E coverage.
- The team must maintain strict generated/shared contracts.

## Reversal criteria

Reconsider Electron if the packaged Tauri prototype fails any two of:

- reliable Python sidecar startup on macOS and Windows,
- signed update flow,
- acceptable webview audio/UI behavior,
- deterministic local filesystem capability behavior,
- acceptable packaged crash diagnostics.

Reconsider PySide6 only if web/PWA reuse is removed from the product strategy.

## References

- Tauri 2 capability, sidecar, CSP and updater documentation
- Electron process model, security checklist, distribution and updater documentation
- Qt for Python deployment and licensing documentation
- `4gray/iptvnator` desktop security, packaging and feature-separation patterns
