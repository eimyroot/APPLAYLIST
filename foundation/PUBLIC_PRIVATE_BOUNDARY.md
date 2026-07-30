---
id: FOUNDATION-PUBLIC-PRIVATE-BOUNDARY
title: APPLAYLIST Public / Private Boundary
status: ACCEPTED
owner: APPLAYLIST Engineering
created: 2026-07-30
updated: 2026-07-30
supersedes: null
related:
  - SECURITY.md
  - VISION.md
---

# APPLAYLIST Public / Private Boundary

## Private by default

The following are private/local data unless a future explicitly authorized feature defines a
different boundary:

- raw audio files and music-library contents;
- absolute local library paths;
- user library indexes and local database contents;
- user transition decisions and feedback;
- local runtime logs that may contain path or operational context;
- credentials, tokens, secrets and signing material;
- unsanitized benchmark datasets and reports.

These values must not be committed to Git or sent to a remote service merely because a provider,
UI, or integration exists.

## Repository-safe material

The repository may contain:

- source code;
- schemas and contracts;
- synthetic or properly licensed fixtures approved for repository use;
- sanitized deterministic evidence receipts;
- documentation;
- configuration examples containing placeholders only.

## External-service rule

Any future feature that uploads audio, fingerprints, embeddings, metadata, or user decisions must
have an explicit trust-boundary design, purpose, consent/authority model, retention policy,
failure behavior, and security review.

## Logging rule

Logs and evidence should prefer stable identifiers and redacted metadata over raw paths, secrets,
or private media content.

## Current boundary

Current WB001 changes documentation only. They do not activate any remote audio transfer,
telemetry, external analysis, or new runtime integration.
