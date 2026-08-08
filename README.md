# APPLAYLIST

APPLAYLIST is a local-first DJ preparation product that turns a selected local music library into an explainable, editable and interoperable DJ set.

```text
select local library
→ import and analyze tracks
→ build an explainable constrained set
→ inspect and edit transitions
→ export to an existing DJ workflow
```

## Current status

- Canonical repository: `nulleimy/APPLAYLIST`
- Canonical branch: `feature/bundle-0-bootstrap`
- Current merged checkpoint: **Bundle 46 — MIR Benchmark Harness**
- Active architecture slice: **Bundle 47 — Desktop Shell Architecture and Security ADR**
- Supported Python: `>=3.11,<3.13`
- Release status: **not yet product-ready**
- Default composition authority remains `legacy`
- Canonical composition remains available behind controlled configuration
- Real local Librosa MIR exists as a benchmark candidate
- Production provider authority remains blocked on licensed benchmark and human review evidence

The repository now contains the library scanner, stable content identity, tagged metadata persistence, a real baseline MIR provider, a fail-closed benchmark harness, composition/export foundations and repository hygiene tooling.

The next implementation target is a secure packaged desktop proof, not additional infrastructure abstraction.

## Product objective

The first release must let a DJ:

1. install and open a signed local desktop application,
2. select one explicit local audio folder,
3. import supported files with stable identity and metadata,
4. analyze BPM, key/Camelot, energy and duration using a real local provider,
5. inspect confidence, warnings and failures,
6. create a deterministic explainable set under explicit musical constraints,
7. manually reorder, lock, replace and regenerate tracks,
8. export an approved playlist as path-valid UTF-8 M3U8.

## Canonical product documents

- [Product Definition v1](docs/product/APPLAYLIST_PRODUCT_DEFINITION_V1.md)
- [Target Architecture v2](docs/architecture/APPLAYLIST_TARGET_ARCHITECTURE_V2.md)
- [Desktop Shell ADR](docs/architecture/ADR_BUNDLE_47_DESKTOP_SHELL.md)
- [Desktop Security Contract v1](docs/architecture/APPLAYLIST_DESKTOP_SECURITY_CONTRACT_V1.md)
- [MIR Benchmark Specification v1](docs/quality/APPLAYLIST_MIR_BENCHMARK_SPEC_V1.md)
- [License Decision Register v1](docs/compliance/APPLAYLIST_LICENSE_DECISION_REGISTER_V1.md)
- [Product Roadmap — Bundles 41–54](docs/roadmap/APPLAYLIST_PRODUCT_ROADMAP_41_54.md)

## Target runtime architecture

```text
React / TypeScript renderer
        │ typed Tauri commands and events
        ▼
Tauri Rust desktop core
        │ capabilities, native dialogs, sidecar lifecycle, updates
        ▼
Authenticated loopback Python sidecar
        │ FastAPI transport → application services
        ▼
Library / analysis / composition / playlist / export
        │
        ├── provider boundary
        └── repository boundary
```

Desktop decision:

- primary: **Tauri 2 + React/TypeScript + packaged Python sidecar**,
- fallback: **Electron + React/TypeScript + packaged Python sidecar** only if the Tauri proof fails accepted gates,
- not selected under the current shared-web direction: **PySide6/QML**.

The React renderer never receives arbitrary shell access, unrestricted filesystem authority, the Python sidecar credential or direct SQLite access.

## Component boundaries

- `api/` — HTTP schemas/routes and transport validation
- `core/` — domain contracts, configuration, provider registry, benchmark and pure rules
- `services/` — application orchestration, library, analysis, composition and export
- `data/` — models, repositories, migrations and persistence
- `workers/` — typed background-processing foundation
- `frontend/` — future React product UI; starts only in Bundle 48 proof
- `desktop/` — future Tauri core and packaged sidecar supervision; starts only in Bundle 48 proof
- `scripts/` — safe operator and verification commands
- `tests/` — unit, integration, security and regression evidence
- `docs/` — product, architecture, security, quality, compliance and operations

## Non-negotiable engineering rules

1. Do not run project tests with global Python.
2. Use the project virtual environment.
3. Do not use Python 3.14 for the product runtime yet.
4. Do not commit `.env`, virtual environments, databases, caches, benchmark audio or duplicate cloud-sync files.
5. Optional audio backends must not import on mandatory boot.
6. Providers never persist directly.
7. Only normalized validated analysis records may be stored.
8. Routes and renderer code never own heavy product logic.
9. Repositories own persistence.
10. Tests and product acceptance gates pass before every checkpoint.
11. New abstractions require a named product need.
12. Default-provider or authority changes require benchmark and rollback evidence.
13. Renderer code never receives generic shell or filesystem APIs.
14. Packaged sidecar binds loopback only and uses per-session authentication.
15. Desktop update artifacts are signed and private signing keys remain outside the repository.
16. Every bundle includes a schema tree and explicit out-of-scope list.

## Local Python development

```bash
cd /path/to/APPLAYLIST
python3.11 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e ".[dev]"
cp .env.example .env
.venv/bin/python -m uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```

## Verification

```bash
cd /path/to/APPLAYLIST
.venv/bin/python -m compileall -q api core services data workers
.venv/bin/python -m ruff check .
.venv/bin/python -m pytest -q
```

Repository hygiene:

```bash
make hygiene-audit
make hygiene-plan
make hygiene-verify
```

MIR benchmark against an externally stored licensed dataset:

```bash
.venv/bin/python scripts/run_mir_benchmark.py \
  --manifest /absolute/path/manifest.json \
  --dataset-root /absolute/path/dataset \
  --output /absolute/path/artifacts/report.json \
  --provider librosa \
  --source-commit "$(git rev-parse HEAD)"
```

No benchmark audio or restricted annotations belong in the repository.

## Product-first implementation order

1. Bundle 41 — Product Baseline Realignment ✅
2. Bundle 42 — Bounded Library Import ✅
3. Bundle 43 — Stable Track Identity and Metadata Boundary ✅
4. Bundle 44 — Tagged Metadata and Persistence ✅
5. Bundle 45 — Baseline Librosa MIR Provider ✅
6. Bundle 46 — MIR Benchmark Harness ✅
7. Bundle 47 — Desktop Shell Architecture and Security ADR
8. Bundle 48 — Tauri/Python Sidecar Proof
9. Bundle 49 — Desktop Library Shell
10. Bundle 50 — Analysis Job and Inspector
11. Bundle 51 — Transition Intelligence v1
12. Bundle 52 — Explainable Set Builder
13. Bundle 53 — Manual Playlist Editor
14. Bundle 54 — M3U8 End-to-End Release Slice

Until Bundle 54, do not prioritize cloud accounts, streaming integrations, popularity/trend scoring, live mixing, stems, mobile clients, proprietary database reverse engineering, generative AI chat as the primary product surface or additional generalized composition infrastructure.

## Release gates

- Python CI passes on 3.11 and 3.12.
- Frontend/Rust CI is added when Bundle 48 introduces those toolchains.
- Mandatory boot does not require optional audio dependencies.
- Provider output is normalized and validated before storage.
- No fake success or hidden provider fallback.
- Desktop renderer has no generic host authority.
- Packaged artifacts pass layout and clean-machine smoke tests.
- Sidecar lifecycle, authentication and shutdown are proven.
- Signing, notarization, updater and SBOM evidence exist before external release.
- Product-facing slices demonstrate the declared user outcome; a green test count alone is not sufficient.

## License and intellectual property

APPLAYLIST is a **commercial proprietary product**. Original APPLAYLIST code and product-specific materials are **All Rights Reserved** unless a specific file explicitly states otherwise.

- Repository visibility: **PRIVATE**
- Source-code license: [Proprietary / All Rights Reserved](LICENSE.md)
- Authorized application builds: [End User License Agreement](EULA.md) plus applicable commercial/beta terms
- Third-party software: [Third-Party Notices and Release Compliance Index](THIRD_PARTY_NOTICES.md)
- Brand, logos and visual identity: [Trademark and Brand Policy](TRADEMARKS.md)

Third-party dependencies, native libraries, models, datasets, media and other externally owned materials retain their own rights and licenses. The proprietary APPLAYLIST license does not relicense them. A commercial installer remains blocked until the exact shipped dependency set satisfies the distribution gates in the license decision register and third-party notice process.
