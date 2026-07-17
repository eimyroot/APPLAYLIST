# APPLAYLIST Desktop Host Proof Guide

## Purpose

This guide verifies Bundle 48B only: the minimal React/Tauri host boundary and opaque library-root capability.

It does not start the Python sidecar, scan a library, analyze music or create a signed production installer.

## Repository Layout

```text
frontend/desktop/
├── package.json
├── package-lock.json
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
├── Cargo.lock
├── build.rs
├── tauri.conf.json
├── icons/icon.png
├── capabilities/main.json
└── src/
    ├── lib.rs
    └── main.rs
```

## Final Locked Verification

The committed dependency graph is authoritative. Do not regenerate lockfiles during verification.

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

The final workflow must not run:

```text
npm install
cargo generate-lockfile
cargo fmt without --check
git commit
git push
```

## macOS App Proof

After the frontend build, run the Tauri CLI from the actual Tauri project root:

```bash
cd desktop/tauri
../../frontend/desktop/node_modules/.bin/tauri \
  build \
  --config tauri.conf.json \
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

The v2 security contract fails when renderer TypeScript contains:

- direct `fetch`, XMLHttpRequest, WebSocket or EventSource access,
- loopback addresses,
- Tauri shell, filesystem, HTTP or dialog plugin imports,
- Node filesystem or child-process imports,
- Tauri imports outside `src/desktopBridge.ts`,
- invoke calls outside `src/desktopBridge.ts`,
- dynamic or non-literal invoke command names,
- invoke commands outside the explicit allow-list.

The only allowed renderer commands are:

```text
desktop_status
choose_library_root
```

## Manual Proof

Run the development shell only in a trusted checkout.

First start Vite:

```bash
cd frontend/desktop
npm ci --ignore-scripts
npm run dev
```

In another terminal start Tauri from its project root:

```bash
cd desktop/tauri
../../frontend/desktop/node_modules/.bin/tauri dev --config tauri.conf.json
```

Expected behavior:

1. host status reports `applaylist-desktop-v1` and `host-ready`,
2. native folder dialog opens from the Rust command,
3. cancelling returns no capability,
4. selecting a directory returns an opaque `libroot_...` identifier and display name,
5. no absolute path appears in renderer-visible state.

## Security Notes

- Never replace the native dialog with a renderer text field for host paths.
- Never add renderer access to `plugin-fs`, `plugin-shell`, `plugin-http` or `plugin-dialog`.
- Never import Tauri APIs outside `desktopBridge.ts`.
- Never construct invoke command names dynamically.
- Never expose capability registry lookup as a generic renderer command.
- Never log the internal canonical path merely to debug the UI.
- Capability persistence is not part of this proof; registry state is session-only.
- Bundle 48C must keep sidecar credentials, URL and lifecycle ownership in Rust.

## CI Interpretation

A workflow result with no assigned steps is not evidence that a build command failed. Required checks remain fail-closed and must be rerun after GitHub-hosted runner access is restored.

## Rollback

Revert the isolated Bundle 48B squash commit. Remove local `node_modules`, `dist` and Rust `target` directories; none belongs in Git.
