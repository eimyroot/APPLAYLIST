# Bundle 47 — Desktop Shell Architecture ADR

## Status

Implemented as a decision-only bundle. No frontend, Rust runtime, Tauri configuration or Python sidecar executable is added here.

## Decision

```text
Tauri 2
+ React / TypeScript
+ typed capability bridge
+ authenticated local Python sidecar
+ existing Python services and SQLite
```

Electron remains the fallback if the packaged Tauri prototype cannot meet lifecycle, signing, update or filesystem-capability gates. PySide6/QML remains suitable only for a Python-only operator tool if web/PWA reuse is removed.

## Donor selection

From `4gray/iptvnator`, APPLAYLIST adopts only these architectural principles:

- shared web UI with an explicit desktop feature boundary,
- typed renderer-to-host bridge,
- hardened renderer defaults,
- navigation and external URL gates,
- native-dialog-derived filesystem capabilities,
- explicit desktop/PWA feature matrix,
- packaged-app smoke testing,
- signed release and updater discipline,
- keyboard-first workspace UX.

Rejected donor scope:

- Angular and NgRx adoption,
- IPTV, EPG, Xtream, Stalker, TMDB or playback code,
- remote proxy logic,
- direct code copy,
- automatic selection of Electron merely because the donor uses it.

## Schema tree

```text
APPLAYLIST Desktop Runtime
├── React renderer [untrusted/lower trust]
│   ├── Library
│   ├── Analysis
│   ├── Set Builder
│   ├── Playlist Editor
│   └── Export
│
├── Typed DesktopBridge
│   └── validated commands only
│
├── Tauri capability boundary
│   ├── native folder selection
│   ├── scoped library-root capability
│   ├── scoped export-destination capability
│   ├── external URL handoff
│   └── updater capability
│
├── PythonSidecarSupervisor
│   ├── packaged executable selection
│   ├── free loopback port
│   ├── per-launch memory-only secret
│   ├── health/readiness timeout
│   ├── process monitoring
│   ├── bounded restart
│   └── graceful/forced shutdown
│
└── Python application services [canonical domain]
    ├── library ingestion
    ├── metadata and persistence
    ├── MIR analysis
    ├── transition scoring
    ├── set composition
    └── export
```

## Required prototype before product UI expansion

Bundle 48 must prove only the risky foundation:

```text
packaged Tauri shell
  → starts packaged Python sidecar
  → authenticates loopback call
  → receives /health and /ready
  → selects a folder natively
  → grants scoped read capability
  → performs bounded scan
  → returns a redacted file summary
  → shuts down without orphan process
```

No full visual design, playlist editor or updater implementation belongs in that prototype.

## Acceptance gates for Bundle 48

- macOS development and packaged smoke,
- Windows CI or representative packaged smoke,
- no sidecar listening beyond loopback,
- rejected request without per-launch credential,
- rejected arbitrary renderer path,
- bounded startup timeout,
- bounded restart policy,
- graceful shutdown and orphan-process assertion,
- typed bridge contract test,
- CSP and navigation policy present,
- package layout evidence,
- no production provider activation.

## Roadmap

```text
Bundle 47 — architecture ADR                         COMPLETE IN BRANCH
Bundle 48 — desktop contract + sidecar prototype     NEXT
Bundle 49 — React library shell
Bundle 50 — analysis inspector
Bundle 51 — explainable set builder
Bundle 52 — manual playlist editor
Bundle 53 — interoperable export vertical slice
Bundle 54 — signing, updater and packaged release gate
```

## Rollback

Revert the isolated documentation squash commit. No runtime or data rollback is required.
