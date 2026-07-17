# APPLAYLIST

APPLAYLIST is a local-first DJ preparation product that turns a selected local music library into an explainable, editable and interoperable DJ set.

```text
select local library
-> import and analyze tracks
-> build a constrained set
-> inspect and edit transitions
-> export to an existing DJ workflow
```

## Current status

- Canonical repository: `nulleimy/APPLAYLIST`
- Canonical branch: `feature/bundle-0-bootstrap`
- Current runtime checkpoint: **Bundle 39 — Canonical Source-Path Scope**
- Product baseline: **Bundle 40 — Product Baseline Realignment**
- Supported Python: `>=3.11,<3.13`
- Release status: **not yet product-ready**
- Default composition authority remains `legacy`
- Canonical composition is available behind controlled configuration
- Legacy analysis remains active while the real baseline provider and benchmark are pending

The repository has strong provider, composition, export and security foundations. The next work is intentionally product-first: library import, real analysis evidence, benchmark validation, desktop workflow, manual editing and M3U8 release.

## Product baseline

- [Product Definition v1](docs/product/APPLAYLIST_PRODUCT_DEFINITION_V1.md)
- [Target Architecture v1](docs/architecture/APPLAYLIST_TARGET_ARCHITECTURE_V1.md)
- [MIR Benchmark Specification v1](docs/quality/APPLAYLIST_MIR_BENCHMARK_SPEC_V1.md)
- [License Decision Register v1](docs/compliance/APPLAYLIST_LICENSE_DECISION_REGISTER_V1.md)
- [Product Roadmap — Bundles 40–50](docs/roadmap/APPLAYLIST_PRODUCT_ROADMAP_40_50.md)

## Product objective

The first release must let a DJ:

1. select one explicit local audio folder,
2. import supported files with stable identity and metadata,
3. analyze BPM, key/Camelot, energy and duration using a real provider,
4. inspect confidence, warnings and failures,
5. create a deterministic set under explicit musical constraints,
6. manually reorder, lock, replace and regenerate tracks,
7. export an approved playlist as path-valid M3U8.

## Architecture

```text
Desktop UI / FastAPI
        |
Application services
        |
+-------+--------------------+
|                            |
Provider boundary       Repository boundary
metadata/audio          tracks/analyses/playlists/jobs
        |                            |
        +------> normalized domain <-+
                         |
                composition and export
```

Component boundaries:

- `api/` — HTTP routes, middleware and transport validation
- `core/` — domain contracts, configuration, provider registry and pure rules
- `services/` — application orchestration, analysis, composition and export
- `data/` — models, repositories and persistence
- `workers/` — asynchronous processing foundation
- `tests/` — unit, integration and regression tests
- `docs/` — product, architecture, rollout, quality and operations

## Non-negotiable engineering rules

1. Do not run tests with global Python.
2. Use `.venv/bin/python`.
3. Do not use Python 3.14 for this project yet.
4. Do not commit `.env`, `.venv`, databases, caches or macOS/iCloud duplicate files.
5. Optional audio backends must not import on the mandatory API boot path.
6. Providers never persist directly.
7. Only normalized and validated analysis records may be stored.
8. API routes must not contain heavy audio or product use-case logic.
9. Repositories own persistence.
10. Tests and product acceptance gates must pass before every checkpoint.
11. New abstractions require a named product need.
12. Default-provider or authority changes require benchmark and rollback evidence.

## Local development

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

Release gates:

- CI passes on Python 3.11 and 3.12,
- mandatory boot does not require an optional audio backend,
- provider output is normalized and validated before storage,
- no fake success or hidden provider fallback,
- API contract changes have an explicit migration plan,
- exported playlist paths exist,
- product-facing slices demonstrate their user-visible acceptance result.

## Product-first implementation order

1. Bundle 40 — Product Baseline Realignment
2. Bundle 41 — Library Import Boundary
3. Bundle 42 — Metadata and Stable Track Identity
4. Bundle 43 — Analysis Job Contract
5. Bundle 44 — Real Baseline Audio Provider
6. Bundle 45 — MIR Benchmark Harness
7. Bundle 46 — Desktop Library Shell
8. Bundle 47 — Analysis Inspector
9. Bundle 48 — Set Builder
10. Bundle 49 — Manual Playlist Editor
11. Bundle 50 — M3U8 End-to-End Release Slice

Until Bundle 50, do not prioritize cloud accounts, streaming integration, live mixing, stems, mobile clients, proprietary database reverse engineering or additional generalized composition infrastructure.