# Bundle 48A — Authenticated Python Readiness Sidecar

## Status

Implemented on an isolated feature branch. Not yet merged.

## Product Value

Bundle 48A proves that the future Tauri desktop core can supervise a packaged Python process without exposing arbitrary shell, filesystem or sidecar network authority to the renderer.

## Schema Tree

```text
APPLAYLIST Desktop Proof
└── Bundle 48A: Python sidecar boundary
    ├── private stdin startup envelope
    │   ├── protocol version
    │   ├── per-session secret
    │   └── readiness nonce
    ├── loopback ephemeral listener
    ├── machine-readable readiness evidence
    ├── authenticated health
    ├── authenticated shutdown
    ├── signal-aware graceful exit
    ├── PyInstaller onedir package proof
    └── Linux/macOS packaged smoke workflow

Future Bundle 48B
└── Tauri 2 + React supervisor proof
    ├── typed commands
    ├── renderer isolation
    ├── secret ownership in Rust
    ├── sidecar lifecycle
    └── opaque folder capability ID
```

## Changed Boundary

```text
Rust supervisor contract (documented, not implemented)
  -> services.desktop.sidecar
  -> packaged process artifact
```

## Security Invariants

- No secret or nonce in argv.
- No secret or raw nonce in readiness output or errors.
- No environment-variable credential transport.
- Exact startup schema and protocol version.
- Loopback-only bind.
- OS-selected ephemeral port.
- Constant-time secret and nonce comparison.
- Generic unauthorized response.
- No generic RPC, shell, filesystem, database or product API.
- Renderer remains unable to connect directly.

## Packaging Decision

- `PyInstaller==6.21.0` is isolated under the `desktop-build` optional dependency.
- First proof uses `onedir` for inspectability.
- Each OS builds its own target-native artifact.
- CI artifacts are proof evidence, not signed releases.

## Out of Scope

- React/Vite workspace,
- Rust/Tauri core,
- native folder dialog,
- opaque capability registry,
- library import UI,
- MIR or composition UI,
- updater,
- code signing/notarization,
- production distribution.

## Acceptance

- Python 3.11 and 3.12 process tests pass.
- Missing/wrong secret and nonce fail closed.
- Correct health handshake succeeds.
- Body-bearing shutdown is rejected.
- Correct shutdown terminates within timeout.
- Credentials do not appear in process args or captured output.
- PyInstaller package builds on Linux and macOS.
- Packaged executable passes negative-auth, health and shutdown smoke checks.
- Existing full Python regression suite remains green.

## Rollback

Revert one isolated squash commit. No database or product-runtime migration is involved.

## Next Dependency

Bundle 48B adds the minimal React/Tauri supervisor and proves that the renderer cannot access the sidecar endpoint or private startup credentials.
