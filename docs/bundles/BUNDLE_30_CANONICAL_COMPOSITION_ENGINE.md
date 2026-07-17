# Bundle 30 — Canonical Deterministic Composition Engine

## Goal

Introduce a pure and explainable DJ composition engine without switching the existing API, database or pipeline.

## Baseline problem

The existing composer selects the first repository result as its opening track and delegates candidate scoring to a module that owns a global Spotify client. Candidate evaluation can therefore depend on external I/O and does not enforce hard transition constraints.

## Implemented boundary

`services/composition/` is a new isolated domain package:

- `models.py` defines immutable requests, tracks, constraints, decisions and results.
- `camelot.py` validates Camelot keys and evaluates same, adjacent and relative-key compatibility.
- `scoring.py` performs pure transition scoring.
- `engine.py` performs deterministic candidate filtering, opening selection and playlist composition.

The package imports no FastAPI, database repository, filesystem adapter or external provider client.

## Deterministic contract

- Input order does not affect output order.
- Duplicate `track_id` values are reduced deterministically.
- Every selection uses explicit tie-break fields.
- Stage-aware BPM limits are hard gates.
- Harmonic, energy, genre, artist, label and source rules produce explicit reasons.
- A stalled composition returns a controlled partial result rather than silently selecting an invalid transition.

## Donor provenance

The algorithmic concepts were audited from `nulleimy/Applaylist-old` at commit `f04f65058e83620919b542f40029f04732761231`.

No source branch, runtime configuration, dependency file, API route or persistence implementation was merged from that repository. The implementation was rebuilt against the canonical APPLAYLIST architecture and test contract.

## Non-goals

- no replacement of `services/composer/Composer`,
- no pipeline or API feature flag,
- no database adapter,
- no removal of Spotify integration from the legacy scorer,
- no frontend changes.

## Verification

- Camelot normalization and compatibility tests,
- deterministic output under reversed input order,
- BPM hard-gate partial result,
- start-key opening selection,
- artist, label and source spacing behavior,
- duplicate identifier handling,
- genre-filtered empty result,
- full Python 3.11 and 3.12 CI.

## Rollback

Revert the future Bundle 30 squash commit. No database or data rollback is required.
