# Applaylist-old donor audit

Source: `nulleimy/Applaylist-old` at `f04f65058e83620919b542f40029f04732761231`.

## Decision

Treat the repository as read-only donor material. Do not merge it, use it as a runtime dependency, or cherry-pick broad commits.

## Candidate capabilities

- deterministic playlist composer with BPM, Camelot, energy-stage and spacing rules,
- structured M3U/M3U8/JSON export contracts and sidecars,
- missing-path repair workflow,
- React export dialog.

Each capability must be ported in a new bundle from the canonical APPLAYLIST head.

## Rejected baseline patterns

- empty `pyproject.toml` and unpinned dependencies,
- Python 3.13 CI with `pip install ... || true`,
- global FastAPI bootstrap and wildcard CORS,
- raw exception text returned by routes,
- unbounded recursive filesystem search,
- filename-only path cache,
- working-directory-relative runtime files,
- broad exception swallowing.

## Migration order

1. Pure canonical composition engine.
2. Structured export service and API.
3. Bounded path resolution with explicit roots and search budgets.
4. Frontend export and repair UX using canonical APIs.

Bundle 29 imports no code from this repository.
