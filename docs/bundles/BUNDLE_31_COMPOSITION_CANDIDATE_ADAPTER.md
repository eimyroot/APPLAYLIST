# Bundle 31 — Playlist Candidate Composition Adapter

## Goal

Create an explicit and auditable boundary between persisted playlist candidates and the canonical deterministic composition engine.

## Read-model enrichment

The existing database schema already contains track genre, source and duration metadata. The composition candidate JOIN now exposes:

- `genre`,
- `source`,
- analyzed duration when available,
- track metadata duration as a fallback through SQL `COALESCE`.

No database migration is required.

## Adapter contract

`adapt_playlist_candidates()` processes candidates in deterministic `track_id` and path order.

Required composition fields fail closed:

- non-empty track identifier,
- non-empty path,
- finite positive BPM,
- valid Camelot key,
- finite energy in the inclusive range 0–1.

Invalid candidates are excluded and receive stable issue codes.

Duration is not a transition-safety metric. A missing or invalid duration may therefore use the explicitly configured fallback. Every fallback is recorded as a `duration_fallback` issue and is never silent.

## Isolation

- The production pipeline is not switched.
- The legacy composer remains unchanged.
- The adapter performs no database query itself.
- The adapter performs no network, filesystem or provider call.
- No schema migration or public API change is included.

## Verification

- deterministic candidate ordering,
- metadata preservation,
- malformed BPM, key, energy and path rejection,
- boolean metric rejection,
- explicit duration fallback evidence,
- invalid fallback configuration rejection,
- repository JOIN integration with analyzed-duration precedence,
- full Python 3.11 and 3.12 CI.

## Rollback

Revert the future Bundle 31 squash commit. No data rollback is required.
