---
id: OPS-LOCAL-GATE-RUNBOOK
title: APPLAYLIST Local Engineering Gate
status: ACCEPTED
owner: APPLAYLIST Engineering
created: 2026-07-30
updated: 2026-07-30
supersedes: null
related:
  - ../../STATUS.md
  - ../../docs/decisions/ADR-0001-LOCAL-FIRST-GIT.md
---

# APPLAYLIST — Local Engineering Gate

## Canonical commands

```bash
make doctor
make lint
make type
make test
make security
make verify
make bundle
```

`make verify` is the authoritative local engineering gate for this baseline. GitHub Actions may
add evidence but are not a required gate.

## Environment

Create a local environment from the committed hash-locked dependency graph:

```bash
make bootstrap PYTHON_BOOTSTRAP=python3.12
```

Python 3.11 and 3.12 are supported. `.python-version` remains `3.11`; the lock is verified during
WB002 on Python 3.12 and must remain installable on supported interpreters before claiming a wider
release matrix.

## Dependency lock

`requirements.lock` is generated from `pyproject.toml`, the committed audio baseline
`constraints/audio-stack-py311.txt`, the committed non-audio direct baseline
`constraints/local-baseline-py312.txt`, and
`pip-compile --generate-hashes --allow-unsafe`.
The packaging bootstrap set (`pip`, `setuptools`, `wheel`) is intentionally included and
hash-locked; omitting it would make `--require-hashes` installation incomplete.

Installations use:

```bash
python -m pip install --require-hashes -r requirements.lock
python -m pip install --no-build-isolation --no-deps -e .
```

The lock is the exact dependency authority. Version ranges in `pyproject.toml` remain human-readable
compatibility declarations, not install-time resolution authority.

## Differential debt gates

The repository already contains quality/type/security debt. WB002 does not relabel that debt as
clean.

- Ruff findings are compared exactly with `tools/quality/ruff-baseline.txt`.
- mypy findings are compared exactly with `tools/quality/mypy-baseline.txt`.
- Bandit findings are compared exactly with `tools/quality/bandit-baseline.txt`.
- any new finding fails the corresponding gate;
- Bandit HIGH severity findings are never baselined;
- high-confidence secret-like tracked paths fail the security gate.

A later work block may reduce the baselines. Baseline growth is not allowed.

## Tool choices

- Ruff — fast Python lint/import-order gate.
- mypy — explicit static type-checking gate.
- Bandit — local Python security static analysis.
- pip-tools — deterministic, hash-locked pip dependency compilation.

These tools are development-only and do not alter product runtime behavior.
