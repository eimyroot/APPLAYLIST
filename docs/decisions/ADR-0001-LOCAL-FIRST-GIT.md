---
id: ADR-0001-LOCAL-FIRST-GIT
title: Local-First Git Is the Authoritative Engineering Workflow
status: ACCEPTED
owner: APPLAYLIST Engineering
created: 2026-07-30
updated: 2026-07-30
supersedes: null
related:
  - foundation/IDENTITY.md
  - STATUS.md
---

# ADR-0001 — Local-First Git

## Context

APPLAYLIST requires reproducible work even when hosted CI is unavailable or non-authoritative.
Previous repository copies also existed in synchronization-provider locations, creating integrity
and source-of-truth risk.

## Decision

The authoritative engineering workflow is local-first Git:

1. work from the verified canonical local repository outside synchronization-provider storage;
2. verify Git state before every work block;
3. execute relevant local static checks/tests/security checks;
4. preserve deterministic evidence and rollback artifacts;
5. commit one logical work block;
6. use GitHub as collaboration/archive remote;
7. do not make GitHub Actions a required gate for the current local-first program.

The current verified local path is `/Users/eimyna/00_DEV/APPLAYLIST`.

## Consequences

- local verification must be reproducible and auditable;
- EPIC-002 must provide stable `make doctor`, `make lint`, `make test`, `make verify`, and
  `make bundle` commands;
- CI may add evidence but cannot replace missing local evidence;
- remote branch/default-branch metadata does not by itself define runtime authority;
- merges, force pushes, releases and history rewrites remain separately authorized operations.

## Rollback

This ADR may be superseded only by a later accepted ADR with an explicit migration and rollback
plan. It must not be silently bypassed by convenience tooling.
