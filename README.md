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

Until EPIC-002 closes the deterministic engineering baseline, verify the interpreter explicitly.
A supported baseline is Python 3.11 or 3.12.

Example setup:

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install --upgrade pip setuptools wheel
.venv/bin/python -m pip install -e ".[dev]" -c constraints/audio-stack-py311.txt
```

Run tests:

```bash
.venv/bin/python -m pytest -q
```

Run the API locally:

```bash
.venv/bin/python -m uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```

Health endpoint:

```text
GET /health
```

EPIC-002 will replace ad-hoc local commands with the canonical
`make doctor / lint / test / verify / bundle` interface.

## Security and privacy

Do not commit `.env`, credentials, local databases, audio libraries, private benchmark material,
or unsanitized user data. See [`foundation/PUBLIC_PRIVATE_BOUNDARY.md`](foundation/PUBLIC_PRIVATE_BOUNDARY.md).
