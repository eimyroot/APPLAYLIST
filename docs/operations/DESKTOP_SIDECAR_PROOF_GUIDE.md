# APPLAYLIST Desktop Sidecar Proof Guide

## Status

Bundle 48A proves only the Python sidecar boundary required by the canonical Bundle 48 Tauri proof.

It does not create the renderer, Tauri core, folder capability registry, updater, product UI or signed release.

## Schema Tree

```text
future Tauri supervisor
  -> spawn packaged executable
  -> write one private JSON line to stdin
      ├── protocol
      ├── per-session secret
      └── readiness nonce
  -> Python readiness sidecar
      ├── validate exact envelope
      ├── bind 127.0.0.1:0
      ├── emit ready event
      │   ├── protocol
      │   ├── loopback host
      │   ├── ephemeral port
      │   ├── nonce SHA-256
      │   └── process ID
      ├── authenticated GET /v1/health
      ├── authenticated POST /v1/shutdown
      └── graceful process exit
```

## Security Contract

- Secret and nonce are supplied through stdin, never command-line arguments.
- The startup envelope is read exactly once and is bounded to 8192 bytes.
- Only the exact `protocol`, `secret` and `nonce` fields are accepted.
- Secret and nonce must be distinct printable ASCII values between 32 and 256 characters.
- The service binds only to `127.0.0.1` and requests an ephemeral port from the OS.
- The raw nonce is not printed. Readiness exposes only its SHA-256 digest.
- The raw secret is never returned or logged.
- Health and shutdown require both secret and nonce headers.
- Missing or incorrect credentials return the same generic unauthorized response.
- Unknown routes and unsupported methods return controlled JSON responses.
- Shutdown accepts no request body.
- The renderer must never learn the sidecar URL, secret or nonce in Bundle 48B.

## Startup Envelope

The future Rust supervisor writes one newline-terminated JSON object:

```json
{"protocol":"applaylist-sidecar-v1","secret":"<session-secret>","nonce":"<readiness-nonce>"}
```

Do not pass the envelope in argv, environment variables, logs or renderer events.

## Readiness Event

The sidecar prints one JSON line to stdout:

```json
{
  "event": "ready",
  "host": "127.0.0.1",
  "nonce_sha256": "<digest>",
  "port": 49152,
  "process_id": 12345,
  "protocol": "applaylist-sidecar-v1"
}
```

The supervisor must verify:

1. event is `ready`,
2. protocol matches,
3. host is exactly `127.0.0.1`,
4. port is in the valid TCP range,
5. nonce digest matches its startup nonce,
6. the child process is still alive,
7. authenticated health succeeds.

## Local Source Test

```bash
python -m pytest -q tests/test_desktop_readiness_sidecar.py
```

## Packaging Proof

Install the explicitly separated packaging dependency:

```bash
python -m pip install -e ".[dev,desktop-build]"
```

Build a target-native PyInstaller `onedir` package:

```bash
python scripts/build_desktop_sidecar.py
```

Smoke-test the package:

```bash
python scripts/smoke_desktop_sidecar.py \
  artifacts/desktop-sidecar/package-manifest.json
```

PyInstaller is not a cross-compiler. Build each target on its target operating system.

## Why `onedir` First

The proof intentionally uses `onedir` because package contents and missing native libraries are easier to inspect. Bundle 48B may stage a target-triple sidecar executable for Tauri only after packaged lifecycle tests are stable.

A single-file format must not be treated as automatically superior: it extracts at startup and can complicate startup time, diagnostics and macOS signing behavior.

## Evidence

CI uploads:

```text
artifacts/desktop-sidecar/
├── dist/
├── package-manifest.json
├── smoke-evidence.json
├── spec/
└── work/
```

The package manifest records target platform, Python version and package size. It is proof evidence, not a distributable signed release.

## Rollback

Revert the isolated Bundle 48A squash commit. No data, schema or product-runtime rollback is required.
