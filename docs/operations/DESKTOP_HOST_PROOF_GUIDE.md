# APPLAYLIST Desktop Host Proof Guide

## Purpose

This guide verifies Bundle 48B only: the minimal React/Tauri host boundary and opaque library-root capability.

It does not start the Python sidecar, scan a library, analyze music or create a production installer.

## Repository Layout

```text
frontend/desktop/
├── package.json
├── package-lock.json              # required before final merge
├── index.html
├── tsconfig.json
├── vite.config.ts
├── scripts/security-contract.mjs
└── src/
    ├── App.tsx
    ├── desktopBridge.ts
    ├── main.tsx
    └── styles.css

desktop/tauri/
├── Cargo.toml
├── Cargo.lock                     # required before final merge
├── build.rs
├── tauri.conf.json
├── capabilities/main.json
└── src/
    ├── lib.rs
    └── main.rs
```

## Bootstrap Lockfile Stage

The first CI pass is allowed to generate lockfiles because the toolchains are new to the repository.

Locally:

```bash
cd frontend/desktop
npm install --ignore-scripts
npm run check
npm run security:contract
npm run build

cd ../../desktop/tauri
cargo generate-lockfile
cargo fmt -- --check
cargo clippy --all-targets --locked -- -D warnings
cargo test --locked
cargo build --release --locked
```

Do not merge the bootstrap state. Download the CI-produced lockfiles, compare Linux/macOS outputs and commit the accepted exact files.

## Final Locked Stage

After lockfiles are committed:

```bash
cd frontend/desktop
npm ci --ignore-scripts
npm run check
npm run security:contract
npm run build

cd ../../desktop/tauri
cargo fmt -- --check
cargo clippy --all-targets --locked -- -D warnings
cargo test --locked
cargo build --release --locked
```

No final workflow may run `npm install` or `cargo generate-lockfile`.

## macOS App Proof

From `frontend/desktop` after `npm ci` and `npm run build`:

```bash
npm run tauri -- build \
  --config ../../desktop/tauri/tauri.conf.json \
  --bundles app
```

Expected proof directory:

```text
desktop/tauri/target/release/bundle/macos/APPLAYLIST.app
```

This is an unsigned engineering proof. It is not an externally distributable release.

## Renderer Security Check

```bash
cd frontend/desktop
npm run security:contract
```

The check fails when renderer TypeScript contains:

- direct `fetch`, XMLHttpRequest, WebSocket or EventSource access,
- loopback addresses,
- Tauri shell, filesystem, HTTP or dialog plugin imports,
- Node filesystem or child-process imports,
- any invoke command outside the explicit allow-list.

## Manual Proof

Run the Vite/Tauri development shell only in a trusted development checkout:

```bash
cd frontend/desktop
npm run dev
```

In another terminal:

```bash
cd frontend/desktop
npm run tauri -- dev --config ../../desktop/tauri/tauri.conf.json
```

Expected behavior:

1. host status reports `applaylist-desktop-v1` and `host-ready`,
2. native folder dialog opens from the Rust command,
3. cancelling returns no capability,
4. selecting a directory returns an opaque `libroot_...` identifier and display name,
5. no absolute path appears in renderer-visible state.

## Security Notes

- Never replace the native dialog with a renderer text field for host paths.
- Never add `@tauri-apps/plugin-fs`, `plugin-shell` or `plugin-http` to the renderer.
- Never expose the capability registry lookup method as a generic renderer command.
- Never log the internal canonical path merely to debug the UI.
- Capability persistence is not part of this proof; registry state is session-only.

## Rollback

Revert the isolated Bundle 48B squash commit. Remove generated `node_modules`, `dist` and Rust `target` directories locally; none belong in Git.
