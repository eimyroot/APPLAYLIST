# APPLAYLIST License Decision Register v1

## Status

Engineering compliance register updated by Bundle 47. Entries marked `review_required` are not approved for product distribution.

This document is an engineering control, not legal advice. Final commercial distribution decisions require legal review appropriate to the business model and target jurisdictions.

## Decision states

- `approved_dev` — permitted for development and CI under current understanding.
- `approved_distribution` — cleared for intended packaged distribution with documented obligations.
- `experiment_only` — may be used for isolated evaluation but not shipped.
- `review_required` — unresolved; do not add to product dependencies or installers.
- `rejected_current` — not selected for the current product direction; reconsider only through a new ADR.
- `rejected` — must not be used for the stated product mode.

## Current Python runtime stack

| Component | Intended role | Current state | Required action |
|---|---|---|---|
| Python | sidecar/runtime | approved_dev | verify redistribution, Python license and frozen-runtime notices for each packaged target |
| FastAPI | local/headless transport | approved_dev | include dependency notice; packaged mode must bind loopback only and require session authentication |
| Pydantic | contracts/configuration | approved_dev | include dependency license manifest |
| NumPy | numerical baseline | approved_dev | verify binary-wheel notices and packaged native dependencies |
| SciPy | signal-processing baseline | approved_dev | verify binary-wheel notices and packaged native dependencies |
| SoundFile | audio decode boundary | approved_dev | audit bundled native `libsndfile` obligations |
| Librosa | lazy baseline MIR candidate | approved_dev | run real licensed datasets and human DJ review before production-authoritative approval |
| TinyTag 2.2.1 | read-only audio metadata | approved_dev | retain MIT notice; verify exact resolved version in packaged SBOM |

`approved_dev` does not automatically mean approved for a signed commercial installer.

## Metadata dependencies

| Component | Candidate use | State | Decision notes |
|---|---|---|---|
| TinyTag 2.2.1 | read-only audio metadata | approved_dev | MIT, pure Python, no dependencies, read-only API; selected for MVP metadata ingestion |
| Mutagen | metadata read/write | review_required | broader functionality than MVP requires; do not add while TinyTag satisfies the scope |

## MIR dependencies

| Component | Candidate use | State | Decision notes |
|---|---|---|---|
| Librosa + NumPy/SciPy/SoundFile | local BPM/key/energy baseline | approved_dev | implemented behind lazy boundary; Bundle 46 harness exists; production authority remains blocked on real dataset, packaging and human-review evidence |
| Essentia | advanced BPM/key/energy benchmark | experiment_only | commercial distribution requires explicit licensing decision; model licenses evaluated individually |
| Essentia pretrained models | optional ML descriptors | review_required | no model download or distribution without a per-model license record |
| madmom | beat/downbeat research | review_required | release age, compatibility and model-data restrictions require review |
| remote audio-analysis API | analysis provider | rejected for MVP | conflicts with local-first privacy and reproducibility goals unless separately approved |

### Librosa authority decision

- approved for development, CI and controlled local benchmark use,
- not approved as the production-authoritative provider,
- no claim of parity with Mixed In Key or another commercial analyzer,
- analysis remains local with no audio upload,
- provider and algorithm provenance are mandatory,
- packaged distribution remains blocked on native dependency review and signed sidecar proof,
- production authority remains blocked on licensed public/private benchmark reports and human DJ review.

## Desktop and frontend candidates

| Component | Candidate use | State | Decision notes |
|---|---|---|---|
| Tauri 2 | primary desktop shell | approved_dev | framework is MIT or Apache-2.0 where applicable; selected by Bundle 47 ADR for proof implementation; exact Rust/JS plugin set requires SBOM and notice audit |
| React / TypeScript | shared desktop/web UI | approved_dev | exact packages and licenses will be pinned in Bundle 48; no frontend dependency is approved merely by this architecture decision |
| Tauri official shell/fs/dialog/updater plugins | least-privilege capabilities | review_required | approve individually after exact version, permission scope and transitive dependency audit |
| Packaged Python sidecar tool | freeze Python service | review_required | Bundle 48 must compare PyInstaller/Nuitka or another selected method, native libraries, artifact reproducibility and notices |
| Electron | documented desktop fallback | approved_dev | MIT; may be used only if the Tauri proof fails accepted packaging/WebView/security gates and a fallback ADR is recorded |
| Electron Forge/builder/updater stack | fallback packaging | review_required | not a current dependency; exact package and update model require review if fallback is activated |
| PySide6 / Qt for Python | direct Python desktop shell | rejected_current | LGPLv3/GPLv3 or commercial Qt terms; does not satisfy shared React/browser UI direction without a second frontend |
| Qt commercial distribution | alternative desktop shell | rejected_current | reconsider only if shared-web requirement changes and commercial licensing is approved |
| pyside6-deploy / Nuitka Qt path | PySide packaging | rejected_current | no proof work planned under current Tauri target |

### Bundle 47 Tauri decision

Approved only for an isolated proof bundle under these conditions:

- no generic shell or unrestricted filesystem permission,
- renderer communicates through named typed commands,
- Rust core owns native dialogs and opaque path capabilities,
- Rust core owns packaged Python sidecar lifecycle,
- sidecar binds loopback only with per-session authentication,
- renderer never receives the sidecar credential or generic base URL,
- updater artifacts require signatures,
- no signing private key enters source control or the application bundle,
- proof records artifact size, startup time, idle memory and package layout,
- exact plugin and packaging dependencies are added to this register before merge.

Tauri is not yet `approved_distribution`.

### Electron fallback conditions

Electron may replace Tauri only when the proof demonstrates a material failure in one or more of:

- target sidecar packaging,
- declared platform WebView behavior,
- accessibility or packaged testing,
- signing/updater viability,
- maintainable delivery cost.

The Electron fallback remains bound by the same desktop security contract: context isolation, sandboxing, Node integration disabled, typed preload bridge and no generic renderer authority.

## Donor repository policy

| Donor | State | Permitted use |
|---|---|---|
| `4gray/iptvnator` | architecture_reference | study shared web/desktop separation, typed bridge, package tests, feature matrix and updater discipline |

Rules:

- no direct code copy without file-level license and history review,
- do not copy IPTV, EPG, playback, proxy, Angular/NgRx or provider logic,
- product screenshots, branding and artwork are not donor material,
- architectural ideas must be reimplemented against APPLAYLIST contracts.

## Export formats and interoperability

| Format/integration | State | Notes |
|---|---|---|
| M3U8 | approved_dev | first MVP export; path-integrity and encoding tests required |
| JSON manifest | approved_dev | internal evidence format; schema version required |
| rekordbox XML | review_required | implement from documented import format; avoid proprietary database manipulation |
| Traktor NML | review_required | format and compatibility tests required before product claim |
| OneLibrary | monitor | evaluate only through published compatible interfaces or partnership path |
| proprietary database reverse engineering | rejected | outside MVP without explicit legal/product approval |

## Benchmark datasets

Every dataset requires a manifest containing:

- dataset name/version,
- source and retrieval date,
- license text or stable reference,
- allowed research/commercial use,
- redistribution permission,
- checksums,
- storage location outside the repository.

Rules:

- dataset audio is never committed,
- non-redistributable annotations remain outside source control,
- public reports contain only permitted aggregate or derived data,
- private DJ collections require documented ownership or permission.

## Installer compliance requirements

Before any external desktop release:

1. generate complete SBOMs for frontend, Rust shell and frozen Python sidecar,
2. collect JavaScript, Rust, Python and native-library notices,
3. document linking, source-offer or relinking obligations where applicable,
4. verify no `experiment_only` or unresolved `review_required` component is packaged,
5. verify signing/notarization inputs contain no secrets in source or artifacts,
6. archive exact lockfiles, toolchain versions and build provenance,
7. verify sidecar binary and package layout,
8. verify updater signature configuration and protect private update keys,
9. run signed packaged application on a clean target account/machine,
10. execute one real local import/analyze/export smoke workflow.

## Approval template

A dependency may move to `approved_distribution` only with:

- exact package and version,
- role and alternatives,
- upstream license/copyright notices,
- transitive and native dependencies,
- linking/embedding/packaging method,
- distribution obligations,
- security maintenance status,
- SBOM entry,
- approving reviewer and date.

## Immediate decisions

- retain TinyTag for read-only metadata,
- retain filename fallback as explicit degraded evidence,
- retain Librosa as a benchmark candidate, not commercial-parity truth,
- keep Essentia out of production dependencies,
- use Tauri 2 + React/TypeScript + packaged Python sidecar as the Bundle 48 proof target,
- keep Electron as a controlled fallback only,
- do not add PySide6 under the current shared-web direction,
- implement M3U8 before proprietary ecosystem adapters,
- prohibit unreviewed models, plugins and signing material in runtime or CI artifacts.
