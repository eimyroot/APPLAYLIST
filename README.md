# APPLAYLIST

APPLAYLIST is a local-first, privacy-first and explainable **DJ intelligence platform** for audio
analysis, transition assessment, playlist/set preparation and future DJ workflow tooling.

The DJ remains the final decision maker.

## Truth and status

Use these documents for current project truth:

- [`STATUS.md`](STATUS.md) — current verified state and known debt;
- [`ROADMAP.md`](ROADMAP.md) — canonical product/engineering sequence;
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — current component and authority boundaries;
- [`PRODUCT.md`](PRODUCT.md) — current vs planned product capabilities;
- [`VISION.md`](VISION.md) — product direction.

Historical bundle documents under `docs/` remain evidence for their original work blocks. They are
not automatically the current source of truth.

## Current capability boundary

The repository contains backend/API, persistence, jobs/workers, analysis-provider, composer,
transition-foundation, explainability and export building blocks.

However:

- the legacy analysis path remains the default runtime path;
- Transition Intelligence runtime activation is off;
- WB006C beat-grid work is shadow evidence only;
- downbeat, phrase, segment-level vocal/bass and overlap intelligence are not yet accepted;
- desktop/product UI and release validation remain future roadmap work.

## Local development

Canonical working directory:

```bash
cd "/Users/eimyna/00_DEV/APPLAYLIST"
```

The local engineering baseline is controlled by the committed hash-locked dependency graph.

Bootstrap a supported Python 3.11/3.12 environment:

```bash
make bootstrap PYTHON_BOOTSTRAP=python3.12
```

Run the canonical local gate:

```bash
make doctor
make lint
make type
make test
make security
make verify
make bundle
```

Run the API locally:

```bash
.venv/bin/python -m uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```

Health endpoint:

```text
GET /health
```

See `docs/ops/LOCAL_GATE_RUNBOOK.md` for the canonical local gate and explicit debt-baseline policy.

## Security and privacy

Do not commit `.env`, credentials, local databases, audio libraries, private benchmark material,
or unsanitized user data. See [`foundation/PUBLIC_PRIVATE_BOUNDARY.md`](foundation/PUBLIC_PRIVATE_BOUNDARY.md).
