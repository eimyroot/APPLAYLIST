# APPLAYLIST Desktop Security Contract v1

## Status

Accepted architecture contract for the desktop-shell proof and later product UI.

This contract applies regardless of whether the shell implementation remains Tauri or uses the documented Electron fallback.

## Security objective

The desktop renderer must behave like an untrusted presentation process. It may request named product operations but must never receive general host authority.

```text
renderer request
  → typed desktop command
  → capability and input validation
  → application-service request
  → normalized response
```

## Principal boundaries

### Renderer principal

Allowed:

- render local product state,
- submit validated command payloads,
- receive progress/events,
- store non-sensitive transient UI preferences,
- request native selection dialogs.

Forbidden:

- arbitrary shell/process execution,
- unrestricted filesystem APIs,
- direct SQLite access,
- direct Python import or plugin loading,
- direct sidecar network access,
- update installation ownership,
- long-lived secrets,
- arbitrary URL fetching,
- changing production provider defaults.

### Desktop-core principal

The desktop core owns:

- window/navigation policy,
- native file/folder dialogs,
- opaque filesystem capabilities,
- sidecar process lifecycle,
- local authentication material,
- typed command routing,
- external-browser handoff,
- update verification and installation,
- application shutdown coordination.

### Python-sidecar principal

The sidecar owns:

- APPLAYLIST transport endpoints,
- application-service orchestration,
- provider execution,
- repository transactions,
- composition and export behavior,
- structured product evidence.

The sidecar must not assume that a string received from the renderer is authorized filesystem input.

## Renderer command allow-list

The initial desktop bridge may expose only these command families:

```text
app.status
app.version
app.restart_sidecar

library.choose_root
library.scan
library.import
library.list

analysis.start
analysis.cancel
analysis.status
analysis.list_results

composition.create
composition.status

playlist.get
playlist.reorder
playlist.lock
playlist.replace
playlist.approve

export.choose_destination
export.m3u8

file.reveal_owned_record
update.status
update.check
update.download
update.install
```

A new command requires:

1. named product use case,
2. typed request/response contract,
3. capability and authorization analysis,
4. negative tests,
5. documentation update.

No generic command such as `run`, `exec`, `read_file`, `write_file`, `request_url` or `call_api` is permitted.

## Filesystem authorization

### Native-selection rule

A local root or export destination becomes authorized only after selection through a native dialog owned by the desktop core.

The renderer receives:

```text
capability_id
human-readable label
allowed operations
expiration/session state
```

The renderer does not receive reusable host authority from a text input.

### Capability types

| Capability | Operations | Persistence |
|---|---|---|
| `LibraryRootCapability` | bounded scan/read | session by default |
| `ExportDestinationCapability` | create one approved export | single-use by default |
| `OwnedRecordCapability` | reveal an APPLAYLIST-owned path | derived from repository record |
| `RememberedLibraryCapability` | re-open approved root after revalidation | explicit opt-in |

### Filesystem invariants

- canonical containment is checked after path resolution,
- symlink escape is rejected,
- library read authority does not grant write authority,
- export authority does not grant directory traversal,
- existing export files are not overwritten without explicit product policy,
- capabilities are bound to one desktop session or persistent approved record,
- revoked/expired capability IDs fail closed,
- audit logs contain capability ID and operation, not secrets.

## Sidecar process contract

### Spawn

- the desktop core spawns one target-specific packaged sidecar,
- no renderer-controlled executable path is accepted,
- no renderer-controlled raw command-line array is accepted,
- startup arguments are fixed or schema validated,
- the sidecar binary is part of the signed package layout.

### Authentication

- one random session credential is generated per sidecar process,
- credential transfer uses inherited stdin or an equivalent private startup channel,
- the renderer never receives the credential,
- every product request is authenticated,
- credentials are not written to logs, crash reports, config or SQLite.

### Network binding

For the initial FastAPI transport:

- bind only to `127.0.0.1`,
- use an ephemeral port,
- reject unauthenticated requests,
- disable permissive CORS,
- disable packaged Swagger/ReDoc/OpenAPI exposure unless explicitly required for diagnostics,
- never bind `0.0.0.0` in packaged mode,
- do not trust arbitrary `Host`, `Origin` or forwarded headers.

### Readiness envelope

The sidecar emits one machine-readable readiness envelope containing:

```text
protocol_version
process_nonce
port
service_version
ready_state
```

The desktop core validates the nonce and protocol before enabling product commands.

### Shutdown

```text
desktop quit
  → stop accepting renderer commands
  → request graceful sidecar shutdown
  → wait bounded timeout
  → terminate child if still alive
  → clear capability and credential state
```

The sidecar must not outlive the owning desktop session.

## IPC and schema rules

- all commands have explicit TypeScript and Rust types,
- Python transport schemas remain versioned,
- unknown fields are rejected for security-sensitive commands,
- payload size limits are defined,
- request IDs are generated by the desktop core,
- errors use stable codes and safe user messages,
- stack traces and local absolute paths are not exposed to the renderer by default,
- bridge drift fails build/typecheck rather than becoming runtime fallback.

## Navigation and web content

Packaged mode:

- loads only bundled frontend assets,
- denies arbitrary in-window navigation,
- denies new windows by default,
- opens allow-listed `https:` links in the operating-system browser,
- does not load remote JavaScript,
- uses a restrictive Content Security Policy,
- sanitizes rendered Markdown and imported metadata,
- forbids inline credentials and unsafe protocol handlers.

Development mode may allow only explicitly configured loopback frontend origins.

## Update security

- updater ownership remains in the desktop core,
- update artifacts must be signed,
- the update verification public key may be bundled,
- private signing keys stay only in protected release infrastructure,
- renderer can request update actions but cannot provide update URLs or signatures,
- release notes are treated as untrusted content and sanitized,
- downgrade behavior requires explicit release policy.

## Logging and observability

Required desktop events:

- shell startup and version,
- sidecar state transition,
- readiness timeout/failure,
- capability issued/revoked/expired,
- product command result code and duration,
- update state,
- packaged smoke-test evidence.

Logs must redact:

- session credentials,
- signing material,
- sensitive environment values,
- unnecessary full local paths,
- user audio content.

## Packaged release gates

A desktop artifact cannot be declared ready unless all are true:

1. installer/application signature verified,
2. macOS notarization accepted where applicable,
3. package layout contains the expected sidecar and no development secrets,
4. renderer has no generic shell or filesystem permission,
5. sidecar binds only to loopback,
6. unauthenticated sidecar request is rejected,
7. native folder selection produces an opaque capability,
8. symlink/path escape test fails closed,
9. sidecar terminates with the desktop app,
10. update signature verification is enabled,
11. clean-machine startup and one real workflow smoke test pass,
12. SBOM and third-party notices are archived.

## Negative tests required in the proof bundle

- renderer attempts arbitrary shell command,
- renderer submits a manually typed path,
- renderer calls an undeclared command,
- renderer attempts direct sidecar request,
- expired capability is reused,
- sidecar readiness nonce is wrong,
- sidecar binds non-loopback address,
- malformed or oversized IPC payload,
- external navigation to non-allow-listed scheme,
- sidecar hangs during shutdown.

## Fallback compatibility

If the Tauri proof fails and Electron is selected, this contract remains binding:

- context isolation on,
- Node integration off,
- sandbox on,
- typed preload bridge only,
- sender validation for every IPC handler,
- restricted navigation and CSP,
- no generic host APIs exposed to renderer.

## Rollback

This document changes no runtime behavior. It can be superseded by a later ADR, but weakening any invariant requires a named threat analysis, compensating controls and explicit approval.
