# Bundle 48B — Tauri Host and Opaque Library Capability Proof

## Status

Implemented on an isolated feature branch. Not yet merged.

## Product Value

Bundle 48B proves that a minimal React renderer can ask the Tauri host for desktop status and a native library-folder selection without receiving general host, filesystem, network or sidecar authority.

## Schema Tree

```text
APPLAYLIST Desktop Proof
├── Bundle 48A: authenticated Python sidecar ✅
│   ├── private stdin startup envelope
│   ├── loopback ephemeral listener
│   ├── authenticated health/shutdown
│   └── Linux/macOS package proof
│
└── Bundle 48B: Tauri host capability proof
    ├── React / TypeScript renderer
    │   └── typed invoke-only bridge
    │       ├── desktop_status
    │       └── choose_library_root
    │
    └── Tauri Rust core
        ├── DesktopStatus command
        ├── native folder dialog
        ├── canonical directory validation
        ├── in-memory CapabilityRegistry
        │   ├── cryptographically random ID
        │   ├── internal canonical path
        │   ├── lookup
        │   └── revocation
        └── renderer response
            ├── capabilityId
            └── displayName
```

## Changed Boundary

```text
untrusted React renderer
  → named Tauri invoke command
  → Rust validation and capability ownership
  → sanitized response
```

The real directory path never becomes part of the renderer contract.

## Security Invariants

- Renderer imports only `@tauri-apps/api/core` for `invoke`.
- Renderer cannot use direct HTTP, WebSocket or EventSource access.
- Renderer cannot import Tauri shell, filesystem, HTTP or dialog plugins.
- Tauri capabilities grant only `core:default` to the `main` window.
- The dialog plugin is called only by Rust.
- Only existing directories can become library-root capabilities.
- Paths are canonicalized before storage.
- Capability IDs use random UUID v4 values and do not encode the path.
- Capability lookup and revocation remain internal to Rust.
- Error text does not disclose rejected paths.
- No sidecar URL, secret or nonce is exposed.
- No product database, MIR, composition or export operation is activated.

## Dependency Decision

Direct dependencies are exactly pinned in the frontend and Rust manifests.

The bootstrap workflow generates `package-lock.json` and `Cargo.lock` as evidence. Those exact lockfiles must be committed before the PR may leave draft state. The final workflow must then use `npm ci` and Cargo `--locked` only.

## Proof Gates

```text
frontend
├── npm exact dependency graph
├── TypeScript strict check
├── renderer security contract
└── production Vite build

Rust host
├── cargo fmt
├── cargo clippy -D warnings
├── capability registry tests
├── release compile proof
└── macOS .app bundle proof
```

## Out of Scope

- Python sidecar supervision from Rust,
- renderer-to-sidecar networking,
- library scanning or persistence,
- product library table,
- analysis, composition or export screens,
- updater,
- signing and notarization,
- production release claim.

## Acceptance

- npm and Cargo lockfiles are committed and final CI uses locked modes,
- TypeScript and Vite production build pass,
- renderer security contract passes,
- Rust format, clippy, tests and release build pass,
- macOS `.app` proof is generated,
- renderer response contains no host path,
- capability IDs are distinct, resolvable internally and revocable,
- existing Python 3.11/3.12 regression remains green,
- PR Guard, review-thread and mergeability gates pass.

## Rollback

Revert one isolated squash commit. No database, product-runtime or user-data migration is involved.

## Next Dependency

Bundle 48C adds Rust ownership of the packaged Bundle 48A sidecar lifecycle, private startup credentials, readiness validation and bounded shutdown. Parent issue #78 remains open until that proof is complete.
