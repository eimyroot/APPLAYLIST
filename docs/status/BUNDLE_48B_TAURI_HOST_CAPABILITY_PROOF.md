# Bundle 48B — Tauri Host and Opaque Library Capability Proof

## Status

Implemented on an isolated feature branch. Not yet merged.

The implementation and bootstrap packaging proof are complete. Final merge remains fail-closed until GitHub-hosted runners can start the committed locked workflow.

## Product Value

Bundle 48B proves that a minimal React renderer can ask the Tauri host for desktop status and native library-folder selection without receiving general host, filesystem, network or sidecar authority.

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
    │   └── desktopBridge.ts — sole typed IPC boundary
    │       ├── desktop_status
    │       └── choose_library_root
    │
    └── Tauri Rust core
        ├── DesktopStatus command
        ├── native folder dialog
        ├── canonical directory validation
        ├── in-memory CapabilityRegistry
        │   ├── random UUID v4 capability ID
        │   ├── internal canonical path
        │   ├── internal lookup
        │   └── internal revocation
        └── sanitized renderer response
            ├── capabilityId
            └── displayName
```

## Changed Boundary

```text
untrusted React renderer
  → desktopBridge.ts
  → literal allow-listed Tauri command
  → Rust validation and capability ownership
  → sanitized response
```

The real directory path never becomes part of the renderer contract.

## Security Invariants

- `desktopBridge.ts` is the only renderer file allowed to import Tauri APIs or call `invoke`.
- Every invoke command must be a literal member of the two-command allow-list.
- Renderer cannot use direct HTTP, XMLHttpRequest, WebSocket or EventSource access.
- Renderer cannot contain loopback addresses.
- Renderer cannot import Tauri shell, filesystem, HTTP or dialog plugins.
- Tauri capabilities grant only `core:default` to the `main` window.
- The dialog plugin is called only by Rust.
- Only existing directories can become library-root capabilities.
- Paths are canonicalized before storage.
- Capability IDs use UUID v4 values and do not encode the path.
- Capability lookup and revocation remain internal to Rust.
- Error text does not disclose rejected paths.
- No sidecar URL, secret or nonce is exposed.
- No product database, MIR, composition or export operation is activated.

## Locked Dependency Decision

The npm and Cargo dependency graphs are committed as:

```text
frontend/desktop/package-lock.json
desktop/tauri/Cargo.lock
```

The committed binary icon is:

```text
desktop/tauri/icons/icon.png
```

The final workflow is read-only and uses:

```text
npm ci --ignore-scripts
cargo fmt --check
cargo clippy --locked -- -D warnings
cargo test --locked
cargo build --locked --release
```

It cannot generate lockfiles, format source files, materialize assets or push commits.

## Proof Gates

```text
frontend
├── committed npm lockfile
├── npm ci
├── TypeScript strict check
├── renderer security contract v2
└── production Vite build

Rust host
├── committed Cargo lockfile
├── cargo fmt --check
├── cargo clippy -D warnings
├── capability registry tests
├── release compile proof
└── macOS .app bundle proof
```

A previous bootstrap run successfully completed TypeScript, renderer security v1, clippy, Rust tests, release build and creation of `APPLAYLIST.app`. The final locked run must still execute on the exact committed head before merge.

## Current External Blocker

On the final committed head, Desktop Host Locked Proof, Python CI and PR Guard all failed before runner assignment and returned no steps. Public GitHub status reported Actions operational, so this is treated as a repository/account runner-start condition rather than code evidence. No required check is waived.

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

- npm and Cargo lockfiles are committed and CI uses locked modes,
- TypeScript and Vite production build pass,
- renderer security contract v2 passes,
- Rust format, clippy, tests and release build pass,
- macOS `.app` proof is generated,
- renderer response contains no host path,
- capability IDs are distinct, internally resolvable and revocable,
- existing Python 3.11/3.12 regression remains green,
- PR Guard, review-thread and mergeability gates pass,
- the final locked workflow runs successfully on the exact merge head.

## Rollback

Revert one isolated squash commit. No database, product-runtime or user-data migration is involved.

## Next Dependency

Bundle 48C adds Rust ownership of the packaged Bundle 48A sidecar lifecycle, private startup credentials, readiness validation and bounded shutdown. Parent issue #78 remains open until that proof is complete.
